#!/usr/bin/env python3
"""Compare Python vs Clojure stat block extraction across all COF2 reference PDFs."""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CAMPAIGNS = [
    ("momie", "COF2_10_Mondanites_Et_Momies_web_v1a.pdf"),
    ("dernier-faelys", "COF2_07_Le_Dernier_Faelys_web_v0.pdf"),
    ("mortelle-xelys", "COF2_Mortelle_Xelys.pdf"),
    ("croissez-et-multipliez", "COF2_Croissez_Et_Multipliez.pdf"),
    ("retour-en-grace", "COF2_Retour_En_Grace.pdf"),
]

# Python inline-parse false positives on AZULRIA equipment lines.
PYTHON_ABILITY_FALSE_POSITIVES = {
    ("momie", "AZULRIA"): {"Masse +9", "Équipement : masse +1, vêtement luxueux, chemise de mailles, dague"},
}


@dataclass
class StatBlockSummary:
    name: str
    pages: tuple[int, int]
    nc: int | str | None
    subtitle: str | None
    attributes: dict
    defense: int | None
    vigor: int | None
    initiative: int | None
    attacks: list[dict]
    ability_titles: list[str]
    ability_text_lens: list[int]
    rulebook: str | None
    block_count: int
    raw_len: int

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "pages": list(self.pages),
            "nc": self.nc,
            "subtitle": self.subtitle,
            "attributes": self.attributes,
            "defense": self.defense,
            "vigor": self.vigor,
            "initiative": self.initiative,
            "attacks": self.attacks,
            "abilities": [
                {"title": t, "text_len": n}
                for t, n in zip(self.ability_titles, self.ability_text_lens)
            ],
            "rulebook": self.rulebook,
            "block_count": self.block_count,
            "raw_len": self.raw_len,
        }


def _named_only(summaries: list[StatBlockSummary]) -> dict[str, StatBlockSummary]:
    return {s.name: s for s in summaries if (s.name or "").strip()}


def python_stat_blocks(pdf: Path) -> list[StatBlockSummary]:
    from rpg_ingest.raw.providers.legacy import LegacyExtractionProvider
    from rpg_ingest.raw.block_merging import merge_fragmented_blocks
    from rpg_ingest.raw.stat_blocks import annotate_stat_blocks
    from rpg_ingest.raw.stat_blocks.registry import resolve_profile

    ext = LegacyExtractionProvider().extract(pdf)
    merged = merge_fragmented_blocks(ext.pages).pages
    profile = resolve_profile("cof2", merged)
    stat = annotate_stat_blocks(merged, profile)
    out: list[StatBlockSummary] = []
    for span in stat.spans:
        parsed = profile.parse_span(span)
        abilities = parsed.abilities
        out.append(
            StatBlockSummary(
                name=parsed.name or "",
                pages=(span.page_start, span.page_end),
                nc=parsed.nc,
                subtitle=parsed.subtitle,
                attributes=dict(parsed.attributes or {}),
                defense=parsed.defense,
                vigor=parsed.vigor,
                initiative=parsed.initiative,
                attacks=[
                    {
                        "name": attack.name,
                        "attack_bonus": attack.attack_bonus,
                        "damage": attack.damage,
                    }
                    for attack in (parsed.attacks or [])
                ],
                ability_titles=[a.title for a in abilities],
                ability_text_lens=[len(a.text or "") for a in abilities],
                rulebook=(
                    parsed.rulebook_reference.profile_name
                    if parsed.rulebook_reference
                    else None
                ),
                block_count=len(span.blocks),
                raw_len=len(parsed.raw_text or ""),
            )
        )
    return sorted(out, key=lambda s: (s.pages[0], s.name))


def clojure_stat_blocks(pdf: Path) -> list[StatBlockSummary]:
    code = f"""
(require '[cheshire.core :as json]
         '[rpg.ingest.extract.pdf :as pdf]
         '[rpg.ingest.block-merging :as bm]
         '[rpg.ingest.stat-blocks.core :as sb]
         '[rpg.ingest.stat-blocks.registry :as reg])
(let [pdf "{pdf.as_posix()}"
      extracted (pdf/extract-document pdf)
      profile (reg/resolve-profile "cof2" (:pages extracted))
      {{:keys [pages]}} (bm/merge-fragmented-pages (:pages extracted) profile)
      {{:keys [spans]}} (sb/annotate-stat-blocks profile pages)]
  (println
    (json/generate-string
      (mapv (fn [span]
              (let [p (sb/parse-span profile span)]
                {{:name (:name p)
                 :page-start (:page-start span)
                 :page-end (:page-end span)
                 :nc (:nc p)
                 :subtitle (:subtitle p)
                 :attributes (:attributes p)
                 :defense (:defense p)
                 :vigor (:vigor p)
                 :initiative (:initiative p)
                 :attacks (:attacks p)
                 :abilities (mapv (fn [a] {{:title (:title a) :text (:text a)}})
                                  (:abilities p))
                 :rulebook (get-in p [:rulebook-reference :profile-name])
                 :block_count (count (:blocks span))
                 :raw-text (:raw-text p)}}))
            spans))))
"""
    result = subprocess.run(
        ["clojure", "-M", "-e", code],
        cwd=ROOT / "packages/ingest-clj",
        capture_output=True,
        text=True,
        check=True,
    )
    raw = json.loads(result.stdout.strip())
    summaries = []
    for d in raw:
        abilities = d.get("abilities", [])
        attacks = [
            {
                "name": attack.get("name"),
                "attack_bonus": attack.get("attack_bonus", attack.get("attack-bonus")),
                "damage": attack.get("damage"),
            }
            for attack in (d.get("attacks") or [])
            if attack.get("name")
        ]
        summaries.append(
            StatBlockSummary(
                name=d.get("name") or "",
                pages=(d["page-start"], d["page-end"]),
                nc=d.get("nc"),
                subtitle=d.get("subtitle"),
                attributes=dict(d.get("attributes") or {}),
                defense=d.get("defense"),
                vigor=d.get("vigor"),
                initiative=d.get("initiative"),
                attacks=attacks,
                ability_titles=[a["title"] for a in abilities],
                ability_text_lens=[len(a.get("text") or "") for a in abilities],
                rulebook=d.get("rulebook"),
                block_count=d["block_count"],
                raw_len=len(d.get("raw-text") or ""),
            )
        )
    return sorted(summaries, key=lambda s: (s.pages[0], s.name))


def compare_campaign(campaign_id: str, pdf_name: str) -> dict:
    pdf = ROOT / "data/pdfs" / pdf_name
    if not pdf.is_file():
        return {"campaign_id": campaign_id, "status": "skipped", "reason": "pdf missing"}

    py = python_stat_blocks(pdf)
    clj = clojure_stat_blocks(pdf)
    py_by_name = _named_only(py)
    clj_by_name = _named_only(clj)
    py_names = set(py_by_name)
    clj_names = set(clj_by_name)

    issues: list[str] = []
    warnings: list[str] = []

    missing = sorted(py_names - clj_names)
    if missing:
        issues.append(f"missing names: {missing}")

    extra = sorted(clj_names - py_names)
    if extra:
        warnings.append(f"extra names (acceptable if valid stat blocks): {extra}")

    for name in sorted(py_names & clj_names):
        p = py_by_name[name]
        c = clj_by_name[name]
        if p.nc is not None and c.nc != p.nc:
            issues.append(f"{name}: nc py={p.nc} clj={c.nc}")
        for field in ("defense", "vigor", "initiative"):
            py_val = getattr(p, field)
            clj_val = getattr(c, field)
            if py_val is not None and py_val != clj_val:
                issues.append(f"{name}: {field} py={py_val} clj={clj_val}")
        if p.attributes and p.attributes != c.attributes:
            warnings.append(f"{name}: attrs differ py={p.attributes} clj={c.attributes}")
        if p.rulebook != c.rulebook:
            issues.append(f"{name}: rulebook py={p.rulebook} clj={c.rulebook}")

        py_attack_names = {a["name"] for a in p.attacks}
        clj_attack_names = {a.get("name") for a in c.attacks}
        missing_attacks = sorted(py_attack_names - clj_attack_names)
        if missing_attacks:
            warnings.append(f"{name}: missing attacks {missing_attacks}")

        py_titles = set(p.ability_titles)
        clj_titles = set(c.ability_titles)
        false_pos = PYTHON_ABILITY_FALSE_POSITIVES.get((campaign_id, name), set())
        py_titles -= false_pos
        py_titles -= py_attack_names
        missing_abilities = sorted(py_titles - clj_titles)
        if missing_abilities:
            warnings.append(f"{name}: missing abilities {missing_abilities}")

    return {
        "campaign_id": campaign_id,
        "pdf": pdf_name,
        "python_named_count": len(py_names),
        "clojure_named_count": len(clj_names),
        "python_names": sorted(py_names),
        "clojure_names": sorted(clj_names),
        "issues": issues,
        "warnings": warnings,
        "ok": not issues,
        "python": [s.to_dict() for s in py],
        "clojure": [s.to_dict() for s in clj],
    }


def main() -> int:
    verbose = "--verbose" in sys.argv
    results = []
    failed = 0
    for campaign_id, pdf_name in CAMPAIGNS:
        result = compare_campaign(campaign_id, pdf_name)
        results.append(result)
        if result.get("status") == "skipped":
            print(f"[SKIP] {campaign_id}")
            continue
        status = "OK" if result.get("ok") else "DIFF"
        if result.get("ok") and result.get("warnings"):
            status = "OK*"
        print(
            f"[{status}] {campaign_id}: py={result['python_named_count']} "
            f"clj={result['clojure_named_count']} "
            f"issues={len(result['issues'])} warnings={len(result['warnings'])}"
        )
        for issue in result["issues"]:
            print(f"  ! {issue}")
            failed += 1
        for warning in result["warnings"]:
            print(f"  ~ {warning}")
        if verbose:
            print(json.dumps(result, indent=2, ensure_ascii=False))

    out_path = ROOT / "artifacts" / "stat-blocks-comparison.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {out_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

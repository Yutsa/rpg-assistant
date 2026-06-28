#!/usr/bin/env python3
"""Compare Python vs Clojure stat block extraction on Momie page 15."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / "data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf"


def python_spans():
    from rpg_ingest.raw.providers.legacy import LegacyExtractionProvider
    from rpg_ingest.raw.block_merging import merge_fragmented_blocks
    from rpg_ingest.raw.stat_blocks import annotate_stat_blocks
    from rpg_ingest.raw.stat_blocks.registry import resolve_profile

    ext = LegacyExtractionProvider().extract(PDF)
    merged = merge_fragmented_blocks(ext.pages).pages
    profile = resolve_profile("cof2", merged)
    stat = annotate_stat_blocks(merged, profile)
    out = []
    for span in [s for s in stat.spans if s.page_start <= 15 <= s.page_end]:
        parsed = profile.parse_span(span)
        out.append(
            {
                "name": parsed.name,
                "nc": parsed.nc,
                "subtitle": parsed.subtitle,
                "attributes": parsed.attributes,
                "abilities": [
                    {"title": a.title, "text_len": len(a.text or "")}
                    for a in parsed.abilities
                ],
                "rulebook": (
                    parsed.rulebook_reference.profile_name
                    if parsed.rulebook_reference
                    else None
                ),
                "block_count": len(span.blocks),
                "raw_len": len(parsed.raw_text or ""),
            }
        )
    return out


def clojure_spans():
    code = f"""
(require '[cheshire.core :as json]
         '[rpg.ingest.extract.pdf :as pdf]
         '[rpg.ingest.block-merging :as bm]
         '[rpg.ingest.stat-blocks.core :as sb]
         '[rpg.ingest.stat-blocks.registry :as reg])
(let [pdf "{PDF.as_posix()}"
      extracted (pdf/extract-document pdf)
      profile (reg/resolve-profile "cof2" (:pages extracted))
      {{:keys [pages]}} (bm/merge-fragmented-pages (:pages extracted) profile)
      {{:keys [spans]}} (sb/annotate-stat-blocks profile pages)
      p15 (filter #(= 15 (:page-start %)) spans)]
  (println
    (json/generate-string
      (mapv (fn [span]
              (let [p (sb/parse-span profile span)]
                {{:name (:name p)
                 :nc (:nc p)
                 :subtitle (:subtitle p)
                 :attributes (:attributes p)
                 :abilities (mapv (fn [a] {{:title (:title a) :text_len (count (or (:text a) ""))}})
                                  (:abilities p))
                 :rulebook (get-in p [:rulebook-reference :profile-name])
                 :block_count (count (:blocks span))
                 :raw_len (count (or (:raw-text p) ""))}}))
            p15))))
"""
    result = subprocess.run(
        ["clojure", "-M", "-e", code],
        cwd=ROOT / "packages/ingest-clj",
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout.strip())


def main():
    py = python_spans()
    clj = clojure_spans()
    print("=== Python (PyMuPDF) ===")
    print(json.dumps(py, indent=2, ensure_ascii=False))
    print("\n=== Clojure (PDFBox) ===")
    print(json.dumps(clj, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

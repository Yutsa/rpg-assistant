#!/usr/bin/env python3
"""Génère un rapport HTML + PNG de la passe 2 sections (Momie p.5)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf"
OUT_DIR = ROOT / "artifacts/pass2-demo"
INGEST_CLJ = ROOT / "packages/ingest-clj"

COLORS = ["#2563eb", "#16a34a", "#d97706", "#9333ea", "#dc2626", "#0891b2"]


def run_assign_sections() -> dict:
    script = f"""
(require '[rpg.ingest.extract.pdf :as pdf]
         '[rpg.ingest.sections :as sections]
         '[cheshire.core :as json])
(let [page (pdf/extract-page "{PDF}" 5)
      result (sections/assign-sections [page]
                {{:campaign-id "momie" :document-id "doc_demo"}})
      blocks (:blocks page)
      payload {{:page {{:page_number (:page-number page)
                       :width (:width page)
                       :height (:height page)}}
                :blocks (mapv #(hash-map :block_index (:block-index %)
                                       :text (:text %)
                                       :bbox (:bbox %))
                              blocks)
                :sections (mapv #(select-keys % [:id :title :level])
                                 (:sections result))
                :heading_anchors (:heading-anchors result)
                :block_assignments (:block-assignments result)}}]
  (println (json/generate-string payload)))
"""
    proc = subprocess.run(
        ["clojure", "-Sdeps", '{:paths ["src"] :deps {cheshire/cheshire {:mvn/version "5.13.0"}}}', "-M", "-e", script],
        cwd=INGEST_CLJ,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        proc.check_returncode()
    return json.loads(proc.stdout.strip())


def html_report(data: dict) -> str:
    section_colors = {s["id"]: COLORS[i % len(COLORS)] for i, s in enumerate(data["sections"])}
    anchors = {tuple(a) for a in data["heading_anchors"]}
    page_num = data["page"]["page_number"]
    pw, ph = data["page"]["width"], data["page"]["height"]
    blocks_html = []
    for b in sorted(data["blocks"], key=lambda x: x["block_index"]):
        idx = b["block_index"]
        bid = f"block_doc_demo_005_{idx:03d}"
        sec_id = data["block_assignments"].get(bid, "")
        color = section_colors.get(sec_id, "#94a3b8")
        is_heading = (page_num, idx) in anchors
        bb = b["bbox"]
        x, y = bb["x0"] / pw * 100, bb["y0"] / ph * 100
        w = max((bb["x1"] - bb["x0"]) / pw * 100, 2)
        h = max((bb["y1"] - bb["y0"]) / ph * 100, 1.5)
        label = b["text"].replace("\n", " ")[:52]
        tag = "TITRE" if is_heading else "corps"
        blocks_html.append(
            f'<div class="block" style="left:{x:.1f}%;top:{y:.1f}%;width:{w:.1f}%;height:{h:.1f}%;'
            f'border-color:{color};background:{color}33">'
            f"<small>#{idx} {tag}</small><br>{label}</div>"
        )
    sections_html = "".join(
        f'<li><span style="color:{section_colors[s["id"]]}">■</span> '
        f'<strong>{s["title"]}</strong></li>'
        for s in data["sections"]
    )
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"/>
<title>Passe 2 Momie p.5</title>
<style>
body {{ font-family: system-ui,sans-serif; margin:24px; background:#0f172a; color:#e2e8f0; }}
.layout {{ position:relative; width:min(920px,96vw); aspect-ratio:{pw}/{ph};
  background:#fff; border:2px solid #475569; margin:16px 0; }}
.block {{ position:absolute; border:2px solid; font-size:9px; overflow:hidden;
  padding:2px; color:#111; box-sizing:border-box; }}
.pass {{ color:#4ade80; font-weight:600; }}
</style></head><body>
<h1>Passe 2 Clojure — assign-sections</h1>
<p class="pass">Momie p.5 · {len(data["sections"])} sections · {len(data["block_assignments"])} affectations corps</p>
<div class="layout">{''.join(blocks_html)}</div>
<h2>Sections</h2><ul>{sections_html}</ul>
</body></html>"""


def render_png(data: dict, png_path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    pw, ph = data["page"]["width"], data["page"]["height"]
    scale = 1.4
    img = Image.new("RGB", (int(pw * scale) + 360, int(ph * scale) + 80), "#0f172a")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    section_colors = {s["id"]: COLORS[i % len(COLORS)] for i, s in enumerate(data["sections"])}
    anchors = {tuple(a) for a in data["heading_anchors"]}
    page_num = data["page"]["page_number"]

    draw.text((16, 12), f"Passe 2 assign-sections — Momie p.5 — {len(data['sections'])} sections", fill="#e2e8f0", font=font)
    ox, oy = 16, 40
    page_img = Image.new("RGB", (int(pw * scale), int(ph * scale)), "white")
    pd = ImageDraw.Draw(page_img)
    for b in data["blocks"]:
        idx = b["block_index"]
        bid = f"block_doc_demo_005_{idx:03d}"
        sec_id = data["block_assignments"].get(bid, "")
        color = section_colors.get(sec_id, "#94a3b8")
        bb = b["bbox"]
        x0, y0 = bb["x0"] * scale, bb["y0"] * scale
        x1, y1 = bb["x1"] * scale, bb["y1"] * scale
        pd.rectangle([x0, y0, x1, y1], outline=color, width=2)
        tag = "T" if (page_num, idx) in anchors else "c"
        pd.text((x0 + 2, y0 + 2), f"{idx}{tag}", fill=color, font=font)
    img.paste(page_img, (ox, oy))
    ly = oy + int(ph * scale) + 12
    for i, s in enumerate(data["sections"]):
        c = section_colors[s["id"]]
        draw.text((16, ly + i * 18), f"■ {s['title']}", fill=c, font=font)
    img.save(png_path)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = run_assign_sections()
    html_path = OUT_DIR / "momie-page5-sections.html"
    html_path.write_text(html_report(data), encoding="utf-8")
    print(f"Wrote {html_path}")
    png_path = OUT_DIR / "momie-page5-sections.png"
    render_png(data, png_path)
    print(f"Wrote {png_path}")


if __name__ == "__main__":
    main()

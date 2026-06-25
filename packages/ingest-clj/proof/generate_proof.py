#!/usr/bin/env python3
import json
import pathlib
import sqlite3
import sys

doc_id = sys.argv[1]
run_id = sys.argv[2]
db_path = sys.argv[3]
result_path = sys.argv[4]
out_dir = pathlib.Path(sys.argv[5])

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

def count(table: str) -> int:
    return conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE document_id = ?", (doc_id,)
    ).fetchone()[0]

method = conn.execute(
    "SELECT DISTINCT extraction_method FROM pages WHERE document_id = ?", (doc_id,)
).fetchone()[0]

run_row = conn.execute(
    "SELECT id, status, stats, finished_at FROM ingestion_runs WHERE id = ?", (run_id,)
).fetchone()

sample = conn.execute(
    """SELECT block_index, substr(text, 1, 80) AS text_preview
       FROM page_blocks WHERE document_id = ? AND page_number = 7
       ORDER BY block_index LIMIT 5""",
    (doc_id,),
).fetchall()

result = json.loads(pathlib.Path(result_path).read_text())
pages = count("pages")
blocks = count("page_blocks")
sections = count("sections")
chunks = count("chunks")

proof = {
    "command": (
        "cd packages/ingest-clj && clojure -M:ingest import "
        "--pdf ../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf "
        "--campaign-id momie --db sqlite:../../data/rpg_assistant.db"
    ),
    "result": result,
    "counts": [
        {"table": "pages", "count": pages, "expected": "20", "ok": pages == 20},
        {"table": "page_blocks", "count": blocks, "expected": "> 150", "ok": blocks > 150},
        {"table": "sections", "count": sections, "expected": "0", "ok": sections == 0},
        {"table": "chunks", "count": chunks, "expected": "0", "ok": chunks == 0},
    ],
    "extraction_method": method,
    "run": dict(run_row),
    "sample_blocks": [dict(row) for row in sample],
}

out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "proof-data.json").write_text(json.dumps(proof, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(proof, indent=2, ensure_ascii=False))

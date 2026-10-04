#!/usr/bin/env python3
"""Build a deduplicated training corpus from collected text.

Training ingest is topic-neutral: lawful collected text is not rejected because
of its subject matter. Runtime assistant policy remains a separate concern.
"""
import argparse
import hashlib
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("inputs", nargs="+")
ap.add_argument("--out", default="data/corpus.txt")
a = ap.parse_args()

out = Path(a.out)
out.parent.mkdir(parents=True, exist_ok=True)
seen = set()
written = 0

with out.open("w", encoding="utf-8") as w:
    for root in a.inputs:
        p = Path(root)
        files = [p] if p.is_file() else p.rglob("*.txt")
        for f in files:
            try:
                s = f.read_text(encoding="utf-8", errors="ignore").strip()
            except Exception:
                continue
            if not s:
                continue
            h = hashlib.sha256(s.encode("utf-8", "ignore")).digest()
            if h in seen:
                continue
            seen.add(h)
            w.write(s + "\n\n")
            written += 1

print(f"wrote {written} documents to {out}; topic-filtering=off")

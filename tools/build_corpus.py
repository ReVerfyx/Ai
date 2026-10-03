#!/usr/bin/env python3
import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from policy.engine import check_text, sanitize_untrusted

ap = argparse.ArgumentParser()
ap.add_argument("inputs", nargs="+")
ap.add_argument("--out", default="data/corpus.txt")
a = ap.parse_args()

out = Path(a.out)
out.parent.mkdir(parents=True, exist_ok=True)
seen = set()
written = 0
blocked = 0

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
            ok, _ = check_text(s, "training_ingest")
            if not ok:
                blocked += 1
                continue
            s = sanitize_untrusted(s)
            h = hashlib.sha256(s.encode()).digest()
            if h in seen:
                continue
            seen.add(h)
            w.write(s + "\n\n")
            written += 1

print(f"wrote {written} documents to {out}; policy-blocked={blocked}")

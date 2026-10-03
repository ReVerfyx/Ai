#!/usr/bin/env python3
"""Build manifest.tsv from *.ppm plus optional same-name *.txt captions."""
import argparse
from pathlib import Path
ap=argparse.ArgumentParser(); ap.add_argument("folder"); ap.add_argument("--out",default="data/images.tsv")
a=ap.parse_args(); root=Path(a.folder).resolve(); out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True)
rows=[]
for p in sorted(root.rglob("*.ppm")):
    cap=p.with_suffix(".txt")
    caption=cap.read_text(encoding="utf-8",errors="ignore").strip() if cap.exists() else p.stem.replace("_"," ")
    rows.append(f"{p}\t{caption}")
out.write_text("\n".join(rows)+("\n" if rows else ""),encoding="utf-8")
print(f"wrote {len(rows)} samples to {out}")

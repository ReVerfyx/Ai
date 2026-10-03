#!/usr/bin/env python3
"""One self-learning cycle: crawl -> corpus -> candidate training -> backup -> promote."""
import argparse, shutil, subprocess, time
from pathlib import Path

ap=argparse.ArgumentParser()
ap.add_argument("--seed",action="append",required=True)
ap.add_argument("--pages",type=int,default=50)
ap.add_argument("--model",default="models/text.bin")
ap.add_argument("--bin",default="build/reai")
ap.add_argument("--epochs",type=int,default=1)
a=ap.parse_args()

root=Path(__file__).resolve().parents[1]
model=root/a.model
candidate=model.with_suffix(".candidate.bin")

subprocess.check_call(["python3",str(root/"tools/crawl.py"),*a.seed,"--out",str(root/"data/web"),"--pages",str(a.pages),"--delay","1.0"])
subprocess.check_call(["python3",str(root/"tools/build_corpus.py"),str(root/"data/web"),"--out",str(root/"data/corpus.txt")])
if not model.exists():
    subprocess.check_call([str(root/a.bin),"text-init",str(model),"128"])

shutil.copy2(model,candidate)
subprocess.check_call([str(root/a.bin),"text-train",str(candidate),str(root/"data/corpus.txt"),str(a.epochs),"64","0.0005"])

if candidate.stat().st_size < 1024:
    raise SystemExit("candidate checkpoint is invalid")

backup=model.with_suffix(f".backup-{int(time.time())}.bin")
shutil.copy2(model,backup)
candidate.replace(model)
print("promoted",model,"backup",backup)

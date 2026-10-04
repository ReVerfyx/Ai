#!/usr/bin/env python3
import json, os, subprocess, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/"data/research/state.json"

def fmt_bytes(n):
    for unit in ["B","KB","MB","GB"]:
        if n<1024 or unit=="GB": return f"{n:.1f} {unit}"
        n/=1024
    return f"{n:.1f} GB"

def age(ts):
    if not ts: return "-"
    s=max(0,int(time.time()-ts))
    if s<60:return f"{s}s"
    if s<3600:return f"{s//60}m"
    return f"{s//3600}h"

print("ReVerfyx AI learning progress")
print()

for unit in ["reai","reai-trainer","reai-learning"]:
    try:
        r=subprocess.run(["systemctl","is-active",unit],capture_output=True,text=True,timeout=3)
        print(f"{unit}: {r.stdout.strip() or 'unknown'}")
    except Exception:
        pass

print()
for w in [0,1]:
    model=ROOT/"models/workers"/f"worker-{w}.bin"
    corpus=ROOT/"data/worker-corpus"/f"worker-{w}.txt"
    docs=list((ROOT/"data/web"/f"worker-{w}").rglob("*.txt")) if (ROOT/"data/web"/f"worker-{w}").exists() else []
    if model.exists():
        st=model.stat()
        try:
            magic=model.read_bytes()[:8]
            engine="unicode5m" if magic==b"REAIUC51" else ("sparse50m" if magic==b"REAISP21" else "legacy")
        except Exception:
            engine="?"
        print(f"worker-{w}: engine={engine} model={fmt_bytes(st.st_size)} updated={age(st.st_mtime)} ago")
    else:
        print(f"worker-{w}: model=missing")
    print(f"          docs={len(docs)} corpus={fmt_bytes(corpus.stat().st_size) if corpus.exists() else 'missing'}")

if STATE.exists():
    try:
        st=json.loads(STATE.read_text(encoding="utf-8"))
        print()
        print(f"research cycles: {st.get('cycles',0)}")
        for item in st.get("last",[]):
            print(f"last worker-{item.get('worker')}: {item.get('topic')} docs={item.get('docs')} wiki={item.get('wiki')} github={item.get('github')}")
        cov=st.get("coverage",{})
        if cov:
            best=sorted(cov.items(),key=lambda x:x[1],reverse=True)[:8]
            print("coverage:", ", ".join(f"{k}={v}" for k,v in best))
    except Exception as e:
        print("state error:",e)
else:
    print()
    print("research state: not started")

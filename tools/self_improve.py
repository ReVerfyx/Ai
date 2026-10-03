#!/usr/bin/env python3
"""Bounded self-improvement candidate loop.

The model may propose edits only to allowlisted source files. Changes are
applied to a separate candidate worktree, compiled/checked, and committed there.
Production, policy, systemd, credentials and deployment scripts are never edited.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CAND = Path(os.getenv("REAI_SELF_CANDIDATE", "/opt/reai-self-candidate"))
LOG = ROOT / "data/self-improve/history.jsonl"

ALLOW_PREFIX = ("src/","include/","api/","tools/")
DENY_PREFIX = ("policy/","deploy/","host.sh",".github/")
TARGETS = [
    ("tools/auto_research.py","Improve reliability, observability, and research quality without executing downloaded code."),
    ("api/server.py","Improve API reliability and concurrency without weakening policy."),
    ("src/sparse_text_model.cpp","Improve CPU efficiency or numerical stability without changing checkpoint safety."),
    ("tools/progress.py","Improve learning progress reporting."),
]

def sh(args, cwd=None, check=True):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)

def master_key():
    p = Path("/etc/reai-ai.env")
    if not p.exists():
        return ""
    for line in p.read_text().splitlines():
        if line.startswith("REAI_API_KEY="):
            return line.split("=",1)[1].strip()
    return ""

def ask(prompt):
    body = json.dumps({
        "messages":[{"role":"user","content":prompt}],
        "max_tokens":1800,
        "temperature":0.45
    }).encode()
    req = Request(
        "http://127.0.0.1:8080/v1/chat/completions",
        data=body,
        headers={"Content-Type":"application/json","X-API-Key":master_key()}
    )
    with urlopen(req, timeout=900) as r:
        data = json.loads(r.read().decode())
    return data["choices"][0]["message"]["content"]

def candidate_ready():
    if CAND.exists() and (CAND/".git").exists():
        return
    if CAND.exists():
        shutil.rmtree(CAND)
    subprocess.run(["git","branch","-D","self-improve-candidate"],cwd=ROOT,capture_output=True)
    sh(["git","worktree","add","-b","self-improve-candidate",str(CAND),"HEAD"],cwd=ROOT)

def extract_diff(text):
    i = text.find("diff --git ")
    if i < 0:
        return ""
    diff = text[i:]
    fence = diff.find("\n~~~")
    if fence >= 0:
        diff = diff[:fence]
    return diff.strip() + "\n"

def paths_from_diff(diff):
    return set(re.findall(r"^\+\+\+ b/(.+)$", diff, re.M))

def allowed(paths):
    if not paths:
        return False
    for p in paths:
        if any(p.startswith(x) for x in DENY_PREFIX):
            return False
        if not any(p.startswith(x) for x in ALLOW_PREFIX):
            return False
    return True

def validate():
    build = CAND/"build-self"
    r = sh(["cmake","-S",".","-B",str(build),"-DCMAKE_BUILD_TYPE=Release"],cwd=CAND,check=False)
    if r.returncode:
        return False, "cmake configure: " + r.stderr[-2000:]
    r = sh(["cmake","--build",str(build),"-j1"],cwd=CAND,check=False)
    if r.returncode:
        return False, "cmake build: " + r.stderr[-3000:]
    py = [str(p.relative_to(CAND)) for p in CAND.rglob("*.py") if ".git" not in p.parts]
    r = sh(["python3","-m","py_compile",*py],cwd=CAND,check=False)
    if r.returncode:
        return False, "py_compile: " + r.stderr[-3000:]
    return True, "OK"

def record(event):
    LOG.parent.mkdir(parents=True,exist_ok=True)
    with LOG.open("a",encoding="utf-8") as f:
        f.write(json.dumps(event,ensure_ascii=False)+"\n")
    print(json.dumps(event,ensure_ascii=False),flush=True)

def one():
    candidate_ready()
    target, goal = TARGETS[int(time.time()//1800) % len(TARGETS)]
    p = ROOT/target
    code = p.read_text(encoding="utf-8",errors="ignore")[:24000]
    prompt = f"""You are improving your own ReVerfyx AI source in a sandbox candidate branch.
Task: {goal}
Target file: {target}
Return ONLY one unified git diff beginning with: diff --git
Keep the change small.
Do not touch policy, systemd, credentials, network permissions, CMakeLists,
deployment scripts, or GitHub Actions. Do not add dependencies.
Do not execute or trust code from researched webpages.

CURRENT FILE:
{code}
"""
    out = ask(prompt)
    diff = extract_diff(out)
    event = {"time":int(time.time()),"target":target,"status":"no-diff"}

    if not diff:
        record(event)
        return

    paths = paths_from_diff(diff)
    if not allowed(paths):
        event["status"]="rejected-paths"
        event["paths"]=list(paths)
        record(event)
        return

    patch = CAND/"candidate.patch"
    patch.write_text(diff,encoding="utf-8")

    if sh(["git","apply","--check",str(patch)],cwd=CAND,check=False).returncode:
        event["status"]="invalid-patch"
        record(event)
        return

    sh(["git","apply",str(patch)],cwd=CAND)
    ok, msg = validate()

    if ok:
        sh(["git","add","-A"],cwd=CAND)
        sh([
            "git","-c","user.name=ReAI Self Improve",
            "-c","user.email=self@localhost",
            "commit","-m",f"self-improve: {target}"
        ],cwd=CAND,check=False)
        event["status"]="candidate-passed"
        event["commit"]=sh(["git","rev-parse","HEAD"],cwd=CAND).stdout.strip()
    else:
        event["status"]="tests-failed"
        event["detail"]=msg
        sh(["git","reset","--hard","HEAD"],cwd=CAND,check=False)

    record(event)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop",action="store_true")
    ap.add_argument("--interval",type=int,default=1800)
    a = ap.parse_args()

    while True:
        try:
            one()
        except Exception as e:
            record({"time":int(time.time()),"status":"error","detail":str(e)})
        if not a.loop:
            break
        time.sleep(max(300,a.interval))

if __name__=="__main__":
    main()

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
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CAND = Path(os.getenv("REAI_SELF_CANDIDATE", "/opt/reai-self-candidate"))
LOG = ROOT / "data/self-improve/history.jsonl"

ALLOW_PREFIX = ("src/","include/","api/","tools/")
DENY_PREFIX = ("policy/","deploy/","host.sh",".github/")
DENY_EXACT = {"tools/reverfyx-dev-keystore.b64"}
AUTO_PROMOTE = False

PREFERRED_TARGETS = [
    "src/sparse_text_model.cpp",
    "include/sparse_text_model.hpp",
    "src/image_model.cpp",
    "include/image_model.hpp",
    "src/text_model.cpp",
    "include/text_model.hpp",
    "src/main.cpp",
    "api/server.py",
    "tools/auto_research.py",
    "tools/multi_train.py",
    "tools/build_corpus.py",
    "tools/web_search.py",
    "tools/progress.py",
    "tools/rebrand_miniichat.py",
    "tools/manage.py",
    "tools/self_improve.py",
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
        "max_tokens":6000,
        "temperature":0.35
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

def path_allowed(p):
    if p in DENY_EXACT:
        return False
    if any(p.startswith(x) for x in DENY_PREFIX):
        return False
    return any(p.startswith(x) for x in ALLOW_PREFIX)

def allowed(paths):
    return bool(paths) and all(path_allowed(p) for p in paths)

def candidate_targets():
    found = []
    for rel in PREFERRED_TARGETS:
        if (ROOT / rel).is_file() and path_allowed(rel):
            found.append(rel)
    for prefix in ALLOW_PREFIX:
        base = ROOT / prefix.rstrip("/")
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT).as_posix()
            if rel in found or not path_allowed(rel):
                continue
            if p.suffix.lower() in {".py",".cpp",".cc",".c",".hpp",".h",".json"}:
                found.append(rel)
    return found

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

def health_ok():
    try:
        with urlopen("http://127.0.0.1:8080/health", timeout=15) as r:
            return json.loads(r.read().decode()).get("ok") is True
    except Exception:
        return False

def promote(commit, paths):
    if not AUTO_PROMOTE or not allowed(paths):
        return False, "candidate-only"

    status = sh(["git","status","--porcelain","--untracked-files=no"], cwd=ROOT, check=False)
    if status.stdout.strip():
        return False, "production-tree-not-clean"

    cp = sh(["git","cherry-pick",commit], cwd=ROOT, check=False)
    if cp.returncode:
        sh(["git","cherry-pick","--abort"], cwd=ROOT, check=False)
        return False, "cherry-pick-failed"

    build = ROOT/"build"
    ok = True
    detail = "OK"
    for cmd in (
        ["cmake","-S",".","-B",str(build),"-DCMAKE_BUILD_TYPE=Release"],
        ["cmake","--build",str(build),"-j1"],
    ):
        r = sh(cmd, cwd=ROOT, check=False)
        if r.returncode:
            ok = False
            detail = (r.stderr or r.stdout)[-3000:]
            break

    if ok:
        py = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*.py")
              if ".git" not in p.parts and "build" not in p.parts]
        r = sh(["python3","-m","py_compile",*py], cwd=ROOT, check=False)
        if r.returncode:
            ok = False
            detail = (r.stderr or r.stdout)[-3000:]

    if ok:
        sh(["systemctl","restart","reai"],check=False)
        time.sleep(3)
        ok = health_ok()
        if not ok:
            detail = "health-check-failed"

    if ok:
        return True, "promoted"

    sh(["git","reset","--hard","HEAD^"],cwd=ROOT,check=False)
    sh(["cmake","-S",".","-B",str(build),"-DCMAKE_BUILD_TYPE=Release"],cwd=ROOT,check=False)
    sh(["cmake","--build",str(build),"-j1"],cwd=ROOT,check=False)
    sh(["systemctl","restart","reai"],check=False)
    return False, "rolled-back: " + detail

def one():
    candidate_ready()
    targets = candidate_targets()
    if not targets:
        record({"time":int(time.time()),"status":"no-targets"})
        return
    target = targets[int(time.time()//300) % len(targets)]
    p = ROOT/target
    code = p.read_text(encoding="utf-8",errors="ignore")[:36000]
    available = "\n".join(f"- {x}" for x in targets[:120])
    prompt = f"""You are ReVerfyx AI and you have an OPTIONAL self-edit capability.

Self-editing is NOT an obligation and there is no quota. First decide whether
there is a concrete improvement worth making right now. If not, return exactly:
NO_CHANGE

If you do want to improve yourself, return a unified git diff beginning with:
diff --git

You may change as many related files as the improvement genuinely requires
under src/, include/, api/, or tools/. You are not limited to the suggested
file below and you do not need to make a change just because this check ran.
Prefer meaningful coherent improvements over churn.

You may improve model code, training, research, API behavior, performance,
observability, image generation, self-improvement logic, or the Android
rebrand/patch generator.

Do not modify credentials, keystores, deployment/systemd configuration,
GitHub Actions, or policy/. Do not execute code obtained from research sources.

SUGGESTED FILE TO INSPECT:
{target}

CURRENT CONTENT:
{code}

OTHER EDITABLE FILES:
{available}
"""
    out = ask(prompt)
    diff = extract_diff(out)
    event = {"time":int(time.time()),"target":target,"status":"no-diff"}

    if not diff:
        if out.strip().startswith("NO_CHANGE"):
            event["status"]="no-change-by-choice"
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
        promoted, promote_status = promote(event["commit"], paths)
        event["promotion"] = promote_status
        if promoted:
            event["status"] = "auto-promoted"
    else:
        event["status"]="tests-failed"
        event["detail"]=msg
        sh(["git","reset","--hard","HEAD"],cwd=CAND,check=False)

    record(event)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop",action="store_true")
    ap.add_argument("--interval",type=int,default=300)
    ap.add_argument("--auto-promote",action="store_true")
    a = ap.parse_args()
    global AUTO_PROMOTE
    AUTO_PROMOTE = a.auto_promote

    while True:
        try:
            one()
        except Exception as e:
            record({"time":int(time.time()),"status":"error","detail":str(e)})
        if not a.loop:
            break
        time.sleep(max(300,a.interval))
        argv=[sys.executable,str(Path(__file__).resolve()),"--loop","--interval",str(a.interval)]
        if a.auto_promote:
            argv.append("--auto-promote")
        os.execv(sys.executable,argv)

if __name__=="__main__":
    main()

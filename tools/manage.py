#!/usr/bin/env python3
import json, os, secrets, shutil, subprocess, sys, time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
AI_ENV=Path("/etc/reai-ai.env")
KEYS=Path("/etc/reai-api-keys.json")

def run(args, check=True, **kw):
    print("+"," ".join(map(str,args)), flush=True)
    return subprocess.run(list(map(str,args)), check=check, **kw)

def env_read(path):
    out={}
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k,v=line.split("=",1);out[k]=v
    return out

def env_set(path,key,value):
    d=env_read(path);d[key]=str(value)
    path.write_text("\n".join(f"{k}={v}" for k,v in d.items())+"\n")
    path.chmod(0o600)

def master_key():
    return env_read(AI_ENV).get("REAI_API_KEY","")

def cmd_upgrade50m():
    run(["apt-get","update"])
    run(["apt-get","install","-y","build-essential","cmake","python3","git"])
    run(["cmake","-S",ROOT,"-B",ROOT/"build","-DCMAKE_BUILD_TYPE=Release"])
    run(["cmake","--build",ROOT/"build","-j",str(max(1,os.cpu_count() or 1))])

    workers=ROOT/"models/workers";legacy=ROOT/"models/legacy"
    workers.mkdir(parents=True,exist_ok=True);legacy.mkdir(parents=True,exist_ok=True)
    stamp=time.strftime("%Y%m%d-%H%M%S")
    for i,seed in ((0,1337),(1,9256)):
        p=workers/f"worker-{i}.bin"
        sparse=False
        if p.exists():
            with p.open("rb") as f:sparse=f.read(8)==b"REAISP21"
        if p.exists() and not sparse:
            shutil.copy2(p,legacy/f"worker-{i}-{stamp}.bin")
            p.unlink()
        if not p.exists():
            run([ROOT/"build/reai","sparse-init",p,"256","192","512",str(seed)])

    if not KEYS.exists():
        KEYS.write_text('{"keys":[]}\n');KEYS.chmod(0o600)

    image64=ROOT/"models/image-64.bin"
    if not image64.exists():
        run([ROOT/"build/reai","image-init",image64,"64","256"])

    env_set(AI_ENV,"REAI_TEXT_MODEL",ROOT/"models/workers/worker-0.bin")
    env_set(AI_ENV,"REAI_IMAGE_MODEL",image64)
    env_set(AI_ENV,"REAI_API_KEYS_FILE",KEYS)

    learn_env=Path("/etc/reai-learning.env")
    if learn_env.exists():
        env_set(learn_env,"REAI_TRAIN_ENGINE","sparse")

    run(["systemctl","restart","reai"],check=False)
    if run(["systemctl","list-unit-files"],check=False,capture_output=True,text=True).stdout.find("reai-learning.service")>=0:
        run(["systemctl","restart","reai-learning"],check=False)

    run([ROOT/"build/reai","sparse-info",workers/"worker-0.bin"])
    for p in sorted(workers.glob("worker-*.bin")):
        print(p, f"{p.stat().st_size/1024/1024:.1f} MB")
    print("50M sparse profile enabled.")

def load_keys():
    try:return json.loads(KEYS.read_text())
    except Exception:return {"keys":[]}

def save_keys(d):
    KEYS.write_text(json.dumps(d,indent=2));KEYS.chmod(0o600)

def cmd_key_new(name):
    d=load_keys();key="reai_"+secrets.token_urlsafe(36)
    d.setdefault("keys",[]).append({"name":name[:64],"key":key,"created":int(time.time())})
    save_keys(d);print(key)

def cmd_keys():
    for x in load_keys().get("keys",[]):
        k=x.get("key","")
        print(f"{x.get('name','client')}: {k[:12]}...{k[-6:] if len(k)>6 else ''}")

def api_post(path,payload):
    body=json.dumps(payload,ensure_ascii=False).encode()
    req=Request("http://127.0.0.1:8080"+path,data=body,headers={
        "Content-Type":"application/json","X-API-Key":master_key()})
    with urlopen(req,timeout=1200) as r:return json.loads(r.read().decode())

def cmd_chat(prompt):
    d=api_post("/v1/chat/completions",{"messages":[{"role":"user","content":prompt}],"max_tokens":350})
    print(d["choices"][0]["message"]["content"])

def cmd_image(prompt):
    d=api_post("/v1/images/generations",{"prompt":prompt,"steps":32})
    print("http://127.0.0.1:8080"+d["data"][0]["url"])

def write_service(name,body):
    p=Path("/etc/systemd/system")/f"{name}.service"
    p.write_text(body)
    run(["systemctl","daemon-reload"])
    run(["systemctl","enable","--now",name])

def cmd_observe():
    write_service("reai-observer",f"""[Unit]
Description=ReVerfyx AI observer
After=reai.service
[Service]
Type=simple
User={os.getenv('USER','root')}
WorkingDirectory={ROOT}
ExecStart=/usr/bin/python3 {ROOT}/tools/observer.py
Restart=on-failure
RestartSec=5
Nice=10
[Install]
WantedBy=multi-user.target
""")
    print("Observer: http://127.0.0.1:8765")
    print("Open that address in a browser inside the RDP session.")

def cmd_improve(auto=False):
    extra = " --auto-promote" if auto else ""
    write_service("reai-self-improve",f"""[Unit]
Description=ReVerfyx AI self-improvement candidate loop
After=reai.service network-online.target
[Service]
Type=simple
User={os.getenv('USER','root')}
WorkingDirectory={ROOT}
ExecStart=/usr/bin/python3 {ROOT}/tools/self_improve.py --loop --interval 300{extra}
Restart=on-failure
RestartSec=60
Nice=8
[Install]
WantedBy=multi-user.target
""")
    print("Self-improvement loop enabled." + (" Safe auto-promotion ON." if auto else " Candidate-only mode."))

def cmd_improve_log():
    p=ROOT/"data/self-improve/history.jsonl"
    if not p.exists():print("No proposals yet.");return
    print("\n".join(p.read_text(errors="ignore").splitlines()[-50:]))

def main():
    cmd=sys.argv[1] if len(sys.argv)>1 else ""
    args=sys.argv[2:]
    if cmd=="upgrade50m":cmd_upgrade50m()
    elif cmd=="key-new":cmd_key_new(args[0] if args else "client")
    elif cmd=="keys":cmd_keys()
    elif cmd=="chat":cmd_chat(" ".join(args) or "Привет")
    elif cmd=="image":cmd_image(" ".join(args) or "mountains at night")
    elif cmd=="observe":cmd_observe()
    elif cmd=="improve":cmd_improve(False)
    elif cmd=="improve-auto":cmd_improve(True)
    elif cmd=="improve-once":run(["python3",ROOT/"tools/self_improve.py"])
    elif cmd=="improve-log":cmd_improve_log()
    else:raise SystemExit("unknown manage command: "+cmd)

if __name__=="__main__":main()

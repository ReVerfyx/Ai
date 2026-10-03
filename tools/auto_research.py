#!/usr/bin/env python3
"""Autonomous read-only research loop for ReVerfyx AI 0.0.2.

Stage 1: targeted Wikipedia bootstrap.
Stage 2: coverage-based research across Wikipedia, GitHub, and the public web.
No downloaded code is executed.
"""
import argparse, base64, hashlib, json, os, random, shutil, subprocess, tempfile, time
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from web_search import fetch_results

ROOT = Path(__file__).resolve().parents[1]
TOPICS = json.loads((ROOT/"tools/research_topics.json").read_text(encoding="utf-8"))["topics"]
STATE = ROOT/"data/research/state.json"
BOOTSTRAP_DONE = ROOT/"data/research/.bootstrap_done"
UA = "ReVerfyxAI/0.0.2 (+https://github.com/ReVerfyx/Ai; autonomous read-only research)"

CODE_EXT = {".py",".java",".kt",".kts",".c",".cc",".cpp",".h",".hpp",".js",".ts",".tsx",".jsx",".go",".rs",".sh",".sql",".md",".txt",".json",".yaml",".yml",".toml"}

def http_json(url, headers=None, retries=5, timeout=25):
    h={"User-Agent":UA,"Accept":"application/json"}
    if headers: h.update(headers)
    last=None
    for i in range(retries):
        try:
            with urlopen(Request(url,headers=h),timeout=timeout) as r:
                return json.loads(r.read(6_000_000).decode("utf-8","replace"))
        except (URLError,HTTPError,TimeoutError) as e:
            last=e; time.sleep(min(2**i,12))
    raise RuntimeError(f"HTTP failed: {last}")

def save_doc(worker, source, title, text, kind):
    text=text.strip()
    if len(text)<300: return False
    out=ROOT/"data/web"/f"worker-{worker}"/kind
    out.mkdir(parents=True,exist_ok=True)
    payload=f"SOURCE: {source}\nTITLE: {title}\nTYPE: {kind}\n\n{text}\n"
    name=hashlib.sha256(payload.encode()).hexdigest()+".txt"
    p=out/name
    if p.exists(): return False
    p.write_text(payload,encoding="utf-8")
    return True

def wiki_search(host, query, limit=6):
    base=f"https://{host}/w/api.php"
    data=http_json(base+"?"+urlencode({
        "action":"query","format":"json","generator":"search",
        "gsrsearch":query,"gsrnamespace":"0","gsrlimit":str(limit),
        "prop":"extracts|info","explaintext":"1","inprop":"url","redirects":"1"
    }))
    return list((data.get("query") or {}).get("pages",{}).values())

def fetch_wiki_topic(worker, topic):
    hosts=["ru.wikipedia.org","en.wikipedia.org"]
    added=0
    queries=list(topic.get("wiki") or [])+[topic["query"]]
    for idx,q in enumerate(queries[:5]):
        host=hosts[(worker+idx)%len(hosts)]
        try:
            for page in wiki_search(host,q,5):
                title=str(page.get("title") or "")
                text=str(page.get("extract") or "")
                url=str(page.get("fullurl") or f"https://{host}/wiki/{quote(title.replace(' ','_'))}")
                if save_doc(worker,url,title,text,"wikipedia"): added+=1
        except Exception as e:
            print(f"[research] wiki {host} {q}: {e}",flush=True)
    return added

def github_headers():
    h={"Accept":"application/vnd.github+json"}
    tok=os.getenv("GITHUB_TOKEN","").strip()
    if tok: h["Authorization"]="Bearer "+tok
    return h

def github_search_repos(query, limit=3):
    if not query: return []
    url="https://api.github.com/search/repositories?"+urlencode({
        "q":query,"sort":"stars","order":"desc","per_page":str(limit)
    })
    data=http_json(url,github_headers())
    return data.get("items") or []

def github_contents(owner_repo, path=""):
    url=f"https://api.github.com/repos/{owner_repo}/contents/{quote(path)}"
    return http_json(url,github_headers())

def fetch_github_topic(worker, topic):
    query=topic.get("github","").strip()
    if not query: return 0
    added=0
    try:
        repos=github_search_repos(query,2 if os.getenv("GITHUB_TOKEN") else 1)
    except Exception as e:
        print(f"[research] github search: {e}",flush=True); return 0
    for repo in repos:
        full=repo.get("full_name","")
        if not full: continue
        desc=repo.get("description") or ""
        meta=f"Repository: {full}\nDescription: {desc}\nStars: {repo.get('stargazers_count',0)}\nLanguage: {repo.get('language')}\n"
        if save_doc(worker,repo.get("html_url",""),full,meta,"github-meta"): added+=1
        try:
            root=github_contents(full,"")
        except Exception as e:
            print(f"[research] github contents {full}: {e}",flush=True); continue
        if not isinstance(root,list): continue
        candidates=[x for x in root if x.get("type")=="file" and Path(x.get("name","")).suffix.lower() in CODE_EXT]
        # Prefer README + a few source/config files.
        candidates=sorted(candidates,key=lambda x:(0 if x.get("name","").lower().startswith("readme") else 1, x.get("size",999999)))
        max_files=12 if os.getenv("GITHUB_TOKEN") else 6
        for item in candidates[:max_files]:
            if int(item.get("size") or 0)>120_000: continue
            try:
                d=github_contents(full,item.get("path",""))
                enc=d.get("encoding")
                content=d.get("content","")
                if enc=="base64":
                    raw=base64.b64decode(content)
                    text=raw.decode("utf-8","replace")
                else:
                    continue
                src=d.get("html_url") or item.get("html_url") or repo.get("html_url","")
                if save_doc(worker,src,f"{full}/{item.get('path','')}",text,"github-code"): added+=1
            except Exception as e:
                print(f"[research] github file {full}/{item.get('path','')}: {e}",flush=True)
    return added

def fetch_web_topic(worker, topic):
    added = 0
    query = str(topic.get("query") or "").strip()
    if not query:
        return 0
    try:
        for url, text in fetch_results(query, limit=2):
            title = urlparse_title(url)
            if save_doc(worker, url, title, text, "web"):
                added += 1
    except Exception as e:
        print(f"[research] web search {query}: {e}", flush=True)
    return added

def urlparse_title(url):
    try:
        from urllib.parse import urlparse
        u = urlparse(url)
        tail = (u.path.rstrip("/").split("/")[-1] or u.netloc).replace("-", " ").replace("_", " ")
        return (u.netloc + " — " + tail)[:180]
    except Exception:
        return url[:180]

def load_state():
    if STATE.exists():
        try: return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception: pass
    return {"cycles":0,"coverage":{},"last":[],"started":int(time.time())}

def save_state(st):
    STATE.parent.mkdir(parents=True,exist_ok=True)
    tmp=STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st,ensure_ascii=False,indent=2),encoding="utf-8")
    os.replace(tmp,STATE)

def choose_topic(st, worker):
    coverage=st.setdefault("coverage",{})
    # Independent workers pick from lowest-covered topics with worker offset.
    ranked=sorted(TOPICS,key=lambda t:(coverage.get(t["id"],0), t["id"]))
    pool=ranked[:max(4,min(10,len(ranked)))]
    return pool[worker % len(pool)]

def build_and_train(workers, epochs):
    subprocess.check_call(["python3",str(ROOT/"tools/build_corpus.py"),
                           str(ROOT/"data/web/worker-0"),
                           "--out",str(ROOT/"data/worker-corpus/worker-0.txt")])
    if workers>1:
        subprocess.check_call(["python3",str(ROOT/"tools/build_corpus.py"),
                               str(ROOT/"data/web/worker-1"),
                               "--out",str(ROOT/"data/worker-corpus/worker-1.txt")])
    subprocess.check_call(["python3",str(ROOT/"tools/multi_train.py"),
                           "--workers",str(workers),"--epochs",str(epochs),
                           "--corpus-dir","data/worker-corpus"])

def bootstrap(workers, pages_per_topic, epochs):
    print("[learn] stage=bootstrap wikipedia",flush=True)
    # broad, deterministic first pass
    broad=[
        "Programming language","Computer science","Software engineering","Algorithm",
        "Country","Geography","Language","Internet","Operating system","Database",
        "Artificial intelligence","Mobile app"
    ]
    for w in range(workers):
        host="ru.wikipedia.org" if w%2==0 else "en.wikipedia.org"
        target=ROOT/"data/web"/f"worker-{w}"/"bootstrap"
        target.mkdir(parents=True,exist_ok=True)
        saved=0
        for q in broad:
            try:
                for page in wiki_search(host,q,pages_per_topic):
                    title=str(page.get("title") or "")
                    if save_doc(w,page.get("fullurl",""),title,str(page.get("extract") or ""),"bootstrap"):
                        saved+=1
            except Exception as e:
                print(f"[bootstrap] {host} {q}: {e}",flush=True)
        print(f"[bootstrap] worker-{w} saved={saved}",flush=True)
    build_and_train(workers,epochs)
    BOOTSTRAP_DONE.parent.mkdir(parents=True,exist_ok=True)
    BOOTSTRAP_DONE.write_text(str(int(time.time())),encoding="utf-8")
    print("[learn] bootstrap complete",flush=True)

def prune(max_gb):
    if max_gb<=0: return
    root=ROOT/"data/web"
    files=[p for p in root.rglob("*.txt") if p.is_file()]
    total=sum(p.stat().st_size for p in files)
    limit=int(max_gb*1024**3)
    if total<=limit: return
    for p in sorted(files,key=lambda x:x.stat().st_mtime):
        try:
            size=p.stat().st_size; p.unlink(); total-=size
            if total<=limit: break
        except FileNotFoundError: pass

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--workers",type=int,default=2)
    ap.add_argument("--bootstrap-only",action="store_true")
    ap.add_argument("--skip-bootstrap",action="store_true")
    ap.add_argument("--bootstrap-pages",type=int,default=6)
    ap.add_argument("--epochs",type=int,default=1)
    ap.add_argument("--sleep",type=int,default=120)
    ap.add_argument("--max-data-gb",type=float,default=20)
    a=ap.parse_args()
    workers=max(1,min(a.workers,os.cpu_count() or 1))

    if not a.skip_bootstrap and not BOOTSTRAP_DONE.exists():
        bootstrap(workers,a.bootstrap_pages,a.epochs)
    if a.bootstrap_only:
        return

    st=load_state()
    print("[learn] stage=research browser read-only",flush=True)
    while True:
        cycle=int(st.get("cycles",0))+1
        last=[]
        for w in range(workers):
            topic=choose_topic(st,w)
            print(f"[research] cycle={cycle} worker={w} topic={topic['id']}",flush=True)
            wiki=fetch_wiki_topic(w,topic)
            gh=fetch_github_topic(w,topic)
            web=fetch_web_topic(w,topic)
            gained=wiki+gh+web
            st.setdefault("coverage",{})[topic["id"]]=st["coverage"].get(topic["id"],0)+gained
            last.append({"worker":w,"topic":topic["id"],"docs":gained,"wiki":wiki,"github":gh,"web":web})
        st["cycles"]=cycle
        st["last"]=last
        st["updated"]=int(time.time())
        save_state(st)
        prune(a.max_data_gb)
        try:
            build_and_train(workers,a.epochs)
        except subprocess.CalledProcessError as e:
            print(f"[research] training error: {e}",flush=True)
        time.sleep(max(30,a.sleep))

if __name__=="__main__":
    main()

#!/usr/bin/env python3
"""Autonomous research loop for ReVerfyx AI.

The research agent keeps a persistent curiosity/memory state, discovers new
topics from what it reads, searches the public web/Wikipedia/GitHub without a
global corpus-size cap, and may run selected downloaded code only inside the
disposable root sandbox provided by tools/sandbox_exec.py.
"""
import argparse, base64, hashlib, json, os, random, re, shutil, subprocess, tempfile, time
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from web_search import fetch_results

ROOT = Path(__file__).resolve().parents[1]
TOPICS = json.loads((ROOT/"tools/research_topics.json").read_text(encoding="utf-8"))["topics"]
STATE = ROOT/"data/research/state.json"
BRAIN = ROOT/"data/research/brain.json"
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
    for idx,q in enumerate(queries[:8]):
        host=hosts[(worker+idx)%len(hosts)]
        try:
            for page in wiki_search(host,q,8):
                title=str(page.get("title") or "")
                text=str(page.get("extract") or "")
                url=str(page.get("fullurl") or f"https://{host}/wiki/{quote(title.replace(' ','_'))}")
                if save_doc(worker,url,title,text,"wikipedia"): added+=1
        except Exception as e:
            print(f"[research] wiki {host} {q}: {e}",flush=True)
    return added

def fetch_random_wiki(worker, limit=12):
    host="ru.wikipedia.org" if worker%2==0 else "en.wikipedia.org"
    base=f"https://{host}/w/api.php"
    try:
        data=http_json(base+"?"+urlencode({
            "action":"query","format":"json","generator":"random",
            "grnnamespace":"0","grnlimit":str(limit),
            "prop":"extracts|info","explaintext":"1","inprop":"url"
        }))
        added=0
        for page in (data.get("query") or {}).get("pages",{}).values():
            title=str(page.get("title") or "")
            text=str(page.get("extract") or "")
            url=str(page.get("fullurl") or f"https://{host}/wiki/{quote(title.replace(' ','_'))}")
            if save_doc(worker,url,title,text,"wikipedia-random"):
                added+=1
        return added
    except Exception as e:
        print(f"[research] random wiki {host}: {e}",flush=True)
        return 0

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

def fetch_github_topic(worker, topic, brain=None):
    """Pick repositories for a topic and ingest each selected repo as a whole.

    Repositories are shallow-cloned into a temporary directory. No downloaded
    code, build script, hook, submodule, or binary is executed.
    """
    query=topic.get("github","").strip()
    if not query:
        return 0
    added=0
    try:
        repos=github_search_repos(query,3 if os.getenv("GITHUB_TOKEN") else 2)
    except Exception as e:
        print(f"[research] github search: {e}",flush=True)
        return 0

    for repo in repos:
        full=str(repo.get("full_name") or "")
        clone_url=str(repo.get("clone_url") or "")
        if not full or not clone_url:
            continue

        desc=repo.get("description") or ""
        meta=(
            f"Repository: {full}\nDescription: {desc}\n"
            f"Stars: {repo.get('stargazers_count',0)}\n"
            f"Language: {repo.get('language')}\n"
        )
        if save_doc(worker,repo.get("html_url",""),full,meta,"github-meta"):
            added+=1

        with tempfile.TemporaryDirectory(prefix="reai-github-") as td:
            checkout=Path(td)/"repo"
            env=os.environ.copy()
            env["GIT_TERMINAL_PROMPT"]="0"
            try:
                cp=subprocess.run(
                    [
                        "git","-c","core.hooksPath=/dev/null",
                        "clone","--depth","1","--single-branch","--no-tags",
                        "--filter=blob:limit=16m",clone_url,str(checkout)
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=180,
                    env=env,
                )
                if cp.returncode:
                    print(f"[research] github clone {full}: {cp.stderr[-500:]}",flush=True)
                    continue
            except Exception as e:
                print(f"[research] github clone {full}: {e}",flush=True)
                continue

            repo_files=0
            repo_bytes=0
            for p in checkout.rglob("*"):
                if not p.is_file() or ".git" in p.parts:
                    continue
                try:
                    size=p.stat().st_size
                    # Very large individual files are usually generated assets,
                    # dumps, archives, vendored bundles, or binaries.
                    if size > 16_000_000:
                        continue
                    raw=p.read_bytes()
                except Exception:
                    continue

                # Binary detection. All text files are accepted regardless of extension.
                if b"\x00" in raw[:8192]:
                    continue
                try:
                    text=raw.decode("utf-8")
                except UnicodeDecodeError:
                    text=raw.decode("utf-8","replace")

                if len(text.strip()) < 80:
                    continue

                rel=p.relative_to(checkout).as_posix()
                src=f"https://github.com/{full}/blob/HEAD/{quote(rel)}"
                if save_doc(worker,src,f"{full}/{rel}",text,"github-code"):
                    added+=1
                    repo_files+=1
                    repo_bytes+=len(raw)

            print(
                f"[research] github full-repo {full}: "
                f"text-files={repo_files} bytes={repo_bytes}",
                flush=True,
            )
            active_brain=brain if brain is not None else load_brain()
            maybe_sandbox_repo(worker, query, checkout, full, active_brain)
            if brain is None:
                save_brain(active_brain)
    return added

def fetch_web_topic(worker, topic):
    added = 0
    query = str(topic.get("query") or "").strip()
    if not query:
        return 0
    try:
        for url, text in fetch_results(query, limit=5):
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

def load_brain():
    if BRAIN.exists():
        try:
            data=json.loads(BRAIN.read_text(encoding="utf-8"))
            if isinstance(data,dict):
                data.setdefault("interests",{})
                data.setdefault("history",[])
                return data
        except Exception:
            pass
    interests={}
    for t in TOPICS:
        q=str(t.get("query") or t.get("id") or "").strip()
        if q:
            interests[q]=1.0
    return {"interests":interests,"history":[],"created":int(time.time())}

def save_brain(brain):
    BRAIN.parent.mkdir(parents=True,exist_ok=True)
    interests=brain.setdefault("interests",{})
    # Keep the persistent brain bounded as metadata; the actual training corpus is unlimited.
    best=sorted(interests.items(),key=lambda x:x[1],reverse=True)[:1000]
    brain["interests"]={k:round(float(v),4) for k,v in best}
    brain["history"]=brain.get("history",[])[-500:]
    brain["updated"]=int(time.time())
    tmp=BRAIN.with_suffix(".tmp")
    tmp.write_text(json.dumps(brain,ensure_ascii=False,indent=2),encoding="utf-8")
    os.replace(tmp,BRAIN)

STOPWORDS={
    "https","http","www","source","title","type","this","that","with","from","into",
    "для","как","что","это","или","при","его","она","они","также","который","которые",
    "the","and","are","was","were","have","has","not","you","your","about","using",
}

def discover_interests(worker, brain, max_files=80):
    root=ROOT/"data/web"/f"worker-{worker}"
    if not root.exists():
        return
    files=sorted(
        (p for p in root.rglob("*.txt") if p.is_file()),
        key=lambda p:p.stat().st_mtime,
        reverse=True
    )[:max_files]
    counts={}
    for p in files:
        try:
            text=p.read_text(encoding="utf-8",errors="ignore")[:18000]
        except Exception:
            continue
        for token in re.findall(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9_+.#-]{3,48}",text):
            key=token.strip("._-").lower()
            if len(key)<4 or key in STOPWORDS or key.isdigit():
                continue
            counts[key]=counts.get(key,0)+1
    interests=brain.setdefault("interests",{})
    for key,count in sorted(counts.items(),key=lambda x:x[1],reverse=True)[:80]:
        interests[key]=float(interests.get(key,0.0))*0.995 + min(8.0, 0.2*count)

def choose_brain_topic(brain, worker):
    interests=brain.setdefault("interests",{})
    if not interests:
        return None
    ranked=sorted(interests.items(),key=lambda x:x[1],reverse=True)[:120]
    # Mostly follow high-interest concepts, sometimes deliberately explore the tail.
    if random.random()<0.72:
        pool=ranked[:max(12,min(40,len(ranked)))]
    else:
        pool=ranked
    query=random.choice(pool)[0]
    return {
        "id":"brain:"+hashlib.sha1(query.encode("utf-8","ignore")).hexdigest()[:10],
        "query":query,
        "wiki":[query],
        "github":query,
        "_brain_query":query,
    }

def maybe_sandbox_repo(worker, query, checkout, full, brain):
    interests=brain.setdefault("interests",{})
    score=float(interests.get(str(query).lower(),0.0))
    # Curiosity-driven opportunity, not an obligation. Higher-interest subjects
    # are more likely to be tried, while random exploration still happens.
    probability=min(0.45,0.08 + score*0.015)
    if random.random()>=probability:
        return None
    try:
        cp=subprocess.run(
            ["python3",str(ROOT/"tools/sandbox_exec.py"),str(checkout)],
            capture_output=True,text=True,errors="replace",timeout=35
        )
        output=(cp.stdout or cp.stderr or "")[-12000:]
        if output.strip():
            save_doc(
                worker,
                f"sandbox://{full}",
                f"Sandbox experiment: {full}",
                output,
                "sandbox-result",
            )
        brain.setdefault("history",[]).append({
            "time":int(time.time()),"action":"sandbox-run",
            "repo":full,"query":query,"result":output[-1200:]
        })
        return output
    except Exception as e:
        brain.setdefault("history",[]).append({
            "time":int(time.time()),"action":"sandbox-error",
            "repo":full,"query":query,"result":str(e)
        })
        return None

def choose_topic(st, worker, brain):
    dynamic=choose_brain_topic(brain,worker)
    if dynamic and random.random()<0.80:
        return dynamic
    coverage=st.setdefault("coverage",{})
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

    warmup=ROOT/"data/warmup/ru-basic.txt"
    if warmup.exists():
        warm=warmup.read_text(encoding="utf-8",errors="ignore")
        for i in range(workers):
            corpus=ROOT/"data/worker-corpus"/f"worker-{i}.txt"
            if corpus.exists():
                with corpus.open("a",encoding="utf-8") as fh:
                    fh.write("\n\n"+warm+"\n")

    args=["python3",str(ROOT/"tools/multi_train.py"),
          "--workers",str(workers),"--epochs",str(epochs),
          "--corpus-dir","data/worker-corpus"]

    # Auto-detect the active checkpoint format so staged learning always
    # invokes the matching trainer.
    worker0=ROOT/"models/workers/worker-0.bin"
    try:
        if worker0.exists():
            magic=worker0.read_bytes()[:8]
            if magic == b"REAIUC51":
                args += ["--engine","unicode"]
            elif magic == b"REAISP21":
                args += ["--engine","sparse"]
    except OSError:
        pass

    subprocess.check_call(args)

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
    ap.add_argument("--max-data-gb",type=float,default=0)
    ap.add_argument("--train-every",type=int,default=4,
                    help="Train after this many research cycles; larger values prioritize faster data collection")
    a=ap.parse_args()
    workers=max(1,min(a.workers,os.cpu_count() or 1))

    if not a.skip_bootstrap and not BOOTSTRAP_DONE.exists():
        bootstrap(workers,a.bootstrap_pages,a.epochs)
    if a.bootstrap_only:
        return

    st=load_state()
    brain=load_brain()
    print("[learn] stage=autonomous research brain",flush=True)
    while True:
        cycle=int(st.get("cycles",0))+1
        last=[]
        for w in range(workers):
            topic=choose_topic(st,w,brain)
            print(f"[research] cycle={cycle} worker={w} topic={topic['id']}",flush=True)
            wiki=fetch_wiki_topic(w,topic)
            random_wiki=fetch_random_wiki(w,12)
            gh=fetch_github_topic(w,topic,brain)
            web=fetch_web_topic(w,topic)
            gained=wiki+random_wiki+gh+web
            st.setdefault("coverage",{})[topic["id"]]=st["coverage"].get(topic["id"],0)+gained
            last.append({
                "worker":w,"topic":topic["id"],"docs":gained,
                "wiki":wiki,"random_wiki":random_wiki,"github":gh,"web":web
            })
            q=str(topic.get("_brain_query") or topic.get("query") or topic["id"]).lower()
            brain.setdefault("interests",{})[q]=float(brain.setdefault("interests",{}).get(q,0.0))+max(0.2,gained*0.15)
            brain.setdefault("history",[]).append({
                "time":int(time.time()),"action":"research","query":q,
                "docs":gained,"wiki":wiki,"random_wiki":random_wiki,"github":gh,"web":web
            })
            discover_interests(w,brain)
        st["cycles"]=cycle
        st["last"]=last
        st["updated"]=int(time.time())
        save_state(st)
        save_brain(brain)
        prune(a.max_data_gb)
        train_every=max(1,a.train_every)
        if cycle % train_every == 0:
            print(f"[research] training batch at cycle={cycle}",flush=True)
            try:
                build_and_train(workers,a.epochs)
            except subprocess.CalledProcessError as e:
                print(f"[research] training error: {e}",flush=True)
        else:
            print(f"[research] collected cycle={cycle}; next training in {train_every-(cycle % train_every)} cycle(s)",flush=True)
        time.sleep(max(5,a.sleep))

if __name__=="__main__":
    main()

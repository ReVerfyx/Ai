#!/usr/bin/env python3
import html, json, os, subprocess, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.getenv("REAI_OBSERVER_PORT", "8765"))
HOST = os.getenv("REAI_OBSERVER_HOST", "127.0.0.1")
TOKEN = os.getenv("REAI_OBSERVER_TOKEN", "")

def service(name):
    try:
        return subprocess.run(["systemctl","is-active",name],capture_output=True,text=True,timeout=2).stdout.strip()
    except Exception:
        return "?"

def recent_logs():
    try:
        p = subprocess.run(["journalctl","-u","reai-learning","-n","80","--no-pager"],
                           capture_output=True,text=True,timeout=4)
        return p.stdout[-16000:]
    except Exception as e:
        return str(e)

def fmt_size(n):
    n = float(n)
    for u in ("B","KB","MB","GB"):
        if n < 1024 or u == "GB":
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} GB"

def model_rows():
    rows=[]
    for i in (0,1):
        p=ROOT/"models/workers"/f"worker-{i}.bin"
        c=ROOT/"data/worker-corpus"/f"worker-{i}.txt"
        wdir=ROOT/"data/web"/f"worker-{i}"
        docs=list(wdir.rglob("*.txt")) if wdir.exists() else []
        rows.append({
            "worker":i,
            "model":fmt_size(p.stat().st_size) if p.exists() else "missing",
            "updated":time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(p.stat().st_mtime)) if p.exists() else "-",
            "corpus":fmt_size(c.stat().st_size) if c.exists() else "missing",
            "docs":len(docs),
        })
    return rows

def research():
    p=ROOT/"data/research/state.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def newest_sources():
    web=ROOT/"data/web"
    if not web.exists():
        return []
    files=sorted(web.rglob("*.txt"),key=lambda p:p.stat().st_mtime,reverse=True)[:20]
    out=[]
    for p in files:
        try:
            lines=p.read_text(encoding="utf-8",errors="ignore").splitlines()[:4]
            src=next((x[8:] for x in lines if x.startswith("SOURCE: ")),str(p))
            title=next((x[7:] for x in lines if x.startswith("TITLE: ")),p.name)
            out.append((title,src,time.strftime("%H:%M:%S",time.localtime(p.stat().st_mtime))))
        except Exception:
            pass
    return out

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        if parsed.path not in ("/","/index.html"):
            self.send_error(404)
            return
        if TOKEN:
            supplied = parse_qs(parsed.query).get("token", [""])[0]
            if supplied != TOKEN:
                raw=b"Unauthorized"
                self.send_response(401)
                self.send_header("Content-Type","text/plain; charset=utf-8")
                self.send_header("Content-Length",str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
        st=research()
        body=["""<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="5">
<title>ReVerfyx AI Observer</title>
<style>
body{font-family:system-ui;background:#0f1115;color:#e9edf1;margin:24px}
.card{background:#171a21;border:1px solid #2b3039;border-radius:14px;padding:16px;margin:12px 0}
.badge{display:inline-block;padding:4px 9px;border-radius:12px;background:#252b34;margin-right:6px}
table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #2b3039;text-align:left}
pre{white-space:pre-wrap;max-height:360px;overflow:auto;background:#0c0e12;padding:12px;border-radius:10px}
</style></head><body><h1>ReVerfyx AI Observer</h1>"""]
        body.append("<div class=card>")
        for n in ("reai","reai-learning","reai-observer","reai-self-improve"):
            body.append(f"<span class=badge>{html.escape(n)}: {html.escape(service(n))}</span>")
        body.append("</div><div class=card><h2>Models</h2><table><tr><th>worker</th><th>model</th><th>corpus</th><th>docs</th><th>updated</th></tr>")
        for r in model_rows():
            body.append(f"<tr><td>{r['worker']}</td><td>{r['model']}</td><td>{r['corpus']}</td><td>{r['docs']}</td><td>{r['updated']}</td></tr>")
        body.append("</table></div>")
        body.append(f"<div class=card><h2>Research</h2><p>cycles: {st.get('cycles',0)}</p>")
        for x in st.get("last",[]):
            body.append(f"<p>worker-{x.get('worker')}: <b>{html.escape(str(x.get('topic')))}</b> docs={x.get('docs')} wiki={x.get('wiki')} github={x.get('github')}</p>")
        body.append("</div><div class=card><h2>Newest sources</h2>")
        for title,src,tm in newest_sources():
            body.append(f"<div>{html.escape(tm)} — <b>{html.escape(title)}</b><br><small>{html.escape(src)}</small></div><br>")
        body.append("</div><div class=card><h2>Learning log</h2><pre>"+html.escape(recent_logs())+"</pre></div></body></html>")
        raw="".join(body).encode()
        self.send_response(200)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self,*args):
        pass

if __name__=="__main__":
    shown = HOST if HOST != "0.0.0.0" else "SERVER_IP"
    print(f"observer http://{shown}:{PORT}",flush=True)
    ThreadingHTTPServer((HOST,PORT),H).serve_forever()

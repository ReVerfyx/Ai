#!/usr/bin/env python3
"""Small polite crawler that builds text training shards without third-party packages."""
import argparse, hashlib, html, re, time
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

UA = "ReVerfyxAI-ResearchCrawler/0.1"

class Extractor(HTMLParser):
    def __init__(self):
        super().__init__(); self.text=[]; self.links=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in {"script","style","noscript","svg"}: self.skip += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href: self.links.append(href)
    def handle_endtag(self, tag):
        if tag in {"script","style","noscript","svg"} and self.skip: self.skip -= 1
    def handle_data(self, data):
        if not self.skip: self.text.append(data)

def normalize_text(parts):
    s = html.unescape("\n".join(parts))
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def allowed(url, robots):
    u=urlparse(url); base=f"{u.scheme}://{u.netloc}"
    if base not in robots:
        rp=RobotFileParser(); rp.set_url(base+"/robots.txt")
        try: rp.read()
        except Exception: rp=None
        robots[base]=rp
    rp=robots[base]
    return True if rp is None else rp.can_fetch(UA,url)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("seeds", nargs="+"); ap.add_argument("--out", default="data/web")
    ap.add_argument("--pages", type=int, default=100); ap.add_argument("--delay", type=float, default=1.0); ap.add_argument("--same-host", action="store_true")
    a=ap.parse_args(); out=Path(a.out); out.mkdir(parents=True, exist_ok=True)
    q=deque(a.seeds); seen=set(); robots={}; seed_hosts={urlparse(x).netloc for x in a.seeds}; saved=0
    while q and saved<a.pages:
        url=urldefrag(q.popleft())[0]
        if url in seen or not url.startswith(("http://","https://")): continue
        seen.add(url)
        if a.same_host and urlparse(url).netloc not in seed_hosts: continue
        if not allowed(url,robots): continue
        try:
            req=Request(url,headers={"User-Agent":UA,"Accept":"text/html"})
            with urlopen(req,timeout=15) as r:
                if "text/html" not in r.headers.get_content_type(): continue
                raw=r.read(2_000_000).decode(r.headers.get_content_charset() or "utf-8",errors="replace")
            ex=Extractor(); ex.feed(raw); text=normalize_text(ex.text)
            if len(text)<400: continue
            h=hashlib.sha256(text.encode()).hexdigest()
            p=out/f"{h}.txt"
            if not p.exists(): p.write_text(f"SOURCE: {url}\n\n{text}",encoding="utf-8"); saved+=1; print(saved,url)
            for link in ex.links[:500]:
                nxt=urldefrag(urljoin(url,link))[0]
                if nxt not in seen: q.append(nxt)
        except Exception as e: print("skip",url,e)
        time.sleep(max(0,a.delay))
if __name__=="__main__": main()

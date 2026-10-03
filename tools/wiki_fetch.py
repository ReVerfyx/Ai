#!/usr/bin/env python3
"""Fetch random Wikipedia articles for one independent ReAI worker.

Uses the public MediaWiki API with a descriptive User-Agent. No third-party
Python packages are required.
"""
import argparse
import hashlib
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

UA = "ReVerfyxAI/0.0.2 (+https://github.com/ReVerfyx/Ai; educational research crawler)"

def api_base(seed):
    u = urlparse(seed)
    host = u.netloc or "en.wikipedia.org"
    if not host.endswith("wikipedia.org"):
        raise ValueError("wiki_fetch only supports wikipedia.org seeds")
    return f"https://{host}/w/api.php", host

def request_json(base, params, retries=5):
    url = base + "?" + urlencode(params)
    last = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={
                "User-Agent": UA,
                "Accept": "application/json",
                "Accept-Language": "ru,en;q=0.8",
                "Connection": "close",
            })
            with urlopen(req, timeout=25) as r:
                return json.loads(r.read(4_000_000).decode("utf-8", "replace"))
        except (URLError, HTTPError, TimeoutError) as e:
            last = e
            time.sleep(min(2 ** attempt, 12))
    raise RuntimeError(f"MediaWiki API failed: {last}")

def clean_html(raw):
    raw = re.sub(r"(?is)<(script|style|table|sup|math).*?>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = re.sub(r"[ \t\r\f\v]+", " ", raw)
    raw = re.sub(r"\n\s*\n+", "\n\n", raw)
    return raw.strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seed")
    ap.add_argument("--out", required=True)
    ap.add_argument("--pages", type=int, default=40)
    ap.add_argument("--batch", type=int, default=10)
    ap.add_argument("--delay", type=float, default=0.4)
    args = ap.parse_args()

    base, host = api_base(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    wanted = max(1, args.pages)
    saved = 0
    seen_titles = set()

    while saved < wanted:
        batch = min(max(1, args.batch), wanted - saved, 20)
        data = request_json(base, {
            "action": "query",
            "format": "json",
            "generator": "random",
            "grnnamespace": "0",
            "grnlimit": str(batch),
            "prop": "extracts|info",
            "explaintext": "0",
            "exsectionformat": "plain",
            "inprop": "url",
            "redirects": "1",
        })

        pages = list((data.get("query") or {}).get("pages", {}).values())
        if not pages:
            time.sleep(2)
            continue

        for page in pages:
            if saved >= wanted:
                break
            title = str(page.get("title") or "").strip()
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)

            extract = clean_html(page.get("extract") or "")
            if len(extract) < 500:
                continue

            source = page.get("fullurl") or f"https://{host}/wiki/" + title.replace(" ", "_")
            text = f"SOURCE: {source}\nTITLE: {title}\n\n{extract}\n"
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            path = out / f"{digest}.txt"
            if not path.exists():
                path.write_text(text, encoding="utf-8")
                saved += 1
                print(f"[wiki] {saved}/{wanted} {title}", flush=True)

        time.sleep(max(0.0, args.delay))

    print(f"[wiki] saved={saved} out={out}", flush=True)

if __name__ == "__main__":
    main()

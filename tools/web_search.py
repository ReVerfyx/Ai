#!/usr/bin/env python3
"""Read-only general web search/fetch helper for ReVerfyx AI.

Uses DuckDuckGo HTML search when reachable. It never executes JavaScript,
downloads binaries, or follows private/local network addresses.
"""
import html
import ipaddress
import re
import socket
from urllib.parse import urlencode, urlparse, parse_qs, unquote
from urllib.request import Request, urlopen

UA="ReVerfyxAI/0.0.3 (+https://github.com/ReVerfyx/Ai; read-only research)"

def public_url(url):
    try:
        u=urlparse(url)
        if u.scheme not in ("http","https") or not u.hostname:
            return False
        host=u.hostname.lower()
        if host in ("localhost",) or host.endswith(".local"):
            return False
        for info in socket.getaddrinfo(host,None):
            ip=ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        return True
    except Exception:
        return False

def get(url, limit=1_500_000):
    if not public_url(url):
        raise ValueError("non-public URL blocked")
    req=Request(url,headers={"User-Agent":UA,"Accept":"text/html,text/plain;q=0.9,*/*;q=0.1"})
    with urlopen(req,timeout=20) as r:
        ctype=(r.headers.get("Content-Type") or "").lower()
        if "text/" not in ctype and "html" not in ctype and "json" not in ctype:
            raise ValueError("non-text content")
        return r.read(limit).decode("utf-8","replace")

def clean(raw):
    raw=re.sub(r"(?is)<(script|style|svg|noscript).*?>.*?</\1>"," ",raw)
    raw=re.sub(r"(?is)<[^>]+>"," ",raw)
    raw=html.unescape(raw)
    raw=re.sub(r"\s+"," ",raw)
    return raw.strip()

def search(query, limit=4):
    url="https://html.duckduckgo.com/html/?"+urlencode({"q":query})
    raw=get(url,2_000_000)
    links=[]
    for m in re.finditer(r'class="result__a"[^>]+href="([^"]+)"',raw,re.I):
        href=html.unescape(m.group(1))
        if "uddg=" in href:
            try:
                href=unquote(parse_qs(urlparse(href).query).get("uddg",[""])[0])
            except Exception:
                pass
        if public_url(href) and href not in links:
            links.append(href)
        if len(links)>=limit:
            break
    return links

def fetch_results(query, limit=3):
    out=[]
    for url in search(query,limit=limit+2):
        try:
            text=clean(get(url))
            if len(text)<500:
                continue
            out.append((url,text[:120_000]))
            if len(out)>=limit:
                break
        except Exception:
            pass
    return out

#!/usr/bin/env python3
"""Continuous, fully independent self-learning for ReVerfyx AI 0.0.2."""
import argparse
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--seed", action="append", default=[])
ap.add_argument("--pages", type=int, default=50)
ap.add_argument("--workers", type=int, default=min(2, os.cpu_count() or 1))
ap.add_argument("--epochs", type=int, default=1)
ap.add_argument("--cycles", type=int, default=1, help="0 = run forever")
ap.add_argument("--hours", type=float, default=0.0, help="0 = no time limit")
ap.add_argument("--pause", type=float, default=5.0)
ap.add_argument("--bin", default="build/reai")
ap.add_argument("--same-host", action="store_true")
ap.add_argument("--max-data-gb", type=float, default=0.0, help="max cached web data across workers; 0 = unlimited")
a = ap.parse_args()

root = Path(__file__).resolve().parents[1]
started = time.time()
cycle = 0

def crawl_for_worker(worker_id: int, seed: str):
    target = root / "data" / "web" / f"worker-{worker_id}"
    target.mkdir(parents=True, exist_ok=True)

    if "wikipedia.org" in seed:
        cmd = [
            "python3", str(root / "tools/wiki_fetch.py"), seed,
            "--out", str(target),
            "--pages", str(a.pages),
            "--delay", "0.4"
        ]
    else:
        cmd = [
            "python3", str(root / "tools/crawl.py"), seed,
            "--out", str(target),
            "--pages", str(a.pages),
            "--delay", "1.0"
        ]
        if a.same_host:
            cmd.append("--same-host")

    subprocess.check_call(cmd)

def prune_web_cache():
    if a.max_data_gb <= 0:
        return
    root_dir = root / "data" / "web"
    files = [p for p in root_dir.rglob("*.txt") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    limit = int(a.max_data_gb * 1024 * 1024 * 1024)
    if total <= limit:
        return
    for p in sorted(files, key=lambda x: x.stat().st_mtime):
        try:
            size = p.stat().st_size
            p.unlink()
            total -= size
            if total <= limit:
                break
        except FileNotFoundError:
            pass
    print(f"[storage] web cache pruned to {total / (1024**3):.2f} GiB")

def build_worker_corpus(worker_id: int):
    source = root / "data" / "web" / f"worker-{worker_id}"
    source.mkdir(parents=True, exist_ok=True)
    out = root / "data" / "worker-corpus" / f"worker-{worker_id}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.check_call([
        "python3", str(root / "tools/build_corpus.py"), str(source),
        "--out", str(out)
    ])
    return out

while True:
    cycle += 1
    print(f"\n=== ReAI independent learning cycle {cycle} ===")

    if a.seed:
        with ThreadPoolExecutor(max_workers=min(a.workers, len(a.seed))) as pool:
            futures = [
                pool.submit(crawl_for_worker, i % a.workers, seed)
                for i, seed in enumerate(a.seed)
            ]
            for f in futures:
                f.result()

    prune_web_cache()

    corpora = []
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures = [pool.submit(build_worker_corpus, i) for i in range(a.workers)]
        for f in futures:
            corpora.append(f.result())

    usable = [p for p in corpora if p.exists() and p.stat().st_size > 128]
    if not usable:
        print("[learn] no usable corpus yet; waiting 60 seconds before retry", flush=True)
        if a.cycles > 0 and cycle >= a.cycles:
            break
        if a.hours > 0 and (time.time() - started) >= a.hours * 3600:
            break
        time.sleep(max(60.0, a.pause))
        continue

    subprocess.check_call([
        "python3", str(root / "tools/multi_train.py"),
        "--workers", str(a.workers),
        "--epochs", str(a.epochs),
        "--bin", a.bin,
        "--corpus-dir", "data/worker-corpus"
    ])

    if a.cycles > 0 and cycle >= a.cycles:
        break
    if a.hours > 0 and (time.time() - started) >= a.hours * 3600:
        break
    time.sleep(max(15.0, a.pause))

print("self-learning finished")

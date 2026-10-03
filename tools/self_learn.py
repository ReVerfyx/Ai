#!/usr/bin/env python3
"""Continuous independent self-learning loop for ReVerfyx AI 0.0.2."""
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
a = ap.parse_args()

root = Path(__file__).resolve().parents[1]
started = time.time()
cycle = 0

def crawl_for_worker(worker_id: int, seed: str):
    target = root / "data" / "web" / f"worker-{worker_id}"
    cmd = [
        "python3", str(root / "tools/crawl.py"), seed,
        "--out", str(target), "--pages", str(a.pages), "--delay", "1.0"
    ]
    if a.same_host:
        cmd.append("--same-host")
    subprocess.check_call(cmd)

while True:
    cycle += 1
    print(f"\n=== ReAI independent learning cycle {cycle} ===")

    if a.seed:
        # Seeds are distributed round-robin. Each crawl target belongs to one worker.
        with ThreadPoolExecutor(max_workers=min(a.workers, len(a.seed))) as pool:
            futures = [
                pool.submit(crawl_for_worker, i % a.workers, seed)
                for i, seed in enumerate(a.seed)
            ]
            for f in futures:
                f.result()

    web = root / "data" / "web"
    web.mkdir(parents=True, exist_ok=True)
    subprocess.check_call([
        "python3", str(root / "tools/build_corpus.py"), str(web),
        "--out", str(root / "data/corpus.txt")
    ])

    subprocess.check_call([
        "python3", str(root / "tools/multi_train.py"),
        "--workers", str(a.workers),
        "--epochs", str(a.epochs),
        "--bin", a.bin
    ])

    if a.cycles > 0 and cycle >= a.cycles:
        break
    if a.hours > 0 and (time.time() - started) >= a.hours * 3600:
        break
    time.sleep(max(0.0, a.pause))

print("self-learning finished")

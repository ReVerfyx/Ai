#!/usr/bin/env python3
"""Independent parallel trainers for ReVerfyx AI 0.0.2.

Every worker owns its own checkpoint and its own corpus shard.
Workers NEVER average, merge, copy learned weights into each other, or
automatically replace the production model.
"""
import argparse
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

def split_corpus(corpus: Path, out_dir: Path, workers: int):
    text = corpus.read_text(encoding="utf-8", errors="ignore")
    docs = [x.strip() for x in text.split("\n\n") if x.strip()]
    if not docs:
        raise RuntimeError("corpus is empty")
    buckets = [[] for _ in range(workers)]
    sizes = [0] * workers
    for doc in sorted(docs, key=len, reverse=True):
        i = min(range(workers), key=lambda x: sizes[x])
        buckets[i].append(doc)
        sizes[i] += len(doc.encode("utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, bucket in enumerate(buckets):
        p = out_dir / f"worker-{i}.txt"
        p.write_text("\n\n".join(bucket) + "\n", encoding="utf-8")
        paths.append(p)
    return paths

def ensure_worker(binary: Path, production: Path, worker_model: Path, hidden: int):
    worker_model.parent.mkdir(parents=True, exist_ok=True)
    if worker_model.exists():
        return
    if production.exists():
        shutil.copy2(production, worker_model)
    else:
        subprocess.check_call([str(binary), "text-init", str(worker_model), str(hidden)])

def train_worker(binary: Path, worker_id: int, model: Path, shard: Path,
                 epochs: int, seq_len: int, lr: float):
    if shard.stat().st_size <= seq_len + 2:
        print(f"[worker {worker_id}] skipped: shard too small")
        return
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    print(f"[worker {worker_id}] independent model={model.name} shard={shard.name}")
    subprocess.check_call([
        str(binary), "text-train", str(model), str(shard),
        str(epochs), str(seq_len), str(lr)
    ], env=env)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--production-model", default="models/text.bin")
    ap.add_argument("--workers-dir", default="models/workers")
    ap.add_argument("--corpus", default="data/corpus.txt")
    ap.add_argument("--shards-dir", default="data/worker-shards")
    ap.add_argument("--bin", default="build/reai")
    ap.add_argument("--workers", type=int, default=min(2, os.cpu_count() or 1))
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--seq-len", type=int, default=64)
    ap.add_argument("--lr", type=float, default=0.0005)
    ap.add_argument("--hidden", type=int, default=128)
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    binary = (root / args.bin).resolve()
    production = (root / args.production_model).resolve()
    corpus = (root / args.corpus).resolve()
    workers_dir = (root / args.workers_dir).resolve()
    shards_dir = (root / args.shards_dir).resolve()
    workers = max(1, args.workers)

    shards = split_corpus(corpus, shards_dir, workers)
    jobs = []
    for i in range(workers):
        model = workers_dir / f"worker-{i}.bin"
        ensure_worker(binary, production, model, args.hidden)
        jobs.append((i, model, shards[i]))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(train_worker, binary, i, model, shard,
                        args.epochs, args.seq_len, args.lr)
            for i, model, shard in jobs
        ]
        for f in futures:
            f.result()

    print("\nIndependent training complete.")
    print("Production checkpoint was NOT modified.")
    for i, model, shard in jobs:
        print(f"worker-{i}: {model} <- {shard}")

if __name__ == "__main__":
    main()

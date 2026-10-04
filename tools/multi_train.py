#!/usr/bin/env python3
"""Independent trainers for ReVerfyx AI.

Supports the legacy dense engine, the sparse ~50.7M byte engine, and the fast\nUnicode ~4.5M engine. Sparse/Unicode workers remain independent and train\nsequentially on small VPSs so the API stays responsive.
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

def ensure_worker(binary: Path, production: Path, worker_model: Path,
                  hidden: int, engine: str, seed: int, corpus_hint: Path):
    worker_model.parent.mkdir(parents=True, exist_ok=True)
    if worker_model.exists():
        return
    if engine == "sparse":
        subprocess.check_call([
            str(binary), "sparse-init", str(worker_model),
            "256", "192", "512", str(seed)
        ])
    elif engine == "unicode":
        if not corpus_hint.exists():
            raise RuntimeError(f"unicode init needs corpus: {corpus_hint}")
        subprocess.check_call([
            str(binary), "unicode-init", str(worker_model), str(corpus_hint),
            "1024", "128", "64", "256", str(seed)
        ])
    elif production.exists():
        shutil.copy2(production, worker_model)
    else:
        subprocess.check_call([str(binary), "text-init", str(worker_model), str(hidden)])

def train_worker(binary: Path, worker_id: int, model: Path, corpus: Path,
                 epochs: int, seq_len: int, lr: float, engine: str):
    if not corpus.exists() or corpus.stat().st_size <= seq_len + 2:
        print(f"[worker {worker_id}] skipped: corpus missing/too small: {corpus}", flush=True)
        return
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"

    print(
        f"[worker {worker_id}] engine={engine} independent checkpoint={model} corpus={corpus}",
        flush=True
    )

    training = model.with_suffix(model.suffix + f".training-{os.getpid()}-{worker_id}")
    shutil.copy2(model, training)
    try:
        cmd = "unicode-train" if engine == "unicode" else ("sparse-train" if engine == "sparse" else "text-train")
        subprocess.check_call([
            str(binary), cmd, str(training), str(corpus),
            str(epochs), str(seq_len), str(lr)
        ], env=env)
        backup = model.with_suffix(model.suffix + ".previous")
        shutil.copy2(model, backup)
        os.replace(training, model)
    finally:
        training.unlink(missing_ok=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--production-model", default="models/text.bin")
    ap.add_argument("--workers-dir", default="models/workers")
    ap.add_argument("--corpus", default="data/corpus.txt")
    ap.add_argument("--corpus-dir", default="",
                    help="directory containing worker-N.txt")
    ap.add_argument("--shards-dir", default="data/worker-shards")
    ap.add_argument("--bin", default="build/reai")
    ap.add_argument("--workers", type=int, default=min(2, os.cpu_count() or 1))
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--seq-len", type=int, default=64)
    ap.add_argument("--lr", type=float, default=0.0005)
    ap.add_argument("--hidden", type=int, default=128)
    ap.add_argument(
        "--engine",
        choices=["text", "sparse", "unicode"],
        default=os.getenv("REAI_TRAIN_ENGINE", "text")
    )
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    binary = (root / args.bin).resolve()
    production = (root / args.production_model).resolve()
    workers_dir = (root / args.workers_dir).resolve()
    workers = max(1, args.workers)

    if args.corpus_dir:
        cdir = (root / args.corpus_dir).resolve()
        corpora = [cdir / f"worker-{i}.txt" for i in range(workers)]
    else:
        corpus = (root / args.corpus).resolve()
        corpora = split_corpus(corpus, (root / args.shards_dir).resolve(), workers)

    jobs = []
    for i in range(workers):
        model = workers_dir / f"worker-{i}.bin"
        ensure_worker(
            binary, production, model, args.hidden,
            args.engine, 1337 + i * 7919, corpora[i]
        )
        jobs.append((i, model, corpora[i]))

    if args.engine in ("sparse", "unicode"):
        # Independent checkpoints, sequential compute. Unicode is much smaller,
        # but keeping it sequential avoids starving the API on a 2-vCPU VPS.
        max_seq = 64 if args.engine == "unicode" else 48
        for i, model, corpus in jobs:
            train_worker(
                binary, i, model, corpus,
                args.epochs, min(args.seq_len, max_seq), args.lr, args.engine
            )
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(
                    train_worker, binary, i, model, corpus,
                    args.epochs, args.seq_len, args.lr, args.engine
                )
                for i, model, corpus in jobs
            ]
            for f in futures:
                f.result()

    print("\nIndependent training complete; no worker weights were merged.")
    print("Production checkpoint was NOT modified during an active training pass.")
    for i, model, corpus in jobs:
        print(f"worker-{i}: {model} <- {corpus}")

if __name__ == "__main__":
    main()

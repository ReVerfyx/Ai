#!/usr/bin/env python3
"""Parallel CPU training for ReVerfyx AI.

Each worker starts from the same checkpoint, trains on a different corpus shard,
then the checkpoints are averaged into one new model. This lets a 2-core VPS
learn from two shards at the same time without concurrent writes to one file.
"""
import argparse
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MAGIC = b"REAITXT1"
VECTOR_COUNT = 5

def read_checkpoint(path: Path):
    if sys.byteorder != "little":
        raise RuntimeError("v0.0.2 checkpoint merger currently expects little-endian CPU")
    with path.open("rb") as f:
        if f.read(8) != MAGIC:
            raise RuntimeError(f"bad checkpoint: {path}")
        hidden = struct.unpack("<I", f.read(4))[0]
        vectors = []
        for _ in range(VECTOR_COUNT):
            n = struct.unpack("<Q", f.read(8))[0]
            raw = f.read(n * 4)
            if len(raw) != n * 4:
                raise RuntimeError(f"truncated checkpoint: {path}")
            vectors.append(list(struct.unpack(f"<{n}f", raw)))
        return hidden, vectors

def write_checkpoint(path: Path, hidden: int, vectors):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        f.write(MAGIC)
        f.write(struct.pack("<I", hidden))
        for v in vectors:
            f.write(struct.pack("<Q", len(v)))
            f.write(struct.pack(f"<{len(v)}f", *v))
    os.replace(tmp, path)

def average_checkpoints(paths, output: Path):
    parsed = [read_checkpoint(Path(p)) for p in paths]
    hidden = parsed[0][0]
    shapes = [len(v) for v in parsed[0][1]]
    for h, vecs in parsed[1:]:
        if h != hidden or [len(v) for v in vecs] != shapes:
            raise RuntimeError("worker checkpoints have different shapes")
    merged = []
    count = float(len(parsed))
    for vi in range(VECTOR_COUNT):
        n = shapes[vi]
        out = [0.0] * n
        for _, vecs in parsed:
            src = vecs[vi]
            for i in range(n):
                out[i] += src[i]
        for i in range(n):
            out[i] /= count
        merged.append(out)
    write_checkpoint(output, hidden, merged)

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
    paths = []
    for i, bucket in enumerate(buckets):
        p = out_dir / f"shard-{i}.txt"
        p.write_text("\n\n".join(bucket) + "\n", encoding="utf-8")
        paths.append(p)
    return paths

def run_worker(binary: Path, base_model: Path, shard: Path, worker_model: Path,
               epochs: int, seq_len: int, lr: float, worker_id: int):
    shutil.copy2(base_model, worker_model)
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    print(f"[worker {worker_id}] train {shard.name}")
    subprocess.check_call([
        str(binary), "text-train", str(worker_model), str(shard),
        str(epochs), str(seq_len), str(lr)
    ], env=env)
    return worker_model

def rotate_backups(model: Path, keep: int):
    backups = sorted(model.parent.glob(model.stem + ".backup-*.bin"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    for p in backups[max(0, keep):]:
        p.unlink(missing_ok=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="models/text.bin")
    ap.add_argument("--corpus", default="data/corpus.txt")
    ap.add_argument("--bin", default="build/reai")
    ap.add_argument("--workers", type=int, default=min(2, os.cpu_count() or 1))
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--seq-len", type=int, default=64)
    ap.add_argument("--lr", type=float, default=0.0005)
    ap.add_argument("--hidden", type=int, default=128)
    ap.add_argument("--keep-backups", type=int, default=3)
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    model = (root / args.model).resolve()
    corpus = (root / args.corpus).resolve()
    binary = (root / args.bin).resolve()
    workers = max(1, args.workers)

    model.parent.mkdir(parents=True, exist_ok=True)
    if not model.exists():
        subprocess.check_call([str(binary), "text-init", str(model), str(args.hidden)])

    stamp = int(time.time())
    backup = model.with_name(f"{model.stem}.backup-{stamp}.bin")
    shutil.copy2(model, backup)

    with tempfile.TemporaryDirectory(prefix="reai-train-") as td:
        work = Path(td)
        shards = split_corpus(corpus, work, workers)
        active = [(i, s) for i, s in enumerate(shards) if s.stat().st_size > args.seq_len + 2]
        if not active:
            raise RuntimeError("all shards are too small; add more training data or reduce workers")

        with ThreadPoolExecutor(max_workers=len(active)) as pool:
            futures = []
            worker_models = []
            for i, shard in active:
                wm = work / f"worker-{i}.bin"
                worker_models.append(wm)
                futures.append(pool.submit(
                    run_worker, binary, model, shard, wm,
                    args.epochs, args.seq_len, args.lr, i
                ))
            for f in futures:
                f.result()

        candidate = work / "merged.bin"
        average_checkpoints(worker_models, candidate)
        os.replace(candidate, model)

    rotate_backups(model, args.keep_backups)
    print(f"[parallel] promoted {model} from {len(active)} workers; backup={backup}")

if __name__ == "__main__":
    main()

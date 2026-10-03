#!/usr/bin/env bash
set -euo pipefail

sudo apt-get update
sudo apt-get install -y build-essential cmake python3

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"

mkdir -p models outputs data/web
if [[ ! -f models/text.bin ]]; then
  ./build/reai text-init models/text.bin 128
fi
if [[ ! -f models/image.bin ]]; then
  ./build/reai image-init models/image.bin 32 256
fi

echo "Ready. Run: python3 api/server.py"

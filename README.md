# ReVerfyx AI

A small **from-scratch generative AI research core** designed to start on a CPU VPS and grow without depending on pretrained Llama, Qwen, DeepSeek, Stable Diffusion, or similar weights.

## From scratch

- Random initial weights generated locally.
- No HuggingFace model downloads.
- No PyTorch, TensorFlow, or Transformers runtime.
- Byte-level text model and backpropagation are implemented in C++20.
- Prompt-conditioned image denoiser and backpropagation are implemented in C++20.
- Project-specific binary checkpoint formats.
- Web crawler, corpus builder, self-learning loop, and API use the Python standard library.

v0.1 is deliberately small enough to run on a CPU VPS. It is a trainable foundation, not yet comparable in quality to large frontier models.

## Install on Ubuntu

```bash
git clone https://github.com/ReVerfyx/Ai.git
cd Ai
chmod +x install.sh
./install.sh
```

## Text model

Create random weights:

```bash
./build/reai text-init models/text.bin 128
```

Train:

```bash
./build/reai text-train models/text.bin data/corpus.txt 5 64 0.001
```

Generate:

```bash
./build/reai text-generate models/text.bin "user: Привет
assistant:" 300 0.85 40
```

The v0.1 text core is a byte-level recurrent network with manually implemented BPTT and Adam. It was chosen first because it can genuinely train on a CPU VPS. A native Transformer core is planned next.

## Image generation

This is **not Stable Diffusion**. The image model starts from random weights and learns from your own image-caption pairs.

Training images currently use PPM P6/P3. A manifest line is:

```text
images/red_square.ppm	a red square
```

Create, train, generate:

```bash
./build/reai image-init models/image.bin 32 256
./build/reai image-train models/image.bin data/images.tsv 20 0.0005
./build/reai image-generate models/image.bin "a red sunset over mountains" outputs/test.ppm 32
```

v0.1 generates 32x32 PPM images so the entire training and inference path can remain small and independently implemented.

## Learn from the internet

The crawler respects robots.txt, identifies itself, rate-limits requests, extracts visible text, and stores source URLs.

```bash
python3 tools/crawl.py https://example.org --same-host --pages 30 --out data/web
python3 tools/build_corpus.py data/web --out data/corpus.txt
./build/reai text-train models/text.bin data/corpus.txt 1 64 0.0005
```

Automated cycle:

```bash
python3 tools/self_learn.py --seed https://example.org --pages 30
```

It trains a candidate checkpoint and keeps a backup before promotion. A held-out quality gate is planned before unattended long-term training.

## API

Start:

```bash
python3 api/server.py
```

Health:

```bash
curl http://127.0.0.1:8080/health
```

Chat:

```bash
curl -s http://127.0.0.1:8080/v1/chat/completions   -H 'Content-Type: application/json'   -d '{"messages":[{"role":"user","content":"Привет"}],"max_tokens":100}'
```

Image generation:

```bash
curl -s http://127.0.0.1:8080/v1/images/generations   -H 'Content-Type: application/json'   -d '{"prompt":"red sunset over mountains","steps":32}'
```

## Disk budget for a ~50 GB free VPS

Keep training data sharded and rotate old checkpoints. A reasonable first target is 10-20 GB of text/code data, 10-15 GB of image data, up to 5 GB of checkpoints/backups, and at least 8-10 GB kept free for builds, temporary data, and the OS.

## Roadmap

- Native causal Transformer with multi-head attention and RoPE.
- Held-out evaluation gate before automatic checkpoint promotion.
- Code-project ingestion and code-specific training shards.
- 64/128 px convolutional-attention image generator.
- Image-understanding encoder.
- Video frame + temporal model.
- Quantized inference.
- Optional project-owned CUDA backend.

## License

The repository's existing LICENSE is preserved unchanged.

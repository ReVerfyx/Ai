# ReVerfyx AI — 0.0.2

From-scratch generative AI research project. The model weights start locally from
random numbers; the project does not load pretrained Llama/Qwen/DeepSeek/Stable
Diffusion weights.

## 0.0.2 architecture

```text
Android
   |
   v
31.77.14.194:8090
Application Gateway
- users / login
- SQLite database
- chat history
- files
- generated media
- central restrictions
   |
   v
2.26.85.86:8080
AI Core
- text model
- image generator
- independent trainers
```

The Android APK contains only the gateway address. It does not contain the AI
server address or the AI-server API key.

## What is implemented

- C++20 text model with locally generated random weights.
- Manual forward/backward training and Adam optimizer.
- Prompt-conditioned from-scratch image denoiser.
- Chat and image-generation API.
- Internet crawler and corpus builder.
- Continuous learning for any chosen number of cycles/hours.
- Two or more independent CPU workers.
- Per-worker web data, corpus and checkpoint.
- Atomic worker checkpoint replacement during training.
- Central machine-readable restriction policy.
- Separate application gateway with account registration/login.
- PBKDF2 password hashing and expiring bearer sessions.
- SQLite chat/message/user database.
- Chat create/list/history/rename/delete.
- Text/code file attachment and analysis.
- Image generation proxied through the gateway.
- Android client with ChatGPT-inspired chat layout, drawer/history/search,
  new chats, files, image generation, copy, voice-to-text and account UI.

## Important worker behavior

`worker-0` and `worker-1` are independent.

```text
worker-0 web -> worker-0 corpus -> worker-0.bin
worker-1 web -> worker-1 corpus -> worker-1.bin
```

There is **no automatic weight averaging, merging or cross-training**.

The default production API serves `models/workers/worker-0.bin`. Worker-1 is
an independent alternative/research branch.

## Install AI server — 2.26.85.86

```bash
sudo apt update
sudo apt install -y git
sudo mkdir -p /opt/reai
sudo chown "$USER":"$USER" /opt/reai
git clone https://github.com/ReVerfyx/Ai.git /opt/reai
cd /opt/reai
bash deploy/install-ai-server.sh
```

Get the generated backend key:

```bash
sudo grep '^REAI_API_KEY=' /etc/reai-ai.env
```

Check:

```bash
sudo systemctl status reai --no-pager
curl http://127.0.0.1:8080/health
```

If UFW is already in use, expose the AI API only to the gateway:

```bash
sudo ufw allow from 31.77.14.194 to any port 8080 proto tcp
```

## Install gateway/user server — 31.77.14.194

Copy the API key printed on the AI server, then:

```bash
sudo apt update
sudo apt install -y git
sudo mkdir -p /opt/reai
sudo chown "$USER":"$USER" /opt/reai
git clone https://github.com/ReVerfyx/Ai.git /opt/reai
cd /opt/reai
REAI_AI_KEY='PASTE_AI_SERVER_KEY_HERE' bash deploy/install-gateway-server.sh
```

Check:

```bash
sudo systemctl status reai-gateway --no-pager
curl http://127.0.0.1:8090/health
```

The Android app uses:

```text
http://31.77.14.194:8090
```

For public deployment, put HTTPS in front of the gateway before using real
passwords outside testing.

## Train for as long as you want

Example: two independent CPU workers, indefinitely:

```bash
cd /opt/reai
python3 tools/self_learn.py \
  --workers 2 \
  --cycles 0 \
  --pages 40 \
  --epochs 1 \
  --seed https://ru.wikipedia.org/wiki/Заглавная_страница \
  --seed https://en.wikipedia.org/wiki/Main_Page
```

Train for 12 hours instead:

```bash
python3 tools/self_learn.py \
  --workers 2 \
  --cycles 0 \
  --hours 12 \
  --pages 40 \
  --epochs 1 \
  --seed https://ru.wikipedia.org/wiki/Заглавная_страница \
  --seed https://en.wikipedia.org/wiki/Main_Page
```

Use more workers only if the VPS actually has more CPU capacity.

## Restriction list

Machine-readable rules:

```text
policy/restrictions.json
```

Runtime checker:

```text
policy/engine.py
```

The same policy is checked at the gateway, at the AI API, and while building
training corpora. The list is deliberately separate from model weights.

## Android

Project:

```text
android/
```

Build with JDK 17 + Gradle 9.6:

```bash
cd android
gradle assembleDebug
```

APK:

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

GitHub Actions also builds a debug APK artifact.

Android Gradle Plugin is pinned to 9.4.0.

## Current model limitations

0.0.2 is a real trainable foundation, but it is intentionally tiny enough for a
small CPU VPS. It is not yet comparable to frontier models.

Current native core:
- text generation/training: yes;
- image generation/training: yes;
- code/text-file analysis: yes, by putting file text into model context;
- image understanding: not yet;
- video understanding: not yet;
- native speech model: not yet (Android client uses Android speech recognition).

## License

The repository's original MIT `LICENSE` is preserved unchanged.

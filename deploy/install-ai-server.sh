#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATEWAY_IP="${GATEWAY_IP:-31.77.14.194}"

sudo apt-get update
sudo apt-get install -y build-essential cmake python3

cmake -S "$ROOT" -B "$ROOT/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$ROOT/build" -j"$(nproc)"
mkdir -p "$ROOT/models" "$ROOT/outputs" "$ROOT/data/web" "$ROOT/data/worker-corpus"

[[ -f "$ROOT/models/text.bin" ]] || "$ROOT/build/reai" text-init "$ROOT/models/text.bin" 128
[[ -f "$ROOT/models/image.bin" ]] || "$ROOT/build/reai" image-init "$ROOT/models/image.bin" 32 256
mkdir -p "$ROOT/models/workers"
[[ -f "$ROOT/models/workers/worker-0.bin" ]] || cp "$ROOT/models/text.bin" "$ROOT/models/workers/worker-0.bin"
[[ -f "$ROOT/models/workers/worker-1.bin" ]] || cp "$ROOT/models/text.bin" "$ROOT/models/workers/worker-1.bin"

if [[ ! -f /etc/reai-ai.env ]]; then
  KEY="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(36))
PY
)"
  sudo tee /etc/reai-ai.env >/dev/null <<EOF
REAI_HOST=0.0.0.0
REAI_PORT=8080
REAI_API_KEY=$KEY
REAI_TEXT_MODEL=$ROOT/models/workers/worker-0.bin
REAI_IMAGE_MODEL=$ROOT/models/image.bin
REAI_API_KEYS_FILE=/etc/reai-api-keys.json
REAI_TRUSTED_GATEWAY_IP=31.77.14.194
EOF
  sudo chmod 600 /etc/reai-ai.env
fi

if ! sudo grep -q '^REAI_API_KEYS_FILE=' /etc/reai-ai.env; then
  echo 'REAI_API_KEYS_FILE=/etc/reai-api-keys.json' | sudo tee -a /etc/reai-ai.env >/dev/null
fi
if ! sudo grep -q '^REAI_TRUSTED_GATEWAY_IP=' /etc/reai-ai.env; then
  echo 'REAI_TRUSTED_GATEWAY_IP=31.77.14.194' | sudo tee -a /etc/reai-ai.env >/dev/null
fi

if [[ ! -f /etc/reai-api-keys.json ]]; then
  echo '{"keys":[]}' | sudo tee /etc/reai-api-keys.json >/dev/null
  sudo chmod 600 /etc/reai-api-keys.json
fi

sudo tee /etc/systemd/system/reai.service >/dev/null <<EOF
[Unit]
Description=ReVerfyx AI 0.0.3 core API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(id -un)
WorkingDirectory=$ROOT
EnvironmentFile=/etc/reai-ai.env
ExecStart=/usr/bin/python3 $ROOT/api/server.py
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now reai

echo
echo "AI core installed."
echo "Status: sudo systemctl status reai --no-pager"
echo "API key: sudo grep '^REAI_API_KEY=' /etc/reai-ai.env"
echo
echo "Recommended firewall rule (run only if UFW is already configured):"
echo "sudo ufw allow from $GATEWAY_IP to any port 8080 proto tcp"

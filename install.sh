#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENABLE_SERVICE=0
TRAINER_SEED=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --service) ENABLE_SERVICE=1; shift ;;
    --trainer)
      TRAINER_SEED="${2:-}"
      if [[ -z "$TRAINER_SEED" ]]; then echo "--trainer needs a seed URL"; exit 2; fi
      shift 2
      ;;
    *) echo "Unknown option: $1"; exit 2 ;;
  esac
done

sudo apt-get update
sudo apt-get install -y build-essential cmake python3

cmake -S "$ROOT" -B "$ROOT/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$ROOT/build" -j"$(nproc)"

mkdir -p "$ROOT/models" "$ROOT/outputs" "$ROOT/data/web"
if [[ ! -f "$ROOT/models/text.bin" ]]; then
  "$ROOT/build/reai" text-init "$ROOT/models/text.bin" 128
fi
if [[ ! -f "$ROOT/models/image.bin" ]]; then
  "$ROOT/build/reai" image-init "$ROOT/models/image.bin" 32 256
fi

if [[ "$ENABLE_SERVICE" == "1" ]]; then
  if [[ ! -f /etc/reai.env ]]; then
    KEY="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)"
    sudo bash -c "cat > /etc/reai.env" <<EOF
REAI_HOST=0.0.0.0
REAI_PORT=8080
REAI_API_KEY=$KEY
EOF
    sudo chmod 600 /etc/reai.env
  fi

  sudo tee /etc/systemd/system/reai.service >/dev/null <<EOF
[Unit]
Description=ReVerfyx AI 0.0.2 API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(id -un)
WorkingDirectory=$ROOT
EnvironmentFile=/etc/reai.env
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
fi

if [[ -n "$TRAINER_SEED" ]]; then
  sudo bash -c "cat > /etc/reai-trainer.env" <<EOF
REAI_TRAIN_ARGS="--workers 2 --cycles 0 --seed $TRAINER_SEED --pages 40 --epochs 1"
EOF
  sudo chmod 600 /etc/reai-trainer.env

  sudo tee /etc/systemd/system/reai-trainer.service >/dev/null <<EOF
[Unit]
Description=ReVerfyx AI 0.0.2 continuous trainer
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(id -un)
WorkingDirectory=$ROOT
EnvironmentFile=/etc/reai-trainer.env
ExecStart=/bin/bash -lc 'exec /usr/bin/python3 "$ROOT/tools/self_learn.py" $REAI_TRAIN_ARGS'
Restart=on-failure
RestartSec=10
Nice=5

[Install]
WantedBy=multi-user.target
EOF

  sudo systemctl daemon-reload
  sudo systemctl enable --now reai-trainer
fi

echo
echo "ReVerfyx AI 0.0.2 ready in $ROOT"
echo "API: python3 api/server.py"
if [[ "$ENABLE_SERVICE" == "1" ]]; then
  echo "API service: systemctl status reai"
  echo "API key: sudo grep REAI_API_KEY /etc/reai.env"
fi
if [[ -n "$TRAINER_SEED" ]]; then
  echo "Trainer: systemctl status reai-trainer"
fi

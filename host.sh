#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/ReVerfyx/Ai.git"
ROOT="/opt/reai"
CMD="${1:-help}"
shift || true

say(){ printf "\n== %s ==\n" "$*"; }

need_repo() {
  sudo apt-get update -y
  sudo apt-get install -y git
  if [[ -d "$ROOT/.git" ]]; then
    sudo chown -R "$(id -un)":"$(id -gn)" "$ROOT"
    git -C "$ROOT" fetch origin main
    git -C "$ROOT" checkout main
    git -C "$ROOT" pull --ff-only origin main
  else
    sudo mkdir -p "$ROOT"
    sudo chown "$(id -un)":"$(id -gn)" "$ROOT"
    git clone "$REPO_URL" "$ROOT"
  fi
}

case "$CMD" in
  ai)
    need_repo
    cd "$ROOT"
    bash deploy/install-ai-server.sh
    echo
    echo "AI READY"
    sudo grep '^REAI_API_KEY=' /etc/reai-ai.env || true
    ;;
  gateway)
    need_repo
    cd "$ROOT"
    KEY="${1:-}"
    if [[ -z "$KEY" ]]; then
      read -rsp "REAI_API_KEY from AI server: " KEY
      echo
    fi
    [[ -n "$KEY" ]] || { echo "AI key required"; exit 2; }
    REAI_AI_KEY="$KEY" bash deploy/install-gateway-server.sh
    echo "GATEWAY READY: http://31.77.14.194:8090"
    ;;
  train)
    need_repo
    cd "$ROOT"
    SEED1="${1:-https://ru.wikipedia.org/wiki/Заглавная_страница}"
    SEED2="${2:-https://en.wikipedia.org/wiki/Main_Page}"
    sudo tee /etc/reai-trainer.env >/dev/null <<EOF
REAI_TRAIN_ARGS=--workers 2 --cycles 0 --pages 40 --epochs 1 --max-data-gb 20 --same-host --seed $SEED1 --seed $SEED2
EOF
    sudo chmod 600 /etc/reai-trainer.env
    sudo tee /etc/systemd/system/reai-trainer.service >/dev/null <<EOF
[Unit]
Description=ReVerfyx AI independent continuous trainers
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
    echo "TRAINING STARTED: 2 independent workers"
    ;;
  stop-train)
    sudo systemctl disable --now reai-trainer 2>/dev/null || true
    echo "TRAINING STOPPED"
    ;;
  update)
    need_repo
    cd "$ROOT"
    if systemctl list-unit-files 2>/dev/null | grep -q '^reai.service'; then
      sudo apt-get install -y build-essential cmake python3
      cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
      cmake --build build -j"$(nproc)"
      sudo systemctl restart reai
    fi
    if systemctl list-unit-files 2>/dev/null | grep -q '^reai-gateway.service'; then
      sudo systemctl restart reai-gateway
    fi
    if systemctl list-unit-files 2>/dev/null | grep -q '^reai-trainer.service'; then
      sudo systemctl restart reai-trainer
    fi
    echo "UPDATED"
    ;;
  status)
    echo "--- AI ---"
    systemctl --no-pager --full status reai 2>/dev/null || true
    echo "--- GATEWAY ---"
    systemctl --no-pager --full status reai-gateway 2>/dev/null || true
    echo "--- TRAINER ---"
    systemctl --no-pager --full status reai-trainer 2>/dev/null || true
    ;;
  logs)
    TARGET="${1:-ai}"
    case "$TARGET" in
      ai) UNIT=reai ;;
      gateway) UNIT=reai-gateway ;;
      train|trainer) UNIT=reai-trainer ;;
      *) echo "logs: ai | gateway | train"; exit 2 ;;
    esac
    sudo journalctl -u "$UNIT" -f -n 80
    ;;
  key)
    sudo grep '^REAI_API_KEY=' /etc/reai-ai.env
    ;;
  help|*)
    cat <<'EOF'
ReVerfyx AI host helper

AI server:
  bash host.sh ai

Gateway/user server:
  bash host.sh gateway AI_KEY

Continuous independent training:
  bash host.sh train

Other:
  bash host.sh stop-train
  bash host.sh update
  bash host.sh status
  bash host.sh logs ai
  bash host.sh logs gateway
  bash host.sh logs train
  bash host.sh key
EOF
    ;;
esac

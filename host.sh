#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/ReVerfyx/Ai.git"
ROOT="/opt/reai"
CMD="${1:-help}"
shift || true

require_local() {
  [[ -d "$ROOT" && -f "$ROOT/tools/self_learn.py" ]] || {
    echo "ReVerfyx AI is not installed in $ROOT"
    echo "Run: bash host.sh ai"
    exit 2
  }
}

ensure_repo() {
  sudo apt-get update -y
  sudo apt-get install -y git
  if [[ ! -d "$ROOT/.git" ]]; then
    sudo mkdir -p "$ROOT"
    sudo chown "$(id -un)":"$(id -gn)" "$ROOT"
    git clone "$REPO_URL" "$ROOT"
  else
    sudo chown -R "$(id -un)":"$(id -gn)" "$ROOT"
  fi
}

update_repo() {
  require_local
  local ok=0
  for n in 1 2 3 4 5; do
    echo "Git update attempt $n/5..."
    if git -C "$ROOT" fetch origin main &&        git -C "$ROOT" checkout main &&        git -C "$ROOT" pull --ff-only origin main; then
      ok=1
      break
    fi
    sleep $((n * 2))
  done
  if [[ "$ok" != "1" ]]; then
    echo "GitHub is temporarily unreachable. Existing local version was NOT damaged."
    exit 3
  fi
}

case "$CMD" in
  ai)
    ensure_repo
    cd "$ROOT"
    bash deploy/install-ai-server.sh
    echo
    echo "AI READY"
    sudo grep '^REAI_API_KEY=' /etc/reai-ai.env || true
    ;;

  gateway)
    ensure_repo
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
    require_local
    cd "$ROOT"
    SEED1="${1:-https://ru.wikipedia.org/wiki/Заглавная_страница}"
    SEED2="${2:-https://en.wikipedia.org/wiki/Main_Page}"

    sudo tee /etc/reai-trainer.env >/dev/null <<EOF
REAI_TRAIN_ARGS="--workers 2 --cycles 0 --pages 40 --epochs 1 --max-data-gb 0 --same-host --seed $SEED1 --seed $SEED2"
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
ExecStart=/bin/bash -lc 'exec /usr/bin/python3 "$ROOT/tools/self_learn.py" \$REAI_TRAIN_ARGS'
Restart=on-failure
RestartSec=10
Nice=5

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable --now reai-trainer
    echo "TRAINING STARTED: 2 independent workers"
    echo "Logs: bash host.sh logs train"
    ;;

  bootstrap|learn|research)
    require_local
    cd "$ROOT"
    sudo systemctl disable --now reai-trainer 2>/dev/null || true
    sudo systemctl disable --now reai-learning 2>/dev/null || true

    case "$CMD" in
      bootstrap)
        LEARN_ARGS="--workers 2 --bootstrap-only --bootstrap-pages 8 --epochs 1 --max-data-gb 0"
        ;;
      research)
        LEARN_ARGS="--workers 1 --skip-bootstrap --epochs 1 --sleep 10 --train-every 1 --max-data-gb 0"
        ;;
      learn)
        LEARN_ARGS="--workers 1 --bootstrap-pages 12 --epochs 1 --sleep 10 --train-every 1 --max-data-gb 0"
        ;;
    esac

    sudo tee /etc/reai-learning.env >/dev/null <<EOF
REAI_LEARN_ARGS="$LEARN_ARGS"
EOF
    sudo chmod 600 /etc/reai-learning.env

    sudo tee /etc/systemd/system/reai-learning.service >/dev/null <<EOF
[Unit]
Description=ReVerfyx AI staged autonomous learning
After=network-online.target reai.service
Wants=network-online.target

[Service]
Type=simple
User=$(id -un)
WorkingDirectory=$ROOT
EnvironmentFile=/etc/reai-learning.env
ExecStart=/bin/bash -lc 'exec /usr/bin/python3 "$ROOT/tools/auto_research.py" \$REAI_LEARN_ARGS'
Restart=on-failure
RestartSec=20
Nice=5

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable --now reai-learning
    if [[ "$CMD" == "learn" ]]; then
      sudo python3 "$ROOT/tools/manage.py" improve-auto || true
    fi
    echo "LEARNING STARTED: $CMD"
    echo "Progress: bash host.sh progress"
    echo "Logs: bash host.sh logs learn"
    ;;

  upgrade50m|upgrade5m|upgrade800k|key-new|keys|chat|image|observe|improve|improve-auto|improve-once|improve-log)
    require_local
    python3 "$ROOT/tools/manage.py" "$CMD" "$@"
    ;;

  stop-train)
    sudo systemctl disable --now reai-trainer 2>/dev/null || true
    echo "TRAINING STOPPED"
    ;;

  stop-learn)
    sudo systemctl disable --now reai-learning 2>/dev/null || true
    echo "AUTONOMOUS LEARNING STOPPED"
    ;;

  progress)
    require_local
    python3 "$ROOT/tools/progress.py"
    ;;

  update)
    update_repo
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
    if systemctl list-unit-files 2>/dev/null | grep -q '^reai-learning.service'; then
      sudo systemctl restart reai-learning
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
    echo "--- LEARNING ---"
    systemctl --no-pager --full status reai-learning 2>/dev/null || true
    ;;

  logs)
    TARGET="${1:-ai}"
    case "$TARGET" in
      ai) UNIT=reai ;;
      gateway) UNIT=reai-gateway ;;
      train|trainer) UNIT=reai-trainer ;;
      learn|learning|research) UNIT=reai-learning ;;
      *) echo "logs: ai | gateway | train | learn"; exit 2 ;;
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

Wikipedia bootstrap only:
  bash host.sh bootstrap

Wikipedia first, then autonomous read-only research:
  bash host.sh learn

Start research stage only:
  bash host.sh research

Legacy continuous Wikipedia training:
  bash host.sh train

Check real learning progress:
  bash host.sh progress

Model profiles / API / observer:
  bash host.sh upgrade800k
  bash host.sh upgrade5m
  bash host.sh upgrade50m
  bash host.sh key-new phone
  bash host.sh keys
  bash host.sh chat "Привет"
  bash host.sh image "ночные горы"
  bash host.sh observe
  bash host.sh improve
  bash host.sh improve-auto
  bash host.sh improve-log

Other:
  bash host.sh stop-train
  bash host.sh stop-learn
  bash host.sh update
  bash host.sh status
  bash host.sh logs ai
  bash host.sh logs gateway
  bash host.sh logs train
  bash host.sh logs learn
  bash host.sh key
EOF
    ;;
esac

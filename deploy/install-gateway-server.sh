#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AI_BASE="${AI_BASE:-http://2.26.85.86:8080}"
AI_KEY="${REAI_AI_KEY:-${1:-}}"

if [[ -z "$AI_KEY" ]]; then
  echo "Usage: REAI_AI_KEY='<key from AI server>' bash deploy/install-gateway-server.sh"
  exit 2
fi

sudo apt-get update
sudo apt-get install -y python3
mkdir -p "$ROOT/data/gateway-files" "$ROOT/data/gateway-media"

sudo tee /etc/reai-gateway.env >/dev/null <<EOF
REAI_GATEWAY_HOST=0.0.0.0
REAI_GATEWAY_PORT=8090
REAI_AI_BASE=$AI_BASE
REAI_AI_KEY=$AI_KEY
REAI_GATEWAY_DB=$ROOT/data/gateway.sqlite3
REAI_GATEWAY_FILES=$ROOT/data/gateway-files
REAI_GATEWAY_MEDIA=$ROOT/data/gateway-media
REAI_MAX_UPLOAD_BYTES=12582912
REAI_SESSION_DAYS=30
EOF
sudo chmod 600 /etc/reai-gateway.env

sudo tee /etc/systemd/system/reai-gateway.service >/dev/null <<EOF
[Unit]
Description=ReVerfyx AI 0.0.2 application gateway
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(id -un)
WorkingDirectory=$ROOT
EnvironmentFile=/etc/reai-gateway.env
ExecStart=/usr/bin/python3 $ROOT/gateway/server.py
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now reai-gateway

echo
echo "Gateway installed on port 8090."
echo "Status: sudo systemctl status reai-gateway --no-pager"
echo "Health: curl http://127.0.0.1:8090/health"

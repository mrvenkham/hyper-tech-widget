#!/usr/bin/env bash
# One-command launcher for your OWN machine (PC or VPS).
# Starts the bot and a public Cloudflare tunnel, then prints the webhook URL
# to paste into TradingView. Ctrl-C stops both.
#
# This does NOT work from the throwaway cloud session that built the project —
# that sandbox blocks public tunnels. Run it where the bot should actually live.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"

# 1. Python deps.
if [ ! -d .venv ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip >/dev/null
  ./.venv/bin/pip install -r requirements.txt
fi

# 2. Secrets.
if [ ! -f .env ]; then
  echo "No .env found. Copy .env.example to .env and set WEBHOOK_SECRET and DASHBOARD_TOKEN first." >&2
  exit 1
fi

# 3. cloudflared (download a local copy if absent).
CF="$(command -v cloudflared || true)"
if [ -z "$CF" ]; then
  echo "Downloading cloudflared..."
  OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
  ARCH="$(uname -m)"; case "$ARCH" in x86_64) ARCH=amd64;; aarch64|arm64) ARCH=arm64;; esac
  curl -sSL -o ./cloudflared "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-${OS}-${ARCH}"
  chmod +x ./cloudflared
  CF="./cloudflared"
fi

cleanup() { kill "${BOT_PID:-}" "${CF_PID:-}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

# 4. Start the bot.
./.venv/bin/python -m bot.main >bot.log 2>&1 &
BOT_PID=$!
sleep 3

# 5. Start the tunnel and extract the public URL.
"$CF" tunnel --url "http://localhost:${PORT}" --no-autoupdate >cf.log 2>&1 &
CF_PID=$!

echo "Waiting for the public URL..."
URL=""
for _ in $(seq 1 30); do
  URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' cf.log | head -1 || true)"
  [ -n "$URL" ] && break
  sleep 1
done

TOKEN="$(grep -E '^DASHBOARD_TOKEN=' .env | cut -d= -f2-)"
echo
echo "============================================================"
if [ -n "$URL" ]; then
  echo "  Bot is live."
  echo "  TradingView webhook URL:  ${URL}/webhook"
  echo "  Dashboard (phone or PC):  ${URL}/?token=${TOKEN}"
else
  echo "  Tunnel URL not found yet. Check cf.log."
  echo "  Local dashboard: http://localhost:${PORT}/?token=${TOKEN}"
fi
echo "  Press Ctrl-C to stop."
echo "============================================================"

wait "$BOT_PID"

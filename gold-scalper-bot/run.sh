#!/usr/bin/env bash
# Convenience launcher. Creates a venv on first run, then starts the bot.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip
  ./.venv/bin/pip install -r requirements.txt
fi

if [ ! -f .env ]; then
  echo "No .env found. Copy .env.example to .env and set your secrets first." >&2
  exit 1
fi

exec ./.venv/bin/python -m bot.main

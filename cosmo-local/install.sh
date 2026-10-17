#!/data/data/com.termux/files/usr/bin/bash
# COSMO Local installer for Termux (Android).
# Installs Ollama, Python and Termux:API tools, downloads COSMO (server + JARVIS page),
# picks a phone model that fits the RAM, adds the `cosmo` command, a boot script
# and home-screen shortcuts. Safe to run again: it keeps your data and settings.
#
#   curl -fsSLo install.sh https://raw.githubusercontent.com/mrvenkham/hyper-tech-widget/claude/hydeck-dashboard-frontend-pvipz2/cosmo-local/install.sh
#   bash install.sh
#
# Pass a model to override the automatic pick:  bash install.sh llama3.2:3b
set -e

BASE="https://raw.githubusercontent.com/mrvenkham/hyper-tech-widget/claude/hydeck-dashboard-frontend-pvipz2/cosmo-local"
DIR="$HOME/cosmo"

say() { printf '\033[1;36m[COSMO]\033[0m %s\n' "$*"; }

if [ -z "$PREFIX" ] || [ ! -d "/data/data/com.termux" ]; then
  echo "This installer runs inside Termux on Android. Install Termux from F-Droid first."
  exit 1
fi

say "Updating packages (answer Y if asked)…"
pkg update -y && pkg upgrade -y -o Dpkg::Options::="--force-confnew"

say "Installing Ollama, Python and the phone-control tools…"
if ! pkg install -y ollama python termux-api; then
  say "Ollama not in the main repo on this device. Adding the TUR repo and retrying…"
  pkg install -y tur-repo
  pkg install -y ollama python termux-api
fi

say "Downloading COSMO to $DIR…"
mkdir -p "$DIR/data"
for f in index.html server.py talk.py start.sh countries.json; do
  curl -fsSL "$BASE/$f" -o "$DIR/$f"
done
chmod +x "$DIR/start.sh" "$DIR/server.py" "$DIR/talk.py"

# Pick a phone model by RAM unless one was passed in.
MODEL="$1"
if [ -z "$MODEL" ]; then
  RAM_GB=$(awk '/MemTotal/ { printf "%d", $2 / 1024 / 1024 + 0.5 }' /proc/meminfo)
  if   [ "$RAM_GB" -lt 5 ]; then MODEL="gemma3:1b"
  elif [ "$RAM_GB" -lt 7 ]; then MODEL="llama3.2:3b"
  else                           MODEL="gemma3:4b"
  fi
  say "This phone has about ${RAM_GB} GB of RAM → phone model $MODEL"
fi

# Keep an existing config (laptop address, Gumroad token); only set the phone model.
python - "$DIR/config.json" "$MODEL" <<'PY'
import json, os, sys
path, model = sys.argv[1:]
cfg = json.load(open(path)) if os.path.exists(path) else {}
engines = cfg.setdefault("engines", [{"name": "Laptop", "url": "", "model": "qwen2.5:7b"},
                                     {"name": "Phone", "url": "http://127.0.0.1:11434", "model": "auto"}])
for e in engines:
    if e["name"] == "Phone":
        e["model"] = model
json.dump(cfg, open(path, "w"), indent=1)
PY

if ! ollama list 2>/dev/null | grep -q "^$MODEL"; then
  say "Downloading the phone model (1–3 GB, once)…"
  ollama serve > "$DIR/ollama.log" 2>&1 &
  OLLAMA_PID=$!
  for i in $(seq 1 30); do curl -fs http://127.0.0.1:11434/api/tags > /dev/null 2>&1 && break; sleep 1; done
  ollama pull "$MODEL"
  kill "$OLLAMA_PID" 2>/dev/null || true
fi

ln -sf "$DIR/start.sh" "$PREFIX/bin/cosmo"

# Start at boot (needs the Termux:Boot app, opened once).
mkdir -p "$HOME/.termux/boot"
printf '#!/data/data/com.termux/files/usr/bin/sh\ntermux-wake-lock\n%s/bin/cosmo --no-open\n' "$PREFIX" > "$HOME/.termux/boot/start-cosmo"
chmod +x "$HOME/.termux/boot/start-cosmo"

# Home-screen buttons (needs the Termux:Widget app).
mkdir -p "$HOME/.shortcuts"
printf '#!/data/data/com.termux/files/usr/bin/sh\n%s/bin/cosmo\n' "$PREFIX" > "$HOME/.shortcuts/COSMO"
printf '#!/data/data/com.termux/files/usr/bin/sh\n%s/bin/cosmo --no-open\n%s/bin/cosmo talk\n' "$PREFIX" "$PREFIX" > "$HOME/.shortcuts/COSMO Talk"
chmod +x "$HOME/.shortcuts/"*

# Allow notifications/torch/etc. by asking Android once.
termux-notification --id cosmo --title "COSMO" --content "Notifications are working. I'll check in at 06:45, 16:30 and 21:30." 2>/dev/null || true

say "Done. Type:  cosmo"
say "Voice mode: cosmo talk   ·   Laptop brain: see laptop/setup-laptop.ps1"

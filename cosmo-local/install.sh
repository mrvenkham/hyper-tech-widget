#!/data/data/com.termux/files/usr/bin/bash
# COSMO Local installer for Termux (Android).
# Installs Ollama + Python, downloads the JARVIS console, picks a model that
# fits this phone's RAM, and adds a `cosmo` command that starts everything.
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

say "Installing Ollama and Python…"
if ! pkg install -y ollama python; then
  say "Ollama not in the main repo on this device. Adding the TUR repo and retrying…"
  pkg install -y tur-repo
  pkg install -y ollama python
fi

say "Downloading the JARVIS console to $DIR…"
mkdir -p "$DIR"
curl -fsSL "$BASE/index.html" -o "$DIR/index.html"
curl -fsSL "$BASE/start.sh"   -o "$DIR/start.sh"
chmod +x "$DIR/start.sh"

# Pick a model by RAM unless one was passed in.
MODEL="$1"
if [ -z "$MODEL" ]; then
  RAM_GB=$(awk '/MemTotal/ { printf "%d", $2 / 1024 / 1024 + 0.5 }' /proc/meminfo)
  if   [ "$RAM_GB" -lt 5 ]; then MODEL="gemma3:1b"
  elif [ "$RAM_GB" -lt 7 ]; then MODEL="llama3.2:3b"
  else                           MODEL="gemma3:4b"
  fi
  say "This phone has about ${RAM_GB} GB of RAM → using $MODEL"
fi
echo "$MODEL" > "$DIR/model.txt"

say "Starting Ollama to download the model (this is the big download, 1–3 GB)…"
ollama serve > "$DIR/ollama.log" 2>&1 &
OLLAMA_PID=$!
for i in $(seq 1 30); do
  curl -fs http://127.0.0.1:11434/api/tags > /dev/null 2>&1 && break
  sleep 1
done
ollama pull "$MODEL"
kill "$OLLAMA_PID" 2>/dev/null || true

# `cosmo` command
ln -sf "$DIR/start.sh" "$PREFIX/bin/cosmo"

say "Done. Type:  cosmo"
say "That starts the AI and opens JARVIS in your browser."

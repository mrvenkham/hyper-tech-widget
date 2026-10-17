#!/data/data/com.termux/files/usr/bin/bash
# The `cosmo` command.
#   cosmo                 start COSMO and open JARVIS
#   cosmo --no-open       start in the background (used at boot)
#   cosmo stop            stop everything
#   cosmo talk            hands-free voice conversation
#   cosmo laptop <ip>     use your laptop as COSMO's brain (cosmo laptop off to stop)
#   cosmo gumroad <token> connect Gumroad sales (cosmo gumroad off to remove)
#   cosmo city <name> <lat> <lon>   set the weather city
#   cosmo status          show what's running
#   cosmo update          download the newest COSMO files
#   cosmo logs            show the server log
DIR="$HOME/cosmo"
PORT=8080
BASE="https://raw.githubusercontent.com/mrvenkham/hyper-tech-widget/claude/hydeck-dashboard-frontend-pvipz2/cosmo-local"

say() { printf '\033[1;36m[COSMO]\033[0m %s\n' "$*"; }

# Edit config.json safely with Python (creates it if missing).
config() {
  python - "$DIR/config.json" "$@" <<'PY'
import json, sys, os
path, key, *vals = sys.argv[1:]
cfg = json.load(open(path)) if os.path.exists(path) else {}
cfg.setdefault("engines", [{"name": "Laptop", "url": "", "model": "qwen2.5:7b"},
                           {"name": "Phone", "url": "http://127.0.0.1:11434", "model": "auto"}])
if key == "laptop":
    v = vals[0]
    url = "" if v == "off" else (v if v.startswith("http") else f"http://{v}:11434")
    for e in cfg["engines"]:
        if e["name"] == "Laptop":
            e["url"] = url
            if len(vals) > 1: e["model"] = vals[1]
    print("Laptop brain " + ("removed" if not url else "set to " + url))
elif key == "gumroad":
    cfg["gumroad_token"] = "" if vals[0] == "off" else vals[0]
    print("Gumroad " + ("disconnected" if vals[0] == "off" else "connected"))
elif key == "city":
    cfg["city"] = {"name": vals[0], "lat": float(vals[1]), "lon": float(vals[2])}
    print(f"Weather city set to {vals[0]}")
json.dump(cfg, open(path, "w"), indent=1)
PY
}

stop_server() {
  pkill -f "$DIR/watchdog.sh" 2>/dev/null
  pkill -f "$DIR/server.py" 2>/dev/null
  pkill -f "http.server $PORT" 2>/dev/null   # the very first COSMO version used this; it blocks port 8080
}
restart_server() { stop_server; sleep 1; start_server; }
start_server() {
  # The first COSMO version served the page with python's http.server; it would
  # keep port 8080 busy and the new server could never start.
  pkill -f "http.server $PORT" 2>/dev/null
  if ! pgrep -f "$DIR/server.py" > /dev/null; then
    # Watchdog: if the server ever crashes, start it again after 3 s.
    cat > "$DIR/watchdog.sh" <<'WD'
DIR="$(cd "$(dirname "$0")" && pwd)"
while true; do
  python "$DIR/server.py" >> "$DIR/server.log" 2>&1
  echo "[server stopped, restarting $(date +%H:%M:%S)]" >> "$DIR/server.log"
  sleep 3
done
WD
    nohup bash "$DIR/watchdog.sh" > /dev/null 2>&1 &
    for i in $(seq 1 30); do curl -fs "http://127.0.0.1:$PORT/api/greet" > /dev/null 2>&1 && return 0; sleep 0.5; done
    say "The server didn't start. Last lines of the log:"
    tail -n 15 "$DIR/server.log"
    return 1
  fi
}

case "$1" in
  stop)
    stop_server
    pkill -f "ollama serve" 2>/dev/null
    termux-wake-unlock 2>/dev/null
    say "COSMO is offline."
    exit 0 ;;
  talk)
    exec python "$DIR/talk.py" ;;
  laptop)
    [ -z "$2" ] && { say "Usage: cosmo laptop 192.168.1.23   (or: cosmo laptop off)"; exit 1; }
    config laptop "${@:2}"; restart_server; exit 0 ;;
  gumroad)
    [ -z "$2" ] && { say "Usage: cosmo gumroad YOUR_ACCESS_TOKEN   (or: cosmo gumroad off)"; exit 1; }
    config gumroad "$2"; restart_server; exit 0 ;;
  city)
    [ -z "$4" ] && { say "Usage: cosmo city Jitra 6.268 100.421"; exit 1; }
    config city "$2" "$3" "$4"; restart_server; exit 0 ;;
  status)
    curl -fs "http://127.0.0.1:$PORT/api/status?refresh=1" | python -m json.tool 2>/dev/null || say "Server not running. Type: cosmo"
    exit 0 ;;
  logs)
    tail -n 40 "$DIR/server.log"; exit 0 ;;
  update)
    mkdir -p "$DIR/icons"; for f in index.html server.py talk.py start.sh countries.json manifest.webmanifest sw.js icons/icon-192.png icons/icon-512.png icons/icon-maskable-512.png; do curl -fsSL "$BASE/$f" -o "$DIR/$f.new" && mv "$DIR/$f.new" "$DIR/$f"; done
    chmod +x "$DIR/start.sh"
    pgrep -f "$DIR/server.py" > /dev/null && restart_server
    say "Updated. Reload the JARVIS page."
    exit 0 ;;
esac

termux-wake-lock 2>/dev/null   # keep Android from killing COSMO in the background
export OLLAMA_HOST="127.0.0.1:11434"

if ! curl -fs http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
  say "Starting the phone AI engine…"
  nohup ollama serve > "$DIR/ollama.log" 2>&1 &
  for i in $(seq 1 30); do curl -fs http://127.0.0.1:11434/api/tags > /dev/null 2>&1 && break; sleep 1; done
fi

say "Starting the COSMO server…"
start_server || exit 1

if [ "$1" != "--no-open" ]; then
  say "COSMO is online."
  # Open the COSMO Android app if it's installed; otherwise JARVIS in the browser.
  out=$(am start -n com.hypertechwidget.cosmo/.MainActivity 2>&1)
  if [ $? -ne 0 ] || echo "$out" | grep -qiE "error|does not exist|unable"; then
    termux-open-url "http://127.0.0.1:$PORT" 2>/dev/null || say "Open http://127.0.0.1:$PORT in Chrome."
  fi
fi

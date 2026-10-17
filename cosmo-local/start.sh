#!/data/data/com.termux/files/usr/bin/bash
# Starts COSMO Local: the Ollama engine + the JARVIS page, then opens the browser.
# Run it with:  cosmo        Stop everything with:  cosmo stop
DIR="$HOME/cosmo"
PORT=8080

say() { printf '\033[1;36m[COSMO]\033[0m %s\n' "$*"; }

if [ "$1" = "stop" ]; then
  pkill -f "ollama serve" 2>/dev/null
  pkill -f "http.server $PORT" 2>/dev/null
  termux-wake-unlock 2>/dev/null
  say "COSMO is offline. Engine and console stopped."
  exit 0
fi

# Keep Android from killing Termux while COSMO runs.
termux-wake-lock 2>/dev/null

# Let the page (served on :8080) talk to the engine (on :11434).
export OLLAMA_ORIGINS="http://127.0.0.1:$PORT,http://localhost:$PORT"
export OLLAMA_HOST="127.0.0.1:11434"

if ! curl -fs http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
  say "Starting the AI engine…"
  nohup ollama serve > "$DIR/ollama.log" 2>&1 &
  for i in $(seq 1 30); do
    curl -fs http://127.0.0.1:11434/api/tags > /dev/null 2>&1 && break
    sleep 1
  done
fi

if ! pgrep -f "http.server $PORT" > /dev/null; then
  say "Starting the JARVIS console…"
  cd "$DIR" && nohup python -m http.server "$PORT" --bind 127.0.0.1 > "$DIR/web.log" 2>&1 &
  sleep 1
fi

say "COSMO is online. Opening http://127.0.0.1:$PORT"
termux-open-url "http://127.0.0.1:$PORT" 2>/dev/null || say "Open http://127.0.0.1:$PORT in Chrome."
say "Leave Termux running in the background. Type 'cosmo stop' to shut down."

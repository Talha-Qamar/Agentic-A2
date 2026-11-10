#!/bin/bash
# Local experiment runner (used while GitHub Actions is unavailable on this account).
# Start once from the repo root:   bash ci/mac_runner.sh
# It keeps the Mac awake, pulls the latest code every cycle and runs each job script dropped into
# runs/queue/ exactly once, writing logs to runs/out/<job>/. Stop with Ctrl+C.
set -u
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
mkdir -p runs/queue runs/out runs/done

if [ -z "${GROQ_API_KEY:-}" ]; then
  printf "Paste your Groq API key (input hidden, kept only in this terminal session): "
  read -rs GROQ_API_KEY; echo
  export GROQ_API_KEY
fi

PY=""
for c in python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1; then
    v=$("$c" -c 'import sys;print(sys.version_info[0]*100+sys.version_info[1])')
    if [ "$v" -ge 311 ]; then PY="$c"; break; fi
  fi
done
if [ -z "$PY" ]; then echo "Need Python 3.11+ (brew install python@3.12)"; exit 1; fi
echo "Using $PY ($($PY --version))"

if [ ! -x .venv/bin/python ]; then
  "$PY" -m venv .venv
  .venv/bin/pip install -q --upgrade pip
fi
.venv/bin/pip install -q -r requirements-eval.txt
echo "Disk free: $(df -h . | tail -1 | awk '{print $4}')"
if command -v ollama >/dev/null 2>&1; then echo "Ollama: $(ollama --version 2>/dev/null)"; ollama list 2>/dev/null | head -5; else echo "Ollama: not installed"; fi
sysctl -n machdep.cpu.brand_string 2>/dev/null; sysctl -n hw.memsize 2>/dev/null | awk '{printf "RAM: %.0f GB\n", $1/1073741824}'

caffeinate -dimsu -w $$ &
echo "Runner ready. Waiting for jobs in runs/queue/ ..."
while true; do
  git pull -q --ff-only origin main 2>/dev/null
  .venv/bin/pip install -q -r requirements-eval.txt 2>/dev/null
  for job in runs/queue/*.sh; do
    [ -e "$job" ] || continue
    name=$(basename "$job" .sh)
    [ -e "runs/done/$name" ] && continue
    mkdir -p "runs/out/$name"
    echo "[$(date '+%H:%M:%S')] running $name"
    ( export PYTHONPATH="$ROOT"; source .venv/bin/activate; cd "$ROOT"; bash "$job" ) > "runs/out/$name/log.txt" 2>&1
    echo $? > "runs/out/$name/exit_code"
    touch "runs/done/$name"
    echo "[$(date '+%H:%M:%S')] finished $name (exit $(cat runs/out/$name/exit_code))"
  done
  sleep 10
done

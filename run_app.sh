#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$ROOT_DIR/src/web"
API_DIR="$ROOT_DIR/src/api"
MCP_DIR="$ROOT_DIR/src/mcp"
PIDS=()
NAMES=()

find_uv() {
  if command -v uv >/dev/null 2>&1; then
    command -v uv
    return
  fi
  if [[ -x "$HOME/.local/bin/uv" ]]; then
    printf '%s\n' "$HOME/.local/bin/uv"
    return
  fi
  printf '%s\n' "uv was not found. Install it from https://docs.astral.sh/uv/." >&2
  exit 1
}

cleanup() {
  local status=$?
  local pid

  trap - EXIT
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  for pid in "${PIDS[@]}"; do
    wait "$pid" 2>/dev/null || true
  done
  exit "$status"
}

start_service() {
  local name=$1
  shift

  "$@" &
  PIDS+=("$!")
  NAMES+=("$name")
}

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

if [[ -z "${NEIS_API_KEY:-}" ]] \
  || [[ "$NEIS_API_KEY" == "replace-with-your-neis-api-key" ]]; then
  printf '%s\n' \
    "NEIS_API_KEY must be set in the environment or in $ROOT_DIR/.env." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  printf '%s\n' "npm was not found. Install a supported Node.js release." >&2
  exit 1
fi

UV_BIN="$(find_uv)"

if [[ ! -d "$WEB_DIR/node_modules" ]]; then
  printf '%s\n' "Installing web dependencies..."
  npm ci --prefix "$WEB_DIR"
fi
if [[ ! -d "$API_DIR/.venv" ]]; then
  printf '%s\n' "Installing API dependencies..."
  (cd "$API_DIR" && "$UV_BIN" sync --locked --all-groups)
fi
if [[ ! -d "$MCP_DIR/.venv" ]]; then
  printf '%s\n' "Installing MCP dependencies..."
  (cd "$MCP_DIR" && "$UV_BIN" sync --locked --all-groups)
fi

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

start_service "api" \
  bash -c 'cd "$1" && exec "$2" run --locked uvicorn app.main:app --reload --host 127.0.0.1 --port 8000' \
  bash "$API_DIR" "$UV_BIN"
start_service "mcp" \
  bash -c 'cd "$1" && exec "$2" run --locked uvicorn app.main:app --reload --host 127.0.0.1 --port 8001' \
  bash "$MCP_DIR" "$UV_BIN"
start_service "web" \
  bash -c 'cd "$1" && exec ./node_modules/.bin/vite --host 127.0.0.1 --port 5173' \
  bash "$WEB_DIR"

printf '\n%s\n' "Local development services are starting:"
printf '  Web: %s\n' "http://127.0.0.1:5173"
printf '  API: %s\n' "http://127.0.0.1:8000"
printf '  MCP: %s\n' "http://127.0.0.1:8001/mcp"
printf '%s\n\n' "Press Ctrl+C to stop all services."

while true; do
  for index in "${!PIDS[@]}"; do
    pid="${PIDS[$index]}"
    if ! kill -0 "$pid" 2>/dev/null; then
      set +e
      wait "$pid"
      status=$?
      set -e
      printf '%s\n' "${NAMES[$index]} exited with status $status." >&2
      exit "$status"
    fi
  done
  sleep 1
done

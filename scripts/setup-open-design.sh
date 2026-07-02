#!/usr/bin/env bash
# Install Open Design (https://github.com/nexu-io/open-design) and wire MCP into Cursor.
# Coexists with Impeccable (.cursor/skills/impeccable) — OD generates artifacts; Impeccable polishes Django templates.
set -euo pipefail

OD_HOME="${OD_HOME:-$HOME/open-design}"
OD_PORT="${OD_PORT:-7456}"
OD_REPO="${OD_REPO:-https://github.com/nexu-io/open-design.git}"
TRADEFLOW_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NODE_MAJOR="${NODE_MAJOR:-24}"

log() { printf '==> %s\n' "$*"; }

ensure_node() {
  if command -v nvm >/dev/null 2>&1 || [[ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]]; then
    export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
    # shellcheck disable=SC1090
    . "$NVM_DIR/nvm.sh"
    if [[ -f "$HOME/.npmrc" ]] && grep -q '^prefix=' "$HOME/.npmrc" 2>/dev/null; then
      mv "$HOME/.npmrc" "$HOME/.npmrc.bak.$(date +%s)" 2>/dev/null || true
    fi
    nvm install "$NODE_MAJOR"
    nvm use "$NODE_MAJOR"
  fi
  if ! node -v | grep -qE "v${NODE_MAJOR}\\."; then
    echo "Open Design requires Node ~${NODE_MAJOR}. Install nvm or Node ${NODE_MAJOR} and re-run." >&2
    exit 1
  fi
}

clone_or_update() {
  if [[ -d "$OD_HOME/.git" ]]; then
    log "Updating Open Design at $OD_HOME"
    git -C "$OD_HOME" pull --ff-only
  else
    log "Cloning Open Design into $OD_HOME"
    git clone --depth 1 "$OD_REPO" "$OD_HOME"
  fi
}

build_od() {
  log "Installing dependencies (pnpm) and building daemon CLI"
  cd "$OD_HOME"
  corepack enable
  corepack prepare pnpm@10.33.2 --activate
  pnpm install
  pnpm --filter @open-design/daemon build
  pnpm --filter @open-design/daemon rebuild better-sqlite3
}

link_cli() {
  mkdir -p "$HOME/.local/bin"
  ln -sf "$OD_HOME/apps/daemon/bin/od.mjs" "$HOME/.local/bin/od"
  export PATH="$HOME/.local/bin:$(dirname "$(command -v node)"):$PATH"
}

sync_tradeflow_design_system() {
  local ds_dir="$OD_HOME/design-systems/tradeflow-colon"
  mkdir -p "$ds_dir"
  if [[ -f "$TRADEFLOW_ROOT/DESIGN.md" ]]; then
    cp "$TRADEFLOW_ROOT/DESIGN.md" "$ds_dir/DESIGN.md"
    log "Synced TradeFlow DESIGN.md -> $ds_dir/DESIGN.md"
  fi
}

install_cursor_mcp() {
  local node_bin od_cli mcp_file od_data
  node_bin="$(command -v node)"
  od_cli="$OD_HOME/apps/daemon/bin/od.mjs"
  od_data="$OD_HOME/.od"
  mkdir -p "$od_data" "$HOME/.cursor"
  mcp_file="$HOME/.cursor/mcp.json"

  # Avoid GNU coreutils `od` at /usr/bin/od — use absolute node + cli paths.
  cat >"$mcp_file" <<EOF
{
  "mcpServers": {
    "open-design": {
      "command": "$node_bin",
      "args": [
        "$od_cli",
        "mcp",
        "--daemon-url",
        "http://127.0.0.1:${OD_PORT}"
      ],
      "env": {
        "OD_DATA_DIR": "$od_data"
      },
      "type": "stdio"
    }
  }
}
EOF
  log "Wrote Cursor MCP config -> $mcp_file"
}

start_daemon() {
  if curl -sf "http://127.0.0.1:${OD_PORT}/api/health" >/dev/null 2>&1; then
    log "Daemon already listening on :${OD_PORT}"
    return
  fi
  log "Starting Open Design daemon on 127.0.0.1:${OD_PORT}"
  nohup node "$OD_HOME/apps/daemon/dist/cli.js" --port "$OD_PORT" --host 127.0.0.1 --no-open \
    >"$OD_HOME/.od/daemon.log" 2>&1 &
  sleep 2
  curl -sf "http://127.0.0.1:${OD_PORT}/api/health" || {
    echo "Daemon failed to start. See $OD_HOME/.od/daemon.log" >&2
    exit 1
  }
  log "Daemon healthy at http://127.0.0.1:${OD_PORT}"
}

main() {
  ensure_node
  clone_or_update
  build_od
  link_cli
  sync_tradeflow_design_system
  install_cursor_mcp
  start_daemon
  cat <<EOF

Open Design is ready.

  Daemon:        http://127.0.0.1:${OD_PORT}
  Design system: tradeflow-colon (from $TRADEFLOW_ROOT/DESIGN.md)
  MCP:           ~/.cursor/mcp.json (restart Cursor to load tools)

Example prompts in Cursor:
  > Use open-design with tradeflow-colon to prototype a B2B catalog hero section
  > od plugin search "landing page"   (CLI, with daemon running)

Impeccable (audit/polish) remains at .cursor/skills/impeccable — use both together.
EOF
}

main "$@"

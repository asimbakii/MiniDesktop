#!/usr/bin/env bash
# MiniDesktop — Linux uninstaller.
#   ./uninstall.sh            remove MiniDesktop (asks before deleting your settings)
#   ./uninstall.sh --purge    also delete settings, paired tablets and Discord tokens
set -euo pipefail

PREFIX="${XDG_DATA_HOME:-$HOME/.local/share}/minidesktop"
PORT="${MINIDESKTOP_PORT:-8765}"
PURGE=0
[ "${1:-}" = "--purge" ] && PURGE=1

say() { printf '\033[1;36m[MiniDesktop]\033[0m %s\n' "$*"; }

curl -fsS -m 2 -X POST -H 'Content-Type: application/json' -d '{}' "http://127.0.0.1:$PORT/api/admin/shutdown" >/dev/null 2>&1 && sleep 2 || true
if [ -x "$PREFIX/venv/bin/python" ] && [ -f "$PREFIX/app/app/launcher.py" ]; then
  "$PREFIX/venv/bin/python" "$PREFIX/app/app/launcher.py" --uninstall-hooks || true   # remove Claude Code hooks
fi
pkill -f "$PREFIX/app/app/launcher.py" 2>/dev/null || true

rm -rf "$PREFIX/app" "$PREFIX/venv"
rm -f "$HOME/.local/bin/minidesktop" \
      "${XDG_DATA_HOME:-$HOME/.local/share}/applications/minidesktop.desktop" \
      "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/minidesktop.desktop"
say "MiniDesktop removed."

if [ "$PURGE" = 0 ] && [ -t 0 ] && [ -d "$PREFIX/data" ]; then
  read -r -p "Also delete settings, paired tablets and Discord tokens ($PREFIX/data)? [y/N] " r
  [[ "$r" =~ ^[Yy] ]] && PURGE=1
fi
if [ "$PURGE" = 1 ]; then
  rm -rf "$PREFIX"
  say "Settings deleted."
fi

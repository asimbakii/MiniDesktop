#!/usr/bin/env bash
# MiniDesktop — Linux installer (per user, no root needed for MiniDesktop itself).
#
#   ./install.sh                 install / update and start MiniDesktop
#   ./install.sh --autostart     also start with your desktop session
#   ./install.sh --yes           don't ask questions (installs missing system packages with sudo)
#   ./install.sh --no-system     skip system packages
#   ./install.sh --no-launch     don't start MiniDesktop after installing
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${XDG_DATA_HOME:-$HOME/.local/share}/minidesktop"
APP="$PREFIX/app"
VENV="$PREFIX/venv"
BIN="$HOME/.local/bin"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
PORT="${MINIDESKTOP_PORT:-8765}"

YES=0; SYSTEM=1; LAUNCH=1; AUTO=0
for a in "$@"; do
  case "$a" in
    --yes|-y) YES=1 ;;
    --no-system) SYSTEM=0 ;;
    --no-launch) LAUNCH=0 ;;
    --autostart) AUTO=1 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "Unknown option: $a"; exit 2 ;;
  esac
done

say()  { printf '\033[1;36m[MiniDesktop]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[MiniDesktop]\033[0m %s\n' "$*"; }
ask()  { [ "$YES" = 1 ] && return 0; [ -t 0 ] || return 1; read -r -p "$1 [Y/n] " r; [[ -z "$r" || "$r" =~ ^[Yy] ]]; }

[ "$(uname -s)" = "Linux" ] || { echo "This installer is for Linux. On Windows use MiniDesktop-Setup.exe."; exit 1; }

# ---------------------------------------------------------------- 1) system packages
missing=()
command -v python3 >/dev/null || missing+=(python3)
python3 -c 'import venv, ensurepip' 2>/dev/null || missing+=(venv)
python3 -c 'import tkinter' 2>/dev/null || missing+=(tk)
python3 -c 'import ctypes.util, sys; sys.exit(0 if ctypes.util.find_library("pulse") else 1)' 2>/dev/null || missing+=(libpulse)
python3 -c 'import gi' 2>/dev/null || missing+=(gi)
if [ -n "${WAYLAND_DISPLAY:-}" ]; then command -v wl-copy >/dev/null || missing+=(wl-clipboard); fi
if [ -n "${DISPLAY:-}" ]; then
  command -v xclip >/dev/null || missing+=(xclip)
  command -v xdotool >/dev/null || missing+=(xdotool)
fi

pkgs_for() {
  local mgr="$1"; shift; local out=()
  for m in "$@"; do
    case "$mgr:$m" in
      apt:python3) out+=(python3) ;;      apt:venv) out+=(python3-venv) ;;   apt:tk) out+=(python3-tk) ;;
      apt:libpulse) out+=(libpulse0) ;;   apt:gi) out+=(python3-gi gir1.2-ayatanaappindicator3-0.1) ;;
      dnf:python3) out+=(python3) ;;      dnf:venv) ;;                        dnf:tk) out+=(python3-tkinter) ;;
      dnf:libpulse) out+=(pulseaudio-libs) ;; dnf:gi) out+=(python3-gobject libayatana-appindicator-gtk3) ;;
      pacman:python3|pacman:venv) out+=(python) ;; pacman:tk) out+=(tk) ;;
      pacman:libpulse) out+=(libpulse) ;; pacman:gi) out+=(python-gobject libayatana-appindicator) ;;
      zypper:python3|zypper:venv) out+=(python3) ;; zypper:tk) out+=(python3-tk) ;;
      zypper:libpulse) out+=(libpulse0) ;; zypper:gi) out+=(python3-gobject typelib-1_0-AyatanaAppIndicator3-0_1) ;;
      *:wl-clipboard) out+=(wl-clipboard) ;; *:xclip) out+=(xclip) ;; *:xdotool) out+=(xdotool) ;;
    esac
  done
  printf '%s\n' "${out[@]}" | sort -u | tr '\n' ' '
}

if [ "${#missing[@]}" -gt 0 ] && [ "$SYSTEM" = 1 ]; then
  if command -v apt-get >/dev/null; then mgr=apt; cmd="sudo apt-get install -y"
  elif command -v dnf >/dev/null; then mgr=dnf; cmd="sudo dnf install -y"
  elif command -v pacman >/dev/null; then mgr=pacman; cmd="sudo pacman -S --needed --noconfirm"
  elif command -v zypper >/dev/null; then mgr=zypper; cmd="sudo zypper install -y"
  else mgr=""; fi
  if [ -n "$mgr" ]; then
    list="$(pkgs_for "$mgr" "${missing[@]}")"
    say "Missing system packages: $list"
    if ask "Install them now with: $cmd $list ?"; then
      [ "$mgr" = apt ] && sudo apt-get update -qq
      # shellcheck disable=SC2086
      $cmd $list
    else
      warn "Skipped. Some features may not work (see README → Linux)."
    fi
  else
    warn "Unknown package manager. Please install: python3 venv, tkinter, libpulse, PyGObject + AyatanaAppIndicator, wl-clipboard/xclip, xdotool."
  fi
fi

command -v python3 >/dev/null || { echo "python3 is required."; exit 1; }
python3 - <<'PY' || { echo "Python 3.10 or newer is required."; exit 1; }
import sys
sys.exit(0 if sys.version_info >= (3, 10) else 1)
PY

# ---------------------------------------------------------------- 2) stop a running copy
if curl -fsS -m 2 -X POST -H 'Content-Type: application/json' -d '{}' "http://127.0.0.1:$PORT/api/admin/shutdown" >/dev/null 2>&1; then
  say "Stopped the running MiniDesktop server."
  sleep 2
fi
pkill -f "$APP/app/launcher.py" 2>/dev/null || true

# ---------------------------------------------------------------- 3) copy files
say "Installing to $APP"
mkdir -p "$PREFIX"
rm -rf "$APP"
mkdir -p "$APP"
cp -r "$SRC/app" "$SRC/server" "$SRC/web" "$SRC/tools" "$APP/"
cp "$SRC/requirements.txt" "$SRC/VERSION" "$SRC/LICENSE" "$APP/" 2>/dev/null || true
# Discord Social SDK bridge: prebuilt (release tarball) or built from source
if [ -x "$SRC/bridge/dcbridge" ]; then
  mkdir -p "$APP/bridge" && cp "$SRC/bridge/"dcbridge "$SRC/bridge/"*.so "$APP/bridge/" 2>/dev/null || true
  cp "$SRC/bridge/"*.txt "$APP/bridge/" 2>/dev/null || true
elif [ -x "$SRC/bridge/build/dcbridge" ]; then
  mkdir -p "$APP/bridge" && cp "$SRC/bridge/build/dcbridge" "$SRC/bridge/build/"*.so "$APP/bridge/"
else
  warn "No Discord friends bridge in this package — the friends list will be unavailable (see README → Linux)."
fi

# ---------------------------------------------------------------- 4) Python environment
say "Creating Python environment (this can take a minute)…"
# --system-site-packages: lets the tray icon use the system's PyGObject / AppIndicator bindings
[ -x "$VENV/bin/python" ] || python3 -m venv --system-site-packages "$VENV"
"$VENV/bin/python" -m pip install -q --disable-pip-version-check --upgrade pip
"$VENV/bin/python" -m pip install -q --disable-pip-version-check -r "$APP/requirements.txt"

# ---------------------------------------------------------------- 5) launcher, menu entry, autostart
mkdir -p "$BIN" "$APPS"
cat > "$BIN/minidesktop" <<EOF
#!/usr/bin/env bash
exec "$VENV/bin/python" "$APP/app/launcher.py" "\$@"
EOF
chmod +x "$BIN/minidesktop"

cat > "$APPS/minidesktop.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=MiniDesktop
Comment=Turn your tablet into a second screen for this PC
Exec=$BIN/minidesktop
Icon=$APP/web/icon-192.png
Categories=Utility;
Terminal=false
EOF
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" >/dev/null 2>&1 || true

if [ "$AUTO" = 1 ]; then
  mkdir -p "$AUTOSTART"
  sed "s|^Exec=.*|Exec=$BIN/minidesktop --tray|" "$APPS/minidesktop.desktop" > "$AUTOSTART/minidesktop.desktop"
  echo "X-GNOME-Autostart-enabled=true" >> "$AUTOSTART/minidesktop.desktop"
  say "MiniDesktop will start with your desktop session."
fi

# ---------------------------------------------------------------- 6) firewall hint
if command -v ufw >/dev/null && systemctl is-active --quiet ufw 2>/dev/null; then
  warn "ufw is active. If the tablet can't connect, run:  sudo ufw allow $PORT/tcp"
elif command -v firewall-cmd >/dev/null && systemctl is-active --quiet firewalld 2>/dev/null; then
  warn "firewalld is active. If the tablet can't connect, run:  sudo firewall-cmd --add-port=$PORT/tcp --permanent && sudo firewall-cmd --reload"
fi

say "Installed MiniDesktop $(cat "$APP/VERSION" 2>/dev/null || echo)."
case ":$PATH:" in *":$BIN:"*) ;; *) warn "$BIN is not in your PATH; start it from the app menu or with $BIN/minidesktop" ;; esac

if [ "$LAUNCH" = 1 ] && { [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; }; then
  say "Starting MiniDesktop…"
  nohup "$BIN/minidesktop" >/dev/null 2>&1 &
fi

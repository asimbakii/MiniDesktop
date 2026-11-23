"""Dosya yolları: geliştirme (kaynak koddan) ve paketlenmiş (PyInstaller exe) durumları için."""
import os
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))

if FROZEN:
    APP_DIR = Path(sys.executable).resolve().parent              # MiniDesktop.exe'nin klasörü
    RES_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))            # paketlenmiş kaynaklar (_internal)
    DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "MiniDesktop"
    BRIDGE_EXE = APP_DIR / "bridge" / "dcbridge.exe"
else:
    APP_DIR = Path(__file__).resolve().parent.parent
    RES_DIR = APP_DIR
    DATA_DIR = APP_DIR / "data"
    BRIDGE_EXE = APP_DIR / "bridge" / "build" / "dcbridge.exe"

if os.environ.get("MINIDESKTOP_DATA"):
    DATA_DIR = Path(os.environ["MINIDESKTOP_DATA"])

WEB_DIR = RES_DIR / "web"
ADMIN_HTML = RES_DIR / "server" / "admin.html"
PORT = int(os.environ.get("MINIDESKTOP_PORT", "8765"))

DATA_DIR.mkdir(parents=True, exist_ok=True)


def hook_command() -> str:
    """Claude Code hook'unun çalıştıracağı komut."""
    if FROZEN:
        return f'"{Path(sys.executable).as_posix()}" --claude-hook'
    py = Path(sys.executable)
    if py.name.lower() == "pythonw.exe":
        py = py.with_name("python.exe")
    return f'"{py.as_posix()}" "{(APP_DIR / "tools" / "claude_hook.py").as_posix()}"'


def server_command(extra: list[str] | None = None) -> list[str]:
    """Sunucuyu ayrı süreç olarak başlatan komut (kontrol uygulaması kullanır)."""
    extra = extra or []
    if FROZEN:
        return [sys.executable, "--server", *extra]
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe")
    return [str(pyw if pyw.exists() else py), str(APP_DIR / "server" / "main.py"), *extra]

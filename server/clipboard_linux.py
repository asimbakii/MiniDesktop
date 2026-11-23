"""Linux panosu: Wayland'de wl-clipboard (wl-paste / wl-copy), X11'de xclip ya da xsel."""
import os
import shutil
import subprocess

from i18n import t

# Şifre yöneticileri (KeePassXC, KDE) bu türü ekler: bu içerikleri geçmişe alma
PRIVATE_TYPES = ("x-kde-passwordManagerHint",)
TEXT_TYPES = ("text/plain", "UTF8_STRING", "STRING", "TEXT", "text/plain;charset=utf-8")


def _tool() -> str | None:
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste") and shutil.which("wl-copy"):
        return "wl"
    if os.environ.get("DISPLAY"):
        if shutil.which("xclip"):
            return "xclip"
        if shutil.which("xsel"):
            return "xsel"
    return None


def _run(args, data: bytes | None = None, timeout: float = 2.0) -> bytes:
    r = subprocess.run(args, input=data, capture_output=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "replace").strip()[:200])
    return r.stdout


def _types(tool: str) -> list[str]:
    try:
        if tool == "wl":
            out = _run(["wl-paste", "--list-types"])
        elif tool == "xclip":
            out = _run(["xclip", "-selection", "clipboard", "-o", "-t", "TARGETS"])
        else:
            return list(TEXT_TYPES)  # xsel türleri listeleyemez
    except Exception:
        return []
    return [x.strip() for x in out.decode("utf-8", "replace").splitlines() if x.strip()]


def clipboard_get() -> str | None:
    tool = _tool()
    if not tool:
        return None
    types = _types(tool)
    if any(p in types for p in PRIVATE_TYPES) or not any(tt in types for tt in TEXT_TYPES):
        return None
    try:
        if tool == "wl":
            out = _run(["wl-paste", "--no-newline", "--type", "text/plain"])
        elif tool == "xclip":
            out = _run(["xclip", "-selection", "clipboard", "-o"])
        else:
            out = _run(["xsel", "--clipboard", "--output"])
    except Exception:
        return None
    return out.decode("utf-8", "replace")


def clipboard_set(text: str):
    tool = _tool()
    data = text.encode("utf-8")
    if tool == "wl":
        _run(["wl-copy"], data)
    elif tool == "xclip":
        _run(["xclip", "-selection", "clipboard", "-in"], data)
    elif tool == "xsel":
        _run(["xsel", "--clipboard", "--input"], data)
    else:
        raise RuntimeError(t("Panoya yazılamadı.") + " (wl-clipboard / xclip)")


def clipboard_seq():
    """Linux'ta değişiklik sayacı yok: None -> çağıran her turda içeriği karşılaştırır."""
    return None

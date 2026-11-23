"""Kısayol tuşu modu: Discord'un genel tuş atamalarını (Sessize Al / Sağırlaştır) göndererek
mikrofon ve kulaklığı kontrol eder. Developer Portal gerektirmez; ama durum (açık/kapalı) okunamaz.

Kullanıcı Discord -> Kullanıcı Ayarları -> Tuş Atamaları'nda bu kısayolları bir kez tanımlar.

Windows: SendInput. Linux: X11'de xdotool, Wayland'de ydotool ya da wtype.
(Not: Discord'un genel kısayolları Linux'ta X11 / XWayland oturumlarında çalışır.)
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from i18n import t

DEFAULTS = {"enabled": True, "mute": "ctrl+shift+f9", "deaf": "ctrl+shift+f10"}

VK = {"ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B, "super": 0x5B,
      "space": 0x20, "home": 0x24, "end": 0x23, "insert": 0x2D, "delete": 0x2E, "pause": 0x13,
      "scrolllock": 0x91, "pageup": 0x21, "pagedown": 0x22}
VK.update({f"f{i}": 0x6F + i for i in range(1, 25)})           # F1..F24
VK.update({chr(c): c for c in range(ord("A"), ord("Z") + 1)})  # harfler
VK.update({chr(c).lower(): c for c in range(ord("A"), ord("Z") + 1)})
VK.update({str(d): 0x30 + d for d in range(10)})
LABELS = {0x11: "Ctrl", 0x10: "Shift", 0x12: "Alt", 0x5B: "Win" if sys.platform == "win32" else "Super"}


def _names(combo: str) -> list[str]:
    parts = [p for p in combo.replace(" ", "").lower().split("+") if p]
    for p in parts:
        if p not in VK:
            raise ValueError(t("Bilinmeyen tuş: {part}", part=p))
    if not parts:
        raise ValueError(t("Kısayol boş"))
    return parts


def parse(combo: str) -> list[int]:
    return [VK[p] for p in _names(combo)]


def pretty(combo: str) -> str:
    out = []
    for part in combo.replace(" ", "").split("+"):
        p = part.lower()
        out.append(LABELS.get(VK.get(p), p.upper() if len(p) <= 3 else p.capitalize()))
    return "+".join(out)


# ------------------------------------------------------------------ Windows
if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes as wt

    EXTENDED = {0x2D, 0x2E, 0x24, 0x23, 0x21, 0x22}
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008
    INPUT_KEYBOARD = 1

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wt.DWORD), ("u", _U)]

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SendInput.argtypes = [wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.MapVirtualKeyW.argtypes = [wt.UINT, wt.UINT]

    def _event(vk: int, up: bool):
        scan = user32.MapVirtualKeyW(vk, 0)
        flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED else 0)
        return INPUT(type=INPUT_KEYBOARD, u=_U(ki=KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)))

    def send(combo: str):
        keys = parse(combo)
        for ev in [_event(k, False) for k in keys]:
            user32.SendInput(1, ctypes.byref(ev), ctypes.sizeof(INPUT))
            time.sleep(0.015)
        time.sleep(0.04)
        for ev in [_event(k, True) for k in reversed(keys)]:
            user32.SendInput(1, ctypes.byref(ev), ctypes.sizeof(INPUT))
            time.sleep(0.015)

# ------------------------------------------------------------------ Linux
else:
    # Linux giriş olay kodları (ydotool için)
    EVDEV = {"ctrl": 29, "control": 29, "shift": 42, "alt": 56, "win": 125, "super": 125, "space": 57, "home": 102,
             "end": 107, "insert": 110, "delete": 111, "pause": 119, "scrolllock": 70, "pageup": 104, "pagedown": 109}
    EVDEV.update({f"f{i}": 58 + i for i in range(1, 11)})
    EVDEV.update({"f11": 87, "f12": 88})
    EVDEV.update({f"f{i}": 170 + i for i in range(13, 25)})  # F13=183 … F24=194
    for row, start in (("qwertyuiop", 16), ("asdfghjkl", 30), ("zxcvbnm", 44)):
        EVDEV.update({ch: start + i for i, ch in enumerate(row)})
    EVDEV.update({str(d): 1 + d for d in range(1, 10)})
    EVDEV["0"] = 11
    XDO = {"ctrl": "ctrl", "control": "ctrl", "shift": "shift", "alt": "alt", "win": "super", "super": "super",
           "space": "space", "home": "Home", "end": "End", "insert": "Insert", "delete": "Delete", "pause": "Pause",
           "scrolllock": "Scroll_Lock", "pageup": "Prior", "pagedown": "Next"}
    MODS = {"ctrl", "control", "shift", "alt", "win", "super"}

    def _run(args):
        r = subprocess.run(args, capture_output=True, timeout=5)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode("utf-8", "replace").strip()[:200] or " ".join(args))

    def send(combo: str):
        names = _names(combo)
        wayland = os.environ.get("XDG_SESSION_TYPE") == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))
        if os.environ.get("DISPLAY") and shutil.which("xdotool") and not (wayland and shutil.which("ydotool")):
            keys = [XDO.get(n, n.upper() if n.startswith("f") and n[1:].isdigit() else n) for n in names]
            _run(["xdotool", "key", "--clearmodifiers", "+".join(keys)])
        elif shutil.which("ydotool"):
            codes = [EVDEV[n] for n in names]
            _run(["ydotool", "key", *[f"{c}:1" for c in codes], *[f"{c}:0" for c in reversed(codes)]])
        elif shutil.which("wtype"):
            mods = [n for n in names if n in MODS]
            keys = [n for n in names if n not in MODS]
            wt_mod = {"control": "ctrl", "win": "logo", "super": "logo"}
            args = ["wtype"]
            for m in mods:
                args += ["-M", wt_mod.get(m, m)]
            for k in keys:
                args += ["-k", XDO.get(k, k.upper() if k.startswith("f") and k[1:].isdigit() else k)]
            for m in reversed(mods):
                args += ["-m", wt_mod.get(m, m)]
            _run(args)
        else:
            raise RuntimeError(t("Kısayol gönderilemedi: xdotool, ydotool ya da wtype kurulu değil."))


class KeyControl:
    def __init__(self, data_dir: Path):
        self.path = data_dir / "discord_keys.json"
        self.cfg = dict(DEFAULTS)
        try:
            self.cfg.update(json.loads(self.path.read_text("utf-8")))
        except Exception:
            pass

    def update(self, data: dict):
        new = dict(self.cfg)
        if "enabled" in data:
            new["enabled"] = bool(data["enabled"])
        for k in ("mute", "deaf"):
            if k in data:
                parse(str(data[k]))  # geçerli mi?
                new[k] = str(data[k]).strip().lower()
        self.cfg = new
        self.path.write_text(json.dumps(self.cfg), "utf-8")

    def toggle(self, what: str):
        send(self.cfg["mute" if what == "mute" else "deaf"])

    def state(self) -> dict:
        return {"enabled": self.cfg["enabled"], "mute": pretty(self.cfg["mute"]), "deaf": pretty(self.cfg["deaf"]),
                "mute_raw": self.cfg["mute"], "deaf_raw": self.cfg["deaf"]}

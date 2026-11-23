"""Kısayol tuşu modu: Discord'un genel tuş atamalarını (Sessize Al / Sağırlaştır) göndererek
mikrofon ve kulaklığı kontrol eder. Developer Portal gerektirmez; ama durum (açık/kapalı) okunamaz.

Kullanıcı Discord -> Kullanıcı Ayarları -> Tuş Atamaları'nda bu kısayolları bir kez tanımlar.
"""
import ctypes
import ctypes.wintypes as wt
import json
import time
from pathlib import Path
from i18n import t

DEFAULTS = {"enabled": True, "mute": "ctrl+shift+f9", "deaf": "ctrl+shift+f10"}

VK = {"ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B,
      "space": 0x20, "home": 0x24, "end": 0x23, "insert": 0x2D, "delete": 0x2E, "pause": 0x13,
      "scrolllock": 0x91, "pageup": 0x21, "pagedown": 0x22}
VK.update({f"f{i}": 0x6F + i for i in range(1, 25)})           # F1..F24
VK.update({chr(c): c for c in range(ord("A"), ord("Z") + 1)})  # harfler
VK.update({chr(c).lower(): c for c in range(ord("A"), ord("Z") + 1)})
VK.update({str(d): 0x30 + d for d in range(10)})
EXTENDED = {0x2D, 0x2E, 0x24, 0x23, 0x21, 0x22}
LABELS = {0x11: "Ctrl", 0x10: "Shift", 0x12: "Alt", 0x5B: "Win"}

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


def parse(combo: str) -> list[int]:
    keys = []
    for part in combo.replace(" ", "").lower().split("+"):
        if not part:
            continue
        if part not in VK:
            raise ValueError(t("Bilinmeyen tuş: {part}", part=part))
        keys.append(VK[part])
    if not keys:
        raise ValueError(t("Kısayol boş"))
    return keys


def pretty(combo: str) -> str:
    out = []
    for part in combo.replace(" ", "").split("+"):
        p = part.lower()
        out.append(LABELS.get(VK.get(p), p.upper() if len(p) <= 3 else p.capitalize()))
    return "+".join(out)


def _event(vk: int, up: bool) -> INPUT:
    scan = user32.MapVirtualKeyW(vk, 0)
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED else 0)
    return INPUT(type=INPUT_KEYBOARD, u=_U(ki=KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)))


def send(combo: str):
    keys = parse(combo)
    downs = [_event(k, False) for k in keys]
    ups = [_event(k, True) for k in reversed(keys)]
    for ev in downs:
        user32.SendInput(1, ctypes.byref(ev), ctypes.sizeof(INPUT))
        time.sleep(0.015)
    time.sleep(0.04)
    for ev in ups:
        user32.SendInput(1, ctypes.byref(ev), ctypes.sizeof(INPUT))
        time.sleep(0.015)


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

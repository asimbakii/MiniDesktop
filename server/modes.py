"""Ekran modları (Normal / Geliştirici / Oyun / Gece), otomatik geçişler ve güç menüsü."""
import asyncio
import ctypes
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

import psutil
from i18n import t

MODES = ("normal", "dev", "game", "night")

# Bu klasörlerin altından çalışan bir .exe "oyun" sayılır
GAME_DIRS = (
    "\\steamapps\\common\\", "\\epic games\\", "\\riot games\\", "\\xboxgames\\", "\\ea games\\",
    "\\ubisoft game launcher\\games\\", "\\gog galaxy\\games\\", "\\gog games\\", "\\battle.net\\games\\",
)
# Oyun klasörlerinde olup oyun olmayanlar (başlatıcılar, yardımcılar, duvar kağıdı vb.)
IGNORE_NAMES = (
    "launcher", "riotclient", "leagueclient", "crashhandler", "crashreport", "crashpad", "easyanticheat",
    "battleye", "beservice", "setup", "redist", "dxsetup", "uninstall", "unins0", "helper", "updater",
    "overlay", "webhelper", "cefprocess", "vgtray", "service",
)
IGNORE_PATHS = ("\\steamworks shared\\", "\\wallpaper_engine\\", "\\steamvr\\", "\\_commonredist\\")


def _game_name(exe_low: str, exe: str) -> str:
    for marker in GAME_DIRS:
        i = exe_low.find(marker)
        if i >= 0:
            rest = exe[i + len(marker):]
            return rest.split("\\", 1)[0] or Path(exe).stem
    return Path(exe).stem


_candidates: dict[int, tuple] = {}  # pid -> (create_time, aday mı, oyun adı, exe adı)


def detect_game() -> dict | None:
    """Çalışan bir oyun var mı? (en çok bellek kullanan aday). Süreç yolları önbelleklenir."""
    best = None
    alive = set()
    for p in psutil.process_iter(["create_time"]):
        pid, ct = p.pid, p.info.get("create_time")
        alive.add(pid)
        cached = _candidates.get(pid)
        if cached is None or cached[0] != ct:
            try:
                exe = p.exe()
            except Exception:
                exe = ""
            low = exe.lower()
            name = os.path.basename(low)
            ok = bool(exe) and any(d in low for d in GAME_DIRS) and not any(x in low for x in IGNORE_PATHS) \
                and not any(x in name for x in IGNORE_NAMES)
            cached = (ct, ok, _game_name(low, exe) if ok else None, os.path.basename(exe))
            _candidates[pid] = cached
        if not cached[1]:
            continue
        try:
            rss = p.memory_info().rss
        except Exception:
            continue
        if rss < 150 * 1024 * 1024:  # küçük yardımcı süreçleri ele
            continue
        if best is None or rss > best["rss"]:
            best = {"name": cached[2], "exe": cached[3], "pid": pid, "since": ct, "rss": rss}
    for pid in list(_candidates):
        if pid not in alive:
            del _candidates[pid]
    return best


def _in_window(now: datetime, start: str, end: str) -> bool:
    def mins(s):
        h, m = s.split(":")
        return int(h) * 60 + int(m)
    n, a, b = now.hour * 60 + now.minute, mins(start), mins(end)
    return a <= n < b if a <= b else (n >= a or n < b)  # gece yarısını aşan aralık


class Modes:
    def __init__(self, data_dir: Path, on_change):
        self.path = data_dir / "modes.json"
        self.on_change = on_change
        self.cfg = {"mode": "normal", "auto_game": True, "auto_night": False, "night_from": "00:00", "night_to": "08:00", "idle_min": 3}
        try:
            self.cfg.update(json.loads(self.path.read_text("utf-8")))
        except Exception:
            pass
        if self.cfg["mode"] not in MODES:
            self.cfg["mode"] = "normal"
        self.game = None
        self._return_to = None        # otomatik geçişten önceki mod
        self._auto_kind = None        # "game" | "night"
        self._suppress_game = None    # kullanıcı oyun modundan elle çıktıysa o oyun için tekrar geçme
        self._suppress_night = False

    @property
    def mode(self) -> str:
        return self.cfg["mode"]

    def _save(self):
        self.path.write_text(json.dumps(self.cfg), "utf-8")

    def _switch(self, mode: str, auto_kind: str | None = None):
        if auto_kind:
            if self._auto_kind is None:
                self._return_to = self.cfg["mode"]
            self._auto_kind = auto_kind
        else:
            self._auto_kind = None
            self._return_to = None
        if self.cfg["mode"] != mode:
            self.cfg["mode"] = mode
            self._save()
            self.on_change()

    # ---------- tabletten ----------
    def set_mode(self, mode: str):
        if mode not in MODES:
            raise ValueError(t("Bilinmeyen mod"))
        # Otomatik moddan elle çıkılıyorsa o durumu bastır
        if self._auto_kind == "game" and mode != "game" and self.game:
            self._suppress_game = self.game["exe"]
        if self._auto_kind == "night" and mode != "night":
            self._suppress_night = True
        self._switch(mode)

    def update_settings(self, data: dict):
        for k in ("auto_game", "auto_night"):
            if k in data:
                self.cfg[k] = bool(data[k])
        for k in ("night_from", "night_to"):
            if k in data:
                v = str(data[k])
                datetime.strptime(v, "%H:%M")
                self.cfg[k] = v
        if "idle_min" in data:
            self.cfg["idle_min"] = max(0, min(120, int(data["idle_min"])))
        self._save()
        self.on_change()

    # ---------- otomatik kurallar ----------
    async def run(self):
        while True:
            try:
                game = await asyncio.to_thread(detect_game)
            except Exception:
                game = None
            changed = (game or {}).get("pid") != (self.game or {}).get("pid")
            self.game = game
            self._apply_rules()
            if changed:
                self.on_change()
            await asyncio.sleep(5)

    def _apply_rules(self):
        mode = self.cfg["mode"]
        # Oyun
        if self.game:
            if self.cfg["auto_game"] and mode != "game" and self.game["exe"] != self._suppress_game:
                self._switch("game", "game")
                return
        else:
            self._suppress_game = None
            if mode == "game" and self._auto_kind == "game":
                back = self._return_to or "normal"
                self._auto_kind = None
                self._return_to = None
                self._switch(back)
                mode = back
        # Gece
        in_night = _in_window(datetime.now(), self.cfg["night_from"], self.cfg["night_to"])
        if not in_night:
            self._suppress_night = False
            if mode == "night" and self._auto_kind == "night":
                self._auto_kind = None
                self._switch(self._return_to or "normal")
        elif self.cfg["auto_night"] and mode == "normal" and not self._suppress_night:
            self._switch("night", "night")

    def state(self) -> dict:
        g = self.game
        return {
            **{k: self.cfg[k] for k in ("mode", "auto_game", "auto_night", "night_from", "night_to", "idle_min")},
            "auto": self._auto_kind,
            "game": {"name": g["name"], "since": g["since"]} if g else None,
        }


# ---------- güç menüsü ----------
def power(action: str):
    """Tabletten onaylı olarak çağrılır. Yanıt tablete ulaşsın diye kısa gecikmeyle çalışır."""
    loop = asyncio.get_running_loop()
    flags = subprocess.CREATE_NO_WINDOW
    if action == "lock":
        loop.call_later(0.3, ctypes.windll.user32.LockWorkStation)
    elif action == "sleep":
        # SetSuspendState(hibernate=False, force=False, wakeupEventsDisabled=False)
        loop.call_later(1.0, lambda: ctypes.windll.powrprof.SetSuspendState(0, 0, 0))
    elif action == "restart":
        subprocess.Popen(["shutdown", "/r", "/t", "3"], creationflags=flags)
    elif action == "shutdown":
        subprocess.Popen(["shutdown", "/s", "/t", "3"], creationflags=flags)
    else:
        raise ValueError(t("Bilinmeyen güç işlemi"))

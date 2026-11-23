"""Ana ses seviyesi ve uygulama bazlı ses mikseri (Windows Core Audio / pycaw)."""
import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor

# comtypes import edilince ana thread'i STA yapar; bu da WinRT async çağrılarını
# (medya API'si) kilitler. Ana thread'i MTA olarak başlat.
sys.coinit_flags = 0  # COINIT_MULTITHREADED
import comtypes  # noqa: E402
from pycaw.pycaw import AudioUtilities
from i18n import t

PRETTY = {
    "chrome.exe": "Chrome",
    "msedge.exe": "Edge",
    "firefox.exe": "Firefox",
    "discord.exe": "Discord",
    "spotify.exe": "Spotify",
    "steam.exe": "Steam",
    "steamwebhelper.exe": "Steam",
    "xboxpcapp.exe": "Xbox",
    "vlc.exe": "VLC",
    "__system__": "Sistem sesleri",
}


def _pretty(key: str) -> str:
    if key == "__system__":
        return t("Sistem sesleri")
    if key in PRETTY:
        return PRETTY[key]
    name = key[:-4] if key.endswith(".exe") else key
    return name[:1].upper() + name[1:]


class Audio:
    def __init__(self):
        # COM nesneleri tek bir thread'de yaşamalı.
        self._ex = ThreadPoolExecutor(1, thread_name_prefix="audio", initializer=comtypes.CoInitialize)

    async def snapshot(self) -> dict:
        return await asyncio.get_running_loop().run_in_executor(self._ex, self._snapshot)

    async def command(self, action: str, key=None, value=None):
        await asyncio.get_running_loop().run_in_executor(self._ex, self._command, action, key, value)

    @staticmethod
    def _sessions():
        for s in AudioUtilities.GetAllSessions():
            try:
                state = s.State
            except Exception:
                state = 1
            if state == 2:  # süresi dolmuş oturum
                continue
            try:
                key = s.Process.name().lower() if s.Process else "__system__"
            except Exception:
                continue
            yield key, state, s

    def _snapshot(self) -> dict:
        speakers = AudioUtilities.GetSpeakers()
        ev = speakers.EndpointVolume
        master = {
            "volume": round(ev.GetMasterVolumeLevelScalar(), 3),
            "muted": bool(ev.GetMute()),
            "device": speakers.FriendlyName,
        }
        apps: dict[str, dict] = {}
        for key, state, s in self._sessions():
            vol = s.SimpleAudioVolume
            entry = apps.get(key)
            if entry is None:
                apps[key] = {
                    "key": key,
                    "name": _pretty(key),
                    "volume": round(vol.GetMasterVolume(), 3),
                    "muted": bool(vol.GetMute()),
                    "active": state == 1,
                }
            elif state == 1:
                entry["active"] = True
        ordered = sorted(apps.values(), key=lambda a: (a["key"] == "__system__", not a["active"], a["name"].lower()))
        return {"master": master, "apps": ordered}

    def _command(self, action, key, value):
        if action in ("master_volume", "master_mute"):
            ev = AudioUtilities.GetSpeakers().EndpointVolume
            if action == "master_volume":
                ev.SetMasterVolumeLevelScalar(max(0.0, min(1.0, float(value))), None)
                if ev.GetMute():
                    ev.SetMute(0, None)
            else:
                ev.SetMute(0 if ev.GetMute() else 1, None)
            return
        targets = [s for k, _, s in self._sessions() if k == key]
        if not targets:
            return
        if action == "app_volume":
            v = max(0.0, min(1.0, float(value)))
            for s in targets:
                s.SimpleAudioVolume.SetMasterVolume(v, None)
        elif action == "app_mute":
            mute = 0 if targets[0].SimpleAudioVolume.GetMute() else 1
            for s in targets:
                s.SimpleAudioVolume.SetMute(mute, None)

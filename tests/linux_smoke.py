"""Linux smoke test (run in CI under xvfb-run + dbus-run-session + PulseAudio).

Checks the Linux implementations against real services:
  * media_linux   — a fake MPRIS player on the session bus (read metadata, play/pause, seek)
  * audio_linux   — PulseAudio null sink (read + set volume)
  * clipboard     — xclip under Xvfb
  * keys          — xdotool under Xvfb
  * stats / netinfo / modes / i18n
  * the full server — pairing + WebSocket state contains the fake player
  * the tray app  — single instance + XDG autostart entry
"""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "app")]
DATA = Path(tempfile.mkdtemp(prefix="md-data-"))
os.environ["MINIDESKTOP_DATA"] = str(DATA)

from dbus_next import Variant  # noqa: E402
from dbus_next.aio import MessageBus  # noqa: E402
from dbus_next.service import PropertyAccess, ServiceInterface, dbus_property, method  # noqa: E402

PASSED = []


def ok(name):
    PASSED.append(name)
    print(f"  ✓ {name}", flush=True)


# ------------------------------------------------------------------ fake MPRIS player
class Root(ServiceInterface):
    def __init__(self):
        super().__init__("org.mpris.MediaPlayer2")

    @dbus_property(access=PropertyAccess.READ)
    def Identity(self) -> "s":
        return "Fake Player"


class Player(ServiceInterface):
    def __init__(self):
        super().__init__("org.mpris.MediaPlayer2.Player")
        self.status = "Playing"
        self.pos = 42_000_000

    @method()
    def PlayPause(self):
        self.status = "Paused" if self.status == "Playing" else "Playing"

    @method()
    def Next(self):
        pass

    @method()
    def Previous(self):
        pass

    @method()
    def SetPosition(self, track: "o", position: "x"):
        self.pos = position

    @method()
    def Seek(self, offset: "x"):
        self.pos += offset

    @dbus_property(access=PropertyAccess.READ)
    def PlaybackStatus(self) -> "s":
        return self.status

    @dbus_property(access=PropertyAccess.READ)
    def Metadata(self) -> "a{sv}":
        return {
            "mpris:trackid": Variant("o", "/org/mpris/MediaPlayer2/Track/1"),
            "xesam:title": Variant("s", "Test Song"),
            "xesam:artist": Variant("as", ["Test Artist"]),
            "xesam:album": Variant("s", "Test Album"),
            "mpris:length": Variant("x", 180_000_000),
        }

    @dbus_property(access=PropertyAccess.READ)
    def Position(self) -> "x":
        return self.pos

    @dbus_property(access=PropertyAccess.READ)
    def CanGoNext(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanGoPrevious(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanSeek(self) -> "b":
        return True


async def start_fake_player():
    bus = await MessageBus().connect()
    player = Player()
    bus.export("/org/mpris/MediaPlayer2", Root())
    bus.export("/org/mpris/MediaPlayer2", player)
    await bus.request_name("org.mpris.MediaPlayer2.fakeplayer")
    return bus, player


# ------------------------------------------------------------------ tests
async def test_media(player):
    from media_linux import Media
    m = Media()
    await m.start()
    snap = await m.snapshot()
    assert snap["available"], snap
    assert snap["title"] == "Test Song" and snap["artist"] == "Test Artist", snap
    assert snap["source_label"] == "Fake Player", snap
    assert snap["playing"] is True and abs(snap["duration"] - 180) < 0.01 and abs(snap["position"] - 42) < 0.01, snap
    ok("media: reads MPRIS metadata")
    await m.command("toggle")
    assert player.status == "Paused"
    assert (await m.snapshot())["playing"] is False
    ok("media: play/pause")
    await m.command("seek", value=90)
    assert player.pos == 90_000_000, player.pos
    ok("media: seek (SetPosition)")


async def test_audio():
    from audio_linux import Audio
    a = Audio()
    s = await a.snapshot()
    assert s["master"]["device"], s
    ok(f"audio: default sink '{s['master']['device']}'")
    await a.command("master_volume", value=0.37)
    s = await a.snapshot()
    assert abs(s["master"]["volume"] - 0.37) < 0.02, s
    await a.command("master_mute")
    assert (await a.snapshot())["master"]["muted"] is True
    ok("audio: set volume + mute")


def test_desktop_bits():
    import clipboard
    clipboard.clipboard_set("MiniDesktop çğş test")
    time.sleep(0.3)
    assert clipboard.clipboard_get() == "MiniDesktop çğş test", clipboard.clipboard_get()
    ok("clipboard: xclip set/get (UTF-8)")
    import keys
    keys.send("ctrl+shift+f9")
    ok("keys: xdotool sends Ctrl+Shift+F9")
    import stats
    snap = stats.Stats().snapshot()
    assert snap["cpu"]["name"] and snap["ram"]["total"] > 0, snap
    ok(f"stats: cpu '{snap['cpu']['name']}', temp={snap['cpu']['temp']}")
    import netinfo
    ok(f"netinfo: primary ip {netinfo.primary_ip()}")
    import modes
    modes.detect_game()
    assert modes._game_name("/home/u/.steam/steam/steamapps/common/cool game/bin/game", "/home/u/.steam/steam/steamapps/common/Cool Game/bin/game") == "Cool Game"
    proton = "reaper -- /h/steamapps/common/proton 9.0/proton waitforexitandrun z:/h/steamapps/common/my game/g.exe"
    assert modes._game_name(proton, proton) == "my game"
    ok("modes: game detection paths (Steam + Proton)")
    import i18n
    os.environ["LANG"] = "tr_TR.UTF-8"
    assert i18n._system_lang() == "tr"
    os.environ["LANG"] = "en_US.UTF-8"
    assert i18n._system_lang() == "en"
    ok("i18n: language from LANG")


def http(path, body=None, port=8799):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())


async def test_server():
    env = {**os.environ, "MINIDESKTOP_PORT": "8799"}
    proc = subprocess.Popen([sys.executable, str(ROOT / "server" / "main.py"), "--no-browser"], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        info = None
        for _ in range(60):
            await asyncio.sleep(0.5)
            try:
                info = await asyncio.to_thread(http, "/api/admin/info")
                break
            except Exception:
                if proc.poll() is not None:
                    raise RuntimeError(proc.stdout.read().decode())
        assert info and info["pin"], info
        ok("server: admin API up")
        page = await asyncio.to_thread(lambda: urllib.request.urlopen("http://127.0.0.1:8799/", timeout=5).read())
        assert b"MiniDesktop" in page
        ok("server: tablet page served")
        token = (await asyncio.to_thread(http, "/api/pair", {"pin": info["pin"], "name": "ci"}))["token"]
        import websockets
        async with websockets.connect(f"ws://127.0.0.1:8799/ws?token={token}") as ws:
            state = None
            for _ in range(5):
                state = json.loads(await asyncio.wait_for(ws.recv(), 10))
                if state.get("media", {}).get("available"):
                    break
        assert state["media"]["title"] == "Test Song", state["media"]
        assert state["audio"]["master"]["device"], state["audio"]
        assert state["stats"].get("cpu"), state["stats"]
        ok("server: WebSocket state has media (MPRIS), audio (Pulse) and stats")
        admin = await asyncio.to_thread(lambda: urllib.request.urlopen("http://127.0.0.1:8799/admin", timeout=5).read())
        assert b"data-lang" in admin
        ok("server: admin page with language")
        await asyncio.to_thread(http, "/api/admin/shutdown", {})
        proc.wait(timeout=15)
        ok("server: clean shutdown")
    finally:
        if proc.poll() is None:
            proc.kill()


def test_tray_app():
    import control
    inst = control.SingleInstance()
    assert inst.claim() is True
    second = control.SingleInstance()
    assert second.claim() is False  # second copy hands over to the first
    time.sleep(0.3)
    assert inst.show_requested() is True
    ok("tray app: single instance (Unix socket)")
    control.autostart_set(True)
    assert control.AUTOSTART_DESKTOP.exists() and "--tray" in control.AUTOSTART_DESKTOP.read_text()
    control.autostart_set(False)
    assert not control.AUTOSTART_DESKTOP.exists()
    ok("tray app: XDG autostart entry")


async def main():
    print(f"Linux smoke test — Python {sys.version.split()[0]}", flush=True)
    bus, player = await start_fake_player()
    await test_media(player)
    await test_audio()
    test_desktop_bits()
    player.status = "Playing"
    await test_server()
    test_tray_app()
    bus.disconnect()
    print(f"\nAll {len(PASSED)} checks passed.")


if __name__ == "__main__":
    asyncio.run(main())

"""Linux medya kontrolü: MPRIS (D-Bus).

Spotify, tarayıcılar (YouTube Music, YouTube…), VLC, Rhythmbox, Elisa vb. MPRIS destekleyen her oynatıcı.
"""
import asyncio
import hashlib
import urllib.parse
import urllib.request
from pathlib import Path

from dbus_next import BusType, Message, MessageType, Variant
from dbus_next.aio import MessageBus

MPRIS = "org.mpris.MediaPlayer2."
OBJ = "/org/mpris/MediaPlayer2"
PLAYER = "org.mpris.MediaPlayer2.Player"
ROOT_IFACE = "org.mpris.MediaPlayer2"
PROPS = "org.freedesktop.DBus.Properties"

PRETTY = {
    "chromium": "Chromium", "chrome": "Chrome", "google-chrome": "Chrome", "firefox": "Firefox", "brave": "Brave",
    "edge": "Edge", "msedge": "Edge", "vivaldi": "Vivaldi", "opera": "Opera", "spotify": "Spotify", "vlc": "VLC",
    "rhythmbox": "Rhythmbox", "elisa": "Elisa", "strawberry": "Strawberry", "clementine": "Clementine",
    "audacious": "Audacious", "mpv": "mpv", "plasma-browser-integration": "Browser",
}


def _v(x):
    return x.value if isinstance(x, Variant) else x


def app_label(bus_name: str) -> str:
    base = bus_name[len(MPRIS):].split(".")[0] if bus_name.startswith(MPRIS) else bus_name
    return PRETTY.get(base.lower(), base[:1].upper() + base[1:])


def _sniff(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def _read_art(url: str) -> bytes | None:
    """mpris:artUrl -> görüntü baytları (file:// ya da http(s)://)."""
    try:
        u = urllib.parse.urlparse(url)
        if u.scheme == "file":
            p = Path(urllib.parse.unquote(u.path))
            return p.read_bytes() if p.is_file() and p.stat().st_size < 10_000_000 else None
        if u.scheme in ("http", "https"):
            req = urllib.request.Request(url, headers={"User-Agent": "MiniDesktop/1.1"})
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.read(10_000_000)
    except Exception:
        return None
    return None


class Media:
    def __init__(self):
        self.bus: MessageBus | None = None
        self.error = None
        self.preferred = None
        self.current = None
        self.art: bytes | None = None
        self.art_mime = "image/png"
        self.art_ver = ""
        self._art_url = None
        self._labels: dict[str, str] = {}
        self._trackid: dict[str, str] = {}

    async def start(self):
        try:
            self.bus = await MessageBus(bus_type=BusType.SESSION).connect()
            self.error = None
        except Exception as e:  # oturum D-Bus'ı yok (ör. SSH / servis olarak çalışma)
            self.bus = None
            self.error = f"D-Bus: {e}"

    async def _call(self, dest, iface, member, signature="", body=None, path=OBJ):
        msg = Message(destination=dest, path=path, interface=iface, member=member, signature=signature, body=body or [])
        reply = await asyncio.wait_for(self.bus.call(msg), 2)
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(f"{reply.error_name}: {reply.body}")
        return reply.body

    async def _players(self) -> list[str]:
        names = (await self._call("org.freedesktop.DBus", "org.freedesktop.DBus", "ListNames", path="/org/freedesktop/DBus"))[0]
        return sorted(n for n in names if n.startswith(MPRIS))

    async def _props(self, name: str) -> dict:
        raw = (await self._call(name, PROPS, "GetAll", "s", [PLAYER]))[0]
        return {k: _v(v) for k, v in raw.items()}

    async def _label(self, name: str) -> str:
        if name not in self._labels:
            try:
                self._labels[name] = str(_v((await self._call(name, PROPS, "Get", "ss", [ROOT_IFACE, "Identity"]))[0]))
            except Exception:
                self._labels[name] = app_label(name)
        return self._labels[name]

    def _pick(self, players: dict) -> str | None:
        if not players:
            return None
        if self.preferred in players:
            return self.preferred
        for n, p in players.items():
            if p.get("PlaybackStatus") == "Playing":
                return n
        if self.current in players:
            return self.current
        return next(iter(players))

    async def snapshot(self) -> dict:
        out = {"available": False, "sources": [], "preferred": self.preferred}
        if not self.bus or not self.bus.connected:
            await self.start()
            if not self.bus:
                out["error"] = self.error
                return out
        players = {}
        for n in await self._players():
            try:
                players[n] = await self._props(n)
            except Exception:
                continue
        out["sources"] = [{"id": n, "label": await self._label(n), "playing": p.get("PlaybackStatus") == "Playing"} for n, p in players.items()]
        cur = self.current = self._pick(players)
        if not cur:
            await self._update_art(None)
            return out
        p = players[cur]
        md = {k: _v(v) for k, v in (p.get("Metadata") or {}).items()}
        artists = md.get("xesam:artist") or []
        if isinstance(artists, str):
            artists = [artists]
        length = (md.get("mpris:length") or 0) / 1_000_000
        pos = (p.get("Position") or 0) / 1_000_000
        if md.get("mpris:trackid"):
            self._trackid[cur] = str(md["mpris:trackid"])
        await self._update_art(md.get("mpris:artUrl"))
        out.update(
            available=True,
            source=cur,
            source_label=await self._label(cur),
            title=str(md.get("xesam:title") or ""),
            artist=", ".join(str(a) for a in artists),
            album=str(md.get("xesam:album") or ""),
            playing=p.get("PlaybackStatus") == "Playing",
            position=max(0.0, min(pos, length) if length else pos),
            duration=max(0.0, length),
            can_seek=bool(p.get("CanSeek")) and length > 0,
            can_next=bool(p.get("CanGoNext")),
            can_prev=bool(p.get("CanGoPrevious")),
            art=self.art_ver if self.art else None,
        )
        return out

    async def _update_art(self, url):
        if url == self._art_url:
            return
        self._art_url = url
        data = await asyncio.to_thread(_read_art, url) if url else None
        if not data:
            self.art, self.art_ver = None, ""
            return
        self.art, self.art_mime, self.art_ver = data, _sniff(data), hashlib.md5(data).hexdigest()[:12]

    async def command(self, action: str, value=None):
        if action == "select_source":
            self.preferred = value or None
            return
        if not self.bus or not self.current:
            return
        cur = self.current
        if action == "toggle":
            await self._call(cur, PLAYER, "PlayPause")
        elif action == "next":
            await self._call(cur, PLAYER, "Next")
        elif action == "prev":
            await self._call(cur, PLAYER, "Previous")
        elif action == "seek" and value is not None:
            target = int(float(value) * 1_000_000)
            trackid = self._trackid.get(cur)
            if trackid:
                await self._call(cur, PLAYER, "SetPosition", "ox", [trackid, target])
            else:  # trackid vermeyen oynatıcılar: göreli atlama
                pos = int((await self._props(cur)).get("Position") or 0)
                await self._call(cur, PLAYER, "Seek", "x", [target - pos])

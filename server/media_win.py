"""Windows medya oturumları (GSMTC): Chrome/YT Music, Spotify vb. her oynatıcıyı kontrol eder."""
import hashlib
import time
from datetime import datetime, timezone

from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as Manager,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status,
)
from winrt.windows.storage.streams import Buffer, InputStreamOptions
from i18n import t

APP_NAMES = {
    "chrome": "Chrome",
    "msedge": "Edge",
    "firefox": "Firefox",
    "opera": "Opera",
    "brave": "Brave",
    "spotify": "Spotify",
    "applemusic": "Apple Music",
    "zunemusic": "Medya Oynatıcı",
    "vlc": "VLC",
}


def app_label(aumid: str) -> str:
    low = aumid.lower()
    for key, label in APP_NAMES.items():
        if key in low:
            return t(label)
    name = aumid.split("!")[-1]
    return name[:-4] if name.lower().endswith(".exe") else name


def _sniff(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


class Media:
    def __init__(self):
        self.mgr = None
        self.preferred = None  # seçilen kaynak (AUMID); None = otomatik
        self.art: bytes | None = None
        self.art_mime = "image/png"
        self.art_ver = ""
        self._art_key = None
        self._art_checked = 0.0

    async def start(self):
        self.mgr = await Manager.request_async()

    def _sessions(self):
        return list(self.mgr.get_sessions()) if self.mgr else []

    def _pick(self, sessions):
        if not sessions:
            return None
        if self.preferred:
            for s in sessions:
                if s.source_app_user_model_id == self.preferred:
                    return s
        for s in sessions:
            if s.get_playback_info().playback_status == Status.PLAYING:
                return s
        return self.mgr.get_current_session() or sessions[0]

    async def snapshot(self) -> dict:
        sessions = self._sessions()
        current = self._pick(sessions)
        out = {
            "available": False,
            "sources": [
                {
                    "id": s.source_app_user_model_id,
                    "label": app_label(s.source_app_user_model_id),
                    "playing": s.get_playback_info().playback_status == Status.PLAYING,
                }
                for s in sessions
            ],
            "preferred": self.preferred,
        }
        if current is None:
            return out

        props = await current.try_get_media_properties_async()
        pb = current.get_playback_info()
        tl = current.get_timeline_properties()
        playing = pb.playback_status == Status.PLAYING

        start = tl.start_time.total_seconds()
        end = tl.end_time.total_seconds()
        pos = tl.position.total_seconds()
        # Tarayıcılar konumu seyrek günceller; oynarken geçen süreyi ekle.
        if playing and tl.last_updated_time:
            elapsed = (datetime.now(timezone.utc) - tl.last_updated_time).total_seconds()
            if elapsed > 0:
                pos += elapsed
        if end > 0:
            pos = min(pos, end)

        await self._update_art(props)
        c = pb.controls
        out.update(
            available=True,
            source=current.source_app_user_model_id,
            source_label=app_label(current.source_app_user_model_id),
            title=props.title or "",
            artist=props.artist or props.album_artist or "",
            album=props.album_title or "",
            playing=playing,
            position=max(0.0, pos - start),
            duration=max(0.0, end - start),
            can_seek=bool(c.is_playback_position_enabled),
            can_next=bool(c.is_next_enabled),
            can_prev=bool(c.is_previous_enabled),
            art=self.art_ver if self.art else None,
        )
        return out

    async def _update_art(self, props):
        key = (props.title, props.artist, props.album_title)
        now = time.monotonic()
        if key == self._art_key and now - self._art_checked < 5:
            return
        if key != self._art_key:
            # Parça değişince kapak bazen geç güncellenir: 1.5 sn sonra tekrar bak.
            self._art_key = key
            self._art_checked = now - 3.5
        else:
            self._art_checked = now

        data = None
        try:
            if props.thumbnail:
                stream = await props.thumbnail.open_read_async()
                size = stream.size
                if size:
                    buf = Buffer(size)
                    await stream.read_async(buf, size, InputStreamOptions.READ_AHEAD)
                    data = bytes(buf)[: buf.length]
        except Exception:
            data = None

        if not data:
            self.art, self.art_ver = None, ""
            return
        ver = hashlib.md5(data).hexdigest()[:12]
        if ver != self.art_ver:
            self.art, self.art_mime, self.art_ver = data, _sniff(data), ver

    async def command(self, action: str, value=None):
        if action == "select_source":
            self.preferred = value or None
            return
        s = self._pick(self._sessions())
        if s is None:
            return
        if action == "toggle":
            await s.try_toggle_play_pause_async()
        elif action == "next":
            await s.try_skip_next_async()
        elif action == "prev":
            await s.try_skip_previous_async()
        elif action == "seek" and value is not None:
            start = s.get_timeline_properties().start_time.total_seconds()
            await s.try_change_playback_position_async(int((start + float(value)) * 10_000_000))

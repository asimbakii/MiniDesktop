"""Discord masaüstü istemcisine yerel RPC (named pipe) ile bağlanır.

Resmi yol: kendi Discord uygulamanın Client ID/Secret'ı ile, sadece senin hesabın için yetki alınır.
Sağladıkları: mikrofon/kulaklık (mute/deafen), bulunduğun ses kanalı + konuşanlar,
(deneysel) bildirim akışı.
"""
import asyncio
import json
import os
import sys
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from keys import KeyControl
from i18n import t

SCOPES_BASE = ["rpc", "rpc.voice.read", "rpc.voice.write"]
SCOPE_NOTIF = "rpc.notifications.read"
CHANNEL_EVENTS = ("VOICE_STATE_CREATE", "VOICE_STATE_UPDATE", "VOICE_STATE_DELETE", "SPEAKING_START", "SPEAKING_STOP")


class RPCError(Exception):
    pass


def avatar_url(user: dict) -> str:
    uid, av = user.get("id"), user.get("avatar")
    if uid and av:
        return f"https://cdn.discordapp.com/avatars/{uid}/{av}.png?size=64"
    try:
        idx = (int(uid) >> 22) % 6
    except Exception:
        idx = 0
    return f"https://cdn.discordapp.com/embed/avatars/{idx}.png"


def _unix_ipc_paths():
    """Linux/macOS: Discord'un IPC soketleri (normal, Flatpak ve Snap kurulumları)."""
    bases = []
    for var in ("XDG_RUNTIME_DIR", "TMPDIR", "TMP", "TEMP"):
        if os.environ.get(var):
            bases.append(os.environ[var])
    bases.append("/tmp")
    subdirs = ("", "app/com.discordapp.Discord", "app/com.discordapp.DiscordCanary", "snap.discord", "snap.discord-canary",
               ".flatpak/com.discordapp.Discord/xdg-run")
    out = []
    for b in dict.fromkeys(bases):
        for sub in subdirs:
            for i in range(10):
                p = os.path.join(b, sub, f"discord-ipc-{i}")
                if os.path.exists(p) and p not in out:
                    out.append(p)
    return out


class _Proto(asyncio.Protocol):
    def __init__(self, owner):
        self.owner = owner
        self.buf = b""

    def data_received(self, data):
        self.buf += data
        while len(self.buf) >= 8:
            op, length = struct.unpack("<II", self.buf[:8])
            if len(self.buf) < 8 + length:
                break
            payload = self.buf[8 : 8 + length]
            self.buf = self.buf[8 + length :]
            try:
                self.owner._on_frame(op, json.loads(payload))
            except Exception as e:  # pragma: no cover
                print("[discord] frame hatası:", e)

    def connection_lost(self, exc):
        self.owner._on_lost()


class DiscordRPC:
    def __init__(self, data_dir: Path, on_change):
        self.cfg_path = data_dir / "discord.json"
        try:
            self.cfg = json.loads(self.cfg_path.read_text("utf-8"))
        except Exception:
            self.cfg = {}
        self.on_change = on_change
        self.status = "not_configured"
        self.error = None
        self.user = None
        self.scopes: list[str] = []
        self.voice = {"mute": False, "deaf": False}
        self.channel = None
        self.members: dict[str, dict] = {}
        self.speaking: set[str] = set()
        self.notifications: dict[str, dict] = {}
        self._t = None
        self._pending: dict[str, asyncio.Future] = {}
        self._lost: asyncio.Future | None = None
        self._close_msg = None
        self._wake: asyncio.Event | None = None
        self._tasks: set = set()
        self.keys = KeyControl(data_dir)  # RPC kurulu değilse kısayol tuşu modu

    # ---------- dışa açık ----------
    def configured(self) -> bool:
        return bool(self.cfg.get("client_id") and self.cfg.get("client_secret"))

    def set_credentials(self, client_id: str, client_secret: str):
        self.cfg = {"client_id": client_id.strip(), "client_secret": client_secret.strip(), "redirect_uri": "http://localhost"}
        self._save()
        self.reconnect()

    def reset_auth(self):
        for k in ("access_token", "refresh_token", "expires_at"):
            self.cfg.pop(k, None)
        self.cfg.pop("notifications", None)
        self._save()
        self.reconnect()

    def reconnect(self):
        if self._t:
            self._t.close()
        if self._wake:
            self._wake.set()

    def control_mode(self) -> str | None:
        """Mikrofon/kulaklık nasıl kontrol ediliyor: 'rpc' (durum da okunur), 'keys' (sadece tuş gönderilir) ya da yok."""
        if self.status == "ready":
            return "rpc"
        if self.keys.cfg["enabled"]:
            return "keys"
        return None

    def state(self) -> dict:
        members = [dict(m, speaking=m["id"] in self.speaking) for m in self.members.values()]
        notes = sorted(self.notifications.values(), key=lambda n: -n["ts"])
        return {
            "control": self.control_mode(),
            "keys": self.keys.state(),
            "status": self.status,
            "error": self.error,
            "user": self.user,
            "mute": self.voice["mute"],
            "deaf": self.voice["deaf"],
            "channel": self.channel,
            "members": members,
            "notifications_enabled": SCOPE_NOTIF in self.scopes,
            "notifications": notes,
        }

    async def command(self, action: str, value=None):
        if action == "clear_notification":
            self.notifications.pop(str(value), None)
            self.on_change()
            return
        if action == "clear_all":
            self.notifications.clear()
            self.on_change()
            return
        if self.status != "ready":
            if self.keys.cfg["enabled"] and action in ("toggle_mute", "toggle_deaf"):
                await asyncio.to_thread(self.keys.toggle, "mute" if action == "toggle_mute" else "deaf")
                return
            raise RPCError(t("Discord bağlı değil."))
        if action == "toggle_mute":
            self._apply_voice(await self.cmd("SET_VOICE_SETTINGS", {"mute": not self.voice["mute"]}))
        elif action == "toggle_deaf":
            self._apply_voice(await self.cmd("SET_VOICE_SETTINGS", {"deaf": not self.voice["deaf"]}))
        elif action == "leave_voice":
            await self.cmd("SELECT_VOICE_CHANNEL", {"channel_id": None})

    # ---------- ana döngü ----------
    async def run(self):
        self._wake = asyncio.Event()
        while True:
            if not self.configured():
                self._set("not_configured")
            else:
                try:
                    await self._session()
                except FileNotFoundError:
                    self._set("disconnected")
                except Exception as e:
                    self._set("error", str(e))
                finally:
                    if self._t:
                        self._t.close()
                    self._t = None
                    self.channel, self.members, self.speaking = None, {}, set()
            try:
                await asyncio.wait_for(self._wake.wait(), 5)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()

    async def _session(self):
        loop = asyncio.get_running_loop()
        self._set("connecting")
        self._close_msg = None
        self._t = await self._connect()
        self._lost = loop.create_future()
        ready = loop.create_future()
        self._pending["__ready__"] = ready
        self._send(0, {"v": 1, "client_id": self.cfg["client_id"]})
        await asyncio.wait_for(ready, 10)

        await self._auth()
        vs = await self.cmd("GET_VOICE_SETTINGS")
        self._apply_voice(vs)
        await self.cmd("SUBSCRIBE", {}, evt="VOICE_SETTINGS_UPDATE")
        await self.cmd("SUBSCRIBE", {}, evt="VOICE_CHANNEL_SELECT")
        if SCOPE_NOTIF in self.scopes:
            try:
                await self.cmd("SUBSCRIBE", {}, evt="NOTIFICATION_CREATE")
            except RPCError:
                self.scopes.remove(SCOPE_NOTIF)
        await self._load_channel()
        self._set("ready")
        await self._lost

    async def _connect(self):
        loop = asyncio.get_running_loop()
        if sys.platform == "win32":
            for i in range(10):
                try:
                    transport, _ = await loop.create_pipe_connection(lambda: _Proto(self), rf"\\.\pipe\discord-ipc-{i}")
                    return transport
                except OSError:
                    continue
        else:
            for path in _unix_ipc_paths():
                try:
                    transport, _ = await loop.create_unix_connection(lambda: _Proto(self), path)
                    return transport
                except OSError:
                    continue
        raise FileNotFoundError(t("Discord açık değil"))

    async def _auth(self):
        tok = self.cfg.get("access_token")
        if tok and self.cfg.get("expires_at", 0) > time.time() + 60:
            try:
                return await self._authenticate(tok)
            except RPCError:
                pass
        if self.cfg.get("refresh_token"):
            try:
                await self._token({"grant_type": "refresh_token", "refresh_token": self.cfg["refresh_token"]})
                return await self._authenticate(self.cfg["access_token"])
            except Exception:
                pass

        self._set("authorizing")
        want_notif = self.cfg.get("notifications", False)  # mesajlar artık Social SDK'dan
        scopes = SCOPES_BASE + ([SCOPE_NOTIF] if want_notif else [])
        try:
            data = await self.cmd("AUTHORIZE", {"client_id": self.cfg["client_id"], "scopes": scopes}, timeout=180)
        except RPCError as e:
            if want_notif and "scope" in str(e).lower():
                self.cfg["notifications"] = False
                self._save()
                data = await self.cmd("AUTHORIZE", {"client_id": self.cfg["client_id"], "scopes": SCOPES_BASE}, timeout=180)
            else:
                raise
        await self._token(
            {
                "grant_type": "authorization_code",
                "code": data["code"],
                "redirect_uri": self.cfg.get("redirect_uri", "http://localhost"),
            }
        )
        await self._authenticate(self.cfg["access_token"])

    async def _authenticate(self, token):
        data = await self.cmd("AUTHENTICATE", {"access_token": token})
        u = data.get("user") or {}
        self.user = {"id": u.get("id"), "name": u.get("global_name") or u.get("username"), "username": u.get("username"), "avatar": avatar_url(u)}
        self.scopes = list(data.get("scopes") or [])

    async def _token(self, form):
        form = {**form, "client_id": self.cfg["client_id"], "client_secret": self.cfg["client_secret"]}
        data = await asyncio.to_thread(_post_token, form)
        self.cfg["access_token"] = data["access_token"]
        self.cfg["refresh_token"] = data.get("refresh_token", self.cfg.get("refresh_token"))
        self.cfg["expires_at"] = time.time() + int(data.get("expires_in", 604800))
        self._save()

    async def _load_channel(self):
        old = self.channel
        if old:
            for evt in CHANNEL_EVENTS:
                try:
                    await self.cmd("UNSUBSCRIBE", {"channel_id": old["id"]}, evt=evt)
                except Exception:
                    pass
        ch = await self.cmd("GET_SELECTED_VOICE_CHANNEL")
        self.members, self.speaking = {}, set()
        if not ch:
            self.channel = None
            self.on_change()
            return
        guild_name = None
        if ch.get("guild_id"):
            try:
                guild_name = (await self.cmd("GET_GUILD", {"guild_id": ch["guild_id"]})).get("name")
            except Exception:
                pass
        self.channel = {"id": ch["id"], "name": ch.get("name") or t("Özel arama"), "guild": guild_name}
        for vs in ch.get("voice_states") or []:
            self._upsert_member(vs)
        for evt in CHANNEL_EVENTS:
            try:
                await self.cmd("SUBSCRIBE", {"channel_id": ch["id"]}, evt=evt)
            except RPCError:
                pass
        self.on_change()

    # ---------- protokol ----------
    async def cmd(self, cmd, args=None, evt=None, timeout=10):
        if not self._t:
            raise RPCError(t("Discord bağlı değil."))
        nonce = str(uuid.uuid4())
        fut = asyncio.get_running_loop().create_future()
        self._pending[nonce] = fut
        payload = {"cmd": cmd, "args": args or {}, "nonce": nonce}
        if evt:
            payload["evt"] = evt
        self._send(1, payload)
        try:
            resp = await asyncio.wait_for(fut, timeout)
        finally:
            self._pending.pop(nonce, None)
        if resp.get("evt") == "ERROR":
            d = resp.get("data") or {}
            raise RPCError(f"{d.get('message') or t('Discord hatası')} ({d.get('code')})")
        return resp.get("data")

    def _send(self, op, payload):
        data = json.dumps(payload).encode()
        self._t.write(struct.pack("<II", op, len(data)) + data)

    def _on_frame(self, op, data):
        if op == 3:  # PING
            self._send(4, data)
        elif op == 2:  # CLOSE
            self._close_msg = f"{data.get('message')} ({data.get('code')})"
            if self._t:
                self._t.close()
        elif op == 1:
            if data.get("cmd") == "DISPATCH":
                if data.get("evt") == "READY":
                    fut = self._pending.pop("__ready__", None)
                    if fut and not fut.done():
                        fut.set_result(data)
                else:
                    self._on_event(data.get("evt"), data.get("data") or {})
            else:
                fut = self._pending.get(data.get("nonce"))
                if fut and not fut.done():
                    fut.set_result(data)

    def _on_lost(self):
        err = ConnectionError(self._close_msg or t("Discord bağlantısı kapandı"))
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(err)
        self._pending.clear()
        if self._lost and not self._lost.done():
            if self._close_msg:
                self._lost.set_exception(err)
            else:
                self._lost.set_result(None)
        self._t = None

    def _on_event(self, evt, data):
        if evt == "VOICE_SETTINGS_UPDATE":
            self._apply_voice(data)
        elif evt == "VOICE_CHANNEL_SELECT":
            task = asyncio.ensure_future(self._load_channel())
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        elif evt in ("VOICE_STATE_CREATE", "VOICE_STATE_UPDATE"):
            self._upsert_member(data)
        elif evt == "VOICE_STATE_DELETE":
            uid = (data.get("user") or {}).get("id")
            self.members.pop(uid, None)
            self.speaking.discard(uid)
        elif evt == "SPEAKING_START":
            self.speaking.add(str(data.get("user_id")))
        elif evt == "SPEAKING_STOP":
            self.speaking.discard(str(data.get("user_id")))
        elif evt == "NOTIFICATION_CREATE":
            self._add_notification(data)
        else:
            return
        self.on_change()

    # ---------- yardımcılar ----------
    def _apply_voice(self, vs):
        if vs:
            self.voice = {"mute": bool(vs.get("mute")), "deaf": bool(vs.get("deaf"))}
            self.on_change()

    def _upsert_member(self, vs):
        u = vs.get("user") or {}
        uid = u.get("id")
        if not uid:
            return
        st = vs.get("voice_state") or {}
        self.members[uid] = {
            "id": uid,
            "name": vs.get("nick") or u.get("global_name") or u.get("username"),
            "avatar": avatar_url(u),
            "muted": bool(st.get("self_mute") or st.get("mute")),
            "deaf": bool(st.get("self_deaf") or st.get("deaf")),
        }

    def _add_notification(self, data):
        msg = data.get("message") or {}
        author = msg.get("author") or {}
        key = str(data.get("channel_id") or author.get("id"))
        entry = self.notifications.get(key) or {
            "key": key,
            "title": data.get("title") or author.get("global_name") or author.get("username") or "Discord",
            "avatar": data.get("icon_url") or avatar_url(author),
            "count": 0,
        }
        entry["count"] += 1
        entry["last"] = (data.get("body") or msg.get("content") or "")[:160]
        entry["ts"] = time.time()
        self.notifications[key] = entry
        if len(self.notifications) > 30:
            oldest = min(self.notifications.values(), key=lambda n: n["ts"])
            self.notifications.pop(oldest["key"], None)

    def _set(self, status, error=None):
        if status != self.status or error != self.error:
            self.status, self.error = status, error
            if status != "ready":
                self.user = None if status in ("not_configured",) else self.user
            self.on_change()

    def _save(self):
        self.cfg_path.write_text(json.dumps(self.cfg, indent=2), "utf-8")


def _post_token(form: dict) -> dict:
    req = urllib.request.Request(
        "https://discord.com/api/oauth2/token",
        data=urllib.parse.urlencode(form).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "MiniDesktop/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        raise RPCError(t("Discord token alınamadı ({code}): {body}", code=e.code, body=body))

"""Discord Social SDK köprüsünü (bridge/build/dcbridge.exe) çalıştırır.

Sağladıkları: tüm Discord arkadaşları + çevrimiçi durumları, gelen DM'ler ve
kişi başına okunmamış sayacı (sayaç bizde tutulur; Discord'un okundu bilgisi SDK'da yok).
"""
import asyncio
import json
import os
import subprocess
import time
from pathlib import Path
from i18n import t

# MiniDesktop'un paylaşılan Discord uygulaması ("MiniDesktop Sosyal", Public Client).
# Kullanıcılar kendi uygulamalarını açmadan sadece Discord'da izin vererek bağlanır.
# Kendi uygulamanı kullanmak için yönetim panelinden ya da MINIDESKTOP_SOCIAL_APP_ID ile değiştirilebilir.
DEFAULT_APP_ID = os.environ.get("MINIDESKTOP_SOCIAL_APP_ID", "1573830953325830276")

STATUS_ORDER = {"online": 0, "streaming": 0, "idle": 1, "dnd": 2, "unknown": 3, "offline": 4}


class Social:
    def __init__(self, bridge_exe: Path, data_dir: Path, on_change):
        self.exe = bridge_exe
        self.cfg_path = data_dir / "social.json"
        self.token_path = data_dir / "social_token.txt"
        self.unread_path = data_dir / "unread.json"
        self.on_change = on_change
        try:
            self.cfg = json.loads(self.cfg_path.read_text("utf-8"))
        except Exception:
            self.cfg = {}
        if "enabled" not in self.cfg:  # eski kurulumlar: app_id girilmişse bağlıydı
            self.cfg["enabled"] = bool(self.cfg.get("app_id"))
        try:
            self.unread: dict[str, dict] = json.loads(self.unread_path.read_text("utf-8"))
        except Exception:
            self.unread = {}
        self.status = "not_configured"
        self.error = None
        self.me = None
        self.friends: dict[str, dict] = {}
        self.proc: asyncio.subprocess.Process | None = None
        self._wake: asyncio.Event | None = None

    # ---------- dışa açık ----------
    def app_id(self) -> str:
        return str(self.cfg.get("app_id") or DEFAULT_APP_ID).strip()

    def custom_app(self) -> bool:
        return bool(self.cfg.get("app_id")) and str(self.cfg["app_id"]) != DEFAULT_APP_ID

    def enabled(self) -> bool:
        return bool(self.cfg.get("enabled"))

    def _save_cfg(self):
        self.cfg_path.write_text(json.dumps(self.cfg), "utf-8")

    def connect(self, app_id: str | None = None):
        """Tek tıkla bağlan: paylaşılan uygulama (ya da verilen özel uygulama) ile Discord izni ister."""
        if app_id is not None:
            app_id = app_id.strip()
            if app_id and app_id != self.app_id():
                self.token_path.unlink(missing_ok=True)  # başka uygulamanın token'ı geçersiz
            self.cfg["app_id"] = app_id or None
        self.cfg["enabled"] = True
        self._save_cfg()
        self.restart()

    def disconnect(self):
        self.cfg["enabled"] = False
        self._save_cfg()
        self.token_path.unlink(missing_ok=True)
        self.me = None
        self.friends = {}
        self.restart()

    def bridge_built(self) -> bool:
        return self.exe.exists()

    def set_app_id(self, app_id: str):
        self.connect(app_id)

    def reauth(self):
        if self.proc and self.proc.stdin:
            try:
                self.proc.stdin.write(b"reauth\n")
            except Exception:
                pass
        else:
            self.token_path.unlink(missing_ok=True)
            self.restart()

    def restart(self):
        if self.proc and self.proc.returncode is None:
            try:
                self.proc.stdin.write(b"quit\n")
            except Exception:
                self.proc.kill()
        if self._wake:
            self._wake.set()

    def state(self) -> dict:
        friends = sorted(self.friends.values(), key=lambda f: (STATUS_ORDER.get(f["status"], 3), f["name"].lower()))
        unread = sorted(self.unread.values(), key=lambda u: -u["ts"])
        for u in unread:  # güncel avatar/durum
            f = self.friends.get(u["id"])
            u["status"] = f["status"] if f else "unknown"
        return {
            "status": self.status,
            "error": self.error,
            "me": self.me,
            "friends": friends,
            "online": sum(1 for f in friends if f["status"] not in ("offline", "unknown")),
            "unread": unread,
            "unread_total": sum(u["count"] for u in unread),
            "bridge": self.bridge_built(),
        }

    async def command(self, action: str, value=None):
        if action == "clear_unread":
            self.unread.pop(str(value), None)
        elif action == "clear_all":
            self.unread.clear()
        else:
            return
        self._save_unread()
        self.on_change()

    # ---------- süreç yönetimi ----------
    async def run(self):
        self._wake = asyncio.Event()
        while True:
            if not self.enabled() or not self.app_id():
                self._set("not_configured")
            elif not self.bridge_built():
                self._set("no_bridge")
            else:
                await self._run_bridge()
            try:
                await asyncio.wait_for(self._wake.wait(), 5)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()

    async def _run_bridge(self):
        self._set("starting")
        try:
            self.proc = await asyncio.create_subprocess_exec(
                str(self.exe),
                self.app_id(),
                str(self.token_path),
                cwd=str(self.exe.parent),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as e:
            self._set("error", t("Köprü başlatılamadı: {e}", e=e))
            return
        try:
            while True:
                line = await self.proc.stdout.readline()
                if not line:
                    break
                try:
                    self._on_event(json.loads(line.decode("utf-8", "replace")))
                except json.JSONDecodeError:
                    pass
        finally:
            code = await self.proc.wait()
            self.proc = None
            self.friends = {}
            if self.status != "error":
                self._set("error" if code else "stopped", t("Köprü kapandı (kod {code})", code=code) if code else None)

    def _on_event(self, ev: dict):
        t = ev.get("t")
        if t == "status":
            self._set(ev.get("status"), ev.get("error") or None)
            return
        if t == "self":
            self.me = ev.get("user")
        elif t == "friends":
            self.friends = {f["id"]: f for f in ev.get("friends", [])}
        elif t == "message":
            self._on_message(ev)
        elif t == "log":
            print("[social]", ev.get("msg", "")[:300])
            return
        self.on_change()

    def _on_message(self, ev: dict):
        partner = str(ev.get("partner"))
        if ev.get("self"):
            # PC'den cevap verdiysen o kişinin sayacını sıfırla
            if self.unread.pop(partner, None):
                self._save_unread()
            return
        author = ev.get("author") or {}
        f = self.friends.get(partner, {})
        entry = self.unread.get(partner) or {"id": partner, "count": 0}
        entry.update(
            name=author.get("name") or f.get("name") or "Bilinmeyen",
            avatar=author.get("avatar") or f.get("avatar"),
            last=(ev.get("content") or "")[:160],
            ts=time.time(),
        )
        entry["count"] += 1
        self.unread[partner] = entry
        self._save_unread()

    def _save_unread(self):
        try:
            self.unread_path.write_text(json.dumps(self.unread, ensure_ascii=False), "utf-8")
        except Exception:
            pass

    def _set(self, status, error=None):
        if status != self.status or error != self.error:
            self.status, self.error = status, error
            self.on_change()

    async def stop(self):
        if self.proc and self.proc.returncode is None:
            try:
                self.proc.stdin.write(b"quit\n")
                await asyncio.wait_for(self.proc.wait(), 2)
            except Exception:
                self.proc.kill()

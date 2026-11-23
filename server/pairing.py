"""Tablet eşleme: PC'de görünen 6 haneli PIN ile cihaz başına kalıcı token."""
import hashlib
import json
import secrets
import time
from pathlib import Path


def device_id(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:10]


class Pairing:
    def __init__(self, data_dir: Path):
        self.path = data_dir / "devices.json"
        try:
            self.devices: dict = json.loads(self.path.read_text("utf-8"))
        except Exception:
            self.devices = {}
        self.pin = f"{secrets.randbelow(1_000_000):06d}"
        self._fails = 0
        self._locked_until = 0.0
        self.last_seen: dict[str, float] = {}

    def _save(self):
        self.path.write_text(json.dumps(self.devices, ensure_ascii=False, indent=2), "utf-8")

    def pair(self, pin: str, name: str) -> str:
        now = time.time()
        if now < self._locked_until:
            raise PermissionError("Çok fazla hatalı deneme. 1 dakika bekleyip tekrar dene.")
        if not secrets.compare_digest(str(pin).strip(), self.pin):
            self._fails += 1
            if self._fails >= 5:
                self._fails = 0
                self._locked_until = now + 60
            raise PermissionError("PIN yanlış.")
        self._fails = 0
        token = secrets.token_urlsafe(32)
        self.devices[token] = {"name": (name or "Tablet")[:60], "created": int(now)}
        self._save()
        return token

    def check(self, token: str | None) -> bool:
        if token and token in self.devices:
            self.last_seen[token] = time.time()
            return True
        return False

    def list(self):
        return [
            {"id": device_id(t), "name": d["name"], "created": d["created"], "last_seen": self.last_seen.get(t)}
            for t, d in self.devices.items()
        ]

    def revoke(self, dev_id: str) -> str | None:
        for t in list(self.devices):
            if device_id(t) == dev_id:
                del self.devices[t]
                self._save()
                return t
        return None

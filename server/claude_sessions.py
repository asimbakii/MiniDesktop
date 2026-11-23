"""Claude Code oturumlarının durumu (Claude Code hook'larından beslenir).

tools/claude_hook.py her hook olayında JSON'u /api/hooks/claude adresine yollar.
Kurulum: yönetim sayfası -> "Claude Code entegrasyonu" (~/.claude/settings.json'a hook ekler).
"""
import json
import shutil
import time
from pathlib import Path

import paths
from i18n import EN, t

HOOK_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "Notification", "Stop", "SessionEnd")
MATCHER_EVENTS = ("PreToolUse",)
SETTINGS = Path.home() / ".claude" / "settings.json"
STALE_AFTER = 6 * 3600


def _tool_label(ev: dict) -> str:
    name = ev.get("tool_name") or "Araç"
    if name.startswith("mcp__"):  # mcp__sunucu__arac -> "sunucu: arac"
        parts = name.split("__")
        name = f"{parts[1]}: {'__'.join(parts[2:])}" if len(parts) > 2 else name
    inp = ev.get("tool_input") or {}
    if name == "Bash":
        return f"$ {str(inp.get('command', '')).splitlines()[0][:80]}" if inp.get("command") else "Bash"
    for key in ("file_path", "notebook_path", "path"):
        if inp.get(key):
            return f"{name}: {Path(str(inp[key])).name}"
    if inp.get("pattern"):
        return f"{name}: {str(inp['pattern'])[:60]}"
    if inp.get("url"):
        return f"{name}: {str(inp['url'])[:60]}"
    if inp.get("description"):
        return f"{name}: {str(inp['description'])[:60]}"
    return name


def _tr_detail(d: str) -> str:
    """Durum metinleri Türkçe saklanır; gönderirken seçili dile çevrilir."""
    if d.startswith("İzin bekliyor:"):
        return t("İzin bekliyor:") + d[len("İzin bekliyor:"):]
    return t(d) if d in EN else d


class ClaudeSessions:
    def __init__(self, on_change):
        self.on_change = on_change
        self.sessions: dict[str, dict] = {}

    # ---------- hook olayları ----------
    def handle(self, ev: dict):
        sid = str(ev.get("session_id") or "")
        name = ev.get("hook_event_name")
        if not sid or not name:
            return
        now = time.time()
        if name == "SessionEnd":
            self.sessions.pop(sid, None)
            self.on_change()
            return
        s = self.sessions.get(sid)
        if s is None:
            s = self.sessions[sid] = {"id": sid, "state": "idle", "detail": "", "prompt": "", "since": now, "started": now, "tools": 0}
        cwd = ev.get("cwd")
        if cwd:
            s["cwd"] = cwd
            s["project"] = Path(cwd).name
        state = s["state"]
        if name == "SessionStart":
            state, s["detail"] = "idle", "Oturum açıldı"
        elif name == "UserPromptSubmit":
            state = "working"
            s["prompt"] = str(ev.get("prompt") or "")[:200]
            s["detail"] = "Düşünüyor…"
            s["tools"] = 0
        elif name == "PreToolUse":
            state = "working"
            s["detail"] = _tool_label(ev)
            s["tools"] += 1
        elif name == "Notification":
            msg = str(ev.get("message") or "")
            if "permission" in msg.lower():
                state, s["detail"] = "permission", msg.replace("Claude needs your permission to use", "İzin bekliyor:")
            else:
                state, s["detail"] = "waiting", "Cevabını bekliyor"
        elif name == "Stop":
            state, s["detail"] = "done", "Tamamlandı"
        if state != s["state"]:
            s["state"] = state
            s["since"] = now
        s["updated"] = now
        self.on_change()

    def dismiss(self, sid: str):
        self.sessions.pop(str(sid), None)
        self.on_change()

    def cwds(self) -> list[str]:
        return [s["cwd"] for s in self.sessions.values() if s.get("cwd")]

    def state(self) -> dict:
        now = time.time()
        for sid in [k for k, s in self.sessions.items() if now - s.get("updated", 0) > STALE_AFTER]:
            del self.sessions[sid]
        order = {"permission": 0, "waiting": 1, "working": 2, "done": 3, "idle": 4}
        items = sorted(self.sessions.values(), key=lambda s: (order.get(s["state"], 5), -s.get("updated", 0)))
        items = [dict(s, detail=_tr_detail(s.get("detail", ""))) for s in items]
        return {"installed": self.hook_installed(), "sessions": items}

    # ---------- kurulum ----------
    def hook_command(self) -> str:
        return paths.hook_command()

    @staticmethod
    def _is_ours(hook: dict) -> bool:
        cmd = str(hook.get("command", ""))
        return "claude_hook.py" in cmd or "--claude-hook" in cmd

    def hook_current(self) -> bool:
        """Kurulu hook'lar bu kopyanın komutunu mu gösteriyor? (kurulum yeri değiştiyse yenilenmeli)"""
        try:
            hooks = self._load().get("hooks", {})
        except Exception:
            return False
        cmd = self.hook_command()
        return any(h.get("command") == cmd for g in hooks.get("PreToolUse", []) for h in g.get("hooks", []))

    def _load(self) -> dict:
        try:
            return json.loads(SETTINGS.read_text("utf-8"))
        except FileNotFoundError:
            return {}

    def hook_installed(self) -> bool:
        try:
            hooks = self._load().get("hooks", {})
        except Exception:
            return False
        return all(any(self._is_ours(h) for g in hooks.get(e, []) for h in g.get("hooks", [])) for e in HOOK_EVENTS)

    def install(self):
        data = self._load()
        if SETTINGS.exists():
            shutil.copy2(SETTINGS, SETTINGS.with_suffix(".json.minidesktop-backup"))
        hooks = self._strip(data.get("hooks", {}))
        cmd = {"type": "command", "command": self.hook_command(), "timeout": 5}
        for e in HOOK_EVENTS:
            group = {"hooks": [cmd]}
            if e in MATCHER_EVENTS:
                group = {"matcher": "*", **group}
            hooks.setdefault(e, []).append(group)
        data["hooks"] = hooks
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")

    def uninstall(self):
        data = self._load()
        if "hooks" not in data:
            return
        shutil.copy2(SETTINGS, SETTINGS.with_suffix(".json.minidesktop-backup"))
        hooks = self._strip(data["hooks"])
        if hooks:
            data["hooks"] = hooks
        else:
            data.pop("hooks")
        SETTINGS.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")

    def _strip(self, hooks: dict) -> dict:
        """Bizim eklediğimiz hook'ları çıkar, kullanıcının diğer hook'larına dokunma."""
        out = {}
        for event, groups in hooks.items():
            kept = []
            for g in groups:
                hs = [h for h in g.get("hooks", []) if not self._is_ours(h)]
                if hs:
                    kept.append({**g, "hooks": hs})
            if kept:
                out[event] = kept
        return out

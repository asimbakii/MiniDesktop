"""Geliştirici modu: git/GitHub, komut butonları, port & süreç izleyici, pano & snippet'ler."""
import asyncio
import collections
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import secrets
import subprocess
import time
import webbrowser
from pathlib import Path

import psutil
from i18n import t

NO_WINDOW = subprocess.CREATE_NO_WINDOW
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07")


# =====================================================================
# Ayarlar (data/devconfig.json) — sadece yönetim sayfasından değişir
# =====================================================================
class DevConfig:
    def __init__(self, data_dir: Path):
        self.path = data_dir / "devconfig.json"
        self.data = {"repos": [], "commands": [], "snippets": []}
        try:
            self.data.update(json.loads(self.path.read_text("utf-8")))
        except Exception:
            pass

    def update(self, data: dict):
        repos = [str(Path(r.strip())) for r in data.get("repos", []) if str(r).strip()]
        for r in repos:
            if not Path(r).is_dir():
                raise ValueError(t("Klasör bulunamadı: {r}", r=r))
        cmds = []
        for c in data.get("commands", []):
            name, cmd = str(c.get("name", "")).strip(), str(c.get("cmd", "")).strip()
            if not name or not cmd:
                continue
            cwd = str(c.get("cwd", "")).strip()
            if cwd and not Path(cwd).is_dir():
                raise ValueError(t("Komut klasörü bulunamadı: {cwd}", cwd=cwd))
            cmds.append({"id": c.get("id") or secrets.token_hex(4), "name": name[:40], "cmd": cmd, "cwd": cwd})
        snips = []
        for s in data.get("snippets", []):
            name, text = str(s.get("name", "")).strip(), str(s.get("text", ""))
            if name and text:
                snips.append({"id": s.get("id") or secrets.token_hex(4), "name": name[:40], "text": text})
        self.data = {"repos": repos, "commands": cmds, "snippets": snips}
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), "utf-8")

    def command(self, cid):
        return next((c for c in self.data["commands"] if c["id"] == cid), None)

    def snippet(self, sid):
        return next((s for s in self.data["snippets"] if s["id"] == sid), None)


# =====================================================================
# Git & GitHub
# =====================================================================
def _run(args, cwd=None, timeout=8) -> str:
    r = subprocess.run(args, cwd=cwd, capture_output=True, timeout=timeout, creationflags=NO_WINDOW)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "replace").strip()[:200])
    return r.stdout.decode("utf-8", "replace")


def _git(path, *args) -> str:
    return _run(["git", "-C", path, *args])


def repo_root(path: str) -> str | None:
    try:
        return str(Path(_git(path, "rev-parse", "--show-toplevel").strip()))
    except Exception:
        return None


def repo_info(path: str) -> dict:
    info = {"path": path, "name": Path(path).name, "branch": "?", "ahead": 0, "behind": 0,
            "staged": 0, "changed": 0, "untracked": 0, "conflicts": 0}
    for line in _git(path, "status", "--porcelain=v2", "--branch").splitlines():
        if line.startswith("# branch.head "):
            info["branch"] = line[14:]
        elif line.startswith("# branch.ab "):
            a, b = line[12:].split()
            info["ahead"], info["behind"] = int(a), abs(int(b))
        elif line[:2] in ("1 ", "2 "):
            xy = line[2:4]
            info["staged"] += xy[0] != "."
            info["changed"] += xy[1] != "."
        elif line.startswith("? "):
            info["untracked"] += 1
        elif line.startswith("u "):
            info["conflicts"] += 1
    try:
        h, subj, rel = _git(path, "log", "-1", "--format=%h%x1f%s%x1f%cr").strip().split("\x1f")
        info["last"] = {"hash": h, "subject": subj[:90], "when": rel}
    except Exception:
        info["last"] = None
    try:
        url = _git(path, "remote", "get-url", "origin").strip()
        m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
        info["slug"] = m.group(1) if m else None
    except Exception:
        info["slug"] = None
    return info


def _gh_json(args, cwd=None):
    return json.loads(_run(["gh", *args], cwd=cwd, timeout=20) or "null")


class GitWatch:
    def __init__(self, cfg: DevConfig, extra_paths, active, on_change):
        self.cfg, self.extra_paths, self.active, self.on_change = cfg, extra_paths, active, on_change
        self.repos: list[dict] = []
        self.gh = {"available": bool(shutil_which("gh")), "review": [], "mine": [], "ci": {}, "error": None, "updated": 0}
        self._root_cache: dict[str, str | None] = {}

    def paths(self) -> list[str]:
        out = []
        for p in list(self.cfg.data["repos"]) + list(self.extra_paths()):
            if p not in self._root_cache:
                self._root_cache[p] = repo_root(p)
            root = self._root_cache[p]
            if root and root not in out:
                out.append(root)
        return out

    async def run(self):
        last_gh = 0.0
        while True:
            if self.active():
                try:
                    self.repos = await asyncio.to_thread(self._local)
                except Exception:
                    pass
                if self.gh["available"] and time.time() - last_gh > 60:
                    last_gh = time.time()
                    await asyncio.to_thread(self._github)
                self.on_change()
                await asyncio.sleep(8)
            else:
                await asyncio.sleep(2)

    def refresh_soon(self):
        self.gh["updated"] = 0

    def _local(self):
        out = []
        for p in self.paths():
            try:
                out.append(repo_info(p))
            except Exception as e:
                out.append({"path": p, "name": Path(p).name, "error": str(e)[:120]})
        return out

    def _github(self):
        fields = "repository,title,number,url,updatedAt,isDraft"
        try:
            self.gh["review"] = _gh_json(["search", "prs", "--review-requested=@me", "--state=open", "--json", fields, "--limit", "8"])
            self.gh["mine"] = _gh_json(["search", "prs", "--author=@me", "--state=open", "--json", fields, "--limit", "8"])
            ci = {}
            for r in self.repos:
                if r.get("slug") and r.get("branch") not in (None, "?", "(detached)"):
                    runs = _gh_json(["run", "list", "-R", r["slug"], "--branch", r["branch"], "--limit", "1",
                                     "--json", "status,conclusion,workflowName,url,displayTitle,createdAt"])
                    if runs:
                        ci[r["path"]] = runs[0]
            self.gh["ci"] = ci
            self.gh["error"] = None
        except Exception as e:
            self.gh["error"] = str(e)[:160]
        self.gh["updated"] = time.time()

    def state(self) -> dict:
        repos = [dict(r, ci=self.gh["ci"].get(r["path"])) for r in self.repos]
        return {"repos": repos, "gh": {k: self.gh[k] for k in ("available", "review", "mine", "error", "updated")}}

    def open_repo(self, path: str):
        if path not in [r["path"] for r in self.repos]:
            raise ValueError(t("Bilinmeyen repo"))
        subprocess.Popen(f'code "{path}"', shell=True, creationflags=NO_WINDOW)

    def open_url(self, url: str):
        known = {p["url"] for p in self.gh["review"] + self.gh["mine"]} | {c["url"] for c in self.gh["ci"].values()}
        if url not in known or not url.startswith("https://github.com/"):
            raise ValueError(t("Bilinmeyen bağlantı"))
        webbrowser.open(url)


def shutil_which(name):
    import shutil
    return shutil.which(name)


# =====================================================================
# Komut butonları
# =====================================================================
def _oem_codec():
    try:
        return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
    except Exception:
        return "cp857"


OEM = _oem_codec()


def _decode(b: bytes) -> str:
    try:
        s = b.decode("utf-8")
    except UnicodeDecodeError:
        s = b.decode(OEM, "replace")
    s = ANSI.sub("", s.rstrip("\r\n"))
    return s.split("\r")[-1]  # ilerleme çubuklarının son hali


class Commands:
    def __init__(self, cfg: DevConfig, on_change):
        self.cfg, self.on_change = cfg, on_change
        self.runs: dict[str, dict] = {}

    async def start(self, cid: str):
        c = self.cfg.command(cid)
        if not c:
            raise ValueError(t("Bilinmeyen komut"))
        run = self.runs.get(cid)
        if run and run["status"] == "running":
            return
        env = {**os.environ, "NO_COLOR": "1", "FORCE_COLOR": "0", "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
        proc = await asyncio.create_subprocess_shell(
            c["cmd"], cwd=c["cwd"] or None, env=env,
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            creationflags=NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        run = self.runs[cid] = {"status": "running", "code": None, "started": time.time(), "ended": None,
                                "lines": collections.deque(maxlen=200), "proc": proc}
        run["lines"].append(f"> {c['cmd']}")
        self.on_change()
        asyncio.ensure_future(self._pump(cid, run))

    async def _pump(self, cid, run):
        proc = run["proc"]
        last = 0.0
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            run["lines"].append(_decode(line))
            if time.time() - last > 0.3:
                last = time.time()
                self.on_change()
        code = await proc.wait()
        run.update(status="ok" if code == 0 else ("stopped" if run.get("stopping") else "fail"), code=code, ended=time.time(), proc=None)
        run["lines"].append(t("[çıkış kodu {code}]", code=code))
        self.on_change()

    async def stop(self, cid: str):
        run = self.runs.get(cid)
        if not run or run["status"] != "running" or not run["proc"]:
            return
        run["stopping"] = True
        try:
            parent = psutil.Process(run["proc"].pid)
            for ch in parent.children(recursive=True):
                ch.kill()
            parent.kill()
        except psutil.NoSuchProcess:
            pass

    async def stop_all(self):
        for cid in list(self.runs):
            await self.stop(cid)

    def state(self) -> list:
        out = []
        for c in self.cfg.data["commands"]:
            r = self.runs.get(c["id"]) or {}
            out.append({
                "id": c["id"], "name": c["name"], "cmd": c["cmd"], "cwd": c["cwd"],
                "status": r.get("status", "idle"), "code": r.get("code"),
                "started": r.get("started"), "ended": r.get("ended"),
                "tail": list(r.get("lines", []))[-14:],
            })
        return out


# =====================================================================
# Port & süreç izleyici
# =====================================================================
SYSTEM_PROCS = {"system", "system idle process", "idle", "registry", "smss.exe", "csrss.exe", "wininit.exe",
                "services.exe", "lsass.exe", "svchost.exe", "spoolsv.exe", "winlogon.exe", "memory compression",
                "fontdrvhost.exe", "dwm.exe", "secure system", "lsaiso.exe", "mdnsresponder.exe"}
# Geliştirme süreçleri: tam ad (uzantısız) ya da önek eşleşmesi
DEV_EXACT = {"node", "python", "pythonw", "py", "java", "javaw", "dotnet", "php", "php-cgi", "ruby", "go", "gopls",
             "deno", "bun", "nginx", "httpd", "uvicorn", "gunicorn", "code", "cargo", "esbuild", "msbuild", "devenv",
             "iisexpress", "claude", "pwsh", "bash", "redis-server", "mongod", "mysqld", "mariadbd", "sqlservr"}
DEV_PREFIX = ("docker", "com.docker", "wsl", "vmmem", "postgres", "rust-analyzer", "idea", "pycharm", "webstorm",
              "rider", "clion", "goland", "datagrip", "gradle", "kotlin", "vite", "next-", "tsserver")


def _is_dev(name: str) -> bool:
    n = name.lower()
    stem = n[:-4] if n.endswith(".exe") else n
    return stem in DEV_EXACT or any(stem.startswith(d) for d in DEV_PREFIX)


class SysMon:
    def __init__(self, active, on_change):
        self.active, self.on_change = active, on_change
        self.ports: list = []
        self.procs: list = []
        self._cache: dict[int, psutil.Process] = {}
        self._denied: set[int] = set()  # erişilemeyen süreçler (tekrar denenmez)
        self._ncpu = psutil.cpu_count() or 1

    async def run(self):
        while True:
            if self.active():
                try:
                    self.ports, self.procs = await asyncio.to_thread(self._scan)
                    self.on_change()
                except Exception:
                    pass
                await asyncio.sleep(5)  # tarama ~0.5 sn sürüyor; sadece geliştirici modunda çalışır
            else:
                await asyncio.sleep(2)

    def _scan(self):
        names = {}
        groups: dict[str, dict] = {}
        alive = set()
        for p in psutil.process_iter(["name"]):
            pid = p.pid
            alive.add(pid)
            name = p.info.get("name") or "?"
            names[pid] = name
            if pid in self._denied or pid in (0, 4) or name.lower() in SYSTEM_PROCS:
                continue
            proc = self._cache.get(pid)
            if proc is None:
                self._cache[pid] = proc = p
                try:
                    proc.cpu_percent(None)
                    proc.memory_info()
                except (psutil.AccessDenied, psutil.ZombieProcess):
                    self._denied.add(pid)
                except Exception:
                    pass
                continue
            try:
                cpu = proc.cpu_percent(None) / self._ncpu
                rss = proc.memory_info().rss
            except (psutil.AccessDenied, psutil.ZombieProcess):
                self._denied.add(pid)
                continue
            except Exception:
                continue
            g = groups.setdefault(name, {"name": name, "cpu": 0.0, "rss": 0, "count": 0, "pids": [], "dev": _is_dev(name)})
            g["cpu"] += cpu
            g["rss"] += rss
            g["count"] += 1
            g["pids"].append(pid)
        for pid in list(self._cache):
            if pid not in alive:
                del self._cache[pid]
        self._denied &= alive
        procs = sorted(groups.values(), key=lambda g: -g["cpu"])[:30]
        for g in procs:
            g["cpu"] = round(g["cpu"], 1)

        ports = {}
        for c in psutil.net_connections(kind="tcp"):
            if c.status != psutil.CONN_LISTEN or not c.laddr or c.laddr.port < 1024:
                continue
            pname = names.get(c.pid, "?")
            if pname.lower() in SYSTEM_PROCS or c.pid in (0, 4, None):
                continue
            port = c.laddr.port
            if port in ports:
                continue
            ports[port] = {"port": port, "ip": c.laddr.ip, "pid": c.pid, "name": pname, "dev": _is_dev(pname),
                           "local_only": c.laddr.ip in ("127.0.0.1", "::1")}
        return sorted(ports.values(), key=lambda p: (not p["dev"], p["port"])), procs

    def state(self) -> dict:
        return {"ports": self.ports, "procs": self.procs}

    def open_port(self, port: int):
        if port not in {p["port"] for p in self.ports}:
            raise ValueError(t("Bilinmeyen port"))
        webbrowser.open(f"http://localhost:{port}")

    def kill(self, pids: list[int]):
        known = {pid for g in self.procs for pid in g["pids"]} | {p["pid"] for p in self.ports}
        me = os.getpid()
        killed = 0
        for pid in pids:
            pid = int(pid)
            if pid not in known or pid == me or pid in (0, 4):
                continue
            try:
                p = psutil.Process(pid)
                if p.name().lower() in SYSTEM_PROCS:
                    continue
                p.kill()
                killed += 1
            except psutil.NoSuchProcess:
                pass
        return killed


# =====================================================================
# Pano (clipboard) & snippet'ler
# =====================================================================
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.OpenClipboard.argtypes = [wt.HWND]
user32.OpenClipboard.restype = wt.BOOL
user32.GetClipboardData.argtypes = [wt.UINT]
user32.GetClipboardData.restype = wt.HANDLE
user32.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]
user32.SetClipboardData.restype = wt.HANDLE
user32.IsClipboardFormatAvailable.argtypes = [wt.UINT]
user32.RegisterClipboardFormatW.argtypes = [wt.LPCWSTR]
user32.RegisterClipboardFormatW.restype = wt.UINT
user32.GetClipboardSequenceNumber.restype = wt.DWORD
kernel32.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wt.HGLOBAL
kernel32.GlobalLock.argtypes = [wt.HGLOBAL]
kernel32.GlobalLock.restype = wt.LPVOID
kernel32.GlobalUnlock.argtypes = [wt.HGLOBAL]
kernel32.GlobalSize.argtypes = [wt.HGLOBAL]
kernel32.GlobalSize.restype = ctypes.c_size_t
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
# Şifre yöneticileri bu formatları ekler: bu içerikleri geçmişe alma
_PRIVATE = [user32.RegisterClipboardFormatW(n) for n in ("ExcludeClipboardContentFromMonitorProcessing", "Clipboard Viewer Ignore")]
_CAN_INCLUDE = user32.RegisterClipboardFormatW("CanIncludeInClipboardHistory")


def _open_clipboard():
    for _ in range(20):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.02)
    return False


def clipboard_get() -> str | None:
    if any(user32.IsClipboardFormatAvailable(f) for f in _PRIVATE):
        return None
    if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT) or not _open_clipboard():
        return None
    try:
        if user32.IsClipboardFormatAvailable(_CAN_INCLUDE):
            h = user32.GetClipboardData(_CAN_INCLUDE)
            p = kernel32.GlobalLock(h) if h else None
            if p:
                allowed = ctypes.c_uint32.from_address(p).value
                kernel32.GlobalUnlock(h)
                if allowed == 0:
                    return None
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return None
        p = kernel32.GlobalLock(h)
        if not p:
            return None
        try:
            return ctypes.wstring_at(p)
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def clipboard_set(text: str):
    data = (text + "\0").encode("utf-16-le")
    if not _open_clipboard():
        raise RuntimeError(t("Pano şu an kullanımda, tekrar dene."))
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        p = kernel32.GlobalLock(h)
        ctypes.memmove(p, data, len(data))
        kernel32.GlobalUnlock(h)
        if not user32.SetClipboardData(CF_UNICODETEXT, h):
            raise RuntimeError(t("Panoya yazılamadı."))
    finally:
        user32.CloseClipboard()


class Clipboard:
    """PC panosundaki son metinler (sadece bellekte; şifre yöneticisi içerikleri atlanır)."""

    def __init__(self, cfg: DevConfig, active, on_change):
        self.cfg, self.active, self.on_change = cfg, active, on_change
        self.history: collections.deque = collections.deque(maxlen=12)
        self._seq = None

    async def run(self):
        while True:
            if self.active():
                seq = user32.GetClipboardSequenceNumber()
                if seq != self._seq:
                    self._seq = seq
                    try:
                        text = await asyncio.to_thread(clipboard_get)
                    except Exception:
                        text = None
                    if text and text.strip() and (not self.history or self.history[0]["text"] != text):
                        self.history.appendleft({"id": secrets.token_hex(4), "text": text[:4000], "ts": time.time()})
                        self.on_change()
                await asyncio.sleep(1)
            else:
                await asyncio.sleep(2)

    async def set(self, text: str):
        await asyncio.to_thread(clipboard_set, str(text)[:100000])

    async def copy_history(self, hid: str):
        item = next((h for h in self.history if h["id"] == hid), None)
        if item:
            await self.set(item["text"])

    async def copy_snippet(self, sid: str):
        s = self.cfg.snippet(sid)
        if not s:
            raise ValueError(t("Bilinmeyen snippet"))
        await self.set(s["text"])

    def clear(self):
        self.history.clear()
        self.on_change()

    def state(self) -> dict:
        return {
            "history": [{"id": h["id"], "text": h["text"][:300], "ts": h["ts"], "long": len(h["text"]) > 300} for h in self.history],
            "snippets": [{"id": s["id"], "name": s["name"], "preview": s["text"][:80]} for s in self.cfg.data["snippets"]],
        }

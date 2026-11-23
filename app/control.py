"""MiniDesktop kontrol uygulaması.

Sunucuyu ayrı bir süreç olarak başlatır/durdurur, tablet adresini + QR'ı + PIN'i ve
bağlantı durumlarını gösterir. Pencere kapatılınca sistem tepsisinde çalışmaya devam eder.
"""
import ctypes
import json
import queue
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
import winreg
from pathlib import Path

import tkinter as tk

import pystray
import qrcode
from PIL import Image, ImageTk

import i18n
import paths
from i18n import t as tr

APP = "MiniDesktop"
PORT = paths.PORT
BASE = f"http://127.0.0.1:{PORT}"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NO_WINDOW = subprocess.CREATE_NO_WINDOW

# Windows 11 koyu tema
C = {
    "bg": "#1f1f1f", "card": "#2b2b2b", "line": "#383838", "text": "#ffffff", "muted": "#a8a8a8",
    "accent": "#4cc2ff", "accent_fg": "#000000", "ok": "#6ccb5f", "bad": "#ff99a4", "warn": "#ffb900",
    "btn": "#373737", "btn_hover": "#424242", "danger": "#c42b1c",
}
FONT = "Segoe UI Variable Text"
FONT_D = "Segoe UI Variable Display"


# ---------------------------------------------------------------- yardımcılar
def api(path: str, body: dict | None = None, timeout: float = 1.5):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def port_open() -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def autostart_command() -> str:
    if paths.FROZEN:
        return f'"{sys.executable}" --tray'
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe")
    return f'"{pyw if pyw.exists() else py}" "{Path(__file__).with_name("launcher.py")}" --tray'


def autostart_get() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP)
            return True
    except OSError:
        return False


def autostart_set(on: bool):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, APP)
            except OSError:
                pass


def resource(name: str) -> Path:
    for p in (paths.RES_DIR / "app" / name, Path(__file__).with_name(name), paths.WEB_DIR / name):
        if p.exists():
            return p
    return Path(name)


# ---------------------------------------------------------------- güvenlik duvarı
def _ps(cmd: str, timeout=20) -> str:
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd], capture_output=True,
                       timeout=timeout, creationflags=NO_WINDOW)
    return r.stdout.decode("utf-8", "replace").strip()


def firewall_state() -> str:
    """'allow' | 'block' | 'none' — gelen bağlantılar bu exe için açık mı? (sadece okuma)"""
    if not paths.FROZEN:
        return "allow"  # geliştirme modunda python.exe kullanılıyor; kontrol etme
    exe = sys.executable.replace("'", "''")
    out = _ps(f"$r = Get-NetFirewallApplicationFilter -Program '{exe}' -ErrorAction SilentlyContinue | "
              "Get-NetFirewallRule -ErrorAction SilentlyContinue | Where-Object { $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' }; "
              "if ($r | Where-Object Action -eq 'Block') { 'block' } elseif ($r) { 'allow' } else { 'none' }")
    return out if out in ("allow", "block", "none") else "none"


def firewall_fix():
    """Yönetici onayı (UAC) ister: bu exe'nin engelleme kurallarını siler, sadece TCP 8765 için izin verir."""
    exe = sys.executable.replace("'", "''")
    cmd = (f"$p='{exe}'; Get-NetFirewallApplicationFilter -Program $p -ErrorAction SilentlyContinue | "
           "Get-NetFirewallRule -ErrorAction SilentlyContinue | Remove-NetFirewallRule; "
           f"New-NetFirewallRule -DisplayName 'MiniDesktop (tablet)' -Direction Inbound -Program $p -Action Allow "
           f"-Protocol TCP -LocalPort {PORT} -Profile Any | Out-Null")
    ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", f'-NoProfile -WindowStyle Hidden -Command "{cmd}"', None, 0)


# ---------------------------------------------------------------- tek kopya
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateMutexW.restype = ctypes.c_void_p
kernel32.CreateEventW.restype = ctypes.c_void_p
kernel32.OpenEventW.restype = ctypes.c_void_p
kernel32.SetEvent.argtypes = [ctypes.c_void_p]
kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
EVENT_NAME = "Local\\MiniDesktopShowWindow"


def claim_single_instance():
    """İlk kopya ise 'göster' olayını döndürür; değilse mevcut kopyayı öne getirip None döner."""
    kernel32.CreateMutexW(None, False, "Local\\MiniDesktopControl")
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        h = kernel32.OpenEventW(0x0002, False, EVENT_NAME)  # EVENT_MODIFY_STATE
        if h:
            kernel32.SetEvent(h)
        return None
    return kernel32.CreateEventW(None, False, False, EVENT_NAME)


# ---------------------------------------------------------------- sunucu süreci
class ServerProcess:
    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.busy = False

    def start(self):
        if port_open():
            return  # zaten çalışıyor (ör. başka yoldan açılmış): ona bağlan
        self.proc = subprocess.Popen(paths.server_command(["--no-browser"]), cwd=str(paths.APP_DIR), creationflags=NO_WINDOW)

    def stop(self, wait: float = 8.0):
        try:
            api("/api/admin/shutdown", {})
        except Exception:
            pass
        end = time.time() + wait
        while time.time() < end and port_open():
            time.sleep(0.2)
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None


# ---------------------------------------------------------------- arayüz parçaları
class Button(tk.Label):
    def __init__(self, parent, text, command, kind="normal", **kw):
        colors = {
            "normal": (C["btn"], C["text"], C["btn_hover"]),
            "primary": (C["accent"], C["accent_fg"], "#6dd0ff"),
            "danger": (C["danger"], "#ffffff", "#d83b2b"),
            "ghost": (C["bg"], C["muted"], C["card"]),
        }[kind]
        self._colors = colors
        super().__init__(parent, text=text, bg=colors[0], fg=colors[1], font=(FONT, 10, "bold" if kind == "primary" else "normal"),
                         padx=kw.pop("padx", 14), pady=kw.pop("pady", 7), cursor="hand2", **kw)
        self.command = command
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Enter>", lambda e: self.configure(bg=self._colors[2]))
        self.bind("<Leave>", lambda e: self.configure(bg=self._colors[0]))

    def set_kind(self, text, kind):
        self._colors = {
            "normal": (C["btn"], C["text"], C["btn_hover"]),
            "primary": (C["accent"], C["accent_fg"], "#6dd0ff"),
            "danger": (C["danger"], "#ffffff", "#d83b2b"),
        }[kind]
        self.configure(text=text, bg=self._colors[0], fg=self._colors[1])


def card(parent, title):
    f = tk.Frame(parent, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
    tk.Label(f, text=title.upper(), bg=C["card"], fg=C["muted"], font=(FONT, 8, "bold")).pack(anchor="w", padx=14, pady=(10, 4))
    return f


# ---------------------------------------------------------------- uygulama
class App:
    def __init__(self, show_event, start_hidden: bool):
        self.show_event = show_event
        self.server = ServerProcess()
        self.q: queue.Queue = queue.Queue()
        self.info = None
        self.state = "starting"  # starting | running | stopping | stopped
        self.qr_url = None
        self.qr_img = None
        self._hooks_checked = False
        self.lang = i18n.lang()
        self._fw_state = "allow"
        self._tray_notified = False

        self.root = tk.Tk()
        self.root.title(APP)
        self.root.configure(bg=C["bg"])
        self.root.resizable(False, False)
        try:
            self.root.iconbitmap(default=str(resource("icon.ico")))
        except Exception:
            pass
        self._dark_titlebar()
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        self.full = tk.Frame(self.root, bg=C["bg"])
        self._build_full()
        self.full.pack(fill="both", expand=True)
        # Küçült (_) düğmesi de görev çubuğu yerine gizli simgelere gönderir
        self.root.bind("<Unmap>", self._on_unmap)

        self._build_tray()
        if start_hidden:
            self.root.withdraw()
        else:
            self._center()

        self.start_server()
        threading.Thread(target=self._poll_loop, daemon=True).start()
        threading.Thread(target=self._firewall_loop, daemon=True).start()
        self.root.after(120, self._pump)

    # ---------- pencere ----------
    def _dark_titlebar(self):
        try:
            self.root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            val = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
        except Exception:
            pass

    def _center(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        x = max(0, (self.root.winfo_screenwidth() - w) // 2)
        y = max(20, (self.root.winfo_screenheight() - h) // 3)
        self.root.geometry(f"+{x}+{y}")

    def show(self):
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.root.after(200, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()

    def _on_unmap(self, event):
        if event.widget is self.root and self.root.state() == "iconic":
            self.root.after(10, self.hide_to_tray)

    def hide_to_tray(self):
        self.root.withdraw()
        if not self._tray_notified:
            self._tray_notified = True
            try:
                self.tray.notify(tr("MiniDesktop gizli simgelerde çalışmaya devam ediyor. Açmak için simgeye tıkla."), APP)
            except Exception:
                pass

    # ---------- tam görünüm ----------
    def _build_full(self):
        f = self.full
        head = tk.Frame(f, bg=C["bg"])
        head.pack(fill="x", padx=18, pady=(16, 10))
        try:
            img = Image.open(resource("icon-192.png")).resize((34, 34), Image.LANCZOS)
            self._logo = ImageTk.PhotoImage(img)
            tk.Label(head, image=self._logo, bg=C["bg"]).pack(side="left")
        except Exception:
            pass
        tk.Label(head, text=APP, bg=C["bg"], fg=C["text"], font=(FONT_D, 17, "bold")).pack(side="left", padx=(10, 0))
        self.status_lbl = tk.Label(head, text=tr("● Başlatılıyor"), bg=C["bg"], fg=C["warn"], font=(FONT, 10, "bold"))
        self.status_lbl.pack(side="right")

        # Güvenlik duvarı uyarısı (gerekince görünür)
        self.fw_bar = tk.Frame(f, bg="#442726", highlightthickness=1, highlightbackground="#6b3a38")
        tk.Label(self.fw_bar, text=tr("⚠  Windows Güvenlik Duvarı tableti engelliyor"), bg="#442726", fg="#ffb4ab",
                 font=(FONT, 10, "bold")).pack(side="left", padx=12, pady=8)
        Button(self.fw_bar, tr("İzin ver"), self.fix_firewall, kind="primary", pady=4, padx=10).pack(side="right", padx=8)
        self.fw_anchor = tk.Frame(f, bg=C["bg"], height=0)
        self.fw_anchor.pack(fill="x")

        # Tablet kartı
        tc = card(f, tr("Tablet bağlantısı"))
        tc.pack(fill="x", padx=18, pady=(0, 10))
        row = tk.Frame(tc, bg=C["card"])
        row.pack(fill="x", padx=14, pady=(0, 14))
        # Yer tutucu görüntü: Label boyutu karakter değil piksel olarak hesaplansın
        self._qr_blank = ImageTk.PhotoImage(Image.new("RGB", (160, 160), "#e9e9e9"))
        self.qr_lbl = tk.Label(row, image=self._qr_blank, compound="center", bg=C["card"], fg="#555555",
                               font=(FONT, 10), text=tr("Başlatılıyor…"), bd=0)
        self.qr_lbl.pack(side="left")
        info = tk.Frame(row, bg=C["card"])
        info.pack(side="left", fill="both", expand=True, padx=(14, 0))
        tk.Label(info, text=tr("Tablette aç ya da QR'ı okut"), bg=C["card"], fg=C["muted"], font=(FONT, 9)).pack(anchor="w")
        self.url_lbl = tk.Label(info, text="—", bg=C["card"], fg=C["accent"], font=("Consolas", 11), cursor="hand2")
        self.url_lbl.pack(anchor="w", pady=(2, 0))
        self.url_lbl.bind("<Button-1>", lambda e: self.copy_url())
        tk.Label(info, text="PIN", bg=C["card"], fg=C["muted"], font=(FONT, 9)).pack(anchor="w", pady=(12, 0))
        self.pin_lbl = tk.Label(info, text="— — —", bg=C["card"], fg=C["text"], font=(FONT_D, 24, "bold"))
        self.pin_lbl.pack(anchor="w")
        self.dev_lbl = tk.Label(info, text="", bg=C["card"], fg=C["muted"], font=(FONT, 9))
        self.dev_lbl.pack(anchor="w", pady=(6, 0))
        self.copy_btn = Button(info, tr("Adresi kopyala"), self.copy_url, pady=4, padx=10)
        self.copy_btn.pack(anchor="w", pady=(8, 0))

        # Durum kartı
        sc = card(f, tr("Durum"))
        sc.pack(fill="x", padx=18, pady=(0, 10))
        self.rows = {}
        for key, label in (("discord", tr("Discord (mikrofon)")), ("social", tr("Arkadaşlar ve DM")), ("claude", "Claude Code"),
                           ("mode", tr("Mod")), ("weather", tr("Hava durumu"))):
            r = tk.Frame(sc, bg=C["card"])
            r.pack(fill="x", padx=14, pady=2)
            tk.Label(r, text=label, bg=C["card"], fg=C["muted"], font=(FONT, 10), width=17, anchor="w").pack(side="left")
            v = tk.Label(r, text="—", bg=C["card"], fg=C["text"], font=(FONT, 10), anchor="w")
            v.pack(side="left", fill="x", expand=True)
            self.rows[key] = v
        tk.Frame(sc, bg=C["card"], height=10).pack()

        # Düğmeler
        btns = tk.Frame(f, bg=C["bg"])
        btns.pack(fill="x", padx=18, pady=(2, 8))
        self.toggle_btn = Button(btns, tr("Durdur"), self.toggle_server, kind="danger")
        self.toggle_btn.pack(side="left")
        Button(btns, tr("Yeniden başlat"), self.restart_server).pack(side="left", padx=6)
        Button(btns, tr("Yönetim paneli ↗"), self.open_admin, kind="primary").pack(side="right")

        bottom = tk.Frame(f, bg=C["bg"])
        bottom.pack(fill="x", padx=18, pady=(4, 14))
        self.auto_var = tk.BooleanVar(value=autostart_get())
        tk.Checkbutton(bottom, text=tr("Windows açılışında başlat"), variable=self.auto_var, command=self.toggle_autostart,
                       bg=C["bg"], fg=C["text"], selectcolor=C["card"], activebackground=C["bg"], activeforeground=C["text"],
                       font=(FONT, 10), bd=0, highlightthickness=0).pack(side="left")
        Button(bottom, tr("Gizli simgelere küçült"), self.hide_to_tray, kind="ghost", padx=8, pady=3).pack(side="right")
        tk.Label(f, text=tr("Pencereyi kapatınca ya da küçültünce MiniDesktop gizli simgelerde çalışmaya devam eder."),
                 bg=C["bg"], fg="#6f6f6f", font=(FONT, 8)).pack(pady=(0, 12))

    # ---------- tepsi ----------
    def _build_tray(self):
        try:
            image = Image.open(resource("icon-192.png"))
        except Exception:
            image = Image.new("RGB", (64, 64), C["accent"])
        menu = pystray.Menu(
            pystray.MenuItem(lambda item: tr("MiniDesktop'ı göster"), lambda: self.q.put(("show",)), default=True),
            pystray.MenuItem(lambda item: tr("Yönetim paneli"), lambda: self.q.put(("admin",))),
            pystray.MenuItem(lambda item: tr("Tablet adresini kopyala"), lambda: self.q.put(("copy",))),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda item: tr("Sunucuyu durdur") if self.state == "running" else tr("Sunucuyu başlat"),
                             lambda: self.q.put(("toggle",))),
            pystray.MenuItem(lambda item: tr("Çıkış"), lambda: self.q.put(("quit",))),
        )
        self.tray = pystray.Icon(APP, image, APP, menu)
        self.tray.run_detached()

    # ---------- sunucu ----------
    def _bg(self, fn, then_state=None):
        def run():
            try:
                fn()
            finally:
                if then_state:
                    self.q.put(("state", then_state))
        threading.Thread(target=run, daemon=True).start()

    def start_server(self):
        self.state = "starting"
        self._render()
        self._bg(self.server.start)

    def stop_server(self):
        self.state = "stopping"
        self._render()
        self._bg(self.server.stop, "stopped")

    def toggle_server(self):
        if self.state in ("running", "starting"):
            self.stop_server()
        elif self.state == "stopped":
            self.start_server()

    def restart_server(self):
        self.state = "stopping"
        self._render()
        self._bg(lambda: (self.server.stop(), self.server.start()), "starting")

    def _firewall_loop(self):
        while True:
            try:
                self.q.put(("fw", firewall_state()))
            except Exception:
                pass
            time.sleep(30)

    def fix_firewall(self):
        firewall_fix()
        # Onaydan sonra durumu birkaç kez yeniden kontrol et
        def recheck():
            for _ in range(6):
                time.sleep(3)
                st = firewall_state()
                self.q.put(("fw", st))
                if st == "allow":
                    break
        threading.Thread(target=recheck, daemon=True).start()

    def _poll_loop(self):
        while True:
            try:
                info = api("/api/admin/info", timeout=1.5)
            except Exception:
                info = None
            self.q.put(("info", info))
            time.sleep(1.5)

    # ---------- olay döngüsü ----------
    def _pump(self):
        try:
            if self.show_event and kernel32.WaitForSingleObject(self.show_event, 0) == 0:
                self.show()
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "info":
                    self._on_info(msg[1])
                elif kind == "fw":
                    self._fw_state = msg[1]
                    if msg[1] == "allow":
                        self.fw_bar.pack_forget()
                    elif not self.fw_bar.winfo_ismapped():
                        self.fw_bar.pack(fill="x", padx=18, pady=(0, 10), before=self.fw_anchor)
                elif kind == "state":
                    self.state = msg[1]
                    self._render()
                elif kind == "show":
                    self.show()
                elif kind == "admin":
                    self.open_admin()
                elif kind == "copy":
                    self.copy_url()
                elif kind == "toggle":
                    self.toggle_server()
                elif kind == "quit":
                    self.quit()
                    return
        except queue.Empty:
            pass
        self.root.after(150, self._pump)

    def _rebuild(self):
        """Dil değişti: pencere içeriğini yeni dille baştan oluştur."""
        self.full.destroy()
        self.full = tk.Frame(self.root, bg=C["bg"])
        self._build_full()
        self.full.pack(fill="both", expand=True)
        self.qr_url = None
        self.q.put(("fw", self._fw_state))
        self.tray.update_menu()

    def _on_info(self, info):
        if info and info.get("lang") and info["lang"] != self.lang:
            self.lang = info["lang"]
            self._rebuild()
        self.info = info
        if info and self.state in ("starting", "stopped"):
            self.state = "running"
        elif not info and self.state == "running":
            self.state = "stopped"
        if info and not self._hooks_checked:
            self._hooks_checked = True
            c = info.get("claude") or {}
            if c.get("installed") and not c.get("current"):
                # Kurulum yeri değişmiş: Claude hook'larını bu kopyaya yönlendir
                self._bg(lambda: api("/api/admin/claude", {"action": "install"}, timeout=5))
        self._render()
        self.tray.update_menu()

    def _render(self):
        st = self.state
        text, color = {
            "running": (tr("● Çalışıyor"), C["ok"]), "starting": (tr("● Başlatılıyor"), C["warn"]),
            "stopping": (tr("● Durduruluyor"), C["warn"]), "stopped": (tr("● Durdu"), C["bad"]),
        }[st]
        self.status_lbl.configure(text=text, fg=color)
        running = st in ("running", "starting")
        self.toggle_btn.set_kind(tr("Durdur") if running else tr("Başlat"), "danger" if running else "primary")

        info = self.info if st == "running" else None
        if not info:
            self.url_lbl.configure(text=tr("Sunucu kapalı") if st == "stopped" else "…")
            self.pin_lbl.configure(text="— — —")
            self.dev_lbl.configure(text="")
            if self.qr_url is not None:
                self.qr_url = None
                self.qr_lbl.configure(image=self._qr_blank, text=tr("Sunucu kapalı") if st == "stopped" else tr("Başlatılıyor…"))
            for v in self.rows.values():
                v.configure(text="—", fg=C["muted"])
            return

        base = info.get("base", "")
        pin = info.get("pin", "")
        self.url_lbl.configure(text=base.replace("http://", ""))
        self.pin_lbl.configure(text=f"{pin[:3]} {pin[3:]}")
        n = len(info.get("devices", []))
        self.dev_lbl.configure(text=tr("Eşli cihaz: {n}", n=n) if n else tr("Henüz eşli cihaz yok"))
        url = info.get("url")
        if url and url != self.qr_url:
            self.qr_url = url
            img = qrcode.make(url, border=2).convert("RGB").resize((160, 160), Image.NEAREST)
            self.qr_img = ImageTk.PhotoImage(img)
            self.qr_lbl.configure(image=self.qr_img, text="")

        d = info.get("discord") or {}
        s = info.get("social") or {}
        c = info.get("claude") or {}
        m = info.get("modes") or {}
        w = info.get("weather") or {}
        dmap = {"ready": (tr("Bağlı"), C["ok"]), "not_configured": (tr("Ayarlanmadı"), C["muted"]), "disconnected": (tr("Discord kapalı"), C["warn"]),
                "authorizing": (tr("İzin bekleniyor"), C["warn"]), "connecting": (tr("Bağlanıyor…"), C["warn"]), "error": (tr("Hata"), C["bad"]),
                "no_bridge": (tr("Köprü yok"), C["muted"]), "starting": (tr("Başlıyor…"), C["warn"]), "stopped": (tr("Durdu"), C["muted"])}
        if d.get("control") == "rpc":
            t, col = tr("Tam kontrol") + (f" · {d['user'].get('name')}" if d.get("user") else ""), C["ok"]
        elif d.get("control") == "keys":
            t, col = tr("Kısayol modu · {k}", k=(d.get('keys') or {}).get('mute', '')), C["ok"]
        else:
            t, col = dmap.get(d.get("status"), (d.get("status") or "—", C["muted"]))
        self.rows["discord"].configure(text=t, fg=col)
        # Arkadaş listesi: bağlı değilse satıra tıklayınca tek adımda bağlan
        social_row = self.rows["social"]
        if s.get("status") == "not_configured" and s.get("bridge_built", True):
            social_row.configure(text=tr("Bağlı değil · Bağlan →"), fg=C["accent"], cursor="hand2")
            social_row.bind("<Button-1>", lambda e: self._bg(lambda: api("/api/admin/social/connect", {}, timeout=5)))
        else:
            t, col = dmap.get(s.get("status"), (s.get("status") or "—", C["muted"]))
            if s.get("status") == "ready":
                t += " · " + tr("{n} arkadaş", n=s.get('friends', 0))
            elif s.get("status") == "authorizing":
                t = tr("Discord'daki izin penceresini onayla")
            social_row.configure(text=t, fg=col, cursor="")
            social_row.unbind("<Button-1>")
        if c.get("installed"):
            self.rows["claude"].configure(text=tr("Kurulu · {n} oturum", n=c.get('sessions', 0)), fg=C["ok"])
        else:
            self.rows["claude"].configure(text=tr("Kurulu değil"), fg=C["muted"])
        names = {"normal": tr("Normal"), "dev": tr("Geliştirici"), "game": tr("Oyun"), "night": tr("Gece")}
        mode_txt = names.get(m.get("mode"), "—") + (tr(" (otomatik)") if m.get("auto") else "")
        if m.get("game"):
            mode_txt += f" · {m['game']['name']}"
        self.rows["mode"].configure(text=mode_txt, fg=C["text"])
        if w.get("label"):
            self.rows["weather"].configure(text=f"{w['label']}" + (f" · {round(w['temp'])}°C, {w.get('desc', '')}" if w.get("temp") is not None else ""), fg=C["text"])
        else:
            self.rows["weather"].configure(text=tr("Ayarlanmadı"), fg=C["muted"])

    # ---------- eylemler ----------
    def open_admin(self):
        if self.state != "running":
            self.start_server()
        webbrowser.open(f"http://localhost:{PORT}/admin")

    def copy_url(self):
        if not self.info:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.info.get("base", ""))
        self.copy_btn.configure(text=tr("Kopyalandı ✓"))
        self.root.after(1500, lambda: self.copy_btn.configure(text=tr("Adresi kopyala")))

    def toggle_autostart(self):
        try:
            autostart_set(self.auto_var.get())
        except OSError:
            self.auto_var.set(autostart_get())

    def quit(self):
        self.root.withdraw()
        try:
            self.tray.stop()
        except Exception:
            pass
        self.server.stop(wait=6)
        self.root.destroy()


def main(start_hidden: bool = False):
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # keskin yazılar
    except Exception:
        pass
    ev = claim_single_instance()
    if ev is None:
        return  # zaten açık: mevcut pencere öne getirildi
    App(ev, start_hidden).root.mainloop()

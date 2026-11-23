"""MiniDesktop.exe giriş noktası.

  MiniDesktop.exe                 kontrol penceresi (+ sunucuyu başlatır)
  MiniDesktop.exe --tray          aynı, ama sadece sistem tepsisinde başlar (Windows açılışı)
  MiniDesktop.exe --server        sadece sunucu (kontrol uygulaması bunu ayrı süreç olarak açar)
  MiniDesktop.exe --claude-hook   Claude Code hook'u: stdin'deki olayı sunucuya iletir
  MiniDesktop.exe --shutdown      çalışan sunucuyu durdurur (kaldırıcı kullanır)
  MiniDesktop.exe --uninstall-hooks  Claude Code hook'larını kaldırır (kaldırıcı kullanır)
"""
import os
import sys


def _post(path: str, data: bytes = b"{}", timeout: float = 1.5):
    import urllib.request
    port = os.environ.get("MINIDESKTOP_PORT", "8765")
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=timeout).close()


def claude_hook():
    # Hızlı ve sessiz olmalı; Claude Code'u asla engellememeli.
    try:
        if sys.stdin is not None:
            data = sys.stdin.buffer.read()
        else:
            with open(0, "rb", closefd=False) as f:
                data = f.read()
        _post("/api/hooks/claude", data)
    except Exception:
        pass
    sys.exit(0)


def main():
    argv = sys.argv[1:]
    if "--claude-hook" in argv:
        claude_hook()
    if not getattr(sys, "frozen", False):
        here = os.path.dirname(os.path.abspath(__file__))
        sys.path[:0] = [here, os.path.join(os.path.dirname(here), "server")]
    if "--server" in argv:
        import main as server_main
        server_main.cli()
    elif "--shutdown" in argv:
        try:
            _post("/api/admin/shutdown")
        except Exception:
            pass
    elif "--uninstall-hooks" in argv:
        from claude_sessions import ClaudeSessions
        try:
            ClaudeSessions(lambda: None).uninstall()
        except Exception:
            pass
    else:
        import control
        control.main(start_hidden="--tray" in argv)


if __name__ == "__main__":
    main()

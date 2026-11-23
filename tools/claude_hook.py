"""Claude Code hook'u: olay JSON'unu MiniDesktop'a iletir.

Hiçbir şey yazdırmaz ve her durumda 0 ile çıkar; Claude Code'un çalışmasını asla engellemez.
"""
import os
import sys
import urllib.request

try:
    data = sys.stdin.buffer.read()
    port = os.environ.get("MINIDESKTOP_PORT", "8765")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/hooks/claude",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=1.5).close()
except Exception:
    pass
sys.exit(0)

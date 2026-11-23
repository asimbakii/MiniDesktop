"""MiniDesktop PC servisi.

Çalıştır:  .venv\\Scripts\\python server\\main.py
Tablet aynı Wi-Fi'da http://<PC-IP>:8765 adresini açar ve PIN ile eşleşir.
"""
import asyncio
import json
import os
import socket
import sys
import time
import webbrowser
from pathlib import Path

import qrcode
import qrcode.image.svg
import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from audio import Audio
from claude_sessions import ClaudeSessions
from devtools import Clipboard, Commands, DevConfig, GitWatch, SysMon, clipboard_get
import modes as modes_mod
from discord_rpc import DiscordRPC
import netinfo
from media import Media
from pairing import Pairing
from social import Social
from stats import Stats
from weather import Weather

from paths import ADMIN_HTML, APP_DIR as ROOT, BRIDGE_EXE, DATA_DIR as DATA, PORT, WEB_DIR as WEB
import i18n
from i18n import t

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
pairing = Pairing(DATA)
media = Media()
audio = Audio()
stats = Stats()
clients: set[WebSocket] = set()
state: dict = {"media": {}, "audio": {}, "stats": {}, "discord": {}, "social": {}, "weather": {}}
_push: asyncio.Event | None = None


def request_push():
    if _push:
        _push.set()


discord = DiscordRPC(DATA, on_change=request_push)
social = Social(BRIDGE_EXE, DATA, on_change=request_push)
weather = Weather(DATA, on_change=request_push)
modes = modes_mod.Modes(DATA, on_change=request_push)
claude = ClaudeSessions(on_change=request_push)
devcfg = DevConfig(DATA)
dev_active = lambda: modes.mode == "dev"  # noqa: E731  ağır taramalar sadece geliştirici modunda
gitwatch = GitWatch(devcfg, claude.cwds, dev_active, on_change=request_push)
commands = Commands(devcfg, on_change=request_push)
sysmon = SysMon(dev_active, on_change=request_push)
clipboard = Clipboard(devcfg, dev_active, on_change=request_push)


def live_state() -> dict:
    """Olay güdümlü modüllerin güncel durumu (her gönderimde yeniden okunur)."""
    out = {
        "lang": i18n.lang(),
        "discord": discord.state(),
        "social": social.state(),
        "weather": weather.state(),
        "mode": modes.state(),
        "claude": claude.state(),
        "commands": commands.state(),
    }
    out["dev"] = {"git": gitwatch.state(), "sys": sysmon.state(), "clip": clipboard.state()} if dev_active() else None
    return out


current_ip = netinfo.primary_ip()


def lan_ip() -> str:
    return current_ip


def base_url(ip: str | None = None) -> str:
    return f"http://{ip or current_ip}:{PORT}"


def pair_url(ip: str | None = None) -> str:
    return f"{base_url(ip)}/?pair={pairing.pin}"


async def ip_watch_loop():
    """PC'nin IP'si değişirse (modem yeni adres verirse) QR'ı yenile ve kullanıcıya haber ver."""
    global current_ip
    while True:
        await asyncio.sleep(15)
        try:
            ip = await asyncio.to_thread(netinfo.primary_ip)
        except Exception:
            continue
        if ip != current_ip and ip != "127.0.0.1":
            old, current_ip = current_ip, ip
            print(f"[ağ] IP değişti: {old} -> {ip}. Tabletin QR kodu yeniden okutması gerekiyor.")
            webbrowser.open(f"http://localhost:{PORT}/admin?ipchanged={old}")


def require_local(request: Request):
    if request.client is None or request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, t("Bu sayfa sadece PC'den açılabilir."))


# ---------------- arka plan döngüleri ----------------
async def refresh_media():
    try:
        state["media"] = await media.snapshot()
    except Exception as e:
        state["media"] = {"available": False, "error": str(e), "sources": []}


async def refresh_audio():
    try:
        state["audio"] = await audio.snapshot()
    except Exception as e:
        state["audio"] = {"error": str(e), "apps": []}


async def fast_loop():
    while True:
        await refresh_media()
        await refresh_audio()
        request_push()
        await asyncio.sleep(1)


async def stats_loop():
    while True:
        try:
            state["stats"] = await asyncio.to_thread(stats.snapshot)
            state["stats"]["t"] = time.time()
        except Exception as e:
            state["stats"] = {"error": str(e)}
        request_push()
        await asyncio.sleep(1.5)


async def pusher():
    while True:
        await _push.wait()
        _push.clear()
        state.update(live_state())
        msg = json.dumps({"type": "state", **state, "ts": time.time()}, ensure_ascii=False)
        for ws in list(clients):
            try:
                await asyncio.wait_for(ws.send_text(msg), 3)
            except Exception:
                clients.discard(ws)
        await asyncio.sleep(0.05)


# ---------------- tablet API ----------------
@app.post("/api/pair")
async def api_pair(request: Request):
    body = await request.json()
    try:
        token = pairing.pair(body.get("pin", ""), body.get("name", "Tablet"))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    print(f"[eşleme] Yeni cihaz eşlendi: {body.get('name')}")
    return {"token": token}


@app.get("/api/art")
async def api_art(token: str = "", v: str = ""):
    if not pairing.check(token):
        raise HTTPException(401)
    if not media.art:
        raise HTTPException(404)
    return Response(media.art, media_type=media.art_mime, headers={"Cache-Control": "private, max-age=86400"})


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, token: str = ""):
    await ws.accept()
    if not pairing.check(token):
        await ws.close(code=4401)
        return
    clients.add(ws)
    state.update(live_state())
    await ws.send_text(json.dumps({"type": "state", **state, "ts": time.time()}, ensure_ascii=False))
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") != "cmd":
                continue
            if not pairing.check(token):
                await ws.close(code=4401)
                return
            target, action = msg.get("target"), msg.get("action")
            try:
                if target == "media":
                    await media.command(action, msg.get("value"))
                    await asyncio.sleep(0.25)
                    await refresh_media()
                elif target == "audio":
                    await audio.command(action, msg.get("key"), msg.get("value"))
                    await refresh_audio()
                elif target == "discord":
                    await discord.command(action, msg.get("value"))
                elif target == "social":
                    await social.command(action, msg.get("value"))
                elif target == "mode":
                    if action == "set":
                        modes.set_mode(msg.get("value"))
                    elif action == "settings":
                        modes.update_settings(msg.get("value") or {})
                elif target == "power":
                    modes_mod.power(action)
                elif target == "claude" and action == "dismiss":
                    claude.dismiss(msg.get("value"))
                elif target == "git":
                    if action == "open_repo":
                        gitwatch.open_repo(msg.get("value"))
                    elif action == "open_url":
                        gitwatch.open_url(msg.get("value"))
                elif target == "cmd":
                    if action == "start":
                        await commands.start(msg.get("value"))
                    elif action == "stop":
                        await commands.stop(msg.get("value"))
                elif target == "sys":
                    if action == "open_port":
                        sysmon.open_port(int(msg.get("value")))
                    elif action == "kill":
                        n = await asyncio.to_thread(sysmon.kill, list(msg.get("value") or []))
                        await ws.send_text(json.dumps({"type": "toast", "message": t("{n} süreç sonlandırıldı", n=n)}, ensure_ascii=False))
                elif target == "clip":
                    if action == "set":
                        await clipboard.set(msg.get("value") or "")
                    elif action == "history":
                        await clipboard.copy_history(msg.get("value"))
                    elif action == "snippet":
                        await clipboard.copy_snippet(msg.get("value"))
                    elif action == "clear":
                        clipboard.clear()
                    elif action == "get":
                        text = await asyncio.to_thread(clipboard_get)
                        await ws.send_text(json.dumps({"type": "clip_text", "text": text or "", "req": msg.get("value")}, ensure_ascii=False))
                    if action not in ("clear", "get"):
                        await ws.send_text(json.dumps({"type": "toast", "message": t("PC panosuna kopyalandı")}, ensure_ascii=False))
                request_push()
            except Exception as e:
                await ws.send_text(json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False))
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(ws)


# ---------------- PC yönetim sayfası (sadece localhost) ----------------
@app.get("/admin")
async def admin_page(request: Request):
    require_local(request)
    lang = i18n.lang()
    html = ADMIN_HTML.read_text("utf-8").replace('<html lang="tr">', f'<html lang="{lang}" data-lang="{lang}">', 1)
    return HTMLResponse(html)


@app.get("/api/admin/info")
async def admin_info(request: Request, ip: str = ""):
    require_local(request)
    addresses = await asyncio.to_thread(netinfo.candidates)
    if ip not in {a["ip"] for a in addresses}:
        ip = current_ip
    url = pair_url(ip)
    svg = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, border=2).to_string(encoding="unicode")
    return {
        "lang": i18n.lang(),
        "lang_setting": i18n.setting(),
        "url": url,
        "base": base_url(ip),
        "ip": ip,
        "addresses": addresses,
        "pin": pairing.pin,
        "qr": svg,
        "devices": pairing.list(),
        "discord": {
            "configured": discord.configured(),
            "client_id": discord.cfg.get("client_id", ""),
            "status": discord.status,
            "error": discord.error,
            "user": discord.user,
            "notifications": discord.state()["notifications_enabled"],
            "control": discord.control_mode(),
            "keys": discord.keys.state(),
        },
        "social": {
            "app_id": social.app_id(),
            "custom_app": social.custom_app(),
            "enabled": social.enabled(),
            "bridge_built": social.bridge_built(),
            "sdk_found": social.bridge_built() or any((ROOT / "bridge" / "sdk").glob("*/include/discordpp.h")),
            "status": social.status,
            "error": social.error,
            "me": social.me,
            "friends": len(social.friends),
        },
        "weather": {"label": weather.cfg.get("label"), "error": weather.error, "temp": (weather.data or {}).get("temp"), "desc": weather.state().get("desc")},
        "modes": modes.state(),
        "claude": {"installed": claude.hook_installed(), "current": claude.hook_current(), "command": claude.hook_command(), "sessions": len(claude.sessions)},
        "devcfg": devcfg.data,
        "gh": bool(gitwatch.gh["available"]),
        "cpu_temp": (state.get("stats") or {}).get("cpu", {}).get("temp"),
    }


@app.post("/api/admin/discord")
async def admin_discord(request: Request):
    require_local(request)
    body = await request.json()
    if not body.get("client_id") or not body.get("client_secret"):
        raise HTTPException(400, t("Client ID ve Client Secret gerekli."))
    discord.set_credentials(body["client_id"], body["client_secret"])
    return {"ok": True}


@app.post("/api/admin/discord/keys")
async def admin_discord_keys(request: Request):
    require_local(request)
    body = await request.json()
    try:
        if body.get("test") in ("mute", "deaf"):
            await asyncio.to_thread(discord.keys.toggle, body["test"])
        else:
            discord.keys.update(body)
    except ValueError as e:
        raise HTTPException(400, str(e))
    request_push()
    return {"ok": True, "keys": discord.keys.state()}


@app.post("/api/admin/discord/reset")
async def admin_discord_reset(request: Request):
    require_local(request)
    discord.reset_auth()
    return {"ok": True}


@app.post("/api/admin/social")
async def admin_social(request: Request):
    require_local(request)
    body = await request.json()
    app_id = str(body.get("app_id", "")).strip()
    if not app_id.isdigit():
        raise HTTPException(400, t("Application ID sadece rakamlardan oluşmalı."))
    social.set_app_id(app_id)
    return {"ok": True}


@app.post("/api/admin/social/connect")
async def admin_social_connect(request: Request):
    require_local(request)
    body = await request.json() if (await request.body()) else {}
    app_id = body.get("app_id")
    if app_id is not None and str(app_id).strip() and not str(app_id).strip().isdigit():
        raise HTTPException(400, t("Application ID sadece rakamlardan oluşmalı."))
    social.connect(None if app_id is None else str(app_id))
    return {"ok": True}


@app.post("/api/admin/social/disconnect")
async def admin_social_disconnect(request: Request):
    require_local(request)
    social.disconnect()
    return {"ok": True}


@app.post("/api/admin/social/reauth")
async def admin_social_reauth(request: Request):
    require_local(request)
    social.reauth()
    return {"ok": True}


@app.post("/api/admin/weather")
async def admin_weather(request: Request):
    require_local(request)
    body = await request.json()
    city = str(body.get("city", "")).strip()
    if not city:
        raise HTTPException(400, t("Şehir adı gir."))
    try:
        cfg = await asyncio.to_thread(weather.set_city, city)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(502, t("Open-Meteo'ya ulaşılamadı: {e}", e=e))
    return {"ok": True, "label": cfg["label"]}


@app.post("/api/hooks/claude")
async def hook_claude(request: Request):
    require_local(request)
    try:
        claude.handle(await request.json())
    except Exception:
        pass
    return {"ok": True}


@app.post("/api/admin/claude")
async def admin_claude(request: Request):
    require_local(request)
    body = await request.json()
    if body.get("action") == "install":
        await asyncio.to_thread(claude.install)
    elif body.get("action") == "uninstall":
        await asyncio.to_thread(claude.uninstall)
    return {"ok": True, "installed": claude.hook_installed()}


@app.post("/api/admin/devconfig")
async def admin_devconfig(request: Request):
    require_local(request)
    try:
        devcfg.update(await request.json())
    except ValueError as e:
        raise HTTPException(400, str(e))
    request_push()
    return {"ok": True, "devcfg": devcfg.data}


@app.post("/api/admin/modes")
async def admin_modes(request: Request):
    require_local(request)
    try:
        modes.update_settings(await request.json())
    except Exception as e:
        raise HTTPException(400, t("Geçersiz ayar: {e}", e=e))
    return {"ok": True}


@app.post("/api/admin/lang")
async def admin_lang(request: Request):
    require_local(request)
    body = await request.json()
    try:
        i18n.set_lang(str(body.get("lang", "auto")))
    except ValueError:
        raise HTTPException(400, "lang: auto | tr | en")
    request_push()  # tabletler yeni dile geçsin
    return {"ok": True, "lang": i18n.lang()}


@app.post("/api/admin/revoke")
async def admin_revoke(request: Request):
    require_local(request)
    body = await request.json()
    token = pairing.revoke(body.get("id", ""))
    if token:
        for ws in list(clients):
            if ws.query_params.get("token") == token:
                await ws.close(code=4401)
    return {"ok": bool(token)}


_server: uvicorn.Server | None = None


@app.post("/api/admin/shutdown")
async def admin_shutdown(request: Request):
    require_local(request)
    if _server:
        _server.should_exit = True
    return {"ok": True}


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")


# ---------------- başlat ----------------
async def main():
    global _push
    _push = asyncio.Event()
    await media.start()

    url = pair_url()
    print("\n  MiniDesktop çalışıyor")
    print(f"  Tablette aç : http://{lan_ip()}:{PORT}")
    print(f"  Eşleme PIN  : {pairing.pin}")
    print(f"  Yönetim     : http://localhost:{PORT}/admin  (QR kod, Discord ayarı)\n")
    try:
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.print_ascii(invert=True)
    except Exception:
        pass

    tasks = [asyncio.create_task(c) for c in (fast_loop(), stats_loop(), pusher(), ip_watch_loop(), discord.run(), social.run(), weather.run(), modes.run(), gitwatch.run(), sysmon.run(), clipboard.run())]
    if "--no-browser" not in sys.argv:
        asyncio.get_running_loop().call_later(1.0, webbrowser.open, f"http://localhost:{PORT}/admin")

    global _server
    server = _server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="warning"))
    try:
        await server.serve()
    finally:
        await social.stop()
        await commands.stop_all()
        for t in tasks:
            t.cancel()


def already_running() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def cli():
    # Penceresiz çalışırken (pythonw / paketlenmiş exe) çıktı yok: log dosyasına yaz.
    if sys.stdout is None or sys.stderr is None:
        log_path = DATA / "minidesktop.log"
        if log_path.exists() and log_path.stat().st_size > 2_000_000:
            log_path.replace(DATA / "minidesktop.old.log")
        log = open(log_path, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log
        print(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} başlatıldı ---")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if already_running():
        # Zaten arka planda çalışıyor: ikinci kopyayı açma, yönetim sayfasını göster.
        print("MiniDesktop zaten çalışıyor, yönetim sayfası açılıyor.")
        if "--no-browser" not in sys.argv:
            webbrowser.open(f"http://localhost:{PORT}/admin")
        sys.exit(0)
    # Windows'ta varsayılan Proactor döngüsü named pipe (Discord IPC) için gerekli.
    asyncio.run(main())


if __name__ == "__main__":
    cli()

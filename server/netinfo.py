"""PC'nin ev ağındaki IP adresini bulur (sanal/VPN adaptörlerini eleyerek)."""
import ipaddress
import socket

import psutil

VIRTUAL_HINTS = (
    "vethernet", "hyper-v", "virtualbox", "vmware", "wsl", "loopback", "bluetooth",
    "tailscale", "zerotier", "hamachi", "radmin", "vpn", "docker", "npcap", "tap-", "tun",
)


def default_route_ip() -> str | None:
    """İşletim sisteminin varsayılan çıkış arayüzünün IP'si (paket gönderilmez)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return None
    finally:
        s.close()


def candidates() -> list[dict]:
    """Tabletin bağlanabileceği yerel IPv4 adresleri, en olası olan başta."""
    stats = psutil.net_if_stats()
    default = default_route_ip()
    out = []
    for name, addrs in psutil.net_if_addrs().items():
        st = stats.get(name)
        if not st or not st.isup:
            continue
        for a in addrs:
            if a.family != socket.AF_INET:
                continue
            ip = ipaddress.ip_address(a.address)
            if not ip.is_private or ip.is_loopback or ip.is_link_local:
                continue
            low = name.lower()
            out.append({
                "ip": a.address,
                "iface": name,
                "virtual": any(h in low for h in VIRTUAL_HINTS),
                "wifi": "wi-fi" in low or "wlan" in low or "wireless" in low,
                "default": a.address == default,
            })
    # Gerçek adaptör > varsayılan rota > Wi-Fi/Ethernet sırası
    out.sort(key=lambda c: (c["virtual"], not c["default"], not c["wifi"]))
    return out


def primary_ip() -> str:
    c = candidates()
    if c:
        return c[0]["ip"]
    return default_route_ip() or "127.0.0.1"

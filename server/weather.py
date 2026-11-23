"""Hava durumu (Open-Meteo: ücretsiz, API anahtarı gerekmez).

Sadece yönetim sayfasında girilen şehir adı / koordinatı Open-Meteo'ya gönderilir.
"""
import asyncio
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "MiniDesktop/1.0"}
REFRESH = 15 * 60

# WMO hava kodu -> (Türkçe açıklama, simge)
WMO = {
    0: ("Açık", "sun"), 1: ("Çoğunlukla açık", "sun-cloud"), 2: ("Parçalı bulutlu", "sun-cloud"), 3: ("Kapalı", "cloud"),
    45: ("Sisli", "fog"), 48: ("Kırağılı sis", "fog"),
    51: ("Hafif çisenti", "drizzle"), 53: ("Çisenti", "drizzle"), 55: ("Yoğun çisenti", "drizzle"),
    56: ("Dondurucu çisenti", "drizzle"), 57: ("Dondurucu çisenti", "drizzle"),
    61: ("Hafif yağmur", "rain"), 63: ("Yağmur", "rain"), 65: ("Şiddetli yağmur", "rain"),
    66: ("Dondurucu yağmur", "rain"), 67: ("Dondurucu yağmur", "rain"),
    71: ("Hafif kar", "snow"), 73: ("Kar", "snow"), 75: ("Yoğun kar", "snow"), 77: ("Kar taneleri", "snow"),
    80: ("Sağanak", "rain"), 81: ("Sağanak", "rain"), 82: ("Şiddetli sağanak", "rain"),
    85: ("Kar sağanağı", "snow"), 86: ("Yoğun kar sağanağı", "snow"),
    95: ("Gök gürültülü fırtına", "storm"), 96: ("Dolulu fırtına", "storm"), 99: ("Dolulu fırtına", "storm"),
}


def describe(code) -> tuple[str, str]:
    return WMO.get(int(code or 0), ("Bilinmiyor", "cloud"))


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


class Weather:
    def __init__(self, data_dir: Path, on_change):
        self.path = data_dir / "weather.json"
        self.on_change = on_change
        try:
            self.cfg = json.loads(self.path.read_text("utf-8"))
        except Exception:
            self.cfg = {}
        self.data = None
        self.error = None
        self._wake: asyncio.Event | None = None

    def configured(self) -> bool:
        return "lat" in self.cfg

    def set_city(self, name: str) -> dict:
        """Şehir adını koordinata çevir (bloklayan çağrı; thread'de çalıştır)."""
        q = urllib.parse.urlencode({"name": name.strip(), "count": 1, "language": "tr", "format": "json"})
        res = _get(f"https://geocoding-api.open-meteo.com/v1/search?{q}").get("results") or []
        if not res:
            raise ValueError(f"'{name}' bulunamadı. Şehir adını farklı yazmayı dene.")
        r = res[0]
        # örn. "Kadıköy, İstanbul" ya da sadece "İstanbul"
        label = ", ".join(x for x in (r.get("name"), r.get("admin1") if r.get("admin1") != r.get("name") else None) if x)
        self.cfg = {"city": r.get("name"), "label": label, "lat": r["latitude"], "lon": r["longitude"]}
        self.path.write_text(json.dumps(self.cfg, ensure_ascii=False), "utf-8")
        if self._wake:
            self._wake.set()
        return self.cfg

    def _fetch(self) -> dict:
        q = urllib.parse.urlencode({
            "latitude": self.cfg["lat"],
            "longitude": self.cfg["lon"],
            "current": "temperature_2m,apparent_temperature,weather_code,is_day,relative_humidity_2m,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto",
            "forecast_days": 4,
        })
        d = _get(f"https://api.open-meteo.com/v1/forecast?{q}")
        cur = d["current"]
        desc, ic = describe(cur["weather_code"])
        days = []
        dd = d["daily"]
        for i, date in enumerate(dd["time"]):
            ddesc, dic = describe(dd["weather_code"][i])
            days.append({
                "date": date,
                "max": dd["temperature_2m_max"][i],
                "min": dd["temperature_2m_min"][i],
                "rain": (dd.get("precipitation_probability_max") or [None] * 4)[i],
                "desc": ddesc,
                "icon": dic,
            })
        return {
            "temp": cur["temperature_2m"],
            "feels": cur["apparent_temperature"],
            "humidity": cur.get("relative_humidity_2m"),
            "wind": cur.get("wind_speed_10m"),
            "is_day": bool(cur.get("is_day", 1)),
            "desc": desc,
            "icon": ic,
            "days": days,
            "updated": time.time(),
        }

    async def run(self):
        self._wake = asyncio.Event()
        while True:
            if self.configured():
                try:
                    self.data = await asyncio.to_thread(self._fetch)
                    self.error = None
                except Exception as e:
                    self.error = f"Hava durumu alınamadı: {e}"
                self.on_change()
            try:
                await asyncio.wait_for(self._wake.wait(), REFRESH if self.configured() else 3600)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()

    def state(self) -> dict:
        return {
            "configured": self.configured(),
            "city": self.cfg.get("city"),
            "label": self.cfg.get("label"),
            "error": self.error,
            **(self.data or {}),
        }

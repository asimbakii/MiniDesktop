"""Dil desteği (Türkçe / English).

Metinler kodda Türkçe yazılır; t("…") İngilizce seçiliyse sözlükteki karşılığı döndürür.
Dil ayarı data/settings.json'da tutulur: "auto" (Windows diline göre), "tr" ya da "en".
"""
import ctypes
import json
import os
import sys
import time

import paths

SETTINGS = paths.DATA_DIR / "settings.json"
LANGS = ("auto", "tr", "en")


def _system_lang() -> str:
    """İşletim sisteminin arayüz dili: Türkçe ise "tr", değilse "en"."""
    if sys.platform == "win32":
        try:
            lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "tr" if (lid & 0x3FF) == 0x1F else "en"  # 0x1F = Türkçe
        except Exception:
            return "en"
    for var in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        v = os.environ.get(var)
        if v:
            return "tr" if v.lower().startswith("tr") else "en"
    return "en"


def _load() -> dict:
    try:
        return json.loads(SETTINGS.read_text("utf-8"))
    except Exception:
        return {}


def setting() -> str:
    v = _load().get("lang", "auto")
    return v if v in LANGS else "auto"


_cache = {"t": 0.0, "v": None}


def lang() -> str:
    # Ayar dosyası sık okunmasın diye 2 sn önbellek
    now = time.monotonic()
    if _cache["v"] is None or now - _cache["t"] > 2:
        s = setting()
        _cache["v"] = _system_lang() if s == "auto" else s
        _cache["t"] = now
    return _cache["v"]


def set_lang(value: str):
    if value not in LANGS:
        raise ValueError("lang")
    data = _load()
    data["lang"] = value
    SETTINGS.write_text(json.dumps(data), "utf-8")
    _cache["v"] = None


def t(text: str, **kw) -> str:
    if lang() == "en":
        text = EN.get(text, text)
    return text.format(**kw) if kw else text


EN = {
    # genel / yönetim
    "Bu sayfa sadece PC'den açılabilir.": "This page can only be opened on the PC.",
    "{n} süreç sonlandırıldı": "{n} process(es) ended",
    "PC panosuna kopyalandı": "Copied to PC clipboard",
    "Application ID sadece rakamlardan oluşmalı.": "The Application ID must contain only digits.",
    "Şehir adı gir.": "Enter a city name.",
    "Open-Meteo'ya ulaşılamadı: {e}": "Could not reach Open-Meteo: {e}",
    "Geçersiz ayar: {e}": "Invalid setting: {e}",
    "Client ID ve Client Secret gerekli.": "Client ID and Client Secret are required.",
    # hava durumu
    "Açık": "Clear", "Çoğunlukla açık": "Mostly clear", "Parçalı bulutlu": "Partly cloudy", "Kapalı": "Overcast",
    "Sisli": "Fog", "Kırağılı sis": "Freezing fog", "Hafif çisenti": "Light drizzle", "Çisenti": "Drizzle",
    "Yoğun çisenti": "Dense drizzle", "Dondurucu çisenti": "Freezing drizzle", "Hafif yağmur": "Light rain",
    "Yağmur": "Rain", "Şiddetli yağmur": "Heavy rain", "Dondurucu yağmur": "Freezing rain", "Hafif kar": "Light snow",
    "Kar": "Snow", "Yoğun kar": "Heavy snow", "Kar taneleri": "Snow grains", "Sağanak": "Showers",
    "Şiddetli sağanak": "Violent showers", "Kar sağanağı": "Snow showers", "Yoğun kar sağanağı": "Heavy snow showers",
    "Gök gürültülü fırtına": "Thunderstorm", "Dolulu fırtına": "Thunderstorm with hail", "Bilinmiyor": "Unknown",
    "'{name}' bulunamadı. Şehir adını farklı yazmayı dene.": "'{name}' was not found. Try a different spelling.",
    "Hava durumu alınamadı: {e}": "Could not get the weather: {e}",
    # Discord
    "Discord bağlı değil.": "Discord is not connected.",
    "Discord açık değil": "Discord is not running",
    "Özel arama": "Private call",
    "Discord hatası": "Discord error",
    "Discord bağlantısı kapandı": "Discord connection closed",
    "Discord token alınamadı ({code}): {body}": "Could not get a Discord token ({code}): {body}",
    "Köprü başlatılamadı: {e}": "Could not start the bridge: {e}",
    "Köprü kapandı (kod {code})": "Bridge exited (code {code})",
    # geliştirici
    "Klasör bulunamadı: {r}": "Folder not found: {r}",
    "Komut klasörü bulunamadı: {cwd}": "Command folder not found: {cwd}",
    "Bilinmeyen repo": "Unknown repository",
    "Bilinmeyen bağlantı": "Unknown link",
    "Bilinmeyen komut": "Unknown command",
    "Bilinmeyen port": "Unknown port",
    "Bilinmeyen snippet": "Unknown snippet",
    "[çıkış kodu {code}]": "[exit code {code}]",
    "Pano şu an kullanımda, tekrar dene.": "The clipboard is busy, try again.",
    "Panoya yazılamadı.": "Could not write to the clipboard.",
    "Araç": "Tool",
    "Oturum açıldı": "Session started",
    "Düşünüyor…": "Thinking…",
    "İzin bekliyor:": "Needs permission:",
    "Cevabını bekliyor": "Waiting for your answer",
    "Tamamlandı": "Done",
    # modlar / güç
    "Bilinmeyen mod": "Unknown mode",
    "Bilinmeyen güç işlemi": "Unknown power action",
    # eşleme
    "Çok fazla hatalı deneme. 1 dakika bekleyip tekrar dene.": "Too many wrong attempts. Wait 1 minute and try again.",
    "PIN yanlış.": "Wrong PIN.",
    # ses / medya / kısayollar
    "Sistem sesleri": "System sounds",
    "Medya Oynatıcı": "Media Player",
    "Bilinmeyen tuş: {part}": "Unknown key: {part}",
    "Kısayol boş": "The shortcut is empty",
    "Kısayol gönderilemedi: xdotool, ydotool ya da wtype kurulu değil.": "Could not send the shortcut: install xdotool, ydotool or wtype.",
    # tepsi uygulaması
    "MiniDesktop gizli simgelerde çalışmaya devam ediyor. Açmak için simgeye tıkla.": "MiniDesktop keeps running in the hidden icons. Click the icon to open it.",
    "● Başlatılıyor": "● Starting",
    "● Çalışıyor": "● Running",
    "● Durduruluyor": "● Stopping",
    "● Durdu": "● Stopped",
    "⚠  Windows Güvenlik Duvarı tableti engelliyor": "⚠  Windows Firewall is blocking the tablet",
    "İzin ver": "Allow",
    "Tablet bağlantısı": "Tablet connection",
    "Başlatılıyor…": "Starting…",
    "Tablette aç ya da QR'ı okut": "Open on the tablet or scan the QR code",
    "Adresi kopyala": "Copy address",
    "Durum": "Status",
    "Discord (mikrofon)": "Discord (mic)",
    "Arkadaşlar ve DM": "Friends & DMs",
    "Mod": "Mode",
    "Hava durumu": "Weather",
    "Durdur": "Stop",
    "Başlat": "Start",
    "Yeniden başlat": "Restart",
    "Yönetim paneli ↗": "Admin panel ↗",
    "Windows açılışında başlat": "Start with Windows",
    "Gizli simgelere küçült": "Minimize to tray",
    "Pencereyi kapatınca ya da küçültünce MiniDesktop gizli simgelerde çalışmaya devam eder.": "When you close or minimize this window, MiniDesktop keeps running in the hidden icons.",
    "MiniDesktop'ı göster": "Show MiniDesktop",
    "Yönetim paneli": "Admin panel",
    "Tablet adresini kopyala": "Copy tablet address",
    "Sunucuyu durdur": "Stop server",
    "Sunucuyu başlat": "Start server",
    "Çıkış": "Quit",
    "Sunucu kapalı": "Server stopped",
    "Eşli cihaz: {n}": "Paired devices: {n}",
    "Henüz eşli cihaz yok": "No paired devices yet",
    "Bağlı": "Connected",
    "Ayarlanmadı": "Not set",
    "Discord kapalı": "Discord not running",
    "İzin bekleniyor": "Waiting for approval",
    "Bağlanıyor…": "Connecting…",
    "Hata": "Error",
    "Köprü yok": "No bridge",
    "Başlıyor…": "Starting…",
    "Durdu": "Stopped",
    "Tam kontrol": "Full control",
    "Kısayol modu · {k}": "Keybind mode · {k}",
    "Bağlı değil · Bağlan →": "Not connected · Connect →",
    "Discord'daki izin penceresini onayla": "Approve the permission window in Discord",
    "{n} arkadaş": "{n} friends",
    "Kurulu · {n} oturum": "Installed · {n} session(s)",
    "Kurulu değil": "Not installed",
    "Normal": "Normal",
    "Geliştirici": "Developer",
    "Oyun": "Game",
    "Gece": "Night",
    " (otomatik)": " (auto)",
    "Kopyalandı ✓": "Copied ✓",
}

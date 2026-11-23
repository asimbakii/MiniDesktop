# MiniDesktop

Android tableti, Windows ya da Linux PC için küçük bir "ikinci masaüstü"ne çevirir. Dört mini pencere:

- **YouTube Music / Spotify oynatıcı:** Kapak, parça bilgisi, sarılabilir ilerleme çubuğu, oynatıcının ses seviyesi. Windows medya API'siyle çalıştığı için Chrome, Spotify ve diğer oynatıcıların hepsiyle uyumlu.
- **Discord:** Arkadaş listesi ve okunmamış DM rozetleri, mikrofon/kulaklık düğmeleri; tam kontrol modunda ses kanalı ve konuşanlar.
- **Görev Yöneticisi:** CPU, RAM, GPU (RTX sıcaklık, VRAM, güç) ve ağ, canlı grafiklerle.
- **Ses karıştırıcısı:** Hoparlör ve uygulama bazlı ses seviyeleri.

## Modlar
Görev çubuğundaki **Başlat** düğmesinden geçilir. Güç menüsü (kilitle, uyku, yeniden başlat, kapat) de buradadır; her işlem iki dokunuşla onaylanır.

| Mod | İçerik |
|---|---|
| **Normal** | Müzik, Discord, performans halkaları, ses karıştırıcı |
| **Geliştirici** | Claude Code oturumları, Kaynak Denetimi (git + GitHub PR/CI), komut butonları, port & süreç izleyici, pano & snippet'ler, dev araçları (UUID, zaman, JWT, Base64, URL). Müzik görev çubuğunda mini oynatıcıya iner. |
| **Oyun** | Büyük performans göstergeleri, oyun adı ve süresi, Discord sesi, mikser. Oyun açılınca otomatik geçer, kapanınca geri döner (Steam/Epic/Riot/Xbox/EA/Ubisoft/GOG klasörlerinden algılanır). |
| **Gece** | Karartılmış ekran, 1 dakikada kırmızı-loş saat ekranı. İstenirse belirlenen saatlerde otomatik. |

### Geliştirici modu kurulumu
Yönetim sayfası → **Geliştirici modu**:
- **Claude Code durumu:** "Kur" düğmesi `~/.claude/settings.json`'a hook ekler; önce yedek alır, diğer hook'lara dokunmaz. Oturumlar çalışıyor / izin bekliyor / cevap bekliyor / tamamlandı olarak görünür.
- **Git repoları:** İzlenecek klasörler. Claude Code'un çalıştığı repolar kendiliğinden eklenir. `gh` CLI giriş yapılmışsa PR'lar ve CI durumu da gelir.
- **Komut butonları** ve **snippet'ler** de buradan tanımlanır. Tablet sadece tanımlı komutları çalıştırabilir.
- **Pano geçmişi** sadece bellekte tutulur. Şifre yöneticilerinin işaretlediği içerikler alınmaz; token'a benzeyen metinler tablette maskelenir.

## Kurulum

1. `MiniDesktop-Setup-x.y.z.exe`'yi çalıştır. Yönetici izni gerekmez; uygulama `%LOCALAPPDATA%\Programs\MiniDesktop` klasörüne kurulur. Python gerekmez.
2. Kurulumdan sonra **MiniDesktop** penceresi açılır ve sunucuyu kendisi başlatır.
3. Pencerede **Windows Güvenlik Duvarı** uyarısı görünürse **İzin ver**'e bas ve Windows'un yönetici onayını ver. Sadece MiniDesktop için, sadece TCP 8765 portu açılır.
4. Penceredeki QR kodu tabletle okut. Tablet aynı Wi-Fi ağında olmalı.

### MiniDesktop penceresi
- Sunucu durumu ve **Durdur / Başlat / Yeniden başlat** düğmeleri
- Tablet adresi, QR kod, PIN ve eşli cihaz sayısı
- Discord, arkadaş listesi, Claude Code, mod ve hava durumu bağlantıları
- **Yönetim paneli** (`localhost:8765/admin`) ve **Windows açılışında başlat** seçeneği
- **Mini görünüm:** Ekranın sağ altında, her zaman üstte duran küçük bir şerit.
- Pencere kapatılınca saat yanındaki **sistem tepsisinde** çalışmaya devam eder. Sağ tık menüsünde göster, yönetim paneli, adresi kopyala, sunucuyu durdur/başlat ve çıkış seçenekleri var.

Kaldırmak için Ayarlar → Uygulamalar → MiniDesktop. Kaldırıcı sunucuyu durdurur ve Claude Code hook'larını siler. Ayarları ve verileri silip silmemeyi de sorar.

Veriler (eşli cihazlar, Discord token'ları, ayarlar, log) `%LOCALAPPDATA%\MiniDesktop` klasöründe durur. **Bu klasörü kimseyle paylaşma.**

## Linux

```bash
curl -L https://github.com/asimbakii/MiniDesktop/releases/latest/download/MiniDesktop-linux.tar.gz | tar xz
cd MiniDesktop && ./install.sh     # oturumla başlasın istersen: --autostart
```

Kullanıcıya özel kurar (`~/.local/share/minidesktop`), eksik paketleri (apt/dnf/pacman/zypper) sorarak kurar, menüye ekler. Kaldırmak: `./uninstall.sh`.
- Medya: MPRIS (Spotify, Chrome/Firefox, VLC…). Ses: PulseAudio/PipeWire. Pano: wl-clipboard ya da xclip.
- Discord mute/deafen kısayol modu X11/XWayland'de çalışır (xdotool/ydotool/wtype); RPC modu her oturumda çalışır.
- Discord arkadaş listesi için köprüyü `bridge/build-bridge.sh` ile kendin derlemelisin.
- GNOME'da tepsi simgesi için *AppIndicator* eklentisi gerekir. Güvenlik duvarı açıksa: `sudo ufw allow 8765/tcp`.

## Kaynaktan derleme (geliştiriciler için)

- `build.bat` → `dist\MiniDesktop-Setup-<VERSION>.exe`. PyInstaller ile exe üretir, Inno Setup ile kurulum dosyası yapar.
  - Python 3.11+ yoksa `tools\setup.ps1` önce winget ile kurar.
  - Inno Setup gerekir: `winget install JRSoftware.InnoSetup`.
  - Sürüm numarası `VERSION` dosyasında.
- Paketlemeden çalıştırmak: `powershell -File tools\setup.ps1`, ardından `.venv\Scripts\python app\launcher.py`. Bu modda veriler proje içindeki `data/` klasöründe tutulur.
- Discord Social SDK köprüsü `bridge\build-bridge.bat` ile derlenirse pakete kendiliğinden eklenir.

### Ağ adresi (IP)
Servis PC'nin ev ağındaki adresini her açılışta kendisi bulur; VPN, Hyper-V, VirtualBox, WSL gibi sanal adaptörleri eler. QR kod her zaman güncel adresle üretilir.
- Birden fazla ağ varsa (örn. hem Wi-Fi hem Ethernet), yönetim sayfasından adres seçebilirsin.
- Modem PC'ye yeni bir IP verirse servis bunu 15 saniye içinde fark eder ve yönetim sayfasını açıp haber verir. Tablette "PC'ye bağlanılamıyor" ekranı çıkar; QR'ı yeniden okutman yeterli.
- Bunun hiç olmaması için modemden PC'ye sabit IP ver ("DHCP rezervasyonu").

### Tablette uygulama olarak kurmak (isteğe bağlı)
Chrome, "uygulama olarak yükleme"yi (tam ekran, ekranı açık tutma) sadece güvenli adreslerde açıyor. Yönetim sayfasındaki **"Tablette uygulama olarak kur"** bölümü, senin PC'nin adresiyle hazır talimatı gösterir:
1. Tablette Chrome'da `chrome://flags/#unsafely-treat-insecure-origin-as-secure` adresini aç.
2. Yönetim sayfasında yazan adresi (örn. `http://192.168.1.50:8765`) kutuya gir, **Enabled** yap, **Relaunch**'a bas.
3. MiniDesktop'ı aç, Chrome menüsünden **Uygulamayı yükle**'yi seç.

## Gereksinimler
- Windows 10/11 (x64): kurulum dosyasıyla Python gerekmez.
- Linux: Python 3.10+, systemd, PulseAudio ya da PipeWire.
- Discord Social SDK köprüsünü derlemek için: Visual Studio 2022+ ("C++ ile masaüstü geliştirme" iş yükü). SDK'nın lisansı gereği SDK dosyaları bu depoda yoktur; herkes kendi Developer Portal hesabından indirir.

## Discord

Developer Portal'a girmek **gerekmez**. Yönetim panelinde (`localhost:8765/admin`) iki kart var:

### Arkadaşlar ve mesajlar (Discord Social SDK)
**Discord ile bağlan**'a bas ve Discord'da açılan pencerede **Yetkilendir**'e tıkla. MiniDesktop'un paylaşılan Discord uygulaması kullanılır; köprü (`dcbridge.exe`) kurulum dosyasında hazır gelir.
- Arkadaş listesi, çevrimiçi durumları ve gelen DM'ler için kişi başına okunmamış sayacı.
- Sayaç servis çalışırken gelen DM'leri sayar; SDK'da "okundu" bilgisi yok. Rozete dokununca ya da PC'den cevap verince sıfırlanır.
- Arkadaşların hangi oyunu oynadığı SDK'da görünmez.
- Discord kuralları gereği 13 yaş altı kullanıcılar bu özelliği kullanamaz.
- İstersen "Gelişmiş" bölümünden kendi Social SDK uygulamanı kullanabilirsin.

### Mikrofon ve kulaklık
- **Kısayol tuşu modu (varsayılan, kurulumsuz):** Discord → Kullanıcı Ayarları → Tuş Atamaları'nda iki kısayol ekle: *Sesi Kapat Aç/Kapat* için `Ctrl+Shift+F9`, *Sağırlaştır Aç/Kapat* için `Ctrl+Shift+F10`. Tuşlar yönetim panelinden değiştirilebilir. Tablet bu kısayolları PC'ye gönderir; mikrofonun açık/kapalı durumu tablette görünmez.
- **Tam kontrol (isteğe bağlı):** Mikrofon durumu ve ses kanalındakileri görmek için kendi Discord uygulamanı açman gerekir, çünkü Discord bu bağlantıya sadece uygulama sahibine izin veriyor. Yönetim panelindeki sihirbaz adım adım götürür: Application ID'yi yapıştırınca uygulamanın OAuth2 sayfasına doğrudan link çıkar. Yaklaşık 3 dakika sürer.

### Kaynaktan derleyenler için
Discord Social SDK dosyaları lisans gereği bu depoda yoktur. SDK'yı kendi Developer Portal hesabından indirip `bridge/sdk/` içine çıkar ve `bridge\build-bridge.bat` ile derle; `build.bat` köprüyü pakete ekler. SDK, koşulları gereği sadece uygulamanın içine gömülü olarak dağıtılabilir; açık kaynak bildirimleri pakette `bridge\Discord-Social-SDK-License-Notices.txt` olarak yer alır. Paylaşılan uygulama yerine kendi uygulamanı kullanmak için `MINIDESKTOP_SOCIAL_APP_ID` ortam değişkenini ayarla ya da `server/social.py` içindeki `DEFAULT_APP_ID`'yi değiştir.

## CPU sıcaklığı

LibreHardwareMonitor'ü yönetici olarak çalıştır ve Options → Remote Web Server'ı aç.

## Dosyalar

- `app/`: Kontrol uygulaması (tkinter + sistem tepsisi) ve exe giriş noktası
- `server/`: Python servisi (FastAPI + WebSocket)
- `web/`: Tablet arayüzü
- `bridge/`: Discord Social SDK köprüsü (C++)
- `installer/`: Inno Setup betiği
- `tools/`: Kurulum, derleme ve Claude hook betikleri

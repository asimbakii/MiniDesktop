"use strict";
/* Dil desteği (Türkçe / English).
   Metinler kodda Türkçe yazılır; İngilizce seçiliyse t("…") sözlükteki karşılığı döndürür.
   Dil PC'deki ayardan gelir (yönetim paneli); değişince sayfa yeni dille yeniden yüklenir. */

const LANG = (() => {
  const q = new URLSearchParams(location.search).get("lang");
  if (q === "tr" || q === "en") return q;
  try {
    const l = localStorage.getItem("md_lang");
    if (l === "tr" || l === "en") return l;
  } catch {}
  return (navigator.language || "").toLowerCase().startsWith("tr") ? "tr" : "en";
})();
const LOCALE = LANG === "tr" ? "tr-TR" : "en-GB";
document.documentElement.lang = LANG;

function t(s, vars) {
  let r = LANG === "en" && Object.prototype.hasOwnProperty.call(I18N_EN, s) ? I18N_EN[s] : s;
  if (vars) r = r.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m));
  return r;
}

// Sunucu farklı bir dil bildirirse kaydet ve sayfayı o dille yeniden yükle
function syncLang(serverLang) {
  if (!serverLang || serverLang === LANG) return;
  try { localStorage.setItem("md_lang", serverLang); } catch {}
  const u = new URL(location.href);
  u.searchParams.set("lang", serverLang);
  location.replace(u.toString());
}

// Statik HTML'i çevir (sayfa yüklenince bir kez)
function applyLang() {
  if (LANG !== "en") return;
  for (const el of document.querySelectorAll("[aria-label],[placeholder],[title]")) {
    for (const a of ["aria-label", "placeholder", "title"]) {
      const v = el.getAttribute(a);
      if (v && I18N_EN[v]) el.setAttribute(a, I18N_EN[v]);
    }
  }
  const done = new Set();
  for (const el of document.querySelectorAll("body *:not(script):not(style)")) {
    const h = el.innerHTML.trim().replace(/\s+/g, " ");
    if (I18N_EN_HTML[h]) { el.innerHTML = I18N_EN_HTML[h]; done.add(el); }
  }
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const s = n.nodeValue.trim();
    if (s && I18N_EN[s] && ![...done].some((d) => d.contains(n))) n.nodeValue = n.nodeValue.replace(s, I18N_EN[s]);
  }
}

// Satır içi HTML içeren öğeler (öğenin innerHTML'i birebir anahtar)
const I18N_EN_HTML = {
  "Tablet PC ile <b>aynı Wi-Fi</b> ağında mı?": "Is the tablet on the <b>same Wi-Fi</b> as the PC?",
  "PC'nin ağ adresi değişmiş olabilir. PC'de açılan MiniDesktop sayfasındaki <b>QR kodu yeniden okut</b>.": "The PC's network address may have changed. <b>Scan the QR code again</b> in the MiniDesktop window on the PC.",
};

const I18N_EN = {
  // eşleme & bağlantı
  "PC'deki MiniDesktop penceresinde görünen 6 haneli PIN'i gir.": "Enter the 6-digit PIN shown in the MiniDesktop window on your PC.",
  "Eşle": "Pair",
  "Eşleşme başarısız": "Pairing failed",
  "Bağlanıyor…": "Connecting…",
  "PC'ye bağlı": "Connected to PC",
  "Bu tabletin eşleşmesi kaldırılmış. PC'deki PIN ile tekrar eşle.": "This tablet was unpaired. Pair again with the PIN shown on the PC.",
  "Bağlantı yok, yeniden deneniyor…": "No connection, retrying…",
  "PC'ye bağlanılamıyor": "Can't reach the PC",
  "Yeniden deneniyor… Bağlanmazsa:": "Retrying… If it doesn't connect:",
  "PC açık ve MiniDesktop çalışıyor mu?": "Is the PC on and MiniDesktop running?",
  "Denenen adres:": "Trying address:",
  // pencere başlıkları
  "Görev Yöneticisi": "Task Manager",
  "Performans": "Performance",
  "Ses karıştırıcısı": "Volume mixer",
  "Çıkış": "Output",
  "Uygulamalar": "Apps",
  "Kaynak Denetimi": "Source Control",
  "Kaynak İzleyicisi": "Resource Monitor",
  "Portlar": "Ports",
  "Süreçler": "Processes",
  "Sadece geliştirme": "Dev only",
  "Pano": "Clipboard",
  "Geçmiş": "History",
  "Snippet'ler": "Snippets",
  "PC panosuna gönder…": "Send to PC clipboard…",
  "Gönder": "Send",
  "Dev Araçları": "Dev Tools",
  // erişilebilirlik etiketleri
  "Önceki": "Previous",
  "Oynat/Duraklat": "Play/Pause",
  "Sonraki": "Next",
  "Sessiz": "Mute",
  "Sessize al": "Mute",
  "Oynatıcı ses seviyesi": "Player volume",
  "GitHub son güncelleme": "GitHub last update",
  "Başlat: modlar ve güç": "Start: modes and power",
  "Hava durumu": "Weather",
  "Discord mikrofon": "Discord microphone",
  "Bekleme ekranı": "Lock screen",
  "Tam ekran": "Full screen",
  "Listeden kaldır": "Remove from list",
  "PC'ye kopyala": "Copy to PC",
  // müzik
  "Otomatik": "Auto",
  "Bilinmeyen parça": "Unknown track",
  "Şu an bir şey çalmıyor": "Nothing is playing",
  "YT Music'te bir şarkı başlat": "Start a song in YT Music",
  "Hoparlör": "Speakers",
  // Discord
  "Çevrimiçi": "Online",
  "Boşta": "Idle",
  "Rahatsız Etmeyin": "Do Not Disturb",
  "Yayında": "Streaming",
  "Çevrimdışı": "Offline",
  "Arkadaş listesini görmek için PC'deki MiniDesktop penceresinde ya da yönetim panelinde <b>Discord ile bağlan</b>'a bas.": "To see your friends list, click <b>Connect with Discord</b> in the MiniDesktop window or the admin panel on your PC.",
  "Bu kurulumda Discord arkadaş köprüsü yok. Kurulum dosyasıyla yüklenen sürümde hazır gelir.": "This installation has no Discord friends bridge. It comes ready in the version installed from the setup file.",
  "PC'de Discord'da açılan pencerede <b>Yetkilendir</b>'e bas.": "Click <b>Authorize</b> in the window Discord opened on your PC.",
  "Bağlantı koptu, yeniden deneniyor…": "Disconnected, retrying…",
  "Bağlantı durdu.": "Connection stopped.",
  "Arkadaşlar": "Friends",
  "Tümü": "All",
  "Ses kanalı": "Voice channel",
  "Direkt mesajlar": "Direct messages",
  "Tümünü okundu say": "Mark all as read",
  "Okunmamış mesaj yok": "No unread messages",
  "Tüm arkadaşlar": "All friends",
  "Şu an çevrimiçi arkadaşın yok": "None of your friends are online",
  "Arkadaş listesi boş": "Your friends list is empty",
  "Ses Bağlandı": "Voice Connected",
  "Bağlantıyı kes": "Disconnect",
  "Mikrofon: kısayol modu": "Mic: shortcut mode",
  "Mikrofon kontrolü kurulmadı": "Mic control not set up",
  "Mikrofonu kapat/aç": "Mute/unmute microphone",
  "Sağırlaştır": "Deafen",
  "Kısayol modu: Discord'da Sessize Al tuş ataması gönderilir": "Shortcut mode: sends Discord's Toggle Mute keybind",
  // performans
  "Bellek": "Memory",
  "Ağ": "Network",
  "Bulunamadı": "Not found",
  // hava
  "Hissedilen {v}°": "Feels like {v}°",
  "Nem %{v}": "Humidity {v}%",
  "Rüzgar {v} km/sa": "Wind {v} km/h",
  "Bugün": "Today",
  "Yarın": "Tomorrow",
  "Yağış %{v}": "Rain {v}%",
  // modlar & başlat menüsü
  "Mod": "Mode",
  "Normal": "Normal",
  "Müzik, Discord, performans, ses": "Music, Discord, performance, volume",
  "Geliştirici": "Developer",
  "Claude Code, git, komutlar, araçlar": "Claude Code, git, commands, tools",
  "Oyun": "Game",
  "Büyük performans, Discord sesi": "Big performance, Discord voice",
  "Gece": "Night",
  "Karartılmış ekran, kırmızı saat": "Dimmed screen, red clock",
  "Kilitle": "Lock",
  "Uyku": "Sleep",
  "Yeniden başlat": "Restart",
  "Kapat": "Shut down",
  "Emin misin?": "Are you sure?",
  "{name}: komut gönderildi": "{name}: command sent",
  "Oyun açılınca Oyun moduna geç": "Switch to Game mode when a game starts",
  "Gece saatlerinde Gece moduna geç": "Switch to Night mode at night",
  "Gece saatlerinde ({from}–{to}) Gece moduna geç": "Switch to Night mode at night ({from}–{to})",
  "Oyun algılanmadı": "No game detected",
  "otomatik": "auto",
  "Claude · {state}{project}{more}": "Claude · {state}{project}{more}",
  "Cevap bekliyor": "Waiting for answer",
  // zaman
  "şimdi": "now",
  "{n} sn": "{n}s",
  "{n} dk": "{n} min",
  "{h} sa {m} dk": "{h} h {m} min",
  "{x} önce": "{x} ago",
  "{x} sonra": "in {x}",
  // Claude Code
  "Çalışıyor": "Working",
  "İzin bekliyor": "Needs permission",
  "Tamamlandı": "Done",
  "Açık Claude Code oturumu yok.": "No open Claude Code sessions.",
  "Claude Code entegrasyonu kurulu değil. PC'de localhost:8765/admin → Geliştirici modu → Kur.": "Claude Code integration is not installed. On the PC: localhost:8765/admin → Developer mode → Install.",
  "{n} oturum": "{n} session(s)",
  "{n} araç çağrısı": "{n} tool call(s)",
  // git
  "Başarılı": "Passed",
  "Atlandı": "Skipped",
  "İptal": "Cancelled",
  "Başarısız": "Failed",
  "Yok": "None",
  "GitHub · {x} önce": "GitHub · {x} ago",
  "GitHub yükleniyor…": "Loading GitHub…",
  "Repolar": "Repositories",
  "İzlenen repo yok. Yönetim sayfasından ekle ya da bir repoda Claude Code çalıştır.": "No watched repositories. Add one in the admin panel or run Claude Code in a repo.",
  "VS Code'da aç": "Open in VS Code",
  "temiz": "clean",
  "İnceleme bekleyen PR'lar": "PRs awaiting your review",
  "Açık PR'larım": "My open PRs",
  "[Taslak] ": "[Draft] ",
  // komutlar
  "Komutlar": "Commands",
  "Hazır": "Ready",
  "Hata": "Error",
  "Durduruldu": "Stopped",
  "Komut yok. PC'de localhost:8765/admin → Geliştirici modu → Komut butonları.": "No commands. On the PC: localhost:8765/admin → Developer mode → Command buttons.",
  "Durdur": "Stop",
  "Çalıştır": "Run",
  "Henüz çıktı yok.": "No output yet.",
  // kaynak izleyicisi
  "Port": "Port",
  "Süreç": "Process",
  "Adres": "Address",
  "Ad": "Name",
  "CPU": "CPU",
  "yerel": "local",
  "ağ": "network",
  "Dinlemede geliştirme sunucusu yok.": "No dev servers listening.",
  "Dinlemede port yok.": "No ports listening.",
  "PC'de tarayıcıda aç": "Open in PC browser",
  "{name} sonlandır": "End {name}",
  "{n} süreci sonlandır": "End {n} processes",
  "Sonlandır": "End task",
  "Geliştirme süreci yok.": "No dev processes.",
  "Emin misin? {label}": "Sure? {label}",
  // pano
  "PC'de bir metin kopyaladığında burada görünür. Şifre yöneticilerinin içerikleri gösterilmez.": "Text you copy on the PC shows up here. Password manager content is never shown.",
  "Geçmişi temizle": "Clear history",
  "Göster": "Show",
  "Gizle": "Hide",
  "gizli olabilir · {n} karakter": "may be secret · {n} chars",
  "Snippet yok. PC'de localhost:8765/admin → Geliştirici modu → Snippet'ler.": "No snippets. On the PC: localhost:8765/admin → Developer mode → Snippets.",
  // dev araçları
  "Zaman": "Time",
  "BÜYÜK HARF": "UPPERCASE",
  "Yeni üret": "Generate",
  "Tarih ya da Unix zamanı tanınmadı.": "Could not parse the date or Unix time.",
  "Unix (sn)": "Unix (s)",
  "Yerel": "Local",
  "Göreli": "Relative",
  "Unix zamanı ya da tarih (boş = şimdi)": "Unix time or date (empty = now)",
  "Geçerli bir JWT değil.": "Not a valid JWT.",
  "Geçerli · {x} sonra sona erecek": "Valid · expires in {x}",
  "Süresi dolmuş · {x} önce": "Expired · {x} ago",
  "Payload'ı PC'ye kopyala": "Copy payload to PC",
  "Çözülemedi: Base64/JSON hatası.": "Could not decode: Base64/JSON error.",
  "JWT yapıştır ya da PC panosundan al": "Paste a JWT or take it from the PC clipboard",
  "PC panosundan al": "From PC clipboard",
  "Metin": "Text",
  "Kodla": "Encode",
  "Kodlanamadı": "Could not encode",
  "Çöz": "Decode",
  "Çözülemedi (geçerli bir {what} değil)": "Could not decode (not valid {what})",
  "URL kodlaması": "URL encoding",
};

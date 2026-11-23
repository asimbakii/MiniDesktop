"use strict";

/* ================= Yardımcılar ================= */
const $ = (s, r = document) => r.querySelector(s);
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}
const ICONS = {
  play: '<path d="M8 5.14v13.72a1 1 0 0 0 1.5.86l11-6.86a1 1 0 0 0 0-1.72l-11-6.86A1 1 0 0 0 8 5.14z"/>',
  pause: '<path d="M6 4h4v16H6zM14 4h4v16h-4z"/>',
  next: '<path d="M5 5.5v13a.75.75 0 0 0 1.15.63L15.5 13v5.5h2v-13h-2V11L6.15 4.87A.75.75 0 0 0 5 5.5z"/>',
  prev: '<path d="M19 5.5v13a.75.75 0 0 1-1.15.63L8.5 13v5.5h-2v-13h2V11l9.35-6.13A.75.75 0 0 1 19 5.5z"/>',
  mic: '<path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2z"/>',
  headphones: '<path d="M12 3a9 9 0 0 0-9 9v7a2 2 0 0 0 2 2h2v-8H5v-1a7 7 0 0 1 14 0v1h-2v8h2a2 2 0 0 0 2-2v-7a9 9 0 0 0-9-9z"/>',
  slash: '<path d="M3.3 2 22 20.7 20.7 22 2 3.3z" fill="#f23f43"/>',
  hangup: '<path d="M12 9c-1.6 0-3.15.25-4.6.72v3.1c0 .39-.23.74-.56.9-.98.49-1.87 1.12-2.66 1.85a1 1 0 0 1-1.41-.01L.29 13.08a.96.96 0 0 1 0-1.36C3.34 8.78 7.46 7 12 7s8.66 1.78 11.71 4.72a1 1 0 0 1 0 1.42l-2.48 2.48a1 1 0 0 1-1.41.01 11.3 11.3 0 0 0-2.67-1.85 1 1 0 0 1-.56-.9v-3.1C15.15 9.25 13.6 9 12 9z"/>',
  speaker: '<path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0 0 14 7.97v8.05A4.48 4.48 0 0 0 16.5 12zM14 3.23v2.06a7 7 0 0 1 0 13.42v2.06A9 9 0 0 0 14 3.23z"/>',
  speakerOff: '<path d="M3 9v6h4l5 5V4L7 9H3z"/><path d="m15.3 9.7 1.4-1.4L19 10.6l2.3-2.3 1.4 1.4-2.3 2.3 2.3 2.3-1.4 1.4-2.3-2.3-2.3 2.3-1.4-1.4 2.3-2.3z"/>',
  signal: '<path d="M4 18h3v-4H4zm5 0h3V9H9zm5 0h3V5h-3z"/>',
  at: '<path d="M12 2a10 10 0 1 0 5 18.66v-2.3A8 8 0 1 1 20 12v1.5a1.5 1.5 0 0 1-3 0V12a5 5 0 1 0-1.46 3.53A3.5 3.5 0 0 0 22 13.5V12A10 10 0 0 0 12 2zm0 13a3 3 0 1 1 0-6 3 3 0 0 1 0 6z"/>',
  friends: '<path d="M13 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM3 5v3H0v2h3v3h2v-3h3V8H5V5H3zm10 7c-2.67 0-8 1.34-8 4v3h16v-3c0-2.66-5.33-4-8-4z"/>',
  lock: '<path d="M12 2a5 5 0 0 0-5 5v3H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8a2 2 0 0 0-2-2h-1V7a5 5 0 0 0-5-5zm-3 8V7a3 3 0 0 1 6 0v3H9z"/>',
  full: '<path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/>',
};
const icon = (...names) => `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">${names.map((n) => ICONS[n]).join("")}</svg>`;
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch {} },
  del(k) { try { localStorage.removeItem(k); } catch {} },
};
const nf1 = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const nf0 = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0 });
const GB = 1024 ** 3;
function fmtTime(s) {
  s = Math.max(0, Math.floor(s || 0));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${x}` : `${m}:${x}`;
}
function fmtRate(bytes) {
  const b = (bytes || 0) * 8;
  if (b < 1e3) return `${nf0.format(b)} bps`;
  if (b < 1e6) return `${nf0.format(b / 1e3)} Kbps`;
  if (b < 1e9) return `${nf1.format(b / 1e6)} Mbps`;
  return `${nf1.format(b / 1e9)} Gbps`;
}
function fmtUptime(s) {
  s = Math.floor(s || 0);
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return `${d}:${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(x).padStart(2, "0")}`;
}
const temp = (t) => (t == null ? "—" : `${nf0.format(t)} °C`);
let toastTimer;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 3500);
}

/* ================= Bağlantı & eşleme ================= */
let token = store.get("md_token");
let ws = null;
let retry = 0;

function deviceName() {
  // Chrome gizlilik için model adını çoğu zaman "K" olarak gönderir; o durumda genel ad kullan.
  const m = navigator.userAgent.match(/Android [\d.]+; ([^;)]+)/);
  const model = m ? m[1].replace(/ Build.*/, "").trim() : "";
  const ua = navigator.userAgent;
  if (/HarmonyOS|OpenHarmony|ArkWeb/i.test(ua)) return "HarmonyOS tablet";
  // iPadOS Safari kendini Mac olarak tanıtır; dokunmatik ekranlı "Mac" = iPad
  if (/iPad/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)) return "iPad";
  if (model && model !== "K") return model;
  return /Android/.test(ua) ? "Android tablet" : "Tablet";
}
function showPair(msg) {
  $("#desk").hidden = true;
  $("#pair").hidden = false;
  if (msg) $("#pair-msg").textContent = msg;
  setTimeout(() => $("#pair-pin").focus(), 50);
}
async function pair(pin) {
  $("#pair-err").textContent = "";
  try {
    const r = await fetch("/api/pair", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pin, name: deviceName() }) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || "Eşleşme başarısız");
    token = j.token;
    store.set("md_token", token);
    history.replaceState(null, "", "/");
    startDesk();
  } catch (e) {
    showPair();
    $("#pair-err").textContent = e.message;
  }
}
$("#pair-form").addEventListener("submit", (e) => { e.preventDefault(); pair($("#pair-pin").value.trim()); });
$("#pair-pin").addEventListener("input", (e) => { const v = e.target.value.replace(/\D/g, "").slice(0, 6); e.target.value = v; if (v.length === 6) pair(v); });

let offlineTimer = null;
function setConn(kind, text) {
  $("#conn").className = "conn " + kind;
  $("#conn-text").textContent = text;
  // Bağlantı 6 sn'den uzun koparsa sebepleri ve çözümü göster
  if (kind === "ok") {
    clearTimeout(offlineTimer);
    offlineTimer = null;
    $("#offline").hidden = true;
  } else if (!offlineTimer && $("#offline").hidden) {
    offlineTimer = setTimeout(() => {
      $("#off-host").textContent = location.host;
      $("#offline").hidden = false;
    }, 6000);
  }
}
function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(token)}`);
  setConn("", "Bağlanıyor…");
  ws.onopen = () => { retry = 0; setConn("ok", "PC'ye bağlı"); };
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.type === "state") render(m);
    else if (m.type === "error" || m.type === "toast") toast(m.message);
    else if (m.type === "clip_text" && typeof onClipText === "function") onClipText(m);
  };
  ws.onclose = (e) => {
    if (e.code === 4401) {
      store.del("md_token");
      token = null;
      showPair("Bu tabletin eşleşmesi kaldırılmış. PC'deki PIN ile tekrar eşle.");
      return;
    }
    setConn("bad", "Bağlantı yok, yeniden deneniyor…");
    setTimeout(connect, Math.min(5000, 400 * 2 ** retry++));
  };
}
function send(target, action, extra = {}) {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: "cmd", target, action, ...extra }));
}
function startDesk() {
  $("#pair").hidden = true;
  $("#desk").hidden = false;
  connect();
}

/* ================= Kaydırıcılar ================= */
function bindRange(input, onSend) {
  let last = 0, timer;
  const paint = () => input.style.setProperty("--pct", input.value + "%");
  input.addEventListener("input", () => {
    paint();
    input._busy = Date.now();
    clearTimeout(timer);
    const now = Date.now();
    if (now - last > 80) { last = now; onSend(input.value / 100); }
    else timer = setTimeout(() => { last = Date.now(); onSend(input.value / 100); }, 80);
  });
  input.addEventListener("change", () => { input._busy = Date.now(); onSend(input.value / 100); });
}
function setRange(input, v) {
  if (input._busy && Date.now() - input._busy < 1200) return;
  input.value = Math.round((v || 0) * 100);
  input.style.setProperty("--pct", input.value + "%");
}

/* ================= Müzik ================= */
const M = { pos: 0, dur: 0, playing: false, t0: 0, drag: false, art: null, srcSig: "", volKey: null };
$("#b-prev").innerHTML = icon("prev");
$("#b-next").innerHTML = icon("next");
$("#b-play").innerHTML = icon("play");
$("#b-prev").onclick = () => send("media", "prev");
$("#b-next").onclick = () => send("media", "next");
$("#b-play").onclick = () => { M.playing = !M.playing; M.pos = curPos(); M.t0 = performance.now(); $("#b-play").innerHTML = icon(M.playing ? "pause" : "play"); send("media", "toggle"); };
bindRange($("#mv-range"), (v) => M.volKey && send("audio", "app_volume", { key: M.volKey, value: v }));
$("#mv-mute").onclick = () => M.volKey && send("audio", "app_mute", { key: M.volKey });

function curPos() {
  const p = M.pos + (M.playing ? (performance.now() - M.t0) / 1000 : 0);
  return M.dur ? Math.min(p, M.dur) : p;
}
function paintProgress(p) {
  const f = M.dur ? Math.max(0, Math.min(1, p / M.dur)) : 0;
  $("#p-fill").style.width = f * 100 + "%";
  $("#p-knob").style.left = f * 100 + "%";
  $("#t-pos").textContent = fmtTime(p);
  $("#t-dur").textContent = fmtTime(M.dur);
}
(function tick() {
  if (!M.drag) paintProgress(curPos());
  requestAnimationFrame(tick);
})();
(function bindSeek() {
  const bar = $("#progress");
  const frac = (e) => { const r = bar.getBoundingClientRect(); return Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)); };
  bar.addEventListener("pointerdown", (e) => { if (!M.dur) return; M.drag = true; bar.classList.add("drag"); bar.setPointerCapture(e.pointerId); paintProgress(frac(e) * M.dur); });
  bar.addEventListener("pointermove", (e) => { if (M.drag) paintProgress(frac(e) * M.dur); });
  const end = (e) => {
    if (!M.drag) return;
    M.drag = false;
    bar.classList.remove("drag");
    const target = frac(e) * M.dur;
    M.pos = target; M.t0 = performance.now();
    send("media", "seek", { value: target });
  };
  bar.addEventListener("pointerup", end);
  bar.addEventListener("pointercancel", () => { M.drag = false; bar.classList.remove("drag"); });
})();

function musicTheme(m) {
  const label = m.source_label || "";
  if (/spotify/i.test(label)) return ["spotify", "Spotify", "sp-logo"];
  if (!m.available || /chrome|edge|firefox|opera|brave/i.test(label)) return ["ytm", "YouTube Music", "ytm-logo"];
  return ["generic", label, ""];
}
function artColor(img) {
  try {
    const c = document.createElement("canvas");
    c.width = c.height = 8;
    const x = c.getContext("2d");
    x.drawImage(img, 0, 0, 8, 8);
    const d = x.getImageData(0, 0, 8, 8).data;
    let r = 0, g = 0, b = 0;
    for (let i = 0; i < d.length; i += 4) { r += d[i]; g += d[i + 1]; b += d[i + 2]; }
    const n = d.length / 4;
    return `rgb(${(r / n) | 0}, ${(g / n) | 0}, ${(b / n) | 0})`;
  } catch { return "#222"; }
}
$("#art").addEventListener("load", (e) => {
  e.target.classList.add("show");
  $("#w-music").style.setProperty("--m-art", artColor(e.target));
  const wp = $("#wallpaper");
  wp.style.backgroundImage = `url("${e.target.src}")`;
  wp.classList.add("has-art");
});

function renderMusic(m, audio) {
  const [theme, appName, logo] = musicTheme(m);
  const win = $("#w-music");
  win.classList.remove("theme-ytm", "theme-spotify", "theme-generic");
  win.classList.add("theme-" + theme);
  $("#music-app").textContent = appName;
  $("#music-logo").className = "tb-icon " + logo;
  $("#music-src").textContent = theme === "ytm" && m.available ? m.source_label : "";

  // Birden fazla kaynak varsa seçici
  const srcs = m.sources || [];
  const sig = JSON.stringify([srcs.map((s) => s.id), m.preferred, m.source]);
  if (sig !== M.srcSig) {
    M.srcSig = sig;
    const box = $("#sources");
    box.replaceChildren();
    if (srcs.length > 1) {
      const auto = el("button", m.preferred ? "" : "on", "Otomatik");
      auto.onclick = () => send("media", "select_source", { value: null });
      box.append(auto);
      for (const s of srcs) {
        const b = el("button", m.preferred === s.id ? "on" : "", s.label);
        b.onclick = () => send("media", "select_source", { value: s.id });
        box.append(b);
      }
    }
  }

  $("#m-title").textContent = m.available ? m.title || "Bilinmeyen parça" : "Şu an bir şey çalmıyor";
  $("#m-artist").textContent = m.available ? [m.artist, m.album].filter(Boolean).join(" • ") : "YT Music'te bir şarkı başlat";

  if (m.art !== M.art) {
    M.art = m.art;
    const img = $("#art");
    if (m.art) img.src = `/api/art?token=${encodeURIComponent(token)}&v=${m.art}`;
    else {
      img.classList.remove("show");
      img.removeAttribute("src");
      $("#wallpaper").classList.remove("has-art");
      $("#wallpaper").style.backgroundImage = "";
      win.style.removeProperty("--m-art");
    }
  }

  if (!M.drag) {
    M.pos = m.position || 0;
    M.dur = m.duration || 0;
    M.playing = !!m.playing;
    M.t0 = performance.now();
  }
  $("#progress").classList.toggle("disabled", !m.can_seek || !M.dur);
  $("#b-play").innerHTML = icon(m.playing ? "pause" : "play");
  $("#b-next").classList.toggle("dim", !m.can_next);
  $("#b-prev").classList.toggle("dim", !m.can_prev);

  // Oynatıcının kendi ses seviyesi (ör. Chrome)
  const app = (audio.apps || []).find((a) => m.source_label && a.name.toLowerCase() === m.source_label.toLowerCase());
  M.volKey = app ? app.key : null;
  const r = $("#mv-range");
  r.disabled = !app;
  $("#mv-mute").innerHTML = icon(app && app.muted ? "speakerOff" : "speaker");
  if (app) setRange(r, app.muted ? 0 : app.volume);
}

/* ================= Ses karıştırıcısı ================= */
const APP_COLORS = { "chrome.exe": "#1a73e8", "discord.exe": "#5865f2", "spotify.exe": "#1db954", "steam.exe": "#1b2838", "steamwebhelper.exe": "#1b2838", "msedge.exe": "#0c59a4", "firefox.exe": "#e66000", "__system__": "#3a3a3a" };
const PALETTE = ["#c2410c", "#0e7490", "#7c3aed", "#be185d", "#15803d", "#a16207", "#1d4ed8"];
function colorFor(key) {
  if (APP_COLORS[key]) return APP_COLORS[key];
  let h = 0;
  for (const ch of key) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return PALETTE[h % PALETTE.length];
}
const mixRows = new Map();
function makeMixRow(key, master) {
  const row = el("div", "mx-row" + (master ? " master" : ""));
  const ic = el("div", "ic");
  const nm = el("div", "nm");
  const val = el("div", "val");
  const line = el("div", "ctl-line");
  const mute = el("button", "mute");
  mute.setAttribute("aria-label", "Sessize al");
  const range = el("input");
  range.type = "range"; range.min = 0; range.max = 100;
  line.append(mute, range);
  row.append(ic, nm, val, line);
  if (master) {
    ic.innerHTML = icon("speaker");
    bindRange(range, (v) => send("audio", "master_volume", { value: v }));
    mute.onclick = () => send("audio", "master_mute");
  } else {
    ic.style.background = colorFor(key);
    bindRange(range, (v) => send("audio", "app_volume", { key, value: v }));
    mute.onclick = () => send("audio", "app_mute", { key });
  }
  range.addEventListener("input", () => { val.textContent = range.value; });
  return { row, ic, nm, val, mute, range };
}
function fillMixRow(r, name, vol, muted, active, master) {
  r.row.classList.toggle("muted", muted);
  if (!master) r.ic.textContent = name.slice(0, 1).toUpperCase();
  r.nm.replaceChildren();
  if (active && !master) r.nm.append(el("i"));
  r.nm.append(document.createTextNode(name));
  r.mute.innerHTML = icon(muted ? "speakerOff" : "speaker");
  setRange(r.range, vol);
  if (!(r.range._busy && Date.now() - r.range._busy < 1200)) r.val.textContent = Math.round(vol * 100);
}
let masterRow = null;
function renderMixer(a) {
  if (!a.master) return;
  if (!masterRow) { masterRow = makeMixRow("__master__", true); $("#mx-master").replaceWith(masterRow.row); }
  fillMixRow(masterRow, a.master.device || "Hoparlör", a.master.volume, a.master.muted, false, true);
  const box = $("#mx-apps");
  const keys = (a.apps || []).map((x) => x.key);
  for (const [k, r] of mixRows) if (!keys.includes(k)) { r.row.remove(); mixRows.delete(k); }
  for (const app of a.apps || []) {
    let r = mixRows.get(app.key);
    if (!r) { r = makeMixRow(app.key, false); mixRows.set(app.key, r); }
    fillMixRow(r, app.name, app.volume, app.muted, app.active, false);
    box.append(r.row); // sırayı korur
  }
}

/* ================= Discord ================= */
const STATUS_TR = { online: "Çevrimiçi", idle: "Boşta", dnd: "Rahatsız Etmeyin", streaming: "Yayında", offline: "Çevrimdışı", unknown: "" };
let dcSig = "";
let dcTab = store.get("md_dc_tab") || "online";
function avatar(src, cls = "av") {
  const i = el("img", cls);
  i.src = src || "https://cdn.discordapp.com/embed/avatars/0.png";
  i.alt = "";
  i.loading = "lazy";
  i.referrerPolicy = "no-referrer";
  return i;
}
function avatarWithStatus(src, status, size = 32) {
  const w = el("span", "avw");
  w.style.setProperty("--s", size + "px");
  w.append(avatar(src, "av"));
  if (status && status !== "unknown") w.append(el("i", "dot " + status));
  return w;
}
function dcEmpty(title, html) {
  const d = el("div", "dc-empty");
  if (title) d.append(el("b", null, title));
  const p = el("div");
  p.innerHTML = html;
  d.append(p);
  return d;
}
function dcCat(text, btnText, onBtn) {
  const cat = el("div", "dc-cat");
  cat.append(el("span", null, text));
  if (btnText) {
    const b = el("button", null, btnText);
    b.onclick = onBtn;
    cat.append(b);
  }
  return cat;
}
const SOCIAL_MSG = {
  not_configured: "Arkadaş listesini görmek için PC'deki MiniDesktop penceresinde ya da yönetim panelinde <b>Discord ile bağlan</b>'a bas.",
  no_bridge: "Bu kurulumda Discord arkadaş köprüsü yok. Kurulum dosyasıyla yüklenen sürümde hazır gelir.",
  starting: "Bağlanıyor…",
  connecting: "Bağlanıyor…",
  authorizing: "PC'de Discord'da açılan pencerede <b>Yetkilendir</b>'e bas.",
  disconnected: "Bağlantı koptu, yeniden deneniyor…",
  stopped: "Bağlantı durdu.",
};
function renderDiscord(d, so) {
  const sig = JSON.stringify([d, so, dcTab]);
  if (sig === dcSig) return;
  dcSig = sig;
  const head = $("#dc-head"), body = $("#dc-body"), voice = $("#dc-voice"), user = $("#dc-user");
  head.replaceChildren();
  body.replaceChildren();
  user.replaceChildren();
  const rpcReady = d.status === "ready";
  const socialReady = so.status === "ready";

  // Başlık çubuğundaki toplam okunmamış rozeti
  const tb = $("#dc-total");
  tb.textContent = so.unread_total > 99 ? "99+" : String(so.unread_total || "");
  tb.hidden = !so.unread_total;

  // Üst başlık: Arkadaşlar | Çevrimiçi | Tümü
  head.innerHTML = icon("friends");
  head.append(el("span", "dc-title", "Arkadaşlar"), el("span", "dc-sep"));
  for (const [key, label] of [["online", "Çevrimiçi"], ["all", "Tümü"]]) {
    const b = el("button", "dc-tab" + (dcTab === key ? " on" : ""), label);
    b.onclick = () => { dcTab = key; store.set("md_dc_tab", key); dcSig = ""; renderDiscord(d, so); };
    head.append(b);
  }

  // 1) Ses kanalı (RPC)
  if (rpcReady && d.channel) {
    body.append(dcCat("Ses kanalı" + (d.channel.guild ? " — " + d.channel.guild : "")));
    const ch = el("div", "dc-channel");
    ch.innerHTML = icon("speaker");
    ch.append(document.createTextNode(d.channel.name));
    body.append(ch);
    for (const m of d.members) {
      const row = el("div", "dc-member" + (m.speaking ? " speaking" : ""));
      const st = el("span", "st");
      if (m.muted) st.innerHTML += icon("mic", "slash");
      if (m.deaf) st.innerHTML += icon("headphones", "slash");
      row.append(avatar(m.avatar), el("span", "nm", m.name), st);
      body.append(row);
    }
  }

  // 2) Direkt mesajlar (Social SDK)
  const unread = so.unread || [];
  body.append(dcCat("Direkt mesajlar", unread.length ? "Tümünü okundu say" : null, () => send("social", "clear_all")));
  if (!socialReady && !unread.length) {
    const box = dcEmpty("", SOCIAL_MSG[so.status] || "");
    if (so.error) box.append(el("div", "dc-err", so.error));
    body.append(box);
  } else if (!unread.length) {
    body.append(el("div", "dc-none", "Okunmamış mesaj yok"));
  }
  for (const u of unread) {
    const b = el("button", "dc-dm unread");
    const tx = el("div", "tx");
    tx.append(el("div", "nm", u.name), el("div", "msg", u.last || ""));
    b.append(avatarWithStatus(u.avatar, u.status, 32), tx, el("span", "badge", u.count > 99 ? "99+" : String(u.count)));
    b.onclick = () => send("social", "clear_unread", { value: u.id });
    body.append(b);
  }

  // 3) Arkadaş listesi
  if (socialReady) {
    const list = dcTab === "online" ? so.friends.filter((f) => f.status !== "offline" && f.status !== "unknown") : so.friends;
    body.append(dcCat((dcTab === "online" ? "Çevrimiçi" : "Tüm arkadaşlar") + " — " + list.length));
    if (!list.length) body.append(el("div", "dc-none", dcTab === "online" ? "Şu an çevrimiçi arkadaşın yok" : "Arkadaş listesi boş"));
    for (const f of list) {
      const row = el("div", "dc-friend" + (f.status === "offline" ? " off" : ""));
      const tx = el("div", "tx");
      tx.append(el("div", "nm", f.name), el("div", "msg", STATUS_TR[f.status] || ""));
      row.append(avatarWithStatus(f.avatar, f.status, 32), tx);
      body.append(row);
    }
  } else if (so.error && unread.length) {
    body.append(el("div", "dc-err", so.error));
  }

  // "Ses Bağlandı" çubuğu
  voice.hidden = !(rpcReady && d.channel);
  if (rpcReady && d.channel) {
    voice.replaceChildren();
    const tx = el("div", "vtx");
    const ok = el("div", "vok");
    ok.innerHTML = icon("signal");
    ok.append(document.createTextNode("Ses Bağlandı"));
    tx.append(ok, el("div", "vch", [d.channel.name, d.channel.guild].filter(Boolean).join(" / ")));
    const hang = el("button", "dc-btn hang");
    hang.innerHTML = icon("hangup");
    hang.setAttribute("aria-label", "Bağlantıyı kes");
    hang.onclick = () => send("discord", "leave_voice");
    voice.append(tx, hang);
  }

  // Kullanıcı paneli (sol alt)
  const meUser = d.user || so.me;
  const me = el("div", "me");
  me.append(avatar(meUser && meUser.avatar, ""), el("i", rpcReady || socialReady ? "" : "off"));
  const who = el("div", "who");
  // Kısayol modunda durum okunamaz: düğmeler çalışır ama açık/kapalı gösterilmez
  const keysMode = d.control === "keys";
  let sub = rpcReady || socialReady ? "@" + ((meUser && meUser.username) || "") : "Çevrimdışı";
  if (!rpcReady && keysMode) sub = "Mikrofon: kısayol modu";
  else if (!rpcReady && socialReady) sub = "Mikrofon kontrolü kurulmadı";
  who.append(el("b", null, meUser ? meUser.name : "Discord"), el("span", null, sub));
  const mic = el("button", "dc-btn" + (rpcReady && d.mute ? " on" : ""));
  mic.innerHTML = rpcReady && d.mute ? icon("mic", "slash") : icon("mic");
  mic.setAttribute("aria-label", "Mikrofonu kapat/aç");
  mic.onclick = () => { send("discord", "toggle_mute"); if (keysMode) flashBtn(mic); };
  const hp = el("button", "dc-btn" + (rpcReady && d.deaf ? " on" : ""));
  hp.innerHTML = rpcReady && d.deaf ? icon("headphones", "slash") : icon("headphones");
  hp.setAttribute("aria-label", "Sağırlaştır");
  hp.onclick = () => { send("discord", "toggle_deaf"); if (keysMode) flashBtn(hp); };
  mic.disabled = hp.disabled = !(rpcReady || keysMode);
  user.append(me, who, mic, hp);
}
function flashBtn(b) {
  b.classList.add("flash");
  setTimeout(() => b.classList.remove("flash"), 450);
}

/* ================= Görev Yöneticisi: halka göstergeler ================= */
const RING_C = 2 * Math.PI * 42;
const RINGS = [
  { k: "cpu", name: "CPU", color: "#2fa8e0" },
  { k: "gpu", name: "GPU", color: "#3ec07a" },
  { k: "ram", name: "Bellek", color: "#b65cf2" },
  { k: "net", name: "Ağ", color: "#e8913a" },
];
let ringEls = null;
let netPeak = 125000; // en az 1 Mbps ölçek; yavaşça söner
function buildRings() {
  const box = $("#rings");
  ringEls = {};
  for (const r of RINGS) {
    const w = el("div", "ring");
    w.style.setProperty("--c", r.color);
    w.innerHTML = `<div class="g"><svg viewBox="0 0 100 100" aria-hidden="true"><circle class="trk" cx="50" cy="50" r="42"/><circle class="val" cx="50" cy="50" r="42" stroke-dasharray="${RING_C}" stroke-dashoffset="${RING_C}"/></svg><div class="num"><b>–</b><small></small></div></div><div class="lbl"></div><div class="sub"></div>`;
    w.querySelector(".lbl").textContent = r.name;
    box.append(w);
    ringEls[r.k] = { val: w.querySelector(".val"), num: w.querySelector(".num b"), unit: w.querySelector(".num small"), sub: w.querySelector(".sub") };
  }
}
function setRing(k, pct, num, unit, sub, hot = false) {
  const r = ringEls[k];
  const p = Math.max(0, Math.min(100, pct || 0));
  r.val.style.strokeDashoffset = String(RING_C * (1 - p / 100));
  r.num.textContent = num;
  r.unit.textContent = unit;
  r.sub.textContent = sub;
  r.sub.classList.toggle("hot", hot);
}
function renderStats(s) {
  if (!s || !s.cpu) return;
  if (!ringEls) buildRings();
  netPeak = Math.max(netPeak * 0.97, s.net.down, s.net.up, 125000);
  const cpuName = (s.cpu.name || "").replace(/AMD |Intel\(R\) |Core\(TM\) |\s+\d+-Core Processor/g, "");
  setRing("cpu", s.cpu.load, nf0.format(s.cpu.load), "%", s.cpu.temp != null ? temp(s.cpu.temp) : cpuName, s.cpu.temp > 85);
  const g = s.gpu;
  if (g) {
    const vram = g.mem_total ? ` · ${nf1.format(g.mem_used / GB)} GB` : "";
    setRing("gpu", g.load, nf0.format(g.load ?? 0), "%", temp(g.temp) + vram, g.temp > 83);
  } else {
    setRing("gpu", 0, "–", "", "Bulunamadı");
  }
  setRing("ram", s.ram.percent, nf0.format(s.ram.percent), "%", `${nf1.format(s.ram.used / GB)} / ${nf0.format(s.ram.total / GB)} GB`);
  const [dn, du] = fmtRate(s.net.down).split(" ");
  setRing("net", (s.net.down / netPeak) * 100, dn, du, `↑ ${fmtRate(s.net.up)}`);
}

/* ================= Hava durumu ================= */
function sunSVG(cx, cy, r) {
  const rays = [0, 45, 90, 135, 180, 225, 270, 315].map((a) => {
    const t = (a * Math.PI) / 180;
    const p = (d) => `${(cx + Math.cos(t) * d).toFixed(1)} ${(cy + Math.sin(t) * d).toFixed(1)}`;
    return `M${p(r + 4)}L${p(r + 9)}`;
  }).join("");
  return `<path d="${rays}" stroke="#FFC83D" stroke-width="3.5" stroke-linecap="round"/><circle cx="${cx}" cy="${cy}" r="${r}" fill="#FFC83D"/>`;
}
const MOON = '<path d="M38 10a20 20 0 1 0 16 30A16 16 0 0 1 38 10z" fill="#F1E6B8"/>';
const SMALL_MOON = '<path d="M26 8a13 13 0 1 0 11 20A10.5 10.5 0 0 1 26 8z" fill="#F1E6B8"/>';
const cloud = (fill = "#E4E9EF") => `<path d="M19 50h28a11 11 0 0 0 1-22 15 15 0 0 0-28-3 12 12 0 0 0-1 25z" fill="${fill}"/>`;
const drops = (n) => [18, 28, 38, 48].slice(0, n).map((x) => `<path d="M${x} 55l-3 7" stroke="#4CC2FF" stroke-width="3.5" stroke-linecap="round"/>`).join("");
function wxIcon(kind, isDay = true) {
  let s;
  switch (kind) {
    case "sun": s = isDay ? sunSVG(32, 32, 12) : MOON; break;
    case "sun-cloud": s = (isDay ? sunSVG(24, 22, 9) : SMALL_MOON) + cloud(); break;
    case "cloud": s = cloud(); break;
    case "fog": s = '<path d="M12 26h40M8 36h48M14 46h36" stroke="#C9D1DA" stroke-width="4" stroke-linecap="round"/>'; break;
    case "drizzle": s = cloud() + drops(2); break;
    case "rain": s = cloud("#C3CBD5") + drops(4); break;
    case "snow": s = cloud() + [20, 32, 44].map((x) => `<circle cx="${x}" cy="58" r="3" fill="#fff"/>`).join(""); break;
    case "storm": s = cloud("#9AA3AE") + '<path d="M33 44l-7 11h6l-3 9 10-13h-6l4-7z" fill="#FFC83D"/>'; break;
    default: s = cloud();
  }
  return `<svg viewBox="0 0 64 64" aria-hidden="true">${s}</svg>`;
}
let wxSig = "";
let wxState = null;
function renderWeather(w) {
  const btn = $("#tb-weather");
  if (!w || !w.configured || w.temp == null) { btn.hidden = true; wxState = null; return; }
  wxState = w;
  btn.hidden = false;
  const sig = JSON.stringify([w.temp, w.icon, w.is_day, w.desc, w.updated]);
  if (sig === wxSig) return;
  wxSig = sig;
  btn.innerHTML = `<span class="wi">${wxIcon(w.icon, w.is_day)}</span><div class="wtx"><b></b><span></span></div>`;
  btn.querySelector("b").textContent = `${Math.round(w.temp)}°C`;
  btn.querySelector(".wtx span").textContent = w.desc;
  if (!$("#wx-fly").hidden) fillWeatherFly();
}
function fillWeatherFly() {
  const w = wxState;
  const fly = $("#wx-fly");
  if (!w) { fly.hidden = true; return; }
  fly.innerHTML = `<div class="wx-city"></div><div class="wx-now"><span class="wi">${wxIcon(w.icon, w.is_day)}</span><div class="t">${Math.round(w.temp)}<small>°C</small></div></div><div class="wx-desc"></div><div class="wx-meta"></div><div class="wx-days"></div>`;
  fly.querySelector(".wx-city").textContent = w.label || w.city || "";
  fly.querySelector(".wx-desc").textContent = w.desc;
  const meta = fly.querySelector(".wx-meta");
  meta.append(el("span", null, `Hissedilen ${Math.round(w.feels)}°`));
  if (w.humidity != null) meta.append(el("span", null, `Nem %${Math.round(w.humidity)}`));
  if (w.wind != null) meta.append(el("span", null, `Rüzgar ${Math.round(w.wind)} km/sa`));
  const days = fly.querySelector(".wx-days");
  (w.days || []).slice(0, 4).forEach((d, i) => {
    const dt = new Date(d.date + "T12:00:00");
    const name = i === 0 ? "Bugün" : i === 1 ? "Yarın" : dt.toLocaleDateString("tr-TR", { weekday: "short" });
    const c = el("div");
    c.innerHTML = `<div class="d"></div><span class="wi">${wxIcon(d.icon, true)}</span><b>${Math.round(d.max)}°</b><span>${Math.round(d.min)}°</span>`;
    c.querySelector(".d").textContent = name;
    if (d.rain) c.append(el("span", "r", `Yağış %${d.rain}`));
    days.append(c);
  });
}
$("#tb-weather").onclick = (e) => {
  e.stopPropagation();
  const fly = $("#wx-fly");
  fly.hidden = !fly.hidden;
  $("#tb-weather").classList.toggle("on", !fly.hidden);
  if (!fly.hidden) fillWeatherFly();
};
document.addEventListener("pointerdown", (e) => {
  if (!$("#wx-fly").hidden && !e.target.closest("#wx-fly, #tb-weather")) {
    $("#wx-fly").hidden = true;
    $("#tb-weather").classList.remove("on");
  }
});

/* ================= Bekleme ekranı ================= */
let idleTimer = null;
// Bekleme süresi moda göre: gece 1 dk, oyun/geliştirici modunda kapalı, normalde ayardaki dakika
function idleMs() {
  const m = (lastState && lastState.mode) || {};
  if (m.mode === "game" || m.mode === "dev") return 0;
  if (m.mode === "night") return 60000;
  return (m.idle_min ?? 3) * 60000;
}
let lastState = {};
let idleArt = null;
function resetIdle() {
  clearTimeout(idleTimer);
  idleTimer = null;
  const ms = idleMs();
  if (!$("#desk").hidden && ms > 0) idleTimer = setTimeout(showIdle, ms);
}
function showIdle() {
  if ($("#desk").hidden) return;
  $("#wx-fly").hidden = true;
  $("#start-menu").hidden = true;
  $("#idle").classList.toggle("night", ((lastState.mode || {}).mode) === "night");
  $("#idle").hidden = false;
  updateIdle(true);
}
function hideIdle() {
  $("#idle").hidden = true;
  resetIdle();
}
$("#idle").addEventListener("click", (e) => { if (!e.target.closest("#idle-play")) hideIdle(); });
$("#idle-play").onclick = () => send("media", "toggle");
document.addEventListener("pointerdown", () => { if ($("#idle").hidden) resetIdle(); }, true);
$("#b-lock").onclick = () => setTimeout(showIdle, 0);
function updateIdle(force = false) {
  if ($("#idle").hidden) return;
  const d = new Date();
  $("#idle-time").textContent = d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
  $("#idle-date").textContent = d.toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long" });
  // Hava durumu
  const wx = $("#idle-wx");
  const w = wxState;
  const wsig = w ? JSON.stringify([w.temp, w.icon, w.desc]) : "";
  if (force || wx.dataset.sig !== wsig) {
    wx.dataset.sig = wsig;
    wx.replaceChildren();
    if (w) {
      wx.innerHTML = `<span class="wi">${wxIcon(w.icon, w.is_day)}</span><div class="wtx"><b></b><span></span></div>`;
      wx.querySelector("b").textContent = `${Math.round(w.temp)}°C`;
      wx.querySelector(".wtx span").textContent = `${w.desc} · ${w.city || ""}`;
    }
  }
  // Çalan şarkı
  const m = lastState.media || {};
  const np = $("#idle-np");
  np.hidden = !m.available;
  if (m.available) {
    $("#idle-title").textContent = m.title || "";
    $("#idle-artist").textContent = m.artist || "";
    $("#idle-play").innerHTML = icon(m.playing ? "pause" : "play");
  }
  const art = m.available && m.art ? `/api/art?token=${encodeURIComponent(token)}&v=${m.art}` : null;
  if (force || art !== idleArt) {
    idleArt = art;
    const bg = $("#idle-bg");
    bg.style.backgroundImage = art ? `url("${art}")` : "";
    bg.classList.toggle("art", !!art);
    const img = $("#idle-art");
    if (art) img.src = art; else img.removeAttribute("src");
  }
}
// Ekran yanmasını önlemek için içerik her dakika birkaç piksel kayar
setInterval(() => {
  const dx = Math.round(Math.random() * 24 - 12), dy = Math.round(Math.random() * 16 - 8);
  $("#idle-content").style.transform = `translate(${dx}px, ${dy}px)`;
}, 60000);
setInterval(() => updateIdle(), 1000);

/* ================= Ana render ================= */
let lastMode = null;
function render(st) {
  lastState = st;
  const mode = (st.mode || {}).mode;
  if (mode !== lastMode) { lastMode = mode; resetIdle(); }
  else if (!idleTimer) resetIdle();
  try { renderWeather(st.weather); } catch (e) { console.error(e); }
  try { renderMusic(st.media || {}, st.audio || {}); } catch (e) { console.error(e); }
  try { renderMixer(st.audio || {}); } catch (e) { console.error(e); }
  try { renderDiscord(st.discord || {}, st.social || {}); } catch (e) { console.error(e); }
  try { renderStats(st.stats); } catch (e) { console.error(e); }
  if (typeof renderExtras === "function") { try { renderExtras(st); } catch (e) { console.error(e); } }
}

/* ================= Görev çubuğu ================= */
function clock() {
  const d = new Date();
  $("#clock-time").textContent = d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
  $("#clock-date").textContent = d.toLocaleDateString("tr-TR");
}
clock();
setInterval(clock, 1000);
$("#b-full").innerHTML = icon("full");
$("#b-lock").innerHTML = icon("lock");
$(".mx-logo").innerHTML = icon("speaker");
$(".tm-logo").replaceChildren();
$("#b-full").onclick = async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else {
      await document.documentElement.requestFullscreen({ navigationUI: "hide" });
      try { await screen.orientation.lock("landscape"); } catch {}
    }
  } catch {}
};
// Ekranın kapanmasını engelle (sadece destekleyen tarayıcılarda)
let wakeLock = null;
async function keepAwake() {
  try { if ("wakeLock" in navigator && !wakeLock) { wakeLock = await navigator.wakeLock.request("screen"); wakeLock.onrelease = () => { wakeLock = null; }; } } catch {}
}
document.addEventListener("pointerdown", keepAwake);
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") keepAwake(); });

/* ================= Başlangıç ================= */
const pinParam = new URLSearchParams(location.search).get("pair");
if (pinParam && !token) pair(pinParam);
else if (token) { history.replaceState(null, "", "/"); startDesk(); }
else showPair();

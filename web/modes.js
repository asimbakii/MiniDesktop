"use strict";
/* Modlar (Normal / Geliştirici / Oyun / Gece), Başlat menüsü, güç, mini oynatıcı, görev çubuğu çipleri. */

Object.assign(ICONS, {
  start: '<path d="M3 3h8.5v8.5H3zM12.5 3H21v8.5h-8.5zM3 12.5h8.5V21H3zM12.5 12.5H21V21h-8.5z"/>',
  power: '<path d="M11 2h2v10h-2z"/><path d="M6.3 5.6l1.4 1.4A7 7 0 1 0 16.3 7l1.4-1.4A9 9 0 1 1 6.3 5.6z"/>',
  monitor: '<path d="M3 4h18a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1h-7v2h3v2H7v-2h3v-2H3a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zm1 2v9h16V6z"/>',
  code: '<path d="M8.6 16.6 4 12l4.6-4.6L7.2 6l-6 6 6 6zm6.8 0L20 12l-4.6-4.6L16.8 6l6 6-6 6z"/>',
  gamepad: '<path d="M7 7h10a5 5 0 0 1 4.9 6l-.7 3.4a2.5 2.5 0 0 1-4.3 1.2L14.6 15H9.4l-2.3 2.6a2.5 2.5 0 0 1-4.3-1.2L2.1 13A5 5 0 0 1 7 7zm0 3v1.5H5.5V13H7v1.5h1.5V13H10v-1.5H8.5V10zm8.5.5a1 1 0 1 0 0 2 1 1 0 0 0 0-2zm2 2a1 1 0 1 0 0 2 1 1 0 0 0 0-2z"/>',
  moon: '<path d="M12.3 2A10 10 0 1 0 22 13.7 7.5 7.5 0 0 1 12.3 2z"/>',
  restart: '<path d="M12 4V1L7 5l5 4V6a6 6 0 1 1-6 6H4a8 8 0 1 0 8-8z"/>',
  chat: '<path d="M4 3h16a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2z"/>',
});

const MODE_INFO = {
  normal: { name: "Normal", desc: "Müzik, Discord, performans, ses", icon: "monitor" },
  dev: { name: "Geliştirici", desc: "Claude Code, git, komutlar, araçlar", icon: "code" },
  game: { name: "Oyun", desc: "Büyük performans, Discord sesi", icon: "gamepad" },
  night: { name: "Gece", desc: "Karartılmış ekran, kırmızı saat", icon: "moon" },
};
const POWER = [
  { k: "lock", name: "Kilitle", icon: "lock" },
  { k: "sleep", name: "Uyku", icon: "moon" },
  { k: "restart", name: "Yeniden başlat", icon: "restart" },
  { k: "shutdown", name: "Kapat", icon: "power" },
];

$("#b-start").innerHTML = icon("start");
$("#mp-prev").innerHTML = icon("prev");
$("#mp-next").innerHTML = icon("next");
$("#mp-prev").onclick = () => send("media", "prev");
$("#mp-next").onclick = () => send("media", "next");
$("#mp-play").onclick = () => send("media", "toggle");
$("#b-mic").onclick = () => send("discord", "toggle_mute");

/* ---------- Başlat menüsü ---------- */
function buildStartMenu() {
  const modes = $("#sm-modes");
  for (const [k, m] of Object.entries(MODE_INFO)) {
    const b = el("button", "sm-mode");
    b.dataset.k = k;
    b.innerHTML = `<span class="ic">${icon(m.icon)}</span><b></b><span class="d"></span>`;
    b.querySelector("b").textContent = m.name;
    b.querySelector(".d").textContent = m.desc;
    b.onclick = () => { send("mode", "set", { value: k }); closeStart(); };
    modes.append(b);
  }
  const pw = $("#sm-power");
  for (const p of POWER) {
    const b = el("button", "sm-pw");
    b.dataset.k = p.k;
    b.innerHTML = `${icon(p.icon)}<span></span>`;
    b.querySelector("span").textContent = p.name;
    b.setAttribute("aria-label", p.name);
    b.onclick = () => armPower(b, p);
    pw.append(b);
  }
  $("#sm-autogame").onchange = (e) => send("mode", "settings", { value: { auto_game: e.target.checked } });
  $("#sm-autonight").onchange = (e) => send("mode", "settings", { value: { auto_night: e.target.checked } });
}
buildStartMenu();

// Güç işlemleri iki dokunuş ister: ilk dokunuş "Emin misin?" der, 3 sn içinde ikinci dokunuş uygular.
function armPower(b, p) {
  if (b.classList.contains("armed")) {
    b.classList.remove("armed");
    send("power", p.k);
    toast(`${p.name}: komut gönderildi`);
    closeStart();
    return;
  }
  for (const x of document.querySelectorAll(".sm-pw.armed")) x.classList.remove("armed"), (x.querySelector("span").textContent = POWER.find((q) => q.k === x.dataset.k).name);
  b.classList.add("armed");
  b.querySelector("span").textContent = "Emin misin?";
  setTimeout(() => { b.classList.remove("armed"); b.querySelector("span").textContent = p.name; }, 3000);
}
function closeStart() {
  $("#start-menu").hidden = true;
  $("#b-start").classList.remove("on");
}
$("#b-start").onclick = (e) => {
  e.stopPropagation();
  const m = $("#start-menu");
  m.hidden = !m.hidden;
  $("#b-start").classList.toggle("on", !m.hidden);
  $("#wx-fly").hidden = true;
};
document.addEventListener("pointerdown", (e) => {
  if (!$("#start-menu").hidden && !e.target.closest("#start-menu, #b-start")) closeStart();
});

/* ---------- Mod uygulama ---------- */
let modeSig = "";
function renderMode(st) {
  const m = st.mode || { mode: "normal" };
  const desk = $("#desk");
  if (desk.dataset.mode !== m.mode) {
    desk.dataset.mode = m.mode;
    document.body.dataset.mode = m.mode;
  }
  const sig = JSON.stringify(m);
  if (sig !== modeSig) {
    modeSig = sig;
    for (const b of document.querySelectorAll(".sm-mode")) {
      b.classList.toggle("on", b.dataset.k === m.mode);
      b.classList.toggle("auto", b.dataset.k === m.mode && !!m.auto);
    }
    $("#sm-autogame").checked = !!m.auto_game;
    $("#sm-autonight").checked = !!m.auto_night;
    $("#sm-nightlbl").textContent = `Gece saatlerinde (${m.night_from}–${m.night_to}) Gece moduna geç`;
  }
  // Oyun bandı
  const gb = $("#game-banner");
  gb.hidden = m.mode !== "game";
  if (m.mode === "game") {
    if (m.game) {
      const mins = Math.max(0, Math.floor((Date.now() / 1000 - m.game.since) / 60));
      const dur = mins >= 60 ? `${Math.floor(mins / 60)} sa ${mins % 60} dk` : `${mins} dk`;
      gb.innerHTML = `${icon("gamepad")}<b></b><span></span>`;
      gb.querySelector("b").textContent = m.game.name;
      gb.querySelector("span").textContent = dur;
    } else {
      gb.innerHTML = `${icon("gamepad")}<span>Oyun algılanmadı</span>`;
    }
  }
}

/* ---------- Başlat menüsü kullanıcı alanı ---------- */
function renderStartUser(st) {
  const box = $("#sm-user");
  const u = (st.discord && st.discord.user) || (st.social && st.social.me);
  const sig = u ? u.name + u.avatar : "-";
  if (box.dataset.sig === sig) return;
  box.dataset.sig = sig;
  box.replaceChildren();
  if (u) {
    const img = el("img");
    img.src = u.avatar;
    img.alt = "";
    img.referrerPolicy = "no-referrer";
    box.append(img, el("span", null, u.name));
  } else {
    box.append(el("span", null, "MiniDesktop"));
  }
}

/* ---------- Görev çubuğu: mini oynatıcı ---------- */
let mpArt = null;
function renderMiniPlayer(st) {
  const mode = (st.mode || {}).mode;
  const m = st.media || {};
  const box = $("#mini-player");
  box.hidden = !(mode === "dev" || mode === "game") || !m.available;
  if (box.hidden) return;
  $("#mp-title").textContent = m.title || "";
  $("#mp-artist").textContent = m.artist || "";
  $("#mp-play").innerHTML = icon(m.playing ? "pause" : "play");
  $("#mp-next").classList.toggle("dim", !m.can_next);
  const art = m.art ? `/api/art?token=${encodeURIComponent(token)}&v=${m.art}` : null;
  if (art !== mpArt) {
    mpArt = art;
    const img = $("#mp-art");
    img.hidden = !art;
    if (art) img.src = art;
  }
}

/* ---------- Görev çubuğu çipleri ---------- */
function renderChips(st) {
  const mode = (st.mode || {}).mode;
  // Claude Code: geliştirici modu dışındayken izin/cevap bekleyen oturum varsa
  const sessions = ((st.claude || {}).sessions) || [];
  const waiting = sessions.filter((s) => s.state === "permission" || s.state === "waiting");
  const cc = $("#tb-claude");
  cc.hidden = mode === "dev" || !waiting.length;
  if (!cc.hidden) {
    const s = waiting[0];
    cc.textContent = `Claude · ${s.state === "permission" ? "İzin bekliyor" : "Cevap bekliyor"}${s.project ? " · " + s.project : ""}${waiting.length > 1 ? ` (+${waiting.length - 1})` : ""}`;
    cc.onclick = () => send("mode", "set", { value: "dev" });
  }
  // Discord okunmamış: Discord penceresinin görünmediği geliştirici modunda
  const so = st.social || {};
  const dc = $("#tb-dc");
  dc.hidden = mode !== "dev" || !so.unread_total;
  if (!dc.hidden) {
    dc.innerHTML = `${icon("chat")}<span></span>`;
    dc.querySelector("span").textContent = so.unread_total > 99 ? "99+" : String(so.unread_total);
    const first = (so.unread || [])[0];
    dc.title = first ? `${first.name}: ${first.last}` : "";
    dc.onclick = () => send("mode", "set", { value: "normal" });
  }
  // Discord mikrofonu: Discord penceresi görünmüyorsa görev çubuğunda
  const d = st.discord || {};
  const mic = $("#b-mic");
  mic.hidden = mode !== "dev" || !d.control;
  if (!mic.hidden) {
    const known = d.control === "rpc";
    mic.innerHTML = known && d.mute ? icon("mic", "slash") : icon("mic");
    mic.classList.toggle("muted", known && !!d.mute);
    mic.title = known ? "" : "Kısayol modu: Discord'da Sessize Al tuş ataması gönderilir";
  }
}

function renderExtras(st) {
  renderMode(st);
  renderStartUser(st);
  renderMiniPlayer(st);
  renderChips(st);
  if (typeof renderDev === "function") renderDev(st);
}

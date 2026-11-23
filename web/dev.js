"use strict";
/* Geliştirici modu pencereleri: Claude Code, Kaynak Denetimi, Komutlar, Kaynak İzleyicisi, Pano, Dev Araçları */

Object.assign(ICONS, {
  branch: '<path d="M6 3a3 3 0 0 1 1 5.83v6.34A3 3 0 1 1 5 15.17V8.83A3 3 0 0 1 6 3zm12 0a3 3 0 0 1 1 5.83V10a4 4 0 0 1-4 4H8v-2h7a2 2 0 0 0 2-2v-1.17A3 3 0 0 1 18 3z"/>',
  playOutline: '<path d="M8 5.14v13.72a1 1 0 0 0 1.5.86l11-6.86a1 1 0 0 0 0-1.72l-11-6.86A1 1 0 0 0 8 5.14z"/>',
  stop: '<path d="M6 6h12v12H6z"/>',
  close: '<path d="M6.4 5 12 10.6 17.6 5 19 6.4 13.4 12l5.6 5.6-1.4 1.4-5.6-5.6L6.4 19 5 17.6l5.6-5.6L5 6.4z"/>',
  copy: '<path d="M8 3h11a2 2 0 0 1 2 2v11h-2V5H8zM5 7h10a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2zm0 2v10h10V9z"/>',
});

function fmtAgo(ts) {
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 5) return "şimdi";
  if (s < 60) return `${s} sn`;
  if (s < 3600) return `${Math.floor(s / 60)} dk`;
  return `${Math.floor(s / 3600)} sa ${Math.floor((s % 3600) / 60)} dk`;
}
function fmtMB(b) {
  const mb = b / 1048576;
  return mb >= 1024 ? `${nf1.format(mb / 1024)} GB` : `${nf0.format(mb)} MB`;
}
const sigs = {};
function changed(key, val) {
  const s = JSON.stringify(val);
  if (sigs[key] === s) return false;
  sigs[key] = s;
  return true;
}
function emptyMsg(text) {
  return el("div", "dv-empty", text);
}

/* ================= Claude Code (Windows Terminal görünümü) ================= */
const CL_STATE = {
  working: ["Çalışıyor", "spin"],
  permission: ["İzin bekliyor", "!"],
  waiting: ["Cevap bekliyor", "?"],
  done: ["Tamamlandı", "✓"],
  idle: ["Boşta", "○"],
};
function renderClaude(c) {
  const sessions = c.sessions || [];
  $("#cl-count").textContent = sessions.length ? `${sessions.length} oturum` : "";
  // Geçen süre her saniye değiştiği için imzaya dakika hassasiyetinde giriyor
  if (!changed("claude", [c, Math.floor(Date.now() / 10000)])) return;
  const body = $("#cl-body");
  body.replaceChildren();
  if (!sessions.length) {
    body.append(emptyMsg(c.installed ? "Açık Claude Code oturumu yok." : "Claude Code entegrasyonu kurulu değil. PC'de localhost:8765/admin → Geliştirici modu → Kur."));
    return;
  }
  for (const s of sessions) {
    const [label, mark] = CL_STATE[s.state] || [s.state, "•"];
    const row = el("div", `cl-row st-${s.state}`);
    const top = el("div", "cl-top");
    const st = el("span", "cl-state");
    if (mark === "spin") st.append(el("i", "cl-spin"));
    else st.append(el("i", "cl-mark", mark));
    st.append(document.createTextNode(label));
    const dismiss = el("button", "cl-x");
    dismiss.innerHTML = icon("close");
    dismiss.setAttribute("aria-label", "Listeden kaldır");
    dismiss.onclick = () => send("claude", "dismiss", { value: s.id });
    top.append(el("b", "cl-proj", s.project || "Oturum"), st, el("span", "cl-time", fmtAgo(s.since)), dismiss);
    row.append(top, el("div", "cl-detail", s.detail || ""));
    if (s.prompt) row.append(el("div", "cl-prompt", "› " + s.prompt));
    if (s.state === "working" && s.tools) row.append(el("div", "cl-meta", `${s.tools} araç çağrısı`));
    body.append(row);
  }
}

/* ================= Kaynak Denetimi (VS Code görünümü) ================= */
function ciBadge(ci) {
  if (!ci) return null;
  let cls = "run", txt = "Çalışıyor";
  if (ci.status === "completed") {
    if (ci.conclusion === "success") (cls = "ok"), (txt = "Başarılı");
    else if (ci.conclusion === "skipped" || ci.conclusion === "cancelled") (cls = "skip"), (txt = ci.conclusion === "skipped" ? "Atlandı" : "İptal");
    else (cls = "fail"), (txt = "Başarısız");
  }
  const b = el("button", `ci ci-${cls}`);
  b.append(el("i"), document.createTextNode(`${ci.workflowName || "CI"}: ${txt}`));
  b.onclick = (e) => { e.stopPropagation(); send("git", "open_url", { value: ci.url }); };
  return b;
}
function prList(title, items) {
  const box = el("div", "pr-sec");
  box.append(el("div", "vsc-head", `${title} (${items.length})`));
  if (!items.length) box.append(el("div", "pr-none", "Yok"));
  for (const p of items) {
    const b = el("button", "pr");
    const repo = (p.repository && (p.repository.nameWithOwner || p.repository.name)) || "";
    b.append(el("span", "pr-repo", `${repo}#${p.number}`), el("span", "pr-title", (p.isDraft ? "[Taslak] " : "") + p.title));
    b.onclick = () => send("git", "open_url", { value: p.url });
    box.append(b);
  }
  return box;
}
function renderGit(g) {
  const age = g.gh && g.gh.updated ? `GitHub · ${fmtAgo(g.gh.updated)} önce` : g.gh && g.gh.available ? "GitHub yükleniyor…" : "";
  $("#git-age").textContent = age;
  if (!changed("git", [g.repos, g.gh && g.gh.review, g.gh && g.gh.mine, g.gh && g.gh.error])) return;
  const body = $("#git-body");
  body.replaceChildren();
  body.append(el("div", "vsc-head", "Repolar"));
  if (!g.repos.length) body.append(emptyMsg("İzlenen repo yok. Yönetim sayfasından ekle ya da bir repoda Claude Code çalıştır."));
  for (const r of g.repos) {
    const b = el("button", "repo");
    b.title = "VS Code'da aç";
    b.onclick = () => send("git", "open_repo", { value: r.path });
    const top = el("div", "repo-top");
    top.append(el("b", null, r.name));
    if (r.error) {
      b.append(top, el("div", "repo-err", r.error));
      body.append(b);
      continue;
    }
    const br = el("span", "repo-br");
    br.innerHTML = icon("branch");
    br.append(document.createTextNode(r.branch));
    top.append(br);
    if (r.ahead) top.append(el("span", "ab", `↑${r.ahead}`));
    if (r.behind) top.append(el("span", "ab", `↓${r.behind}`));
    const badges = el("span", "repo-badges");
    if (r.conflicts) badges.append(el("span", "bd bd-c", `! ${r.conflicts}`));
    if (r.staged) badges.append(el("span", "bd bd-s", `S ${r.staged}`));
    if (r.changed) badges.append(el("span", "bd bd-m", `M ${r.changed}`));
    if (r.untracked) badges.append(el("span", "bd bd-u", `U ${r.untracked}`));
    if (!r.conflicts && !r.staged && !r.changed && !r.untracked) badges.append(el("span", "bd bd-clean", "temiz"));
    top.append(badges);
    b.append(top);
    if (r.last) b.append(el("div", "repo-last", `${r.last.hash} ${r.last.subject} · ${r.last.when}`));
    const ci = ciBadge(r.ci);
    if (ci) b.append(ci);
    body.append(b);
  }
  if (g.gh && g.gh.available) {
    body.append(prList("İnceleme bekleyen PR'lar", g.gh.review || []), prList("Açık PR'larım", g.gh.mine || []));
    if (g.gh.error) body.append(el("div", "repo-err", g.gh.error));
  }
}

/* ================= Komutlar (Windows Terminal sekmeleri) ================= */
let cmdSel = store.get("md_cmd");
const CMD_STATUS = { idle: "Hazır", running: "Çalışıyor", ok: "Başarılı", fail: "Hata", stopped: "Durduruldu" };
function renderCommands(cmds) {
  if (!cmds.some((c) => c.id === cmdSel)) cmdSel = cmds[0] ? cmds[0].id : null;
  if (!changed("cmds", [cmds, cmdSel])) return;
  const tabs = $("#cmd-tabs"), body = $("#cmd-body");
  tabs.replaceChildren();
  body.replaceChildren();
  if (!cmds.length) {
    tabs.append(el("span", "term-tab on", "Komutlar"));
    body.append(emptyMsg("Komut yok. PC'de localhost:8765/admin → Geliştirici modu → Komut butonları."));
    return;
  }
  for (const c of cmds) {
    const t = el("button", `term-tab cmd-${c.status}` + (c.id === cmdSel ? " on" : ""));
    t.append(el("i", "dot"), document.createTextNode(c.name));
    t.onclick = () => { cmdSel = c.id; store.set("md_cmd", c.id); renderCommands(cmds); };
    tabs.append(t);
  }
  const c = cmds.find((x) => x.id === cmdSel);
  const bar = el("div", "cmd-bar");
  const info = el("div", "cmd-info");
  info.append(el("code", null, c.cmd));
  if (c.cwd) info.append(el("span", "cmd-cwd", c.cwd));
  const st = el("span", `cmd-st cmd-${c.status}`, CMD_STATUS[c.status] || c.status);
  if (c.status === "fail" && c.code != null) st.textContent += ` (${c.code})`;
  if (c.started && c.status !== "idle") st.textContent += ` · ${fmtTime((c.ended || Date.now() / 1000) - c.started)}`;
  const run = el("button", "cmd-run" + (c.status === "running" ? " stop" : ""));
  run.innerHTML = c.status === "running" ? icon("stop") + "<span>Durdur</span>" : icon("playOutline") + "<span>Çalıştır</span>";
  run.onclick = () => send("cmd", c.status === "running" ? "stop" : "start", { value: c.id });
  bar.append(info, st, run);
  const out = el("pre", "cmd-out");
  out.textContent = (c.tail || []).join("\n") || "Henüz çıktı yok.";
  body.append(bar, out);
  out.scrollTop = out.scrollHeight;
}

/* ================= Kaynak İzleyicisi: portlar & süreçler ================= */
let rmView = store.get("md_rm") || "ports";
let rmDevOnly = store.get("md_rm_dev") !== "0";
let rmSel = null; // seçili satır anahtarı
let rmArmed = null; // onay bekleyen sonlandırma
for (const b of document.querySelectorAll("#rm-seg button")) {
  b.classList.toggle("on", b.dataset.v === rmView);
  b.onclick = () => {
    rmView = b.dataset.v; store.set("md_rm", rmView); rmSel = null;
    for (const x of document.querySelectorAll("#rm-seg button")) x.classList.toggle("on", x === b);
    sigs.rm = null; renderRmon(lastState.dev && lastState.dev.sys);
  };
}
$("#rm-devonly").checked = rmDevOnly;
$("#rm-devonly").onchange = (e) => { rmDevOnly = e.target.checked; store.set("md_rm_dev", rmDevOnly ? "1" : "0"); sigs.rm = null; renderRmon(lastState.dev && lastState.dev.sys); };
function killButton(label, pids, key) {
  const k = el("button", "rm-act danger");
  const armed = rmArmed === key;
  k.textContent = armed ? `Emin misin? ${label}` : label;
  if (armed) k.classList.add("armed");
  k.onclick = (e) => {
    e.stopPropagation();
    if (rmArmed === key) { rmArmed = null; send("sys", "kill", { value: pids }); }
    else { rmArmed = key; setTimeout(() => { if (rmArmed === key) { rmArmed = null; sigs.rm = null; renderRmon(lastState.dev && lastState.dev.sys); } }, 3000); }
    sigs.rm = null; renderRmon(lastState.dev && lastState.dev.sys);
  };
  return k;
}
function renderRmon(sys) {
  if (!sys) return;
  if (!changed("rm", [sys, rmView, rmDevOnly, rmSel, rmArmed])) return;
  const body = $("#rm-body");
  body.replaceChildren();
  const table = el("div", "rm-table rm-" + rmView);
  if (rmView === "ports") {
    const ports = sys.ports.filter((p) => !rmDevOnly || p.dev);
    table.append(rmRow(["Port", "Süreç", "Adres"], "rm-h"));
    if (!ports.length) body.append(emptyMsg(rmDevOnly ? "Dinlemede geliştirme sunucusu yok." : "Dinlemede port yok."));
    for (const p of ports) {
      const key = "p" + p.port;
      const row = rmRow([String(p.port), p.name, p.local_only ? "yerel" : "ağ"], "rm-r" + (p.dev ? " dev" : ""));
      row.onclick = () => { rmSel = rmSel === key ? null : key; rmArmed = null; sigs.rm = null; renderRmon(sys); };
      table.append(row);
      if (rmSel === key) {
        const acts = el("div", "rm-acts");
        const open = el("button", "rm-act", "PC'de tarayıcıda aç");
        open.onclick = (e) => { e.stopPropagation(); send("sys", "open_port", { value: p.port }); };
        acts.append(open, killButton(`${p.name} sonlandır`, [p.pid], key));
        table.append(acts);
      }
    }
  } else {
    const procs = sys.procs.filter((p) => !rmDevOnly || p.dev).slice(0, 14);
    table.append(rmRow(["Ad", "CPU", "Bellek"], "rm-h"));
    if (!procs.length) body.append(emptyMsg("Geliştirme süreci yok."));
    for (const p of procs) {
      const key = "n" + p.name;
      const row = rmRow([p.count > 1 ? `${p.name} (${p.count})` : p.name, `${nf1.format(p.cpu)}%`, fmtMB(p.rss)], "rm-r" + (p.dev ? " dev" : ""));
      row.style.setProperty("--load", Math.min(100, p.cpu * 3) + "%");
      row.onclick = () => { rmSel = rmSel === key ? null : key; rmArmed = null; sigs.rm = null; renderRmon(sys); };
      table.append(row);
      if (rmSel === key) {
        const acts = el("div", "rm-acts");
        acts.append(killButton(p.count > 1 ? `${p.count} süreci sonlandır` : "Sonlandır", p.pids, key));
        table.append(acts);
      }
    }
  }
  body.prepend(table);
}
function rmRow(cells, cls) {
  const r = el(cls === "rm-h" ? "div" : "button", cls);
  for (const c of cells) r.append(el("span", null, c));
  return r;
}

/* ================= Pano (Windows 11 pano geçmişi görünümü) ================= */
let cpView = "history";
const cpReveal = new Set(); // kullanıcının gösterdiği maskeli öğeler
// Anahtar/token'a benzeyen metinleri varsayılan olarak maskele
function looksSecret(t) {
  const s = t.trim();
  if (/^(sk-|sk_|pk_|rk_|ghp_|gho_|ghs_|ghu_|github_pat_|glpat-|xox[abprs]-|AKIA|AIza|eyJ)/.test(s)) return true;
  return !/\s/.test(s) && s.length >= 20 && /[a-z]/i.test(s) && /\d/.test(s) && !/^https?:\/\//.test(s) && !/^[A-Za-z]:[\\/]/.test(s);
}
for (const b of document.querySelectorAll("#cp-seg button")) {
  b.onclick = () => {
    cpView = b.dataset.v;
    for (const x of document.querySelectorAll("#cp-seg button")) x.classList.toggle("on", x === b);
    sigs.clip = null; renderClip(lastState.dev && lastState.dev.clip);
  };
}
$("#cp-send").onsubmit = (e) => {
  e.preventDefault();
  const t = $("#cp-text").value;
  if (!t) return;
  send("clip", "set", { value: t });
  $("#cp-text").value = "";
};
function renderClip(clip) {
  if (!clip) return;
  if (!changed("clip", [clip, cpView, Math.floor(Date.now() / 30000)])) return;
  const body = $("#cp-body");
  body.replaceChildren();
  if (cpView === "history") {
    if (!clip.history.length) body.append(emptyMsg("PC'de bir metin kopyaladığında burada görünür. Şifre yöneticilerinin içerikleri gösterilmez."));
    else {
      const clr = el("button", "cp-clear", "Geçmişi temizle");
      clr.onclick = () => send("clip", "clear");
      body.append(clr);
    }
    for (const h of clip.history) {
      const b = el("button", "cp-item");
      const secret = looksSecret(h.text) && !cpReveal.has(h.id);
      const shown = secret ? `${h.text.slice(0, 4)}••••••••  (gizli olabilir · ${h.text.length}${h.long ? "+" : ""} karakter)` : h.text + (h.long ? "…" : "");
      b.append(el("span", "cp-text" + (secret ? " masked" : ""), shown), el("span", "cp-time", fmtAgo(h.ts) + " önce"));
      if (looksSecret(h.text)) {
        const eye = el("span", "cp-eye", cpReveal.has(h.id) ? "Gizle" : "Göster");
        eye.onclick = (e) => { e.stopPropagation(); cpReveal.has(h.id) ? cpReveal.delete(h.id) : cpReveal.add(h.id); sigs.clip = null; renderClip(lastState.dev && lastState.dev.clip); };
        b.append(eye);
      }
      b.onclick = () => send("clip", "history", { value: h.id });
      body.append(b);
    }
  } else {
    if (!clip.snippets.length) body.append(emptyMsg("Snippet yok. PC'de localhost:8765/admin → Geliştirici modu → Snippet'ler."));
    const grid = el("div", "cp-snips");
    for (const s of clip.snippets) {
      const b = el("button", "cp-snip");
      b.append(el("b", null, s.name), el("span", null, s.preview));
      b.onclick = () => send("clip", "snippet", { value: s.id });
      grid.append(b);
    }
    body.append(grid);
  }
}

/* ================= Dev Araçları ================= */
const TOOLS = [
  ["uuid", "UUID"], ["time", "Zaman"], ["jwt", "JWT"], ["b64", "Base64"], ["url", "URL"],
];
let tool = store.get("md_tool") || "uuid";
let clipWaiter = null;
function onClipText(m) {
  if (clipWaiter) { const f = clipWaiter; clipWaiter = null; f(m.text); }
}
function fromPC(cb) {
  clipWaiter = cb;
  send("clip", "get", { value: tool });
}
function toPC(text) {
  if (text) send("clip", "set", { value: text });
}
function uuid4() {
  const b = new Uint8Array(16);
  crypto.getRandomValues(b);
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}
function b64urlDecode(s) {
  s = s.replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  const bin = atob(s);
  return new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)));
}
function utf8ToB64(s) {
  const bytes = new TextEncoder().encode(s);
  let bin = "";
  bytes.forEach((b) => (bin += String.fromCharCode(b)));
  return btoa(bin);
}
function b64ToUtf8(s) {
  const bin = atob(s.replace(/\s+/g, ""));
  return new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)));
}
function toolRow(label, value, copyable = true) {
  const r = el("div", "tl-row");
  r.append(el("span", "tl-lbl", label));
  const v = el("code", "tl-val", value);
  r.append(v);
  if (copyable) {
    const c = el("button", "tl-copy");
    c.innerHTML = icon("copy");
    c.setAttribute("aria-label", "PC'ye kopyala");
    c.onclick = () => toPC(v.textContent);
    r.append(c);
  }
  return r;
}
function textInput(ph, onInput) {
  const wrap = el("div", "tl-in");
  const ta = el("textarea");
  ta.rows = 3;
  ta.placeholder = ph;
  ta.oninput = () => onInput(ta.value);
  const get = el("button", "tl-btn", "PC panosundan al");
  get.onclick = () => fromPC((t) => { ta.value = t; onInput(t); });
  wrap.append(ta, get);
  return wrap;
}
function buildTool() {
  const nav = $("#tl-nav");
  nav.replaceChildren();
  for (const [k, name] of TOOLS) {
    const b = el("button", k === tool ? "on" : "", name);
    b.onclick = () => { tool = k; store.set("md_tool", k); buildTool(); };
    nav.append(b);
  }
  const body = $("#tl-body");
  body.replaceChildren();
  const out = el("div", "tl-out");
  if (tool === "uuid") {
    const gen = () => { out.replaceChildren(toolRow("UUID v4", uuid4()), toolRow("BÜYÜK HARF", uuid4().toUpperCase())); };
    const b = el("button", "tl-btn primary", "Yeni üret");
    b.onclick = gen;
    body.append(b, out);
    gen();
  } else if (tool === "time") {
    const show = (v) => {
      out.replaceChildren();
      let d;
      const t = v.trim();
      if (!t) d = new Date();
      else if (/^-?\d+(\.\d+)?$/.test(t)) d = new Date(Number(t) * (t.replace(/^-/, "").split(".")[0].length > 11 ? 1 : 1000));
      else d = new Date(t);
      if (isNaN(d)) { out.append(el("div", "tl-err", "Tarih ya da Unix zamanı tanınmadı.")); return; }
      const rel = Math.round((d - Date.now()) / 1000);
      out.append(
        toolRow("Unix (sn)", String(Math.floor(d / 1000))),
        toolRow("Unix (ms)", String(d.getTime())),
        toolRow("ISO (UTC)", d.toISOString()),
        toolRow("Yerel", d.toLocaleString("tr-TR")),
        toolRow("Göreli", rel === 0 ? "şimdi" : rel < 0 ? `${fmtAgo(d / 1000)} önce` : `${fmtAgo(Date.now() / 1000 - rel)} sonra`, false),
      );
    };
    body.append(textInput("Unix zamanı ya da tarih (boş = şimdi)", show), out);
    show("");
  } else if (tool === "jwt") {
    const show = (v) => {
      out.replaceChildren();
      const parts = v.trim().replace(/^Bearer\s+/i, "").split(".");
      if (parts.length < 2) { if (v.trim()) out.append(el("div", "tl-err", "Geçerli bir JWT değil.")); return; }
      try {
        const head = JSON.parse(b64urlDecode(parts[0]));
        const pay = JSON.parse(b64urlDecode(parts[1]));
        if (pay.exp) {
          const left = pay.exp - Date.now() / 1000;
          out.append(el("div", left > 0 ? "tl-ok" : "tl-err", left > 0 ? `Geçerli · ${fmtAgo(Date.now() / 1000 - left)} sonra sona erecek` : `Süresi dolmuş · ${fmtAgo(pay.exp)} önce`));
        }
        const pre = (o) => { const p = el("pre", "tl-json"); p.textContent = JSON.stringify(o, null, 2); return p; };
        out.append(el("div", "tl-lbl", "Header"), pre(head), el("div", "tl-lbl", "Payload"), pre(pay));
        const c = el("button", "tl-btn", "Payload'ı PC'ye kopyala");
        c.onclick = () => toPC(JSON.stringify(pay, null, 2));
        out.append(c);
      } catch { out.append(el("div", "tl-err", "Çözülemedi: Base64/JSON hatası.")); }
    };
    body.append(textInput("JWT yapıştır ya da PC panosundan al", show), out);
  } else if (tool === "b64" || tool === "url") {
    const show = (v) => {
      out.replaceChildren();
      if (!v) return;
      const rows = [];
      try { rows.push(toolRow("Kodla", tool === "b64" ? utf8ToB64(v) : encodeURIComponent(v))); } catch { rows.push(el("div", "tl-err", "Kodlanamadı")); }
      try { rows.push(toolRow("Çöz", tool === "b64" ? b64ToUtf8(v) : decodeURIComponent(v))); } catch { rows.push(el("div", "tl-muted", "Çözülemedi (geçerli bir " + (tool === "b64" ? "Base64" : "URL kodlaması") + " değil)")); }
      out.append(...rows);
    };
    body.append(textInput("Metin", show), out);
  }
}
buildTool();

/* ================= Giriş noktası ================= */
function renderDev(st) {
  if ((st.mode || {}).mode !== "dev") return;
  renderClaude(st.claude || { sessions: [] });
  renderCommands(st.commands || []);
  if (st.dev) {
    renderGit(st.dev.git);
    renderRmon(st.dev.sys);
    renderClip(st.dev.clip);
  }
}

/* LifeLine front end. Plain JavaScript, no libraries.
   All text from the server is added with textContent (never innerHTML), so it can't inject markup. */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const main = $("#app");
const show = (...nodes) => main.replaceChildren(...nodes.flat(Infinity).filter(Boolean));
const state = { startedAt: null, loc: null, sid: sessionStorage.getItem("ll_sid") || null, view: null, cfg: null, voice: false, spoken: "" };
try { state.voice = localStorage.getItem("ll_voice") === "1"; } catch (e) { /* storage blocked: fine */ }

/* ---------- tiny DOM helper ---------- */
function el(tag, props = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v === false || v == null) continue;
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    n.append(kid.nodeType ? kid : document.createTextNode(kid));
  }
  return n;
}

/* ---------- talking to the server ---------- */
async function api(path, body = {}) {
  try {
    const res = await fetch(path, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.sid, ...body }),
    });
    const data = await res.json();
    if (!res.ok) { toast(data.detail || "Something went wrong. If it's urgent, call 112."); return null; }
    return data;
  } catch (e) {
    toast("Can't reach the server. If it's urgent, call 112 now.");
    return null;
  }
}

function setView(v) {
  if (!v) return;
  if (!v.topic) state.startedAt = null;              // emergency over / not started
  else if (!state.startedAt) state.startedAt = Date.now();   // keep the original start across re-plans
  state.view = v;
  state.sid = v.session_id;
  sessionStorage.setItem("ll_sid", v.session_id);
  if (v.notice) toast(v.notice, 6000);
  render();
}
const act = (path, body) => api(path, body).then(setView);

/* ---------- toast ---------- */
let toastTimer;
function toast(msg, ms = 4500) {
  const t = $("#toast");
  t.textContent = msg; t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), ms);
}

/* ---------- voice: speak steps aloud, listen to the user ---------- */
function speak(text) {
  if (!("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "en-IN"; u.rate = 0.95;
  speechSynthesis.speak(u);
}
function toggleVoice() {
  state.voice = !state.voice;
  try { localStorage.setItem("ll_voice", state.voice ? "1" : "0"); } catch (e) { /* ignore */ }
  if (!state.voice && "speechSynthesis" in window) speechSynthesis.cancel();
  state.spoken = "";
  render();
}
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
function listen(input, form, btn) {
  const r = new Recognition();
  r.lang = "en-IN"; r.interimResults = false; r.maxAlternatives = 1;
  btn.classList.add("rec");
  r.onresult = (e) => { input.value = e.results[0][0].transcript; form.requestSubmit(); };
  r.onerror = () => toast("I couldn't hear you. Please type instead.");
  r.onend = () => btn.classList.remove("rec");
  r.start();
}

/* ---------- audio: beeps for the timer and the CPR beat ---------- */
let audio;
function beep(times = 1, freq = 880, dur = 0.08) {
  try {
    audio = audio || new (window.AudioContext || window.webkitAudioContext)();
    for (let i = 0; i < times; i++) {
      const o = audio.createOscillator(), g = audio.createGain();
      o.frequency.value = freq; o.connect(g); g.connect(audio.destination);
      const t = audio.currentTime + i * 0.25;
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.3, t + 0.01);
      g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      o.start(t); o.stop(t + dur + 0.02);
    }
  } catch (e) { /* audio blocked: visual cue still works */ }
}

/* countdown timer (cooling a burn, pressing a wound...) */
const T = { key: null, total: 0, left: 0, running: false, iv: null };
const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
function stopTimer() { clearInterval(T.iv); T.running = false; }
function toggleTimer() {
  if (T.running) { stopTimer(); render(); return; }
  const end = Date.now() + T.left * 1000;
  T.running = true;
  T.iv = setInterval(() => {
    T.left = Math.max(0, Math.round((end - Date.now()) / 1000));
    const t = $("#timeLeft"); if (t) t.textContent = fmt(T.left);
    if (T.left <= 0) { stopTimer(); beep(3); toast("Time is up. Check the step instructions.", 8000); render(); }
  }, 250);
  render();
}
function timerWidget(a) {
  const key = `${state.view.topic.id}:${a.index}`;
  if (T.key !== key) { stopTimer(); Object.assign(T, { key, total: a.timer, left: a.timer }); }
  const label = T.running ? "Pause" : T.left <= 0 ? "Restart" : T.left < T.total ? "Resume" : "Start timer";
  return el("div", { class: "tools", role: "group", "aria-label": "Timer" },
    el("span", { class: "time", id: "timeLeft" }, fmt(T.left)),
    el("button", { class: "btn secondary", type: "button", onclick: () => { if (T.left <= 0) T.left = T.total; toggleTimer(); } }, label));
}

/* CPR beat: 110 per minute, inside the 100-120 target */
const M = { on: false, iv: null };
function stopMetronome() { clearInterval(M.iv); M.on = false; }
function tick() {
  beep(1, 760, 0.06);
  const p = $(".pulse"); if (p) { p.classList.remove("on"); void p.offsetWidth; p.classList.add("on"); }
}
function toggleMetronome() {
  if (M.on) stopMetronome(); else { M.on = true; tick(); M.iv = setInterval(tick, 60000 / 110); }
  render();
}
function metronomeWidget() {
  return el("div", { class: "tools", role: "group", "aria-label": "CPR beat" },
    el("span", { class: "pulse", "aria-hidden": "true" }),
    el("div", {}, el("b", {}, "Push to the beat"), el("div", { class: "muted small" }, "110 beats per minute")),
    el("button", { class: "btn secondary", type: "button", style: "margin-left:auto", onclick: toggleMetronome }, M.on ? "Stop beat" : "Start beat"));
}


/* ---------- emergency clock + "what to tell the operator" ---------- */
function elapsedText() {
  const s = Math.max(0, Math.floor((Date.now() - (state.startedAt || Date.now())) / 1000));
  return s >= 3600 ? `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m` : fmt(s);
}
function clockText() {
  const t = new Date(state.startedAt || Date.now()).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return `⏱ Started ${t} · ${elapsedText()} ago`;
}
setInterval(() => { const c = $("#clock"); if (c && state.startedAt) c.textContent = clockText(); }, 1000);

function shareLocation() {
  if (!navigator.geolocation) { toast("Location isn't available here. Say the address instead."); return; }
  navigator.geolocation.getCurrentPosition((p) => {
    const lat = p.coords.latitude, lon = p.coords.longitude;
    state.loc = { lat, lon, text: `${lat.toFixed(5)}, ${lon.toFixed(5)} (https://maps.google.com/?q=${lat},${lon})` };
    toast("Location added to the script.");
    render();
  }, () => toast("Couldn't get your location. Say the address instead."), { enableHighAccuracy: true, timeout: 8000 });
}
const hospitalUrl = () => state.loc
  ? `https://www.google.com/maps/search/hospital/@${state.loc.lat},${state.loc.lon},14z`
  : "https://www.google.com/maps/search/hospital+near+me";

function operatorLines(v) {
  const doneCount = v.action.kind === "step" ? v.action.index : v.action.kind === "triage" ? 0 : v.step_titles.length;
  const done = v.step_titles.slice(0, doneCount);
  return [
    `Location: ${state.loc ? state.loc.text : "(tap Share my location, or say the address)"}`,
    `Emergency: ${v.topic.title}. ${v.topic.summary}`,
    v.reasons.length ? `Danger signs: ${v.reasons.join("; ")}` : null,
    `Started: ${clockText().replace("⏱ ", "")}`,
    done.length ? `Done so far: ${done.join(", ")}` : null,
  ].filter(Boolean);
}
function operatorCard(v) {
  const lines = operatorLines(v);
  return el("details", { class: "op", open: v.escalated },
    el("summary", {}, "📞 What to tell the operator"),
    el("ul", {}, lines.map((l) => el("li", {}, l))),
    el("div", { class: "row wrap" },
      el("button", { class: "btn secondary", type: "button", onclick: shareLocation }, "📍 Share my location"),
      el("a", { class: "btn secondary", href: hospitalUrl(), target: "_blank", rel: "noopener noreferrer" }, "🏥 Nearest hospital"),
      el("button", { class: "btn secondary", type: "button", onclick: () => {
        navigator.clipboard.writeText(lines.join("\n")).then(() => toast("Copied."), () => toast("Couldn't copy."));
      } }, "📋 Copy")));
}

/* ---------- screens ---------- */
function callRow() {
  return el("div", { class: "row" },
    el("a", { class: "btn danger", href: "tel:112" }, "📞 Call 112"),
    el("a", { class: "btn danger", href: "tel:108" }, "🚑 Call 108"));
}

function renderHome(clarify) {
  const input = el("input", { type: "text", id: "describe", maxlength: "600", required: true, autocomplete: "off",
    placeholder: "e.g. he cut his hand and it won't stop bleeding", "aria-label": "Describe the emergency" });
  const form = el("form", { class: "ask", onsubmit: async (e) => {
    e.preventDefault();
    const text = input.value.trim(); if (!text) return;
    setView(await api("/api/message", { text }));
  } });
  const mic = Recognition ? el("button", { class: "icon-btn", type: "button", "aria-label": "Speak instead",
    onclick: (e) => listen(input, form, e.currentTarget) }, "🎤") : null;
  [input, mic, el("button", { class: "icon-btn go", type: "submit", "aria-label": "Get help" }, "➜")].filter(Boolean).forEach((n) => form.append(n));

  const groups = state.cfg.categories.map((c) => {
    const topics = state.cfg.topics.filter((t) => t.category === c.id);
    return el("div", { class: "group" },
      el("div", { class: "group-title" }, c.label),
      el("div", { class: "tiles" }, topics.map((t) =>
        el("button", { class: "tile", "data-sev": t.severity, "data-q": `${t.title} ${t.summary}`.toLowerCase(), type: "button",
          onclick: () => act("/api/start", { topic: t.id }) },
          el("span", { class: "ico", "aria-hidden": "true" }, t.icon), el("b", {}, t.title), el("span", { class: "s" }, t.summary)))));
  });
  const search = el("input", { class: "search", type: "search", "aria-label": "Search emergencies",
    placeholder: "🔎 Search: burn, snake, chest pain…", oninput: (e) => {
      const q = e.target.value.toLowerCase().trim();
      document.querySelectorAll(".group").forEach((g) => {
        let any = false;
        g.querySelectorAll(".tile").forEach((t) => { const ok = !q || t.dataset.q.includes(q); t.hidden = !ok; if (ok) any = true; });
        g.hidden = !any;
      });
    } });

  show(
    el("section", { class: "hero" },
      el("h1", {}, "What's the emergency?"),
      el("p", { class: "lead" }, "Tell me in your own words, speak, or tap a card below. English works best; other languages are best effort."),
      form,
      el("p", { class: "hint" }, state.cfg.ai.enabled ? "AI understanding is on. Medical steps always come from a fixed guide based on Red Cross, St John Ambulance and NHS sources, never written by the AI." : "Running offline. Describe it simply, or tap a card.")),
    clarify ? el("div", { class: "warn", role: "alert" }, "I wasn't sure what happened. Try describing it again (what injury? what happened?) or tap the closest card.") : null,
    search,
    groups,
    el("div", { class: "group-title" }, "Emergency numbers (India)"),
    el("div", { class: "numbers" }, state.cfg.numbers.map((n) =>
      el("a", { class: "num", href: `tel:${n.number}` }, el("b", {}, n.number), el("span", {}, n.label)))));
  input.focus({ preventScroll: true });
}

function progressBar(a) {
  const dots = [];
  for (let i = 0; i < a.total; i++) dots.push(el("i", { class: i < a.index ? "done" : i === a.index ? "now" : "" }));
  return el("div", { class: "progress", role: "img", "aria-label": `Step ${a.index + 1} of ${a.total}` }, dots);
}

function renderGuide() {
  const v = state.view, a = v.action, t = v.topic;

  const header = el("div", { class: "top-row" },
    el("span", { class: "ico", "aria-hidden": "true" }, t.icon),
    el("h1", {}, t.title),
    el("button", { class: "icon-btn", type: "button", "aria-pressed": String(state.voice), title: "Read steps aloud", onclick: toggleVoice }, state.voice ? "🔊" : "🔈"));

  const alarm = v.escalated ? el("section", { class: "alarm", role: "alert" },
    el("h2", {}, "🚨 Call 108 / 112 now"),
    el("ul", {}, v.reasons.map((r) => el("li", {}, r))),
    el("p", { style: "margin:0" }, "Keep following the steps below while you wait for help."),
    callRow()) : null;

  let card;
  if (a.kind === "triage") {
    card = el("section", { class: "card" },
      el("div", { class: "kicker" }, `Quick check ${a.index + 1} of ${a.total}`),
      el("p", { class: "question" }, a.text),
      el("div", { class: "row" },
        el("button", { class: "btn primary", type: "button", onclick: () => act("/api/triage", { yes: true }) }, "Yes"),
        el("button", { class: "btn secondary", type: "button", onclick: () => act("/api/triage", { yes: false }) }, "No / not sure")));
  } else if (a.kind === "step") {
    const tool = a.tool === "metronome" ? metronomeWidget() : a.timer ? timerWidget(a) : null;
    card = el("section", { class: "card step" },
      progressBar(a),
      el("div", { class: "kicker" }, `Step ${a.index + 1} of ${a.total}`),
      el("h2", {}, a.title),
      el("p", { class: "big" }, a.text),
      tool,
      a.alt ? el("button", { class: "btn secondary block", type: "button", style: "margin-bottom:10px",
        onclick: () => act("/api/alt") }, a.alt.label) : null,
      el("div", { class: "nav" },
        el("button", { class: "btn secondary", type: "button", disabled: a.index === 0, onclick: () => act("/api/back") }, "← Back"),
        el("button", { class: "btn primary", type: "button", onclick: () => act("/api/next") },
          a.index + 1 === a.total ? "✅ Done" : "✅ Done, next step")));
  } else if (a.kind === "checkin") {
    card = el("section", { class: "card" },
      el("div", { class: "kicker" }, "Check in"),
      el("p", { class: "question" }, a.text),
      el("div", { class: "row" },
        el("button", { class: "btn primary", type: "button", onclick: () => act("/api/checkin", { yes: true }) }, "Yes"),
        el("button", { class: "btn secondary", type: "button", onclick: () => act("/api/checkin", { yes: false }) }, "No")));
  } else {
    card = el("section", { class: `card ${v.resolved ? "done-card" : ""}` },
      el("h2", {}, v.resolved ? "✅ Looks stable. Well done." : "Stay with the person"),
      el("p", {}, v.resolved ? "Keep watching them. If anything gets worse, call 112 / 108 again." :
        "Keep repeating the steps and stay with them until help arrives. Tell the responders what happened and what you did."),
      v.after_care ? el("p", {}, v.after_care) : null,
      v.call_when.length ? el("div", {}, el("b", {}, "Call 112 / 108 if:"), el("ul", {}, v.call_when.map((c) => el("li", {}, c)))) : null);
  }

  const reviewBadge = v.review === "verify"
    ? el("span", { class: "badge verify" }, "Awaiting expert review") : el("span", { class: "badge" }, "Based on official guidance");

  show(
    header, el("div", { class: "clockline muted small" }, el("span", { id: "clock" }, clockText())),
    alarm, card, operatorCard(v),
    el("button", { class: "btn secondary block", type: "button", style: "margin-bottom:12px", onclick: openAsk }, "💬 Ask a question about this"),
    el("details", { class: "no", open: a.kind === "step" }, el("summary", {}, "⛔ What NOT to do"), el("ul", {}, v.avoid.map((x) => el("li", {}, x)))),
    el("details", { class: "sources" }, el("summary", {}, "Sources"),
      el("p", {}, reviewBadge),
      v.sources.map((s) => el("a", { href: s.url, target: "_blank", rel: "noopener noreferrer" }, s.name)),
      v.notes ? el("p", { class: "muted small" }, v.notes) : null),
    el("button", { class: "btn ghost block", type: "button", onclick: () => { stopTimer(); stopMetronome(); act("/api/reset"); } }, "↩ Start over"));

  const key = `${t.id}:${a.kind}:${a.index}`;
  if (state.voice && key !== state.spoken && (a.kind === "step" || a.kind === "triage" || a.kind === "checkin")) {
    state.spoken = key;
    speak(`${a.title ? a.title + ". " : ""}${a.text}`);
  }
  main.focus({ preventScroll: true });
  window.scrollTo({ top: 0 });
}

function render() {
  const v = state.view;
  if (!(v && v.action && v.action.kind === "step" && v.action.tool === "metronome")) stopMetronome();
  if (!(v && v.action && v.action.kind === "step" && v.action.timer)) stopTimer();
  if (!v || !v.topic) { renderHome(v && v.action.kind === "clarify"); return; }
  renderGuide();
}

/* ---------- ask dialog (answers come only from the on-screen protocol) ---------- */
const dlg = $("#askDlg"), log = $("#askLog");
function addMsg(cls, text, meta) {
  log.append(el("div", { class: `msg ${cls}` }, text, meta ? el("small", {}, meta) : null));
  log.scrollTop = log.scrollHeight;
}
function openAsk() {
  log.replaceChildren();
  addMsg("bot", "Ask me anything about the steps on screen. For example: can I give them water?");
  $("#askChips").replaceChildren(...["Can I give them water?", "Should I move them?", "When should I call an ambulance?", "What should I not do?"].map((q) =>
    el("button", { type: "button", onclick: () => submitAsk(q) }, q)));
  dlg.showModal();
  $("#askInput").focus();
}
async function submitAsk(q) {
  addMsg("me", q);
  const wait = el("div", { class: "msg bot" }, "…"); log.append(wait);
  const res = await api("/api/ask", { question: q });
  wait.remove();
  if (!res) { addMsg("bot", "I couldn't answer. Please call 112 / 108 if you're unsure."); return; }
  addMsg("bot", res.answer, res.via === "groq" ? "AI answer, based only on the guide" : "From the guide");
  if (res.view && (res.view.topic?.id !== state.view.topic?.id)) { setView(res.view); dlg.close(); }
}
$("#askForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const i = $("#askInput"), q = i.value.trim();
  if (q) { i.value = ""; submitAsk(q); }
});
$("#askClose").addEventListener("click", () => dlg.close());

/* ---------- start ---------- */
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
(async function init() {
  try {
    state.cfg = await (await fetch("/api/config")).json();
  } catch (e) {
    main.replaceChildren(el("div", { class: "alarm" }, el("h2", {}, "Can't reach LifeLine"),
      el("p", {}, "If someone needs help, call now:"), callRow()));
    return;
  }
  const chip = $("#aiChip");
  chip.textContent = state.cfg.ai.enabled ? "AI on · Groq" : "Offline mode";
  chip.title = state.cfg.ai.enabled ? "AI helps understand your message. Steps are always from the fixed guide, never written by the AI." : "No API key set: using built-in rules only.";
  chip.classList.toggle("on", state.cfg.ai.enabled);
  render();
})();

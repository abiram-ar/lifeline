/* LifeLine photo add-on (loaded after app.js, so it can use el, api, setView, toast, $ from there).
   Adds two buttons to the home screen, shrinks the photo in the browser, sends it for analysis,
   and shows "what I can see" for the user to confirm BEFORE the guide starts. */
"use strict";
(function () {
  const MAX_SIDE = 1024;               // shrink big phone photos: faster, cheaper, and strips camera metadata
  const mainEl = document.getElementById("app");

  /* ---- hidden file pickers: camera (phones open the camera) and gallery ---- */
  const pick = (id, capture) => el("input", {
    type: "file", accept: "image/*", id, hidden: true, capture: capture || false,
    onchange: (e) => { const f = e.target.files[0]; e.target.value = ""; handleFile(f); },
  });
  const camInput = pick("photoCam", "environment");
  const galInput = pick("photoGal");
  document.body.append(camInput, galInput);

  /* ---- the dialog ---- */
  const body = el("div", { id: "photoBody" });
  const dlg = el("dialog", { id: "photoDlg", "aria-labelledby": "photoTitle" },
    el("div", { class: "dlg-head" },
      el("h2", { id: "photoTitle" }, "Photo check"),
      el("button", { class: "icon-btn", type: "button", "aria-label": "Close", onclick: () => dlg.close() }, "✕")),
    body);
  document.body.append(dlg);
  const setBody = (...n) => body.replaceChildren(...n.flat(Infinity).filter(Boolean));

  /* ---- inject the buttons into the home hero (it is rebuilt on every render) ---- */
  function inject() {
    const hero = mainEl.querySelector(".hero");
    if (!hero || hero.querySelector(".photo-row")) return;
    const form = hero.querySelector("form.ask");
    if (!form) return;
    form.after(el("div", { class: "photo-row" },
      el("button", { class: "btn", type: "button", onclick: () => camInput.click() }, "📷 Take a photo"),
      el("button", { class: "btn", type: "button", onclick: () => galInput.click() }, "🖼️ Choose a photo"),
      el("p", { class: "photo-hint" }, "The AI describes what it can see. Fixed rules, not the AI, choose the advice.")));
  }
  /* ---- inside the guide: remind the user which answers came from the photo ---- */
  function injectNotes() {
    const notes = state.view && state.view.photo_notes;
    if (!notes || !notes.length || !state.view.topic) return;
    if (mainEl.querySelector(".photo-notes") || !mainEl.querySelector(".top-row")) return;
    const card = el("div", { class: "photo-notes" },
      el("b", {}, "📷 From your photo"),
      el("ul", {}, notes.map((n) => el("li", {}, n))),
      el("button", { class: "btn ghost", type: "button",
        onclick: () => act("/api/start", { topic: state.view.topic.id }) }, "Not right? Ask me all the questions"));
    (mainEl.querySelector(".clockline") || mainEl.querySelector(".top-row")).after(card);
  }
  const injectAll = () => { inject(); injectNotes(); };
  new MutationObserver(injectAll).observe(mainEl, { childList: true });
  injectAll();

  /* ---- shrink the photo in the browser ---- */
  function compress(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = reject;
      reader.onload = () => {
        const img = new Image();
        img.onerror = reject;
        img.onload = () => {
          const s = Math.min(1, MAX_SIDE / Math.max(img.width, img.height));
          const c = document.createElement("canvas");
          c.width = Math.round(img.width * s); c.height = Math.round(img.height * s);
          c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
          resolve(c.toDataURL("image/jpeg", 0.82));
        };
        img.src = reader.result;
      };
      reader.readAsDataURL(file);
    });
  }

  async function handleFile(file) {
    if (!file) return;
    if (!file.type.startsWith("image/")) { toast("Please choose a photo."); return; }
    let dataUrl;
    try { dataUrl = await compress(file); }
    catch (e) { toast("I couldn't read that photo. Try a JPG or PNG."); return; }

    setBody(
      el("img", { class: "photo-prev", src: dataUrl, alt: "Your photo" }),
      el("p", { class: "photo-wait", role: "status" }, "Looking at the photo… (about 5-15 seconds)"),
      el("p", { class: "muted small" }, "If someone is in danger, call 112 / 108 now. Don't wait for this."),
      el("div", { class: "row" }, el("a", { class: "btn danger", href: "tel:112" }, "📞 Call 112"),
        el("a", { class: "btn danger", href: "tel:108" }, "🚑 Call 108")));
    if (!dlg.open) dlg.showModal();

    const res = await api("/api/photo", { image: dataUrl });
    if (!res) { dlg.close(); return; }               // api() already showed an error message
    if (!res.ok) { showMessage(dataUrl, res.message); return; }
    showResult(dataUrl, res);
  }

  function showMessage(dataUrl, message) {
    setBody(
      el("img", { class: "photo-prev", src: dataUrl, alt: "Your photo" }),
      el("div", { class: "warn", role: "alert" }, message),
      el("button", { class: "btn primary block", type: "button", onclick: () => dlg.close() }, "Describe it in words instead"));
  }

  function showResult(dataUrl, res) {
    const seen = el("ul", { class: "seen" }, res.observed.map((t) => el("li", {}, t)));
    if (!res.routed) {
      setBody(
        el("img", { class: "photo-prev", src: dataUrl, alt: "Your photo" }),
        el("h3", {}, "What I can see"), seen,
        el("div", { class: "warn", role: "alert" }, res.message),
        el("p", { class: "muted small" }, res.caveat),
        el("button", { class: "btn primary block", type: "button", onclick: () => dlg.close() }, "Choose a card or describe it"));
      return;
    }
    setBody(
      el("img", { class: "photo-prev", src: dataUrl, alt: "Your photo" }),
      el("h3", {}, "What I can see"), seen,
      el("div", { class: "photo-plan" },
        el("div", { class: "kicker" }, "Suggested guide"),
        el("b", {}, `${res.topic.icon} ${res.topic.title}`),
        res.reasons.length ? el("ul", {}, res.reasons.map((r) => el("li", {}, r))) : null),
      res.auto_notes && res.auto_notes.length ? el("div", { class: "auto-box" },
        el("b", {}, "The photo already answers these, so I won't ask:"),
        el("ul", {}, res.auto_notes.map((n) => el("li", {}, n)))) : null,
      el("p", { class: "muted small" }, res.caveat),
      el("div", { class: "row" },
        el("button", { class: "btn secondary", type: "button", onclick: () => { dlg.close(); act("/api/reset"); } }, "That's not right"),
        el("button", { class: "btn primary", type: "button", onclick: () => { dlg.close(); setView(res.view); } }, "Start the guide")));
  }
})();

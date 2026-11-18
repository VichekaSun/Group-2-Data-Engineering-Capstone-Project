// Slide navigation, scaling, full screen and overview for the HR pipeline deck.
(function () {
  "use strict";

  const stage = document.getElementById("stage");
  const slides = Array.from(stage.querySelectorAll(".slide"));
  const total = slides.length;
  const pad = (n) => String(n).padStart(2, "0");
  const el = (id) => document.getElementById(id);
  let current = 0;

  // Keep the 1280x720 stage fully visible at any window size.
  function fit() {
    const vp = el("viewport").getBoundingClientRect();
    const scale = Math.min(vp.width / 1280, vp.height / 720);
    stage.style.transform = `translate(-50%, -50%) scale(${scale})`;
  }

  function show(n) {
    current = Math.max(0, Math.min(total - 1, n));
    slides.forEach((s, i) => {
      s.classList.toggle("on", i === current);
      s.classList.toggle("prev", i < current);
      s.setAttribute("aria-hidden", i === current ? "false" : "true");
    });
    el("count").textContent = `${pad(current + 1)} / ${pad(total)}`;
    el("label").textContent = slides[current].dataset.label || "";
    el("prog").style.width = `${((current + 1) / total) * 100}%`;
    el("bprev").disabled = current === 0;
    el("bnext").disabled = current === total - 1;
    if (location.hash !== `#${current + 1}`) history.replaceState(null, "", `#${current + 1}`);
  }

  const next = () => show(current + 1);
  const prev = () => show(current - 1);

  function toggleFullscreen() {
    if (document.fullscreenElement) document.exitFullscreen();
    else if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen();
  }

  // Overview: one button per slide, built from data-label (text only, no HTML injection).
  const ov = el("overview");
  const grid = el("ovgrid");
  slides.forEach((s, i) => {
    const b = document.createElement("button");
    const n = document.createElement("span");
    const t = document.createElement("span");
    n.className = "n"; n.textContent = pad(i + 1);
    t.className = "t"; t.textContent = s.dataset.label || `Slide ${i + 1}`;
    b.append(n, t);
    b.addEventListener("click", () => { show(i); closeOverview(); });
    grid.appendChild(b);
  });
  function openOverview() {
    Array.from(grid.children).forEach((b, i) => b.classList.toggle("cur", i === current));
    ov.classList.add("open");
    grid.children[current].focus();
  }
  function closeOverview() { ov.classList.remove("open"); }

  el("bnext").addEventListener("click", next);
  el("bprev").addEventListener("click", prev);
  el("bfull").addEventListener("click", toggleFullscreen);
  el("bover").addEventListener("click", openOverview);
  el("bprint").addEventListener("click", () => window.print());
  ov.addEventListener("click", (e) => { if (e.target === ov) closeOverview(); });

  // Agenda rows jump to their section.
  stage.addEventListener("click", (e) => {
    const go = e.target.closest("[data-go]");
    if (go) show(Number(go.dataset.go) - 1);
  });

  document.addEventListener("fullscreenchange", () => {
    document.body.classList.toggle("present", !!document.fullscreenElement);
    fit();
  });

  document.addEventListener("keydown", (e) => {
    if (ov.classList.contains("open")) {
      if (e.key === "Escape" || e.key === "o" || e.key === "O") closeOverview();
      return;
    }
    if (e.target.tagName === "BUTTON" && (e.key === " " || e.key === "Enter")) return;
    switch (e.key) {
      case "ArrowRight": case "PageDown": case " ": e.preventDefault(); next(); break;
      case "ArrowLeft": case "PageUp": e.preventDefault(); prev(); break;
      case "Home": show(0); break;
      case "End": show(total - 1); break;
      case "f": case "F": toggleFullscreen(); break;
      case "o": case "O": openOverview(); break;
    }
  });

  // Swipe on touch screens.
  let x0 = null;
  stage.addEventListener("touchstart", (e) => { x0 = e.touches[0].clientX; }, { passive: true });
  stage.addEventListener("touchend", (e) => {
    if (x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0;
    if (Math.abs(dx) > 50) (dx < 0 ? next : prev)();
    x0 = null;
  });

  // ---- Image slots: click an empty slot to pick a local image. ----
  // The image is saved in this browser (IndexedDB), keyed by data-slot, so it
  // is still there after reload. Alt+click a filled slot to remove the image.
  // An <img src="..."> written in the HTML always wins over a saved image.
  const DB_NAME = "hr-deck-slots";
  function db() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => req.result.createObjectStore("img");
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }
  async function store(mode, fn) {
    const d = await db();
    return new Promise((resolve, reject) => {
      const tx = d.transaction("img", mode);
      const r = fn(tx.objectStore("img"));
      tx.oncomplete = () => resolve(r && r.result);
      tx.onerror = () => reject(tx.error);
    });
  }
  const slotsFor = (key) => Array.from(document.querySelectorAll(`.slot[data-slot="${key}"]`));
  function paint(key, url) {
    slotsFor(key).forEach((s) => {
      const img = s.querySelector("img");
      if (s.dataset.fixed) return;
      if (url) { img.src = url; s.classList.add("filled"); }
      else { img.removeAttribute("src"); s.classList.remove("filled"); }
    });
  }
  document.querySelectorAll(".slot").forEach((s) => {
    const img = s.querySelector("img");
    if (img.getAttribute("src")) { s.classList.add("filled"); s.dataset.fixed = "1"; }
  });
  // Real screenshots saved next to the deck (data-src) win over everything:
  // if assets/shots/<key>.png exists, it is shown on every computer.
  document.querySelectorAll(".slot[data-src]").forEach((s) => {
    const probe = new Image();
    probe.onload = () => {
      const img = s.querySelector("img");
      img.src = s.dataset.src; s.classList.add("filled"); s.dataset.fixed = "1";
    };
    probe.src = s.dataset.src;
  });
  const picker = document.createElement("input");
  picker.type = "file"; picker.accept = "image/*"; picker.hidden = true;
  document.body.appendChild(picker);
  let pickKey = null;
  picker.addEventListener("change", () => {
    const file = picker.files[0];
    if (!file || !pickKey) return;
    const reader = new FileReader();
    const key = pickKey;
    reader.onload = () => {
      paint(key, reader.result);
      store("readwrite", (os) => os.put(reader.result, key)).catch(() => {});
    };
    reader.readAsDataURL(file);
    picker.value = "";
  });
  document.addEventListener("click", (e) => {
    const s = e.target.closest(".slot");
    if (!s || s.dataset.fixed) return;
    const key = s.dataset.slot;
    if (s.classList.contains("filled")) {
      if (e.altKey) { paint(key, null); store("readwrite", (os) => os.delete(key)).catch(() => {}); }
      return;
    }
    pickKey = key;
    picker.click();
  });
  if (window.indexedDB) {
    const keys = [...new Set(Array.from(document.querySelectorAll(".slot")).map((s) => s.dataset.slot))];
    keys.forEach((k) => store("readonly", (os) => os.get(k)).then((url) => { if (url) paint(k, url); }).catch(() => {}));
  }

  window.addEventListener("resize", fit);
  window.addEventListener("hashchange", () => show((parseInt(location.hash.slice(1), 10) || 1) - 1));

  fit();
  show((parseInt(location.hash.slice(1), 10) || 1) - 1);
})();

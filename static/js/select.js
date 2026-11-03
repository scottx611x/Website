/* Multi-select + share, the Google Photos way. Curate-only (loaded by base.html
   when curate is on), works on every photo grid that renders `.shot` tiles
   with data-images: the ordered bird gallery, species pages, /photography and
   a share page itself.

   - Desktop: hover a tile for a check circle; click it to start selecting.
     While selecting, a click anywhere on a tile toggles it; shift-click
     selects the range from the last tile you touched.
   - Phone: long-press a tile to start; keep the finger down and drag to sweep
     a range (the page scrolls when you reach an edge); then taps toggle.
   - A bar takes over the top: × / N selected / select all / Share.
   - Share stores the selection (POST /share -> S3) and hands back /s/<id>.

   Clicks are taken in the CAPTURE phase while selecting, so the lightbox and
   the detail view never see them. */
(function () {
  "use strict";
  var TILE = ".masonry .shot[data-images], .pg-just .shot[data-images]";
  var on = false, picked = new Set(), anchor = null;
  var CHECK = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>';

  function tiles() {
    var t = [].slice.call(document.querySelectorAll(TILE));
    // Reading order, not DOM column order: the masonry deals cards across columns.
    if (t.length && t.every(function (el) { return el.hasAttribute("data-index"); })) {
      var groups = [].slice.call(document.querySelectorAll(".masonry, .pg-just"));
      t.sort(function (a, b) {
        var ga = groups.indexOf(a.closest(".masonry, .pg-just")), gb = groups.indexOf(b.closest(".masonry, .pg-just"));
        return ga - gb || (+a.getAttribute("data-index")) - (+b.getAttribute("data-index"));
      });
    }
    return t;
  }

  // ---- the check circle on every tile ---------------------------------------
  function decorate(el) {
    if (el._selDone) return;
    el._selDone = true;
    var b = document.createElement("button");
    b.type = "button"; b.className = "sel-check";
    b.setAttribute("aria-label", "Select photo");
    b.innerHTML = CHECK;
    el.appendChild(b);
  }
  function decorateAll() { document.querySelectorAll(TILE).forEach(decorate); }
  decorateAll();
  var decoRaf = null;
  new MutationObserver(function () {
    if (!decoRaf) decoRaf = requestAnimationFrame(function () { decoRaf = null; decorateAll(); });
  }).observe(document.body, { childList: true, subtree: true });

  // ---- state -------------------------------------------------------------------
  function setPicked(el, yes) {
    if (yes) picked.add(el); else picked.delete(el);
    el.classList.toggle("sel-picked", !!yes);
    var b = el.querySelector(".sel-check");
    if (b) b.setAttribute("aria-pressed", yes ? "true" : "false");
  }
  function enter() {
    if (on) return;
    on = true;
    document.body.classList.add("sel-on");
    bar.hidden = false;
    requestAnimationFrame(function () { bar.classList.add("show"); });
  }
  function exit() {
    on = false; anchor = null;
    picked.forEach(function (el) { el.classList.remove("sel-picked"); });
    picked.clear();
    document.body.classList.remove("sel-on");
    bar.classList.remove("show");
    setTimeout(function () { if (!on) bar.hidden = true; }, 220);
    paint();
  }
  function toggle(el, shift) {
    var all = tiles();
    if (shift && anchor && anchor !== el && all.indexOf(anchor) >= 0) {
      var a = all.indexOf(anchor), z = all.indexOf(el), want = picked.has(anchor);
      for (var i = Math.min(a, z); i <= Math.max(a, z); i++) setPicked(all[i], want);
    } else {
      setPicked(el, !picked.has(el));
    }
    anchor = el;
    if (!picked.size) { exit(); return; }
    paint();
  }

  // ---- the bar -------------------------------------------------------------------
  var bar = document.createElement("div");
  bar.className = "sel-bar"; bar.hidden = true;
  bar.setAttribute("role", "toolbar"); bar.setAttribute("aria-label", "Selection");
  bar.innerHTML =
    '<button type="button" class="sel-x" aria-label="Clear selection">&times;</button>' +
    '<span class="sel-n" aria-live="polite"></span>' +
    '<span class="sel-sp"></span>' +
    '<button type="button" class="sel-all">Select all</button>' +
    '<button type="button" class="sel-go"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 12v7a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7"/><path d="M16 6l-4-4-4 4"/><path d="M12 2v13"/></svg><span>Share</span></button>';
  document.body.appendChild(bar);
  var nEl = bar.querySelector(".sel-n"), goBtn = bar.querySelector(".sel-go");

  function paint() {
    var frames = 0;
    picked.forEach(function (el) { frames += itemsOf(el).length; });
    nEl.textContent = picked.size + " selected" + (frames !== picked.size ? " · " + frames + " photos" : "");
    goBtn.disabled = !picked.size;
  }
  bar.querySelector(".sel-x").addEventListener("click", exit);
  bar.querySelector(".sel-all").addEventListener("click", function () {
    tiles().forEach(function (el) { setPicked(el, true); }); paint();
  });
  goBtn.addEventListener("click", share);

  // ---- clicks: capture phase, so nothing underneath reacts ------------------------
  var swallowClick = false;
  window.addEventListener("click", function (e) {
    if (swallowClick) { swallowClick = false; e.preventDefault(); e.stopImmediatePropagation(); return; }
    var chk = e.target.closest && e.target.closest(".sel-check");
    var el = e.target.closest && e.target.closest(TILE);
    if (!el) return;
    if (chk || on) {
      e.preventDefault(); e.stopImmediatePropagation();
      enter(); toggle(el, e.shiftKey);
    }
  }, true);
  // Keyboard: Enter/Space on a tile while selecting toggles it, Esc leaves.
  window.addEventListener("keydown", function (e) {
    if (!on) return;
    if (e.key === "Escape" && !sheet.classList.contains("open")) { e.preventDefault(); e.stopImmediatePropagation(); exit(); }
    var el = document.activeElement && document.activeElement.closest && document.activeElement.closest(TILE);
    if (el && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); e.stopImmediatePropagation(); toggle(el, e.shiftKey); }
  }, true);

  // ---- touch: long-press to start, drag to sweep ----------------------------------
  var press = null, drag = null, scrollRaf = null, lastY = 0;
  document.addEventListener("touchstart", function (e) {
    if (e.touches.length !== 1) { press = null; return; }
    var el = e.target.closest && e.target.closest(TILE);
    if (!el || (e.target.closest(".sel-check"))) return;
    var t = e.touches[0];
    press = { el: el, x: t.clientX, y: t.clientY, timer: setTimeout(function () {
      if (!press) return;
      enter();
      var all = tiles();
      drag = { snap: new Set(picked), want: !picked.has(press.el), from: all.indexOf(press.el), all: all };
      setPicked(press.el, drag.want); anchor = press.el; paint();
      swallowClick = true;
      if (navigator.vibrate) try { navigator.vibrate(12); } catch (_) {}
    }, 420) };
  }, { passive: true });
  document.addEventListener("touchmove", function (e) {
    var t = e.touches[0];
    if (press && !drag && (Math.abs(t.clientX - press.x) > 10 || Math.abs(t.clientY - press.y) > 10)) {
      clearTimeout(press.timer); press = null; return;   // it was a scroll
    }
    if (!drag) return;
    e.preventDefault();                                  // the finger is selecting, not scrolling
    lastY = t.clientY;
    sweepAt(t.clientX, t.clientY);
    if (!scrollRaf) scrollRaf = requestAnimationFrame(edgeScroll);
  }, { passive: false });
  function endTouch() {
    if (press) clearTimeout(press.timer);
    press = null; drag = null;
    if (scrollRaf) { cancelAnimationFrame(scrollRaf); scrollRaf = null; }
    if (on && !picked.size) exit();
    // A long-press's click arrives after touchend; let it be swallowed, then reset.
    setTimeout(function () { swallowClick = false; }, 450);
  }
  document.addEventListener("touchend", endTouch, { passive: true });
  document.addEventListener("touchcancel", endTouch, { passive: true });
  document.addEventListener("contextmenu", function (e) {
    if ((press || drag || on) && e.target.closest && e.target.closest(TILE)) e.preventDefault();
  });
  function sweepAt(x, y) {
    var hit = document.elementFromPoint(x, y);
    var el = hit && hit.closest && hit.closest(TILE);
    if (!el || !drag) return;
    var to = drag.all.indexOf(el); if (to < 0) return;
    var lo = Math.min(drag.from, to), hi = Math.max(drag.from, to);
    drag.all.forEach(function (t, i) {
      setPicked(t, (i >= lo && i <= hi) ? drag.want : drag.snap.has(t));
    });
    anchor = el; paint();
  }
  function edgeScroll() {
    scrollRaf = null;
    if (!drag) return;
    var edge = 70, v = 0;
    if (lastY < edge + 56) v = -Math.ceil((edge + 56 - lastY) / 6);   // 56: the bar
    else if (lastY > innerHeight - edge) v = Math.ceil((lastY - (innerHeight - edge)) / 6);
    if (v) { scrollBy(0, v); }
    scrollRaf = requestAnimationFrame(edgeScroll);
  }

  // ---- what a tile contributes to a share ------------------------------------------
  function J(el, n) { try { return JSON.parse(el.getAttribute(n) || "[]"); } catch (_) { return []; } }
  function thumbOf(u) { return /\.s3\.amazonaws\.com\//.test(u) ? u.replace("/images/", "/thumbs/") : u; }
  function itemsOf(el) {
    if (el._selItems) return el._selItems;
    var imgs = J(el, "data-images"), vids = J(el, "data-image-videos"), idxs = J(el, "data-image-indices");
    var sp = J(el, "data-image-species"), sp2 = J(el, "data-species");
    var loc = J(el, "data-image-locations"), loc2 = J(el, "data-locations");
    var dates = J(el, "data-dates"), titles = J(el, "data-titles");
    var pid = el.getAttribute("data-post-id") || el.getAttribute("data-id") || "";
    var cover = el.querySelector("img");
    var out = imgs.map(function (u, i) {
      return {
        full: u,
        thumb: (i === 0 && cover && cover.currentSrc) ? cover.currentSrc : thumbOf(u),
        video: vids[i] || "",
        caption: titles[i] || "",
        species: sp[i] || sp2[i] || "",
        location: loc[i] || loc2[i] || "",
        date: dates[i] || el.getAttribute("data-date") || "",
        t: dates[i] || el.getAttribute("data-sighted") || "",   // sortable (ISO)
        key: pid + "-" + (idxs[i] != null ? idxs[i] : i),
        w: i === 0 && cover ? (+cover.getAttribute("width") || null) : null,
        h: i === 0 && cover ? (+cover.getAttribute("height") || null) : null,
      };
    });
    el._selItems = out;
    return out;
  }

  // ---- share ---------------------------------------------------------------------------
  var sheet = document.createElement("div");
  sheet.className = "sel-sheet"; sheet.hidden = true;
  sheet.setAttribute("role", "dialog"); sheet.setAttribute("aria-modal", "true"); sheet.setAttribute("aria-label", "Share link");
  sheet.innerHTML =
    '<div class="sel-card">' +
      '<div class="sel-stack"></div>' +
      '<p class="sel-h">Link ready</p>' +
      '<p class="sel-sub"></p>' +
      '<input class="sel-title" type="text" maxlength="120" placeholder="Name it (optional)" aria-label="Name this share">' +
      '<div class="sel-url"><input readonly aria-label="Share link"><button type="button" class="sel-copy">Copy</button></div>' +
      '<div class="sel-acts">' +
        '<button type="button" class="sel-native" hidden>Share…</button>' +
        '<a class="sel-open" target="_blank" rel="noopener">Open</a>' +
        '<button type="button" class="sel-done">Done</button>' +
      '</div>' +
    '</div>';
  document.body.appendChild(sheet);
  var urlIn = sheet.querySelector(".sel-url input"), titleIn = sheet.querySelector(".sel-title");
  var cur = null;

  function copy(text) {
    function legacy() {
      var ta = document.createElement("textarea"); ta.value = text; ta.setAttribute("readonly", "");
      ta.style.cssText = "position:fixed;top:0;left:0;opacity:0";
      document.body.appendChild(ta); ta.select(); ta.setSelectionRange(0, text.length);
      var ok = false; try { ok = document.execCommand("copy"); } catch (_) {}
      document.body.removeChild(ta); return ok;
    }
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(function () { return true; }, function () { return legacy(); });
    }
    return Promise.resolve(legacy());
  }
  function toast(m, ok) { if (window.siteToast) window.siteToast(m, ok); }

  function share() {
    var items = [];
    tiles().forEach(function (el) { if (picked.has(el)) items = items.concat(itemsOf(el)); });
    if (!items.length) return;
    goBtn.disabled = true; goBtn.classList.add("busy");
    fetch("/share", { method: "POST", headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ items: items }) })
      .then(function (r) { if (!r.ok) throw new Error("share " + r.status); return r.json(); })
      .then(function (d) {
        cur = d;
        urlIn.value = d.url;
        titleIn.value = "";
        sheet.querySelector(".sel-open").href = d.url;
        sheet.querySelector(".sel-sub").textContent = d.count + " photo" + (d.count === 1 ? "" : "s") + " · anyone with the link can view";
        sheet.querySelector(".sel-stack").innerHTML = items.slice(0, 3).reverse().map(function (it) {
          return '<img alt="" src="' + it.thumb.replace(/"/g, "&quot;") + '">';
        }).join("");
        sheet.querySelector(".sel-native").hidden = !navigator.share;
        sheet.hidden = false;
        requestAnimationFrame(function () { sheet.classList.add("open"); });
        exit();
        copy(d.url).then(function (ok) { if (ok) toast("Link copied to clipboard"); });
      })
      .catch(function (err) { console.error(err); toast("Couldn't create the link", false); })
      .then(function () { goBtn.disabled = false; goBtn.classList.remove("busy"); });
  }
  function closeSheet() {
    saveTitle();
    sheet.classList.remove("open");
    setTimeout(function () { sheet.hidden = true; }, 200);
  }
  function saveTitle() {
    if (!cur) return;
    var v = titleIn.value.trim();
    if (v === (cur.title || "")) return;
    cur.title = v;
    fetch("/share/" + cur.id, { method: "POST", headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ title: v }) })
      .then(function (r) { if (r.ok && v) toast("Named “" + v + "”"); });
  }
  titleIn.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); saveTitle(); titleIn.blur(); } });
  titleIn.addEventListener("blur", saveTitle);
  sheet.querySelector(".sel-copy").addEventListener("click", function () {
    copy(urlIn.value).then(function (ok) { toast(ok ? "Link copied to clipboard" : "Couldn't copy the link", ok); });
  });
  urlIn.addEventListener("focus", function () { urlIn.select(); });
  sheet.querySelector(".sel-native").addEventListener("click", function () {
    saveTitle();
    navigator.share({ title: titleIn.value.trim() || "Photos", url: urlIn.value }).catch(function () {});
  });
  sheet.querySelector(".sel-done").addEventListener("click", closeSheet);
  sheet.addEventListener("click", function (e) { if (e.target === sheet) closeSheet(); });
  addEventListener("keydown", function (e) { if (e.key === "Escape" && sheet.classList.contains("open")) closeSheet(); });
})();

/* Recordings-by-day browser: step through days, each day's species consolidated
   (expand to hear each recording). LOG + MEDIA are injected by the template. */
(function () {
  "use strict";
  if (typeof LOG === "undefined" || !LOG.length) return;

  var listEl = document.getElementById("dl-list");
  var titleEl = document.getElementById("dl-daytitle");
  var sumEl = document.getElementById("dl-daysum");
  var dateEl = document.getElementById("dl-date");
  var prevEl = document.getElementById("dl-prev");
  var nextEl = document.getElementById("dl-next");
  var searchEl = document.getElementById("dl-search");
  var sortEl = document.getElementById("dl-sort");
  var nodesEl = document.getElementById("dl-nodes");

  // Listening nodes: stay invisible until a second mic exists. nodeSel filters
  // every day to one mic; the dots (via the shared NodeUI helper) mark where a
  // recording was heard. With one node MULTI is false and this all no-ops.
  var NODES = (typeof LOG_NODES !== "undefined" ? LOG_NODES : []).filter(function (n) { return n && n.name; });
  var MULTI = NODES.length > 1 && window.NodeUI;
  var nodeSel = null;
  function nodeDot(name) { return (MULTI && name) ? window.NodeUI.dot(name) : ""; }
  function renderNodes() {
    if (!nodesEl) return;
    if (!MULTI) { nodesEl.hidden = true; return; }
    var html = '<button type="button" class="node-chip all' + (nodeSel == null ? " on" : "") +
      '" data-node=""><span class="node-dot"></span>all mics</button>';
    html += NODES.map(function (n) { return window.NodeUI.chip(n.name, nodeSel === n.name); }).join("");
    nodesEl.innerHTML = html;
    nodesEl.hidden = false;
  }
  if (nodesEl) nodesEl.addEventListener("click", function (ev) {
    var b = ev.target.closest(".node-chip"); if (!b) return;
    var nm = b.getAttribute("data-node") || "";
    nodeSel = (!nm || nodeSel === nm) ? null : nm;
    renderNodes(); render();
  });

  var DAYNAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  // Timestamps carry the mic's own UTC offset — read wall-clock fields straight
  // from the string so the viewer's timezone never shifts them.
  function parts(t) {
    var m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(t || "");
    if (!m) return null;
    return { day: m[1] + "-" + m[2] + "-" + m[3], y: +m[1], mo: +m[2], d: +m[3], h: +m[4], mi: +m[5] };
  }
  function dayLabel(p) {
    return DAYNAMES[new Date(Date.UTC(p.y, p.mo - 1, p.d)).getUTCDay()] + ", " + MONTHS[p.mo - 1] + " " + p.d + ", " + p.y;
  }
  function timeLabel(p) {
    var h = p.h % 12; if (h === 0) h = 12;
    return h + ":" + (p.mi < 10 ? "0" : "") + p.mi + " " + (p.h < 12 ? "AM" : "PM");
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // Group all detections by day.
  var byDay = {}, days = [];
  LOG.forEach(function (e) {
    var p = parts(e.t); if (!p) return;
    if (!byDay[p.day]) { byDay[p.day] = { p: p, recs: [] }; days.push(p.day); }
    byDay[p.day].recs.push({ e: e, p: p });
  });
  days.sort(); days.reverse();                 // newest first
  var cur = 0;                                 // index into days
  dateEl.min = days[days.length - 1]; dateEl.max = days[0];
  // Order the day: "most heard" (by activity) or "chronological" (as it unfolded).
  // The choice sticks, so a preferred order becomes the default on the next visit.
  var sortMode = "chrono";
  try { sortMode = localStorage.getItem("dl-sort") || "chrono"; } catch (_) {}

  // Consolidate a day's detections into one entry per species.
  function speciesOf(recs) {
    var by = {}, order = [];
    recs.forEach(function (r) {
      var k = r.e.display || r.e.common || "Unknown";
      if (!by[k]) { by[k] = { name: k, slug: r.e.slug, fam: r.e.fam, photo: r.e.photo, shot: r.e.shot, recs: [] }; order.push(by[k]); }
      by[k].recs.push(r);
    });
    order.forEach(function (s) {
      s.count = s.recs.length;
      // The collapsed row always shows the clearest clip + its confidence.
      s.best = s.recs.reduce(function (a, x) { return x.e.conf > a.e.conf ? x : a; }, s.recs[0]);
      s.earliest = s.recs.reduce(function (m, x) { return x.e.t < m ? x.e.t : m; }, s.recs[0].e.t);
      s.recs.sort(sortMode === "chrono"
        ? function (a, b) { return a.e.t < b.e.t ? 1 : a.e.t > b.e.t ? -1 : 0; }   // newest first
        : function (a, b) { return b.e.conf - a.e.conf; });                        // highest confidence first
    });
    order.sort(sortMode === "chrono"
      ? function (a, b) { return a.earliest < b.earliest ? -1 : a.earliest > b.earliest ? 1 : 0; }  // by first heard
      : function (a, b) { return b.count - a.count || (a.name < b.name ? -1 : 1); });
    return order;
  }

  function playBtn(r, label) {
    return '<button type="button" class="dl-play" data-audio="' + esc(r.e.audio) + '" aria-label="Play ' + esc(label) + '">' +
      (r.e.spec ? '<img loading="lazy" decoding="async" src="' + MEDIA + esc(r.e.spec) + '" alt="">' : '') +
      '<span class="dl-needle"></span><span class="dl-ico">&#9654;</span></button>';
  }
  // A stable, shareable token for one recording — the clip filename (already
  // unique), so /birds/live/log#rec-<token> permalinks straight to it.
  function recTokenOf(e) {
    var a = (e.audio || e.spec || "").split("/").pop().replace(/\.[a-z0-9]+$/i, "");
    return a || ((e.slug || "") + "-" + (e.t || "").replace(/[^0-9]/g, "").slice(0, 14));
  }
  function shareBtn(e) {
    return '<button type="button" class="dl-share" data-token="' + esc(recTokenOf(e)) +
      '" title="Copy a link to this recording" aria-label="Copy a link to this recording">' + ICONS.link + '</button>';
  }

  function render() {
    stopAudio();
    var day = byDay[days[cur]];
    var q = (searchEl.value || "").trim().toLowerCase();
    titleEl.textContent = dayLabel(day.p);
    dateEl.value = days[cur];
    prevEl.disabled = cur >= days.length - 1;   // older = higher index
    nextEl.disabled = cur <= 0;
    // The mic filter scopes every number and row on the day to one node.
    var recs = (MULTI && nodeSel)
      ? day.recs.filter(function (r) { return r.e.node === nodeSel; })
      : day.recs;
    var sp = speciesOf(recs);
    if (q) sp = sp.filter(function (s) { return (s.name || "").toLowerCase().indexOf(q) !== -1; });
    var totalRecs = recs.length;
    sumEl.textContent = totalRecs + " recording" + (totalRecs !== 1 ? "s" : "") + " · " +
      speciesOf(recs).length + " species";

    listEl.innerHTML = sp.map(function (s) {
      var conf = Math.round(s.best.e.conf * 100);
      // When: a single time, or the first→last span for a species heard repeatedly.
      var t0 = s.recs.reduce(function (m, r) { return r.e.t < m.e.t ? r : m; }, s.recs[0]);
      var t1 = s.recs.reduce(function (m, r) { return r.e.t > m.e.t ? r : m; }, s.recs[0]);
      var when = (s.count > 1 && timeLabel(t0.p) !== timeLabel(t1.p))
        ? timeLabel(t0.p) + "&ndash;" + timeLabel(t1.p) : timeLabel(s.best.p);
      var nameHtml = s.slug
        ? '<a class="dl-nm" href="/birds/species/' + encodeURIComponent(s.slug) + '">' + esc(s.name) + '</a>'
        : '<span class="dl-nm">' + esc(s.name) + '</span>';
      var tag = s.shot ? '<span class="dl-tag">&#10003; gallery</span>' : '<span class="dl-tag ear">not photographed</span>';
      // Which mic: the featured clip's node, unless the day's calls span mics —
      // then the ×N rows carry the per-recording dots instead of implying one.
      var chainNode = s.best.e.node;
      var mixedNode = MULTI && s.recs.some(function (r) { return r.e.node && r.e.node !== chainNode; });
      var subs = s.recs.map(function (r) {
        return '<div class="dl-sub" data-audio="' + esc(r.e.audio) + '"><span class="st">' + esc(timeLabel(r.p)) + '</span>' +
          '<span class="sc">' + Math.round(r.e.conf * 100) + '%</span>' +
          (mixedNode ? nodeDot(r.e.node) : "") +
          shareBtn(r.e) + playBtn(r, s.name + ' at ' + timeLabel(r.p)) + '</div>';
      }).join("");
      return '<div class="dl-sprow" data-name="' + esc(s.name) + '">' +
        '<div class="dl-sphead">' +
          (s.photo ? '<img class="dl-av" loading="lazy" src="' + esc(s.photo) + '" alt="">' : '<span class="dl-av ear">' + ICONS.ear + '</span>') +
          '<span class="dl-spmain">' + nameHtml +
            '<span class="dl-spmeta"><span class="dl-time mono">' + when + '</span>' +
            (mixedNode ? "" : nodeDot(chainNode)) +
            '<span class="dl-fam">' + esc(s.fam || "") + '</span>' + tag +
            (s.count > 1 ? '<button type="button" class="dl-count" aria-label="Show all ' + s.count + ' recordings, highest confidence first">&times;' + s.count + ' recordings</button>' : '') +
            '<span class="dl-hi mono" title="highest confidence">' + (s.count > 1 ? 'best ' : '') + '<span class="cl">conf</span> ' + conf + '%</span></span></span>' +
          '<span class="dl-spright">' + shareBtn(s.best.e) + playBtn(s.best, s.name) + '</span>' +
        '</div>' +
        (s.count > 1 ? '<div class="dl-subs">' + subs + '</div>' : '') +
      '</div>';
    }).join("") || '<p class="dl-empty">no species match &ldquo;' + esc(q) + '&rdquo; this day.</p>';
  }

  // Expand/collapse a species (clicking the head, but not its links/play button).
  listEl.addEventListener("click", function (ev) {
    if (ev.target.closest(".dl-play") || ev.target.closest("a")) return;
    var head = ev.target.closest(".dl-sphead"); if (!head) return;
    var row = head.closest(".dl-sprow");
    if (row.querySelector(".dl-subs")) row.classList.toggle("open");
  });

  // ---- audio: one shared element, rAF needle on the active thumb ----
  var audio = new Audio(); audio.preload = "none";
  var activeBtn = null, raf = 0;
  function stopAudio() {
    audio.pause();
    if (activeBtn) { activeBtn.classList.remove("playing"); activeBtn.style.setProperty("--p", 0); activeBtn = null; }
    if (raf) { cancelAnimationFrame(raf); raf = 0; }
  }
  function tick() {
    if (activeBtn && audio.duration) activeBtn.style.setProperty("--p", Math.min(1, audio.currentTime / audio.duration));
    raf = requestAnimationFrame(tick);
  }
  audio.addEventListener("ended", stopAudio);
  listEl.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".dl-play"); if (!btn) return;
    ev.stopPropagation();
    if (btn === activeBtn) { stopAudio(); return; }
    stopAudio();
    activeBtn = btn;
    audio.src = MEDIA + btn.getAttribute("data-audio"); audio.currentTime = 0;
    var pl = audio.play(); if (pl && pl.catch) pl.catch(stopAudio);
    btn.classList.add("playing");
    if (!raf) raf = requestAnimationFrame(tick);
  });

  // ---- share: copy a permalink to one recording (mirrors the photo lightbox) ----
  listEl.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".dl-share"); if (!btn) return;
    ev.stopPropagation();
    var url = location.origin + "/birds/live/log#rec-" + btn.getAttribute("data-token");
    function flash(msg) {
      var prev = btn.getAttribute("data-ok") || btn.innerHTML;
      btn.setAttribute("data-ok", prev); btn.classList.add("ok"); btn.innerHTML = msg;
      setTimeout(function () { btn.innerHTML = prev; btn.classList.remove("ok"); }, 1400);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(function () { flash("&#10003;"); }, function () { flash("&#10007;"); });
    } else {
      var ta = document.createElement("textarea"); ta.value = url; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); flash("&#10003;"); } catch (_) { flash("&#10007;"); }
      document.body.removeChild(ta);
    }
  });
  // ---- deep-link: /birds/live/log#rec-<clip> opens that day + recording, plays it ----
  function openFromRecHash() {
    var m = /^#rec-(.+)$/.exec(location.hash || "");
    if (!m) return false;
    var token = m[1], found = null, foundDay = null;
    for (var i = 0; i < days.length && !found; i++) {
      var recs = byDay[days[i]].recs;
      for (var j = 0; j < recs.length; j++) {
        if (recTokenOf(recs[j].e) === token) { found = recs[j]; foundDay = days[i]; break; }
      }
    }
    if (!found) return false;
    cur = days.indexOf(foundDay);
    searchEl.value = "";
    render();
    var name = found.e.display || found.e.common || "";
    var esel = window.CSS && CSS.escape ? CSS.escape : function (s) { return s.replace(/["\\]/g, "\\$&"); };
    var row = listEl.querySelector('.dl-sprow[data-name="' + esel(name) + '"]');
    if (row && row.querySelector(".dl-subs")) row.classList.add("open");
    var target = (found.e.audio && listEl.querySelector('.dl-sub[data-audio="' + esel(found.e.audio) + '"]')) || row;
    var btn = (found.e.audio && listEl.querySelector('.dl-play[data-audio="' + esel(found.e.audio) + '"]'));
    if (target) {
      target.classList.add("dl-flash");
      setTimeout(function () { target.classList.remove("dl-flash"); }, 2200);
      target.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    if (btn) setTimeout(function () { btn.click(); }, 450);
    return true;
  }
  addEventListener("hashchange", openFromRecHash);

  // ---- day navigation ----
  prevEl.addEventListener("click", function () { if (cur < days.length - 1) { cur++; render(); } });
  nextEl.addEventListener("click", function () { if (cur > 0) { cur--; render(); } });
  dateEl.addEventListener("change", function () {
    var i = days.indexOf(dateEl.value);
    if (i >= 0) { cur = i; render(); }
    else {
      // nearest day on/before the picked date, else the oldest
      var target = dateEl.value, best = -1;
      for (var k = 0; k < days.length; k++) { if (days[k] <= target) { best = k; break; } }
      cur = best >= 0 ? best : days.length - 1; render();
    }
  });
  var st; searchEl.addEventListener("input", function () { clearTimeout(st); st = setTimeout(render, 120); });
  // Order toggle: most-heard vs chronological; the pick is remembered.
  function syncSort() {
    if (!sortEl) return;
    sortEl.querySelectorAll("button").forEach(function (b) {
      b.classList.toggle("on", b.getAttribute("data-dlsort") === sortMode);
    });
  }
  if (sortEl) sortEl.addEventListener("click", function (ev) {
    var b = ev.target.closest("button"); if (!b) return;
    sortMode = b.getAttribute("data-dlsort");
    try { localStorage.setItem("dl-sort", sortMode); } catch (_) {}
    syncSort(); render();
  });
  syncSort();
  document.addEventListener("keydown", function (e) {
    if (e.target === searchEl || (e.target.tagName === "INPUT")) return;
    if (e.key === "ArrowLeft" && cur < days.length - 1) { cur++; render(); }
    if (e.key === "ArrowRight" && cur > 0) { cur--; render(); }
  });

  renderNodes();
  // A #rec-<clip> permalink jumps straight to that recording; else the newest day.
  if (!openFromRecHash()) render();
})();

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

  // Consolidate a day's detections into one entry per species.
  function speciesOf(recs) {
    var by = {}, order = [];
    recs.forEach(function (r) {
      var k = r.e.display || r.e.common || "Unknown";
      if (!by[k]) { by[k] = { name: k, slug: r.e.slug, fam: r.e.fam, photo: r.e.photo, shot: r.e.shot, recs: [] }; order.push(by[k]); }
      by[k].recs.push(r);
    });
    order.forEach(function (s) {
      s.recs.sort(function (a, b) { return b.e.conf - a.e.conf; });   // highest confidence first
      s.count = s.recs.length;
      s.best = s.recs[0];
    });
    order.sort(function (a, b) { return b.count - a.count || (a.name < b.name ? -1 : 1); });
    return order;
  }

  function playBtn(r, label) {
    return '<button type="button" class="dl-play" data-audio="' + esc(r.e.audio) + '" aria-label="Play ' + esc(label) + '">' +
      (r.e.spec ? '<img loading="lazy" decoding="async" src="' + MEDIA + esc(r.e.spec) + '" alt="">' : '') +
      '<span class="dl-needle"></span><span class="dl-ico">&#9654;</span></button>';
  }

  function render() {
    stopAudio();
    var day = byDay[days[cur]];
    var q = (searchEl.value || "").trim().toLowerCase();
    titleEl.textContent = dayLabel(day.p);
    dateEl.value = days[cur];
    prevEl.disabled = cur >= days.length - 1;   // older = higher index
    nextEl.disabled = cur <= 0;
    var sp = speciesOf(day.recs);
    if (q) sp = sp.filter(function (s) { return (s.name || "").toLowerCase().indexOf(q) !== -1; });
    var totalRecs = day.recs.length;
    sumEl.textContent = totalRecs + " recording" + (totalRecs !== 1 ? "s" : "") + " · " +
      speciesOf(day.recs).length + " species";

    listEl.innerHTML = sp.map(function (s) {
      var conf = Math.round(s.best.e.conf * 100);
      var nameHtml = s.slug
        ? '<a class="dl-nm" href="/birds/species/' + encodeURIComponent(s.slug) + '">' + esc(s.name) + '</a>'
        : '<span class="dl-nm">' + esc(s.name) + '</span>';
      var tag = s.shot ? '<span class="dl-tag">&#10003; gallery</span>' : '<span class="dl-tag ear">by ear only</span>';
      var subs = s.recs.map(function (r) {
        return '<div class="dl-sub"><span class="st">' + esc(timeLabel(r.p)) + '</span>' +
          '<span class="sc">' + Math.round(r.e.conf * 100) + '%</span>' + playBtn(r, s.name + ' at ' + timeLabel(r.p)) + '</div>';
      }).join("");
      return '<div class="dl-sprow" data-name="' + esc(s.name) + '">' +
        '<div class="dl-sphead">' +
          (s.photo ? '<img class="dl-av" loading="lazy" src="' + esc(s.photo) + '" alt="">' : '<span class="dl-av ear">&#129718;</span>') +
          '<span class="dl-spmain">' + nameHtml +
            '<span class="dl-spmeta"><span class="dl-fam">' + esc(s.fam || "") + '</span>' + tag +
            (s.count > 1 ? '<button type="button" class="dl-count" aria-label="Show all ' + s.count + ' recordings, highest confidence first">&times;' + s.count + ' recordings</button>' : '') +
            '<span class="dl-hi mono" title="highest confidence">' + conf + '%</span></span></span>' +
          '<span class="dl-spright">' + playBtn(s.best, s.name) + '</span>' +
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
  document.addEventListener("keydown", function (e) {
    if (e.target === searchEl || (e.target.tagName === "INPUT")) return;
    if (e.key === "ArrowLeft" && cur < days.length - 1) { cur++; render(); }
    if (e.key === "ArrowRight" && cur > 0) { cur--; render(); }
  });

  render();
})();

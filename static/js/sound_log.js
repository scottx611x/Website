/* Detection log: filter + group-by-day + paginate + inline playback.
   LOG, MEDIA, PAGE are injected by the template before this loads. */
(function () {
  "use strict";
  if (typeof LOG === "undefined" || !LOG.length) return;

  var listEl = document.getElementById("dl-list");
  var moreEl = document.getElementById("dl-more");
  var countEl = document.getElementById("dl-count");
  var selEl = document.getElementById("dl-species");
  var searchEl = document.getElementById("dl-search");
  var soundEl = document.getElementById("dl-sound");
  var soundLbl = document.getElementById("dl-sound-lbl");
  var daysEl = document.getElementById("dl-days");

  var DAYNAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  // Timestamps carry the mic's own UTC offset (…-04:00). Read the wall-clock
  // fields straight out of the string so the viewer's timezone never shifts them.
  function parts(t) {
    var m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(t || "");
    if (!m) return null;
    return { day: m[1] + "-" + m[2] + "-" + m[3], y: +m[1], mo: +m[2], d: +m[3], h: +m[4], mi: +m[5] };
  }
  function dayLabel(p) {
    var wd = new Date(Date.UTC(p.y, p.mo - 1, p.d)).getUTCDay();
    return DAYNAMES[wd] + ", " + MONTHS[p.mo - 1] + " " + p.d;
  }
  function timeLabel(p) {
    var h = p.h, ap = h < 12 ? "AM" : "PM";
    h = h % 12; if (h === 0) h = 12;
    return h + ":" + (p.mi < 10 ? "0" : "") + p.mi + " " + ap;
  }

  // Newest first, with parsed time fields cached on each row.
  var ROWS = LOG.map(function (e) { return { e: e, p: parts(e.t) }; })
    .filter(function (r) { return r.p; })
    .sort(function (a, b) { return a.e.t < b.e.t ? 1 : a.e.t > b.e.t ? -1 : 0; });

  // Species dropdown, alphabetical, with per-species counts.
  var byName = {};
  ROWS.forEach(function (r) {
    var n = r.e.display || r.e.common || "Unknown";
    byName[n] = (byName[n] || 0) + 1;
  });
  Object.keys(byName).sort().forEach(function (n) {
    var o = document.createElement("option");
    o.value = n; o.textContent = n + " (" + byName[n] + ")";
    selEl.appendChild(o);
  });

  var shown = 0, filtered = ROWS;

  function applyFilter() {
    var sp = selEl.value;
    var q = (searchEl.value || "").trim().toLowerCase();
    var soundOnly = soundEl.checked;
    filtered = ROWS.filter(function (r) {
      if (sp && (r.e.display || r.e.common) !== sp) return false;
      if (soundOnly && !r.e.audio) return false;
      if (q) {
        var hay = ((r.e.display || "") + " " + (r.e.common || "") + " " + (r.e.sci || "")).toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
    shown = 0;
    listEl.innerHTML = "";
    stopAudio();
    render();
    renderDayRail();
  }

  // Day rail: one chip per day present in the current filter, click to jump.
  function renderDayRail() {
    if (!daysEl) return;
    var days = [], counts = {};
    filtered.forEach(function (r) {
      if (counts[r.p.day] === undefined) { counts[r.p.day] = 0; days.push(r.p); }
      counts[r.p.day]++;
    });
    daysEl.innerHTML = days.map(function (p) {
      return '<button type="button" class="dl-daychip" data-day="' + p.day + '">' +
        '<span class="dd">' + MONTHS[p.mo - 1] + ' ' + p.d + '</span>' +
        '<span class="dn mono">' + counts[p.day] + '</span></button>';
    }).join("");
  }
  function markActiveDay(day) {
    if (!daysEl) return;
    daysEl.querySelectorAll(".dl-daychip").forEach(function (c) {
      c.classList.toggle("on", c.getAttribute("data-day") === day);
    });
  }
  function jumpToDay(day) {
    // Page in until that day's group exists, then scroll it into view.
    var guard = 0;
    while (!listEl.querySelector('.dl-day[data-day="' + day + '"]') && shown < filtered.length && guard++ < 200) {
      render();
    }
    var grp = listEl.querySelector('.dl-day[data-day="' + day + '"]');
    if (grp) { grp.scrollIntoView({ behavior: "smooth", block: "start" }); markActiveDay(day); }
  }
  if (daysEl) daysEl.addEventListener("click", function (e) {
    var c = e.target.closest(".dl-daychip"); if (c) jumpToDay(c.getAttribute("data-day"));
  });

  function render() {
    var end = Math.min(shown + PAGE, filtered.length);
    // Continue the last open day group if we're paging into it.
    var curDay = listEl.lastElementChild && listEl.lastElementChild.getAttribute("data-day");
    var body = null;
    if (curDay) body = listEl.lastElementChild.querySelector(".dl-daybody");

    for (var i = shown; i < end; i++) {
      var r = filtered[i];
      if (r.p.day !== curDay) {
        curDay = r.p.day;
        var grp = document.createElement("div");
        grp.className = "dl-day";
        grp.setAttribute("data-day", curDay);
        var count = 0, spset = {};
        for (var j = i; j < filtered.length && filtered[j].p.day === curDay; j++) {
          count++; spset[filtered[j].e.display || filtered[j].e.common] = 1;
        }
        var ns = Object.keys(spset).length;
        grp.innerHTML =
          '<div class="dl-dayhead"><span class="dl-dayname">' + esc(dayLabel(r.p)) + '</span>' +
          '<span class="dl-daymeta mono">' + count + ' recording' + (count !== 1 ? 's' : '') +
          ' &middot; ' + ns + ' species</span></div>' +
          '<div class="dl-daybody"></div>';
        listEl.appendChild(grp);
        body = grp.querySelector(".dl-daybody");
      }
      body.appendChild(rowEl(r.e, r.p));
    }
    shown = end;
    if (shown >= filtered.length) { moreEl.hidden = true; }
    else { moreEl.hidden = false; moreEl.textContent = "Load more (" + (filtered.length - shown) + " left)"; }
    countEl.textContent = filtered.length + " detection" + (filtered.length !== 1 ? "s" : "") +
      (filtered.length !== ROWS.length ? " of " + ROWS.length : "");
    if (!filtered.length) countEl.textContent = "No detections match.";
  }

  function rowEl(e, p) {
    var row = document.createElement("div");
    row.className = "dl-row";
    var conf = Math.round((e.conf || 0) * 100);
    var name = e.display || e.common || "Unknown";
    var nameHtml = e.slug
      ? '<a class="dl-nm" href="/birds/species/' + encodeURIComponent(e.slug) + '">' + esc(name) + '</a>'
      : '<span class="dl-nm">' + esc(name) + '</span>';
    var tags = "";
    if (e.shot) tags += '<span class="dl-tag shot">&#10003; gallery</span>';
    else tags += '<span class="dl-tag">by ear only</span>';

    var right;
    if (e.audio) {
      right =
        '<button class="dl-play" data-audio="' + esc(e.audio) + '" aria-label="Play ' + esc(name) + '">' +
        (e.spec ? '<img loading="lazy" decoding="async" src="' + MEDIA + esc(e.spec) + '" alt="">' : '') +
        '<span class="dl-needle"></span><span class="dl-ico">&#9654;</span></button>';
    } else {
      right = '<span class="dl-noaudio">no clip</span>';
    }

    row.innerHTML =
      '<span class="dl-time mono">' + esc(timeLabel(p)) + '</span>' +
      '<span class="dl-main">' + nameHtml + '<span class="dl-fam">' + esc(e.fam || "") + '</span>' + tags + '</span>' +
      '<span class="dl-right"><span class="dl-conf">' +
      '<span class="dl-meter"><i style="width:' + conf + '%"></i></span>' + conf + '%</span>' + right + '</span>';
    return row;
  }

  // ---- Audio: one shared element, rAF-driven needle on the active thumb ----
  var audio = new Audio();
  audio.preload = "none";
  var activeBtn = null, raf = 0;

  function stopAudio() {
    audio.pause();
    if (activeBtn) { activeBtn.classList.remove("playing"); activeBtn.style.setProperty("--p", 0); activeBtn = null; }
    if (raf) { cancelAnimationFrame(raf); raf = 0; }
  }
  function tick() {
    if (activeBtn && audio.duration) {
      activeBtn.style.setProperty("--p", Math.min(1, audio.currentTime / audio.duration));
    }
    raf = requestAnimationFrame(tick);
  }
  audio.addEventListener("ended", stopAudio);

  listEl.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".dl-play");
    if (!btn) return;
    if (btn === activeBtn) { stopAudio(); return; }
    stopAudio();
    activeBtn = btn;
    audio.src = MEDIA + btn.getAttribute("data-audio");
    audio.currentTime = 0;
    var play = audio.play();
    if (play && play.catch) play.catch(function () { stopAudio(); });
    btn.classList.add("playing");
    if (!raf) raf = requestAnimationFrame(tick);
  });

  // ---- Wire controls ----
  selEl.addEventListener("change", applyFilter);
  soundEl.addEventListener("change", function () {
    soundLbl.classList.toggle("on", soundEl.checked);
    applyFilter();
  });
  var searchTimer = 0;
  searchEl.addEventListener("input", function () {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(applyFilter, 140);
  });
  moreEl.addEventListener("click", render);

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  render();
  renderDayRail();
})();

/* Search combobox shared by the bird gallery and Photography.
 *
 *   searchCombo({
 *     box, input, pop,          // the .bird-combo wrapper, its input, its listbox
 *     entries: [{name, meta, count, broad, alt: [..]}],
 *     browse: [..], browseHead: "Browse by family",   // shown when the box is empty
 *     none: function (q) { return "No match for …" },
 *     choose: function (entry) {},                    // a row was picked
 *     fallback: function (text) {}                    // Enter with no rows (optional)
 *   });
 *
 * Ranking matters more than matching: "wood" should put the Woodpeckers family
 * and Wood Duck above Eastern Wood-Pewee, and a <datalist> has no way to
 * express that. Prefix beats word-start beats anywhere; an entry also answers
 * to its `alt` words (a bird's family, a photo's species or place) three tiers
 * down; within a tier the `broad` entries (families, categories) come first,
 * then the better-photographed one, because that is what you are more likely
 * to be after.
 */
(function () {
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function tier(hay, q) {
    var i = String(hay || "").toLowerCase().indexOf(q);
    if (i < 0) return -1;
    if (i === 0) return 0;
    return /[\s\-]/.test(hay.charAt(i - 1)) ? 1 : 2;   // word start, else inside
  }
  function mark(name, q) {
    if (!q) return esc(name);
    var i = name.toLowerCase().indexOf(q);
    if (i < 0) return esc(name);
    return esc(name.slice(0, i)) + "<b>" + esc(name.slice(i, i + q.length)) +
           "</b>" + esc(name.slice(i + q.length));
  }

  window.searchCombo = function (o) {
    var box = o.box, input = o.input, pop = o.pop;
    if (!box || !input || !pop) return;
    var MAX = o.max || 10;
    var items = [], active = -1, open = false;

    function rank(q) {
      var hits = [];
      o.entries.forEach(function (e) {
        var t = tier(e.name, q);
        if (t < 0) {
          (e.alt || []).forEach(function (a) {
            var at = tier(a, q);
            if (at >= 0 && (t < 0 || at + 3 < t)) t = at + 3;
          });
        }
        if (t >= 0) hits.push({ e: e, t: t, b: e.broad ? 0 : 1 });
      });
      hits.sort(function (a, b) {
        return (a.t - b.t) || (a.b - b.b) || ((b.e.count || 0) - (a.e.count || 0)) ||
               a.e.name.localeCompare(b.e.name);
      });
      return hits.slice(0, MAX).map(function (x) { return x.e; });
    }

    function render(q) {
      // Empty box: a browsable menu, so the box is useful before you know
      // what to type.
      items = q ? rank(q) : (o.browse || []).slice();
      active = -1;
      if (!items.length) {
        pop.innerHTML = q ? '<p class="bc-none">' + esc(o.none ? o.none(q) : "No match") + "</p>" : "";
        return;
      }
      pop.innerHTML = (q || !o.browseHead ? "" : '<p class="bc-head">' + esc(o.browseHead) + "</p>") +
        items.map(function (e, i) {
          return '<div class="bc-opt" role="option" aria-selected="false" ' +
                 'id="' + pop.id + "-" + i + '" data-i="' + i + '">' +
                 '<span class="bc-name' + (e.broad ? " is-fam" : "") + '">' +
                 mark(e.name, q) + "</span>" +
                 '<span class="bc-meta">' + esc(e.meta || "") + "</span></div>";
        }).join("");
    }
    function setOpen(v) {
      open = v && !!pop.innerHTML;
      pop.hidden = !open;
      box.classList.toggle("is-open", open);
      input.setAttribute("aria-expanded", open ? "true" : "false");
      if (!open) { input.removeAttribute("aria-activedescendant"); active = -1; }
    }
    function highlight(i) {
      var opts = pop.querySelectorAll(".bc-opt");
      if (!opts.length) return;
      if (active >= 0 && opts[active]) {
        opts[active].classList.remove("on");
        opts[active].setAttribute("aria-selected", "false");
      }
      active = (i + opts.length) % opts.length;
      opts[active].classList.add("on");
      opts[active].setAttribute("aria-selected", "true");
      input.setAttribute("aria-activedescendant", opts[active].id);
      // keep the highlighted row in view when arrowing past the fold
      var r = opts[active], top = r.offsetTop, bot = top + r.offsetHeight;
      if (top < pop.scrollTop) pop.scrollTop = top;
      else if (bot > pop.scrollTop + pop.clientHeight) pop.scrollTop = bot - pop.clientHeight;
    }
    function choose(e) {
      if (!e) return;
      setOpen(false);
      o.choose(e);
    }
    function refresh() {
      render(input.value.trim().toLowerCase());
      setOpen(true);
    }

    input.addEventListener("input", refresh);
    input.addEventListener("focus", refresh);
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (!open) refresh();
        highlight(active + (e.key === "ArrowDown" ? 1 : -1));
      } else if (e.key === "Enter") {
        e.preventDefault();
        // Enter with nothing highlighted takes the top match, which is what
        // "type and hit return" should obviously do.
        if (items.length) choose(active >= 0 ? items[active] : items[0]);
        else if (o.fallback) o.fallback(input.value);
      } else if (e.key === "Escape") {
        if (open) { e.stopPropagation(); setOpen(false); }
      } else if (e.key === "Tab") {
        setOpen(false);
      }
    });
    pop.addEventListener("mousedown", function (e) {
      // mousedown, not click: blur would close the list first
      var r = e.target.closest(".bc-opt");
      if (!r) return;
      e.preventDefault();
      choose(items[+r.dataset.i]);
    });
    pop.addEventListener("mousemove", function (e) {
      var r = e.target.closest(".bc-opt");
      if (r) highlight(+r.dataset.i);
    });
    document.addEventListener("click", function (e) {
      if (!box.contains(e.target)) setOpen(false);
    });
  };
})();

/* The gallery's view menu (#viewMenu / #vmBtn / #vmPop): open, close on a
 * click elsewhere or Escape, and restore the saved thumbnail size. Shared by
 * /birds and Photography. Returns set(open) for callers that close it. */
window.galleryViewMenu = function () {
  var box = document.getElementById("viewMenu");
  var btn = document.getElementById("vmBtn");
  var pop = document.getElementById("vmPop");
  if (!box || !btn || !pop) return function () {};
  function set(v) {
    pop.hidden = !v;
    box.classList.toggle("is-open", v);
    btn.setAttribute("aria-expanded", v ? "true" : "false");
  }
  btn.addEventListener("click", function (e) {
    e.stopPropagation();
    set(pop.hidden);
  });
  // The size slider lives in here, so dragging it must not count as
  // "clicked away".
  pop.addEventListener("click", function (e) { e.stopPropagation(); });
  document.addEventListener("click", function () { set(false); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !pop.hidden) { set(false); btn.focus(); }
  });
  try {
    var v = localStorage.getItem("birdsThumbZoom"), z = document.getElementById("thumbZoom");
    if (v && z) z.value = v;
  } catch (_) { /* private mode */ }
  return set;
};

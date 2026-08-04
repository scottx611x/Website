/* Listening nodes: one subtle, stable visual identity per mic, shared by the live
   feed, the day log, and species pages. Colors are assigned by the node's position
   in the (alphabetically-sorted) roster, so two mics never collide on the same
   color — and because every page sorts the same full roster, a given mic keeps its
   color across pages. Deliberately quiet: a small dot, not a banner. */
(function () {
  "use strict";
  // A calm palette, kept clear of the site's green (species) and amber (away).
  var PAL = [
    { dot: "#2a9d9c", soft: "rgba(42,157,156,.14)" },   // teal
    { dot: "#c25b86", soft: "rgba(194,91,134,.14)" },   // rose
    { dot: "#3d7ec4", soft: "rgba(61,126,196,.14)" },   // blue
    { dot: "#b8863b", soft: "rgba(184,134,59,.14)" },   // ochre
    { dot: "#7c6bd0", soft: "rgba(124,107,208,.14)" },  // violet
    { dot: "#5a8f4e", soft: "rgba(90,143,78,.14)" }     // moss
  ];
  function hash(s) { var h = 0, i; s = s || ""; for (i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) >>> 0; } return h; }
  var MAP = null;  // name -> palette entry, set by assign()
  function style(name) {
    if (MAP && Object.prototype.hasOwnProperty.call(MAP, name)) return MAP[name];
    return PAL[hash(name) % PAL.length];  // fallback before assign() runs
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  window.NodeUI = {
    // Assign a distinct color to each node by sorted position — call once per page
    // with the FULL roster of node names so colors are distinct and page-stable.
    assign: function (names) {
      var uniq = [];
      (names || []).forEach(function (n) { if (n && uniq.indexOf(n) < 0) uniq.push(n); });
      uniq.sort();
      MAP = {};
      uniq.forEach(function (n, i) { MAP[n] = PAL[i % PAL.length]; });
    },
    style: style,
    // A bare dot for inline use next to a recording (name in the tooltip).
    dot: function (name) {
      if (!name) return "";
      return '<span class="node-dot" style="background:' + style(name).dot + '" title="heard on ' + esc(name) + '"></span>';
    },
    // A dot + inline text label, for naming the mic right on a recording row
    // (where a bare dot alone reads as "no mic"). Quieter than the filter chip.
    tag: function (name) {
      if (!name) return "";
      return '<span class="node-tag" title="heard on ' + esc(name) + '">' +
        '<span class="node-dot" style="background:' + style(name).dot + '"></span>' +
        '<span class="node-tagname">' + esc(name) + '</span></span>';
    },
    // A dot + label chip, for the filter row and the "heard on" lines.
    chip: function (name, on) {
      var s = style(name);
      return '<button type="button" class="node-chip' + (on ? " on" : "") + '" data-node="' + esc(name) + '"' +
        (on ? ' style="border-color:' + s.dot + '"' : '') + '>' +
        '<span class="node-dot" style="background:' + s.dot + '"></span>' + esc(name) + '</button>';
    }
  };
})();

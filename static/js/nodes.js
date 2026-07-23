/* Listening nodes: one subtle, stable visual identity per mic, shared by the live
   feed, the day log, and species pages. Color is derived from the node NAME (not
   position), so a node looks the same everywhere regardless of which set of nodes
   a given page happens to show. Deliberately quiet — a small dot, not a banner. */
(function () {
  "use strict";
  // A calm palette, kept clear of the site's green (species) and amber (away).
  var PAL = [
    { dot: "#2a9d9c", soft: "rgba(42,157,156,.14)" },   // teal
    { dot: "#7c6bd0", soft: "rgba(124,107,208,.14)" },  // violet
    { dot: "#3d7ec4", soft: "rgba(61,126,196,.14)" },   // blue
    { dot: "#c25b86", soft: "rgba(194,91,134,.14)" },   // rose
    { dot: "#5a8f4e", soft: "rgba(90,143,78,.14)" },    // moss
    { dot: "#b8863b", soft: "rgba(184,134,59,.14)" }    // ochre
  ];
  function hash(s) { var h = 0, i; s = s || ""; for (i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) >>> 0; } return h; }
  function style(name) { return PAL[hash(name) % PAL.length]; }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  window.NodeUI = {
    style: style,
    // A bare dot for inline use next to a recording (name in the tooltip).
    dot: function (name) {
      if (!name) return "";
      return '<span class="node-dot" style="background:' + style(name).dot + '" title="heard on ' + esc(name) + '"></span>';
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

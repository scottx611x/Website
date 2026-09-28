/* Shared playhead engine.
 *
 * One rAF loop sets a single CSS custom property `--p` (progress, 0..1) on
 * every element registered as a view of the playing clip. The needle, the
 * played "wash" and the unplayed "veil" all key off `--p` in CSS, so they
 * glide together at 60fps instead of stepping ~4x a second on `timeupdate`.
 *
 * Lifted out of the live page so /birds and /birds/live drive their
 * spectrograms with the same code rather than two copies that drift.
 *
 *   var ph = new Playhead(audioEl);
 *   ph.views([specEl]);     // elements carrying .ph-needle/.ph-wash/.ph-veil
 *   ph.sync();              // call after play/pause/seek
 */
(function (w) {
  "use strict";

  function Playhead(audio) {
    this.audio = audio;
    this._views = [];
    this._raf = null;
    var self = this;
    ["play", "pause", "ended", "seeked", "loadedmetadata"].forEach(function (ev) {
      audio.addEventListener(ev, function () { self.sync(); });
    });
  }

  Playhead.prototype.views = function (els) {
    this._views = (els || []).filter(Boolean);
    this._paint();
    return this;
  };

  Playhead.prototype.progress = function () {
    var d = this.audio.duration;
    return (d && isFinite(d)) ? Math.min(1, Math.max(0, this.audio.currentTime / d)) : 0;
  };

  Playhead.prototype._paint = function () {
    var p = this.progress(), on = !this.audio.paused;
    this._views.forEach(function (el) {
      el.style.setProperty("--p", p);
      el.classList.toggle("ph-on", on);
    });
  };

  /* Seek from a click anywhere on a view, as a fraction of its width. */
  Playhead.prototype.seekFromEvent = function (el, e) {
    var d = this.audio.duration;
    if (!d || !isFinite(d)) return;
    var r = el.getBoundingClientRect();
    this.audio.currentTime = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * d;
    this.sync();
  };

  Playhead.prototype.sync = function () {
    var self = this;
    this._paint();
    if (this.audio.paused) {
      if (this._raf) { cancelAnimationFrame(this._raf); this._raf = null; }
      return;
    }
    if (this._raf) return;
    (function loop() {
      self._paint();
      self._raf = self.audio.paused ? null : requestAnimationFrame(loop);
    })();
  };

  Playhead.prototype.stop = function () {
    this.audio.pause();
    this.audio.currentTime = 0;
    this.sync();
  };

  w.Playhead = Playhead;
})(window);

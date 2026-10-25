/* One curate panel, for every surface that edits a bird frame.
 *
 * There used to be two implementations. The masonry lightbox (base.html) could
 * edit species, both dates and the re-ID flag; the field overlay (_field.html)
 * could star a frame. Neither could do the other's job, so which half of
 * curate you got depended on the gallery's sort order — picking "Newest post"
 * silently swapped you into a different editor. On top of that the field
 * overlay posted its per-image maps as sparse arrays, a shape the server
 * ignored, so its two editing controls saved nothing at all.
 *
 * This module owns every per-frame action and the markup for them, so the two
 * surfaces cannot drift again: a control added here appears everywhere, and
 * there is exactly one place where a payload shape can be wrong.
 *
 * The host adapts its own frame object to the shape in `bind()` and supplies
 * an `onPatch` callback to repaint whatever it draws around the panel
 * (captions, filmstrip, grid cards).
 *
 * Bird frames only. /photography edits a different store through
 * /photography/edit and keeps its own path.
 */
(function (w, d) {
    "use strict";

    var SVG = 'viewBox="0 0 24 24" width="15" height="15" fill="none" ' +
              'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
              'stroke-linejoin="round"';
    var ICON = {
        alert: '<svg ' + SVG + '><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>',
        hide: '<svg ' + SVG + '><path d="M9.9 4.2A10.9 10.9 0 0 1 12 4c7 0 10 8 10 8a18.5 18.5 0 0 1-2.2 3.2"/><path d="M6.6 6.6A18.5 18.5 0 0 0 2 12s3 8 10 8a10.9 10.9 0 0 0 5.4-1.4"/><path d="M14.1 14.1a3 3 0 1 1-4.2-4.2"/><path d="m2 2 20 20"/></svg>',
        show: '<svg ' + SVG + '><path d="M2 12s3-8 10-8 10 8 10 8-3 8-10 8-10-8-10-8z"/><circle cx="12" cy="12" r="3"/></svg>',
        star: '<svg ' + SVG + '><path d="m12 3 2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.8 6.2 20.9l1.1-6.5L2.6 9.8l6.5-.9z"/></svg>',
        reid: '<svg ' + SVG + '><path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 3v6h-6"/></svg>'
    };

    function el(tag, cls, html) {
        var n = d.createElement(tag);
        if (cls) n.className = cls;
        if (html != null) n.innerHTML = html;
        return n;
    }

    /* Every save goes through here, so "did it actually persist?" has one
     * answer. The endpoints answer {"ok": true} inside a 200, and a false
     * `ok` is a failure even though the HTTP status says otherwise — that
     * distinction is what made the sparse-array bug invisible for so long. */
    function post(url, body) {
        return fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        }).then(function (r) {
            if (!r.ok) throw new Error(url + " -> " + r.status);
            return r.json();
        }).then(function (j) {
            if (!j || j.ok === false) throw new Error(url + " -> not ok");
            return j;
        });
    }

    /* Per-image maps are keyed by frame index. ALWAYS an object: a sparse
     * array JSON-encodes as a list, which the server used to drop silently.
     * (It now normalizes either shape, but there is no reason to send the
     * shape that was wrong.) */
    function imageMap(index, value) {
        var m = {};
        m[String(index)] = value;
        return m;
    }

    function flash(node, ok) {
        if (!node) return;
        node.classList.remove("saved", "save-failed");
        node.classList.add(ok ? "saved" : "save-failed");
        if (ok) setTimeout(function () { node.classList.remove("saved"); }, 1500);
    }

    function Panel(root, opts) {
        this.root = root;
        this.opts = opts || {};
        this.frame = null;
        this.build();
    }

    Panel.prototype.build = function () {
        var p = this;
        var r = this.root;
        r.classList.add("cur");
        r.innerHTML = "";

        // The species the Instagram caption named. Tapping one is the fast
        // path for the common correction, which is why it sits above the
        // field rather than being something you retype.
        this.suggest = el("div", "cur-suggest");
        this.suggest.hidden = true;
        r.appendChild(this.suggest);

        this.species = this.field(r, "text", "species", "Species for this frame");
        this.location = this.field(r, "text", "location", "Where this frame was taken");

        // Both dates belong to the POST, not the frame — Instagram dates a
        // carousel once. Labelled so that is not a surprise when an edit moves
        // every frame of a post at the same time.
        var dates = el("div", "cur-dates");
        this.taken = this.dateField(dates, "taken", "Capture date (whole post)");
        this.posted = this.dateField(dates, "posted", "Instagram post date (whole post)");
        r.appendChild(dates);

        var row = el("div", "cur-actions");
        this.star = this.toggle(row, "cur-star", ICON.star, "Star");
        this.area = this.toggle(row, "cur-area", ICON.alert, "Out of area");
        this.reid = this.toggle(row, "cur-reid", ICON.reid, "Re-ID");
        this.hide = this.toggle(row, "cur-hide", ICON.hide, "Hide");
        r.appendChild(row);

        this.note = el("p", "cur-note");
        r.appendChild(this.note);

        // change, not input: one save per committed edit, not per keystroke.
        this.species.addEventListener("change", function () { p.saveSpecies(); });
        this.species.addEventListener("keydown", function (e) {
            if (e.key === "Enter") { e.preventDefault(); p.saveSpecies(); p.species.blur(); }
        });
        this.location.addEventListener("change", function () { p.saveLocation(); });
        this.location.addEventListener("keydown", function (e) {
            if (e.key === "Enter") { e.preventDefault(); p.saveLocation(); p.location.blur(); }
        });
        this.taken.addEventListener("change", function () { p.saveDate("capture_date", p.taken, "captureDate"); });
        this.posted.addEventListener("change", function () { p.saveDate("posted", p.posted, "postedDate"); });
        this.star.addEventListener("click", function () { p.toggleStar(); });
        this.area.addEventListener("click", function () { p.toggleArea(); });
        this.reid.addEventListener("click", function () { p.toggleReid(); });
        this.hide.addEventListener("click", function () { p.toggleHidden(); });

        // Typing inside the panel must never reach the host's keyboard
        // shortcuts, or naming a Kestrel pages the gallery on every arrow key.
        r.addEventListener("keydown", function (e) { e.stopPropagation(); });
        r.addEventListener("click", function (e) { e.stopPropagation(); });
    };

    Panel.prototype.field = function (parent, type, placeholder, label) {
        var i = el("input", "cur-field");
        i.type = type;
        i.placeholder = placeholder;
        i.setAttribute("aria-label", label);
        parent.appendChild(i);
        return i;
    };

    Panel.prototype.dateField = function (parent, name, label) {
        var wrap = el("label", "cur-date");
        wrap.appendChild(el("span", null, name));
        var i = el("input");
        i.type = "date";
        i.setAttribute("aria-label", label);
        i.title = label;
        wrap.appendChild(i);
        parent.appendChild(wrap);
        return i;
    };

    Panel.prototype.toggle = function (parent, cls, icon, label) {
        var b = el("button", "cur-act " + cls, icon + "<span>" + label + "</span>");
        b.type = "button";
        b.setAttribute("aria-pressed", "false");
        parent.appendChild(b);
        return b;
    };

    Panel.prototype.say = function (msg, bad) {
        this.note.textContent = msg || "";
        this.note.classList.toggle("is-bad", !!bad);
        if (msg && !bad) {
            var n = this.note;
            setTimeout(function () { if (n.textContent === msg) n.textContent = ""; }, 2000);
        }
    };

    /* Repaint for a frame. Hosts call this on every stage change — editing the
     * photo you were looking at a moment ago is the failure mode worth
     * designing against. */
    Panel.prototype.bind = function (frame) {
        this.frame = frame;
        var ok = !!(frame && frame.postId);
        this.root.classList.toggle("is-empty", !ok);
        [this.species, this.location, this.taken, this.posted,
         this.star, this.area, this.reid, this.hide].forEach(function (n) {
            n.disabled = !ok;
            n.classList.remove("saved", "save-failed");
        });
        this.say("");
        if (!ok) {
            this.suggest.hidden = true;
            return;
        }
        this.species.value = frame.species || "";
        this.location.value = frame.location || "";
        this.taken.value = (frame.captureDate || "").slice(0, 10);
        this.posted.value = (frame.postedDate || "").slice(0, 10);
        this.paintToggles();
        this.paintSuggest();
    };

    Panel.prototype.paintToggles = function () {
        var f = this.frame || {};
        function set(btn, on, label) {
            btn.classList.toggle("on", !!on);
            btn.setAttribute("aria-pressed", on ? "true" : "false");
            var s = btn.querySelector("span");
            if (s && label) s.textContent = label;
        }
        set(this.star, f.starred, f.starred ? "Starred" : "Star");
        set(this.area, f.away, f.away ? "Out of area" : "Out of area");
        set(this.reid, f.reidQueued, f.reidQueued ? "Flagged" : "Re-ID");
        set(this.hide, f.hidden, f.hidden ? "Hidden" : "Hide");
        this.hide.innerHTML = (f.hidden ? ICON.show : ICON.hide) +
            "<span>" + (f.hidden ? "Restore" : "Hide") + "</span>";
    };

    Panel.prototype.paintSuggest = function () {
        var p = this;
        var list = (this.frame && this.frame.captionSpecies) || [];
        this.suggest.innerHTML = "";
        this.suggest.hidden = !list.length;
        if (!list.length) return;
        this.suggest.appendChild(el("span", "cur-suggest-label", "IG detected:"));
        list.forEach(function (name) {
            var c = el("button", "cur-chip", "");
            c.type = "button";
            c.textContent = name;
            if (name === p.frame.species) c.classList.add("is-current");
            c.addEventListener("click", function () {
                p.species.value = name;
                p.saveSpecies();
            });
            p.suggest.appendChild(c);
        });
    };

    /* Each save writes the server first, then the frame, then tells the host.
     * Writing the frame optimistically would leave the panel disagreeing with
     * the data the moment a save failed. */
    Panel.prototype.commit = function (url, body, node, apply, label) {
        var p = this;
        var f = this.frame;
        if (node) node.disabled = true;
        return post(url, body).then(function (j) {
            if (p.frame !== f) return j;   // paged away mid-flight; don't repaint
            apply(j);
            flash(node, true);
            p.say(label ? label + " saved" : "saved");
            if (p.opts.onPatch) p.opts.onPatch(f, j);
            return j;
        }).catch(function (e) {
            flash(node, false);
            p.say("could not save", true);
            throw e;
        }).finally(function () {
            if (node) node.disabled = false;
        });
    };

    Panel.prototype.saveSpecies = function () {
        var f = this.frame, p = this;
        if (!f) return;
        var name = this.species.value.trim();
        if (name === (f.species || "")) return;
        this.commit("/curate/override",
            { id: f.postId, images: imageMap(f.index, name) },
            this.species,
            function () { f.species = name; p.paintSuggest(); }, "species")
            .catch(function () {});
    };

    Panel.prototype.saveLocation = function () {
        var f = this.frame;
        if (!f) return;
        var loc = this.location.value.trim();
        if (loc === (f.location || "")) return;
        this.commit("/curate/override",
            { id: f.postId, image_locations: imageMap(f.index, loc) },
            this.location,
            function () { f.location = loc; }, "location")
            .catch(function () {});
    };

    Panel.prototype.saveDate = function (key, node, prop) {
        var f = this.frame;
        if (!f) return;
        var iso = node.value;           // "" clears back to the caption/post date
        if (iso === (f[prop] || "")) return;
        var body = { id: f.postId };
        body[key] = iso;
        this.commit("/curate/override", body, node,
            function () { f[prop] = iso; }, key === "posted" ? "post date" : "date")
            .catch(function () {});
    };

    Panel.prototype.toggleStar = function () {
        var f = this.frame, p = this;
        if (!f) return;
        var next = !f.starred;
        this.commit("/curate/star", { id: f.postId, index: f.index, on: next },
            this.star, function () { f.starred = next; p.paintToggles(); })
            .catch(function () {});
    };

    Panel.prototype.toggleArea = function () {
        var f = this.frame, p = this;
        if (!f) return;
        var next = f.away ? "local" : "away";
        this.commit("/curate/override",
            { id: f.postId, image_areas: imageMap(f.index, next) },
            this.area,
            function () { f.away = (next === "away"); p.paintToggles(); })
            .catch(function () {});
    };

    Panel.prototype.toggleReid = function () {
        var f = this.frame, p = this;
        if (!f) return;
        this.commit("/curate/reid",
            { id: f.postId, index: f.index, current: f.species || "" },
            this.reid,
            function (j) { f.reidQueued = !!j.queued; p.paintToggles(); })
            .catch(function () {});
    };

    Panel.prototype.toggleHidden = function () {
        var f = this.frame, p = this;
        if (!f) return;
        this.commit("/curate/exclude-image", { id: f.postId, index: f.index },
            this.hide,
            function (j) { f.hidden = !!j.excluded; p.paintToggles(); })
            .catch(function () {});
    };

    w.BirdCurate = {
        mount: function (root, opts) { return root ? new Panel(root, opts) : null; }
    };
})(window, document);

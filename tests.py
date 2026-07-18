import random
import unittest
from unittest import mock

import birds
import blog
import index


class GenericTestBase(unittest.TestCase):
    def setUp(self):
        self.app = index.app
        self.test_client = self.app.test_client()


class RoutesTestCase(GenericTestBase):
    def test_index_route(self):
        response = self.test_client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_index_renders_an_effect_background(self):
        response = self.test_client.get("/")
        self.assertIn(b"bg-effect", response.data)

    def test_effects_retired_from_home(self):
        # The legacy background effects live only on /archive now.
        self.assertEqual(self.test_client.get("/effects/collision").status_code, 404)
        home = self.test_client.get("/").data
        self.assertNotIn(b"collision.js", home)
        self.assertNotIn(b"jquery", home)

    def test_blog_list_route(self):
        # Writing is hidden for now (index.HIDDEN_PAGES).
        self.assertEqual(self.test_client.get("/blog").status_code, 404)

    def test_blog_post_route(self):
        slug = blog.list_posts()[0]["slug"]
        # Writing is hidden for now, so even a real slug 404s.
        self.assertEqual(self.test_client.get("/blog/{}".format(slug)).status_code, 404)

    def test_missing_blog_post_404(self):
        self.assertEqual(self.test_client.get("/blog/nope").status_code, 404)

    def test_photography_route_live(self):
        # The photography gallery is switched on (not in HIDDEN_PAGES).
        self.assertEqual(self.test_client.get("/photography").status_code, 200)

    def test_photography_renders_photos_and_tags(self):
        photos = [{"id": "a", "image": "u", "thumb": "t", "title": "Red Fox",
                   "species": "Red Fox", "location": "Weir Hill", "date": "2026-06-01",
                   "tags": ["wildlife", "mammal"]}]
        with mock.patch.object(birds, "load_photos", return_value=photos):
            r = self.test_client.get("/photography")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Red Fox", r.data)
        self.assertIn(b"tag=wildlife", r.data)  # a tag filter chip

    def test_photography_tag_filter_narrows(self):
        photos = [
            {"id": "a", "image": "u", "thumb": "t", "title": "Fox", "tags": ["wildlife"]},
            {"id": "b", "image": "v", "thumb": "s", "title": "Franconia Ridge", "tags": ["landscape"]},
        ]
        with mock.patch.object(birds, "load_photos", return_value=photos):
            r = self.test_client.get("/photography?tag=landscape")
        self.assertIn(b"Franconia Ridge", r.data)
        self.assertNotIn(b'alt="Fox"', r.data)

    def test_photo_tags_orders_by_frequency(self):
        photos = [{"tags": ["wildlife", "mammal"]}, {"tags": ["wildlife"]}, {"tags": ["macro"]}]
        self.assertEqual(birds.photo_tags(photos), ["wildlife", "macro", "mammal"])

    def test_set_photo_trims_and_dedupes_tags(self):
        photos = [{"id": "x", "title": "", "tags": []}]
        with mock.patch.object(birds, "load_photos", return_value=photos), \
             mock.patch.object(birds, "_save_curation") as save:
            p = birds.set_photo("x", {"title": " Red Fox ", "species": "Red Fox",
                                      "tags": ["wildlife", " Wildlife ", "mammal", ""]})
        self.assertEqual((p["title"], p["species"]), ("Red Fox", "Red Fox"))
        self.assertEqual(p["tags"], ["wildlife", "mammal"])
        save.assert_called_once()

    def test_set_photo_unknown_id_is_none(self):
        with mock.patch.object(birds, "load_photos", return_value=[]):
            self.assertIsNone(birds.set_photo("nope", {"title": "x"}))


    def test_projects_route(self):
        response = self.test_client.get("/projects")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"github.com/scottx611x", response.data)

    def test_birds_route(self):
        # Plain /birds redirects to a seeded URL that pins the shuffle.
        response = self.test_client.get("/birds", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("seed=", response.request.url)

    def test_birds_stats_route(self):
        response = self.test_client.get("/birds/stats")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"by the numbers", response.data)

    def test_birds_map_route(self):
        response = self.test_client.get("/birds/map")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"sightings-map", response.data)

    def test_birds_location_filter(self):
        response = self.test_client.get("/birds?loc=Rea%20St.")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Rea St.", response.data)

    def test_birds_subdomain_serves_gallery_at_root(self):
        response = self.test_client.get(
            "/", headers={"Host": "birds.scott-ouellette.com"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Birds of North Andover", response.data)

    def test_archive_route(self):
        self.assertEqual(self.test_client.get("/archive").status_code, 200)

    def test_archive_effect_routes(self):
        for name in index.ARCHIVE_EFFECTS:
            response = self.test_client.get("/archive/{}".format(name))
            self.assertEqual(response.status_code, 200)

    def test_unknown_archive_effect_404(self):
        self.assertEqual(self.test_client.get("/archive/nope").status_code, 404)


class BlogTestCase(unittest.TestCase):
    def test_posts_sorted_newest_first(self):
        dates = [post["date"] for post in blog.list_posts()]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_get_post_rejects_path_traversal(self):
        self.assertIsNone(blog.get_post("../index"))


class BirdsTestCase(unittest.TestCase):
    def test_load_gallery_returns_list_without_network(self):
        self.assertIsInstance(birds.load_gallery(), list)

    def test_sync_requires_token(self):
        # With no resolvable token anywhere, the sync must refuse loudly.
        with mock.patch.object(birds, "resolve_token", return_value=None):
            with self.assertRaises(RuntimeError):
                birds.instagram_sync(token=None)

    def test_guess_species_trims_location(self):
        self.assertEqual(birds._guess_species("Barred Owl - Rea St.\n\n4-2-26"), "Barred Owl")
        self.assertEqual(birds._guess_species("Barred Owls (and a frog)"), "Barred Owls")

    def test_normalize_species_collapses_variants(self):
        for variant in ["Barred Owls", "Baby Barred Owl", "Barred Owl Baby", "⚠️ Barred Owl"]:
            self.assertEqual(birds.normalize_species(variant), "Barred Owl")
        self.assertEqual(birds.normalize_species("⚠️ Common Loon"), "Common Loon")
        self.assertEqual(birds.normalize_species("Ruby-throated Hummingbird"), "Ruby-throated Hummingbird")

    def test_normalize_handles_es_and_irregular_plurals(self):
        # "-es" plurals mustn't leave a dangling "e"; irregulars have a lookup.
        self.assertEqual(birds.normalize_species("House Finches"), "House Finch")
        self.assertEqual(birds.normalize_species("Thrushes"), "Thrush")
        self.assertEqual(birds.normalize_species("Canadian Geese"), "Canadian Goose")

    def test_canon_species_tolerates_hyphens_plurals_and_typos(self):
        # The caption formats Scott actually types should all land on the right bird.
        cases = {
            "House Finches": "House Finch",            # -es plural
            "Canadian Geese": "Canada Goose",          # colloquial + irregular plural
            "White Throated Sparrow": "White-throated Sparrow",  # missing hyphens
            "Northen Flicker": "Northern Flicker",     # typo
            "Morning Dove": "Mourning Dove",           # typo
        }
        for raw, want in cases.items():
            canon = birds._canon_species(raw)
            self.assertIsNotNone(canon, raw)
            self.assertEqual(canon[0], want, raw)

    def test_block_format_species_with_separate_location_parses(self):
        # Regression: a bare species line + a separate location line (Scott's block
        # format) must yield the species AND its location — a new lifer like Wood
        # Thrush at Weir Hill was dropping to nothing.
        pairs = birds._species_pairs("Wood Thrush\n\nWeir Hill\n\n6-21-26")
        self.assertEqual(pairs, [("Wood Thrush", "Weir Hill", None)])
        self.assertEqual(birds._canon_species("Wood Thrush")[0], "Wood Thrush")

    def test_unknown_bird_is_kept_not_dropped(self):
        # A species not yet in the taxonomy must still parse (block format) and be
        # grouped under "Other birds" so it shows / counts / can be a lifer.
        pairs = birds._species_pairs("Painted Bunting\n\nWeir Hill\n\n6-1-26")
        self.assertEqual(pairs, [("Painted Bunting", "Weir Hill", None)])
        self.assertEqual(birds._canon_species_list("Painted Bunting"),
                         [("Painted Bunting", birds._OTHER_FAMILY)])

    def test_caption_notes_not_treated_as_birds(self):
        for junk in ["Heron Rookery", "Captured by sara", "and parent", "Parents",
                     "Blue Jay eating a Goldfish", "Not a North Andover bird"]:
            self.assertFalse(birds._looks_like_bird(junk), junk)
            self.assertEqual(birds._canon_species_list(junk), [], junk)

    def test_taxonomy_covers_common_new_england_birds(self):
        for sp in ["Wood Thrush", "Baltimore Oriole", "Belted Kingfisher",
                   "American Kestrel", "Scarlet Tanager", "Veery", "Eastern Towhee"]:
            self.assertIsNotNone(birds._canon_species(sp), sp)

    def test_geographic_words_classify_as_locations(self):
        for loc in ["Weir Hill", "Stevens Pond", "Lake Cochichewick",
                    "Harold Parker State Forest", "Glennie Woodlot"]:
            self.assertTrue(birds._is_location_line(loc), loc)

    def test_canon_species_does_not_invent_matches(self):
        # Descriptive captions and near-but-distinct species must NOT fuzzy-collapse.
        for junk in ["Heron Rookery", "Blue Jay eating a Goldfish", "a frog", "Rookery"]:
            self.assertIsNone(birds._canon_species(junk), junk)
        # Similar real species keep their own identity (no false positives).
        self.assertEqual(birds._canon_species("Cooper's Hawk")[0], "Cooper's Hawk")
        self.assertEqual(birds._canon_species("Sharp-shinned Hawk")[0], "Sharp-shinned Hawk")
        self.assertEqual(birds._canon_species("Little Blue Heron")[0], "Little Blue Heron")
        self.assertEqual(birds._canon_species("Great Blue Heron")[0], "Great Blue Heron")

    def test_caption_area_marks_multi_species_line_out_of_area(self):
        # A "A & B" line must not be mistaken for a location line (which would
        # flush the block early as local); the shared ⚠️ tags the whole block.
        caption = ("Osprey\nCooper's Hawk & Boat-tailed Grackle\n\n"
                   "⚠️ Estero, Florida\n1-24-26")
        clean, ooa = birds._caption_area_species(caption)
        self.assertEqual(clean, set())
        self.assertEqual(ooa, {"Osprey", "Cooper's Hawk", "Boat-tailed Grackle"})

    def test_start_ordered_pins_exact_frames_by_original_index(self):
        # Tokens are "<post>.<original image index>"; the named frames lead in
        # order regardless of how images get shuffled within a post.
        shots = [
            {"id": "A", "images": ["a0", "a1"], "image_indices": [0, 1]},
            {"id": "B", "images": ["b0"], "image_indices": [0]},
        ]
        out = birds.start_ordered(shots, ["B.0", "A.1"])
        self.assertEqual([f["images"][0] for f in out[:2]], ["b0", "a1"])
        # Nothing dropped or duplicated: still every frame exactly once.
        self.assertCountEqual([f["images"][0] for f in out], ["a0", "a1", "b0"])

    def test_ticker_species_dedupes(self):
        shots = [{"species": s} for s in ["Barred Owls", "Baby Barred Owl", "Osprey"]]
        self.assertEqual(birds.ticker_species(shots), ["Barred Owl", "Osprey"])

    def test_per_image_override_does_not_bleed_onto_other_frames(self):
        # Editing one frame of a single-species multi-image post must relabel ONLY
        # that frame — the others keep the caption species, not the edited value.
        shot = {"id": "P", "images": ["0", "1", "2", "3"],
                "caption": "Cooper's Hawk - Rea St.\n\n1-2-26",
                "species": "Cooper's Hawk", "species_list": ["Cooper's Hawk"]}
        overrides = {"P": {"images": {"2": "Sharp-shinned Hawk"}}}
        birds.apply_overrides([shot], overrides, apply_exclusions=False)
        self.assertEqual(
            shot["image_species"],
            ["Cooper's Hawk", "Cooper's Hawk", "Sharp-shinned Hawk", "Cooper's Hawk"],
        )

    def test_per_image_override_pins_caption_1to1_for_unedited_frames(self):
        # A caption that pins one species per frame keeps each un-edited frame on its
        # own species when a single frame is overridden.
        shot = {"id": "Q", "images": ["0", "1"],
                "caption": "Blue Jay - Rea St.\nTufted Titmouse - Rea St.\n\n3-4-26",
                "species": "Blue Jay", "species_list": ["Blue Jay", "Tufted Titmouse"]}
        overrides = {"Q": {"images": {"0": "Northern Cardinal"}}}
        birds.apply_overrides([shot], overrides, apply_exclusions=False)
        self.assertEqual(shot["image_species"], ["Northern Cardinal", "Tufted Titmouse"])

    def test_map_points_matches_aliases(self):
        places = [{"name": "Rea St.", "lat": 42.67, "lng": -71.1, "area": "local",
                   "match": ["rea st"]}]
        shots = [{"id": "a", "images": ["u1", "u2"], "species": "Barred Owl",
                  "image_locations": ["Rea St.", "Rea Street Extension"]}]
        pts = birds.map_points(shots, places)
        self.assertEqual(len(pts), 1)
        self.assertEqual(pts[0]["count"], 2)  # alias prefix folds the Extension in
        self.assertEqual(pts[0]["top"], ["Barred Owl"])

    def test_map_points_species_filter(self):
        places = [{"name": "Rea St.", "lat": 42.67, "lng": -71.1, "area": "local",
                   "match": ["rea st"]}]
        shots = [{"id": "a", "images": ["u1", "u2"], "species": "Barred Owl",
                  "image_species": ["Barred Owl", "Osprey"],
                  "image_locations": ["Rea St.", "Rea St."]}]
        owl = birds.map_points(shots, places, species_filter="Barred Owl")
        self.assertEqual(owl[0]["count"], 1)   # only the Barred Owl frame
        self.assertEqual(birds.map_points(shots, places, species_filter="Cardinal"), [])

    def test_loc_key_folds_suffix_variants(self):
        for a, b in [("Rea St.", "Rea Street"), ("Rea St", "Rea Street"),
                     ("Sargent Dr", "Sargent Drive"), ("Oak Ln", "Oak Lane"),
                     ("Main Ct.", "Main Court")]:
            self.assertEqual(birds._loc_key(a), birds._loc_key(b), (a, b))

    def test_canonical_location_abbreviates_consistently(self):
        for variant in ("Rea Street", "Rea St", "Rea st.", "Rea St."):
            self.assertEqual(birds.canonical_location(variant), "Rea St.")
        self.assertEqual(birds.canonical_location("Molly Towne Road"), "Molly Towne Rd.")
        self.assertEqual(birds.canonical_location("Abbot Street"), "Abbott St.")  # typo + abbr
        # squares/landmark names stay spelled out; plain names pass through
        self.assertEqual(birds.canonical_location("Post Office Square, Boston"),
                         "Post Office Square, Boston")
        self.assertEqual(birds.canonical_location("Lake Cochichewick"), "Lake Cochichewick")

    def test_gallery_stats_shape(self):
        stats = birds.gallery_stats(birds.load_gallery())
        for key in ("species", "photos", "videos", "families", "top_species", "by_month"):
            self.assertIn(key, stats)
        self.assertEqual(len(stats["by_month"]), 12)

    def test_stats_series_shape(self):
        shots = birds.load_gallery(shuffle=False)
        series = birds.stats_series(shots)
        # The phenology matrix is comprehensive: one row per life-list species.
        self.assertEqual(len(series["pheno"]), birds.species_count(shots))
        for row in series["pheno"]:
            self.assertEqual(len(row["months"]), 12)
            self.assertEqual(sum(row["months"]), row["total"])
            # Hover previews: exactly the months with photos carry an image.
            self.assertEqual([bool(i) for i in row["imgs"]],
                             [bool(n) for n in row["months"]])
        # Every lifer carries a backdrop photo, framing, and photo candidates.
        for entry in series["accum"]:
            self.assertTrue(entry["img"])
            self.assertTrue(entry["fam"])
            self.assertGreaterEqual(entry["pos"], 0.0)
            self.assertLessEqual(entry["pos"], 1.0)
            self.assertGreaterEqual(entry["posx"], 0.0)
            self.assertLessEqual(entry["posx"], 1.0)
            self.assertIsInstance(entry["cands"], list)
            self.assertTrue(entry["cands"])  # at least its own photo
            # cands are distinct shots, so never more than the species' photo count
            self.assertLessEqual(len(entry["cands"]), entry["total"])
        for day, val in series["per_day"].items():
            self.assertGreaterEqual(val["n"], len(val["sp"]) and 1)
            self.assertTrue(val["img"])

    def test_location_area_override(self):
        name = next(p["name"] for p in birds.load_locations() if p["area"] == "local")
        prior = birds.load_location_overrides().get(name)
        try:
            birds.set_location_override(name, "away")
            self.assertEqual(next(p["area"] for p in birds.load_locations()
                                  if p["name"] == name), "away")
            birds.set_location_override(name, None)  # clear
            self.assertNotIn(name, birds.load_location_overrides())
        finally:
            if prior:
                birds.set_location_override(name, prior.get("area"))

    def test_lifer_curation_roundtrip(self):
        shots = birds.load_gallery(shuffle=False)
        species = birds.stats_series(shots)["accum"][-1]["s"]
        prior = birds.load_lifers().get(species)  # never clobber real curation
        try:
            birds.set_lifer(species, src="https://example.com/x.jpg", pos=0.3, posx=0.7, zoom=1.7)
            entry = next(a for a in birds.stats_series(shots)["accum"] if a["s"] == species)
            self.assertEqual(entry["img"], "https://example.com/x.jpg")
            self.assertEqual(entry["pos"], 0.3)
            self.assertEqual(entry["posx"], 0.7)
            self.assertEqual(entry["zoom"], 1.7)
            # pos and zoom clamp; passing no fields clears the override.
            birds.set_lifer(species, pos=5, zoom=9)
            self.assertEqual(birds.load_lifers()[species]["pos"], 1.0)
            self.assertEqual(birds.load_lifers()[species]["zoom"], 3.0)
            birds.set_lifer(species)
            self.assertNotIn(species, birds.load_lifers())
        finally:
            if prior is not None:
                birds.set_lifer(species, src=prior.get("src"), pos=prior.get("pos"),
                                posx=prior.get("posx"), zoom=prior.get("zoom"))

    def test_sort_posted_leads_with_newest_instagram_posts(self):
        shots = birds.load_gallery(shuffle=False)
        frames = birds.sort_frames(birds.all_photos_shuffled(shots), "posted")
        newest_post = max(s.get("timestamp") or "" for s in shots)
        self.assertEqual(frames[0]["_posted"], newest_post)

    def test_images_at_place_interleaves_posts(self):
        shots = birds.load_gallery(shuffle=False)
        place = next(p for p in birds.load_locations()
                     if p["name"] == "Annie L. Sargent School")
        frames = birds.images_at_place(shots, place)
        posts = {f["post_id"] for f in frames}
        if len(posts) > 1:  # interleave deals one frame per post per round
            lead = {f["post_id"] for f in frames[:len(posts)]}
            self.assertEqual(lead, posts)

    def test_seed_pins_filtered_views_too(self):
        import index, re
        client = index.app.test_client()
        def ids(url):
            return re.findall(r'data-id="([^"]+)"',
                              client.get(url).get_data(as_text=True))[:8]
        url = "/birds?loc=Annie%20L.%20Sargent%20School&seed="
        self.assertEqual(ids(url + "42"), ids(url + "42"))
        self.assertNotEqual(ids(url + "42"), ids(url + "43"))

    def test_gallery_seed_pins_the_shuffle(self):
        import index
        client = index.app.test_client()
        r = client.get("/birds")
        self.assertEqual(r.status_code, 302)
        self.assertIn("seed=", r.headers["Location"])
        seeded = r.headers["Location"]
        import re
        first = re.findall(r'data-id="([^"]+)"', client.get(seeded).get_data(as_text=True))[:8]
        again = re.findall(r'data-id="([^"]+)"', client.get(seeded).get_data(as_text=True))[:8]
        self.assertEqual(first, again)  # same seed -> same arrangement

    def test_images_filtered_by_month_matches_pheno(self):
        shots = birds.load_gallery(shuffle=False)
        series = birds.stats_series(shots)
        row = max(series["pheno"], key=lambda r: r["total"])
        month = max(range(12), key=lambda m: row["months"][m]) + 1
        frames = birds.images_filtered(shots, bird=row["name"], month=month)
        self.assertEqual(len(frames), row["months"][month - 1])
        self.assertEqual(birds.images_filtered(shots, bird=row["name"], month=None
                                               ).__len__(), row["total"])

    def test_multi_species_filter_is_the_union(self):
        # The gallery filter can hold several species at once (?bird=A,B): the
        # result is the union of each species' frames, none double-counted.
        shots = birds.load_gallery(shuffle=False)
        groups = birds.species_groups(shots)
        names = [n for _, sp in groups for n, _ in sp]
        a, b = names[0], names[1]
        fa = {id(f) for f in birds.images_filtered(shots, bird=a)}
        fb = {id(f) for f in birds.images_filtered(shots, bird=b)}
        both = birds.images_filtered(shots, bird="%s,%s" % (a, b))
        self.assertGreaterEqual(len(both), max(len(fa), len(fb)))
        self.assertLessEqual(len(both), len(fa) + len(fb))
        # Every frame carries at least one of the two selected species.
        for f in both:
            got = {c[0] for s in (f.get("image_species") or [])
                   for c in birds._canon_species_list(s)}
            self.assertTrue({a, b} & got, got)

    def test_resolve_species_list_dedupes_and_snaps(self):
        shots = birds.load_gallery(shuffle=False)
        groups = birds.species_groups(shots)
        got = birds.resolve_species_list("Barred Owl, Barred Owl, Blue Jay", groups)
        self.assertEqual(got, ["Barred Owl", "Blue Jay"])
        self.assertEqual(birds.resolve_species_list("", groups), [])

    def test_images_posted_on_matches_post_timestamps(self):
        shots = birds.load_gallery(shuffle=False)
        day = max(s.get("timestamp") or "" for s in shots)[:10]
        frames = birds.images_posted_on(shots, day)
        expected = sum(len(s.get("images") or []) for s in shots
                       if (s.get("timestamp") or "")[:10] == day)
        self.assertEqual(len(frames), expected)
        self.assertGreater(len(frames), 0)

    def test_location_places_resolves_known_spot(self):
        places = birds.location_places(birds.load_gallery(shuffle=False))
        self.assertIn("Rea St.", places)

    def test_images_on_date_matches_per_day_counts(self):
        shots = birds.load_gallery(shuffle=False)
        series = birds.stats_series(shots)
        day = max(series["per_day"], key=lambda k: series["per_day"][k]["n"])
        frames = birds.images_on_date(shots, day)
        self.assertEqual(len(frames), series["per_day"][day]["n"])
        self.assertEqual(birds.images_on_date(shots, "1999-01-01"), [])

    def test_capture_date_from_caption(self):
        self.assertEqual(birds._capture_date("Barred Owl\n\nRea St.\n\n3-27-26", None), "Mar 27, 2026")

    def test_capture_date_falls_back_to_timestamp(self):
        self.assertEqual(
            birds._capture_date("no date here", "2026-04-02T01:50:41+0000"), "Apr 2, 2026"
        )

    def test_assign_weights_ranks_by_likes(self):
        shots = [{"_like": 10}, {"_like": 1}, {"_like": 5}]
        birds._assign_weights(shots)
        self.assertGreater(shots[0]["weight"], shots[2]["weight"])
        self.assertGreater(shots[2]["weight"], shots[1]["weight"])
        self.assertNotIn("_like", shots[0])

    def test_order_gallery_returns_permutation_and_spreads(self):
        species = ["A"] * 5 + ["B"] * 5 + ["C"] * 3
        shots = [{"species": s, "weight": 0.5} for s in species]
        random.seed(0)
        out = birds.order_gallery(shots)
        # Same multiset back (nothing dropped or duplicated).
        self.assertCountEqual([s["species"] for s in out], species)
        # De-clumping keeps adjacent same-species rare (best-effort, not zero).
        dupes = sum(out[i]["species"] == out[i + 1]["species"] for i in range(len(out) - 1))
        self.assertLessEqual(dupes, 1)

    def test_frame_captions_map_each_carousel_image(self):
        caption = "Barred Owl - Rea St.\nNorthern Flicker - Weir Hill\n\n3-15-26"
        caps = birds._frame_captions(caption, 2, "Mar 15, 2026")
        self.assertEqual(caps, [
            "Barred Owl · Rea St. · Mar 15, 2026",
            "Northern Flicker · Weir Hill · Mar 15, 2026",
        ])

    def test_frame_captions_fallback_when_counts_differ(self):
        caption = "Barred Owl\n\nRea St.\n\n4-2-26"
        caps = birds._frame_captions(caption, 3, "Apr 2, 2026")
        self.assertEqual(caps, ["Barred Owl · Rea St. · Apr 2, 2026"] * 3)

    def test_frame_captions_multi_species_more_images(self):
        # 2 species same place, 4 images: can't pin each, show the full list.
        caption = "Barred Owl - Rea St.\nGray Catbird - Rea St.\n\n5-31-26"
        caps = birds._frame_captions(caption, 4, "May 31, 2026")
        self.assertEqual(caps, ["Barred Owl, Gray Catbird · Rea St. · May 31, 2026"] * 4)

    def test_frame_captions_per_line_dates(self):
        # Old format: embedded per-line date; each frame keeps its own date.
        caption = "Hooded Merganser - Lake Cochichewick 11-13-25\nAmerican Robin - Rea Street 11-12-25"
        caps = birds._frame_captions(caption, 2, "Nov 13, 2025")
        self.assertEqual(caps, [
            "Hooded Merganser · Lake Cochichewick · Nov 13, 2025",
            "American Robin · Rea Street · Nov 12, 2025",
        ])


class RealCaptionFormatTestCase(unittest.TestCase):
    """Parsing checks drawn from Scott's actual @birdsofnorthandover formats."""

    CASES = [
        # caption, expected species, expected locations
        ("Red-tailed Hawk\n\nChestnut St.\n\n5-17-26",
         ["Red-tailed Hawk"], ["Chestnut St."]),
        ("⚠️ Great Egret\n\nSummer St. Bridge, Boston\n\n5-28-26",
         ["Great Egret"], ["Summer St. Bridge, Boston"]),
        ("Barred Owls (Baby \"Mojo\" and Parent)\n\nRea St.\n\n5-25-26",
         ["Barred Owls"], ["Rea St."]),
        ("American Herring Gull - Annie L. Sargent School\nEastern Bluebird - Abbott St.\n\n5-25-26",
         ["American Herring Gull", "Eastern Bluebird"],
         ["Annie L. Sargent School", "Abbott St."]),
        ("Hooded Merganser - Lake Cochichewick 11-13-25\nAmerican Robin - Rea Street 11-12-25",
         ["Hooded Merganser", "American Robin"], ["Lake Cochichewick", "Rea Street"]),
        ("Northern Cardinal - 1-23-26\nWhite-breasted Nuthatch - 1-27-26",
         ["Northern Cardinal", "White-breasted Nuthatch"], [None, None]),
        ("Barred Owl\n\nRea St.\n\nMarch-April 2026",
         ["Barred Owl"], ["Rea St."]),
    ]

    def test_species_and_locations(self):
        for caption, species, locations in self.CASES:
            pairs = birds._species_pairs(caption)
            self.assertEqual([sp for sp, _, _ in pairs], species, msg=caption)
            self.assertEqual([loc for _, loc, _ in pairs], locations, msg=caption)

    def test_ticker_uses_full_species_list(self):
        shots = [{"species": "Barred Owl", "species_list": ["Barred Owl", "Gray Catbird", "Osprey"]}]
        self.assertEqual(birds.ticker_species(shots), ["Barred Owl", "Gray Catbird", "Osprey"])

    def test_post_images_uses_video_thumbnail(self):
        video = {"media_type": "VIDEO", "media_url": "v.mp4", "thumbnail_url": "thumb.jpg"}
        self.assertEqual(birds._post_images(video), ["thumb.jpg"])

    def test_post_images_returns_all_carousel_stills(self):
        album = {
            "media_type": "CAROUSEL_ALBUM",
            "children": {"data": [
                {"media_type": "VIDEO", "media_url": "c.mp4", "thumbnail_url": "ct.jpg"},
                {"media_type": "IMAGE", "media_url": "photo.jpg"},
            ]},
        }
        self.assertEqual(birds._post_images(album), ["ct.jpg", "photo.jpg"])

    def test_exclusion_roundtrip(self):
        import os
        import tempfile
        orig_excl, orig_manifest = birds.EXCLUDED_FILE, birds.LOCAL_MANIFEST
        with tempfile.TemporaryDirectory() as d:
            birds.EXCLUDED_FILE = os.path.join(d, "excluded.json")
            birds.LOCAL_MANIFEST = os.path.join(d, "manifest.json")
            try:
                self.assertEqual(birds.load_excluded(), set())
                birds.add_exclusion("abc123")
                self.assertIn("abc123", birds.load_excluded())
                birds.remove_exclusion("abc123")
                self.assertNotIn("abc123", birds.load_excluded())
            finally:
                birds.EXCLUDED_FILE, birds.LOCAL_MANIFEST = orig_excl, orig_manifest


if __name__ == "__main__":
    unittest.main()

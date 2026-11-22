import random
import unittest
from unittest import mock

import birds
import blog
import index
import live_labels as LL


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

    def test_birds_live_route(self):
        response = self.test_client.get("/birds/live")
        self.assertEqual(response.status_code, 200)
        # Light mode: it shares the gallery-header idiom, not a dark band.
        self.assertIn(b"gallery-header", response.data)

    def test_birds_live_json_route(self):
        response = self.test_client.get("/birds/live.json")
        self.assertEqual(response.status_code, 200)
        view = response.get_json()
        for key in ("recent", "species", "counts", "daily", "hours", "generated"):
            self.assertIn(key, view)

    def test_birds_live_json_empty_when_no_sound_data(self):
        with mock.patch.object(birds, "load_sounds", return_value=None):
            view = self.test_client.get("/birds/live.json").get_json()
        self.assertEqual(view["recent"], [])
        self.assertIsNone(view["generated"])

    def test_birds_live_log_route(self):
        response = self.test_client.get("/birds/live/log")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Recordings by day", response.data)
        # The day browser is present when there's data.
        self.assertIn(b'id="dl-daytitle"', response.data)

    def test_birds_live_log_empty_when_no_log_data(self):
        with mock.patch.object(birds, "load_sound_log", return_value=None):
            response = self.test_client.get("/birds/live/log")
        self.assertEqual(response.status_code, 200)
        # Empty state, not the day browser.
        self.assertNotIn(b'id="dl-daytitle"', response.data)

    def test_photography_renders_photos_and_tags(self):
        photos = [{"id": "a", "image": "u", "thumb": "t", "title": "Red Fox",
                   "species": "Red Fox", "location": "Weir Hill", "date": "2026-06-01",
                   "tags": ["wildlife", "mammal"]}]
        with mock.patch.object(birds, "load_photos", return_value=photos):
            r = self.test_client.get("/photography")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Red Fox", r.data)
        self.assertIn(b'"wildlife"', r.data)  # a category in the search menu

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
        # The mic's numbers ride along when sound data exists.
        self.assertIn(b'id="ear-block"', response.data)

    def test_birds_stats_without_sound_data(self):
        with mock.patch.object(birds, "load_sounds", return_value=None):
            response = self.test_client.get("/birds/stats")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'id="ear-block"', response.data)

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
        self.assertIn(b"<title>Birds", response.data)

    def test_archive_route(self):
        self.assertEqual(self.test_client.get("/archive").status_code, 200)

    def test_archive_effect_routes(self):
        for name in index.ARCHIVE_EFFECTS:
            response = self.test_client.get("/archive/{}".format(name))
            self.assertEqual(response.status_code, 200)

    def test_unknown_archive_effect_404(self):
        self.assertEqual(self.test_client.get("/archive/nope").status_code, 404)


class CompactFilterTestCase(unittest.TestCase):
    def test_compact(self):
        f = index.app.jinja_env.filters["compact"]
        self.assertEqual(f(2064), "2,064")
        self.assertEqual(f(9999), "9,999")
        self.assertEqual(f(32907), "32k")
        self.assertEqual(f(None), "0")


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

    def test_per_image_location_override_does_not_bleed_onto_other_frames(self):
        # The location twin of the species test above. A per-image location
        # override used to overwrite the POST's location with the edited value,
        # and every frame without a location of its own falls back to exactly
        # that — so relabelling one frame relabelled the whole carousel.
        shot = {"id": "R", "images": ["0", "1", "2", "3"],
                "caption": "Barred Owl - Rea St.\n\n1-2-26",
                "species": "Barred Owl", "species_list": ["Barred Owl"],
                "location": "Rea St."}
        overrides = {"R": {"image_locations": {"2": "Plum Island"}}}
        birds.apply_overrides([shot], overrides, apply_exclusions=False)
        self.assertEqual(shot["image_locations"][2], "Plum Island")
        # The post keeps its own location, so the un-edited frames keep theirs.
        self.assertEqual(shot["location"], "Rea St.")
        frames = [birds._pseudo_frame(shot, i)[0] for i in range(4)]
        self.assertEqual([f["location"] for f in frames],
                         ["Rea St.", "Rea St.", "Plum Island", "Rea St."])

    def test_per_image_override_pins_caption_1to1_for_unedited_frames(self):
        # A caption that pins one species per frame keeps each un-edited frame on its
        # own species when a single frame is overridden.
        shot = {"id": "Q", "images": ["0", "1"],
                "caption": "Blue Jay - Rea St.\nTufted Titmouse - Rea St.\n\n3-4-26",
                "species": "Blue Jay", "species_list": ["Blue Jay", "Tufted Titmouse"]}
        overrides = {"Q": {"images": {"0": "Northern Cardinal"}}}
        birds.apply_overrides([shot], overrides, apply_exclusions=False)
        self.assertEqual(shot["image_species"], ["Northern Cardinal", "Tufted Titmouse"])

    def test_multispecies_carousel_distributes_not_collapses(self):
        # A 9-photo post captioned with 3 species must spread those species across
        # the frames in caption order — NOT label every frame the first species
        # (the bug that made a crow and a hawk both read as Chimney Swifts).
        cap = ("Chimney Swift - Rea St.\nAmerican Crow - Johnson St.\n"
               "Red-tailed Hawk - Rea St.\n\n6-21-26")
        self.assertEqual(
            birds._caption_image_species(cap, 9),
            ["Chimney Swift"] * 3 + ["American Crow"] * 3 + ["Red-tailed Hawk"] * 3,
        )
        # Uneven split: earlier (headliner) species take the remainder.
        self.assertEqual(
            birds._caption_image_species(cap, 7),
            ["Chimney Swift"] * 3 + ["American Crow"] * 2 + ["Red-tailed Hawk"] * 2,
        )
        # And it holds through the load path for a post with no override / no
        # baked per-frame species — the crow and hawk frames must not be swifts.
        shot = {"id": "C", "images": list("012345678"), "caption": cap,
                "species": "Chimney Swift"}
        birds.apply_overrides([shot], overrides={}, apply_exclusions=False)
        self.assertEqual(shot["image_species"][4], "American Crow")
        self.assertEqual(shot["image_species"][7], "Red-tailed Hawk")
        self.assertNotIn("Chimney Swift", shot["image_species"][3:])

    def test_single_species_carousel_covers_every_frame(self):
        # One species, many photos: every frame is that species (no regression).
        self.assertEqual(
            birds._caption_image_species("Barred Owl - Rea St.\n\n5-1-26", 4),
            ["Barred Owl"] * 4,
        )

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
        """A ?seed pins the arrangement of a FILTERED view, and a different
        seed changes it.

        Reads the field's own order (the #bf-seq payload) rather than the
        masonry's data-id attributes: the field is the gallery's default view
        now, and it renders its sequence as JSON rather than as server-side
        figure markup — so the old assertion was matching a JS template
        literal against itself and could never fail.
        """
        import index, re, json
        client = index.app.test_client()
        def order(url):
            html = client.get(url).get_data(as_text=True)
            m = re.search(r'id="bf-seq"[^>]*>(.*?)</script>', html, re.S)
            return json.loads(m.group(1))[:8] if m else None
        url = "/birds?loc=Annie%20L.%20Sargent%20School&seed="
        self.assertIsNotNone(order(url + "42"), "field sequence should render")
        self.assertEqual(order(url + "42"), order(url + "42"))
        self.assertNotEqual(order(url + "42"), order(url + "43"))

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


class NewPostStarTestCase(unittest.TestCase):
    """A new post's cover is starred on arrival; nothing else is touched."""

    def _post(self, pid, n=6, species=("Osprey",)):
        return {"id": pid, "images": ["x"] * n,
                "image_species": [species[i % len(species)] for i in range(n)]}

    def test_only_new_posts_get_a_cover_star(self):
        shots = [self._post("new"), self._post("old"), self._post("thin", n=3)]
        saved = {}
        with mock.patch.object(birds, "load_starred", return_value=set()), \
             mock.patch.object(birds, "_save_curation",
                               lambda path, data: saved.update(data=data)):
            n = birds.seed_starred_from_covers(shots, only_ids={"new", "thin"})
        # "old" was not new. "thin" is: its cover was picked from the whole
        # shoot, so a small post still gets its star.
        self.assertEqual(n, 2)
        self.assertEqual(saved["data"], ["new-0", "thin-0"])


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


class PerFrameDatesTestCase(unittest.TestCase):
    """Per-frame capture dates from the pipeline's post records (combined-batch
    posts whose frames span shooting days)."""

    def _run_match(self, rec):
        saved = {}
        shot = {"id": "p1", "images": ["u0", "u1", "u2"],
                "caption": rec["caption"], "timestamp": "2026-07-25T12:00:00+0000"}
        with mock.patch.object(birds, "_load_post_records", return_value=[rec]), \
             mock.patch.object(birds, "load_image_species", return_value={}), \
             mock.patch.object(birds, "load_image_dates", return_value={}), \
             mock.patch.object(birds, "_save_curation",
                               side_effect=lambda path, data: saved.__setitem__(path, dict(data))):
            birds.match_post_records([shot])
        return saved

    def test_record_dates_land_iso_normalized_and_aligned(self):
        rec = {"caption": "Barred Owl\nCedar Waxwing\n\nRea St.\n\n7-20-26",
               "files": ["a.jpg", "b.jpg", "c.jpg"],
               "species": ["Barred Owl", "Barred Owl", "Cedar Waxwing"],
               "dates": ["7-20-26", "7-20-26", "7-22-26"]}
        saved = self._run_match(rec)
        self.assertEqual(saved[birds.IMAGE_SPECIES_FILE]["p1"],
                         ["Barred Owl", "Barred Owl", "Cedar Waxwing"])
        self.assertEqual(saved[birds.IMAGE_DATES_FILE]["p1"],
                         ["2026-07-20", "2026-07-20", "2026-07-22"])

    def test_record_without_dates_matches_species_only(self):
        rec = {"caption": "Barred Owl\nCedar Waxwing\n\nRea St.\n\n7-20-26",
               "files": ["a.jpg", "b.jpg", "c.jpg"],
               "species": ["Barred Owl", "Barred Owl", "Cedar Waxwing"]}
        saved = self._run_match(rec)
        self.assertIn(birds.IMAGE_SPECIES_FILE, saved)
        self.assertNotIn(birds.IMAGE_DATES_FILE, saved)

    def test_pseudo_frame_prefers_frame_date_falls_back_to_shot(self):
        shot = {"id": "p", "images": ["u0", "u1"],
                "caption": "Barred Owl\n\nRea St.\n\n7-20-26",
                "timestamp": "2026-07-25T12:00:00+0000",
                "species": "Barred Owl", "image_species": ["Barred Owl", "Barred Owl"],
                "image_dates": [None, "2026-07-22"], "date": "Jul 20, 2026"}
        f0, _ = birds._pseudo_frame(shot, 0)
        f1, _ = birds._pseudo_frame(shot, 1)
        self.assertEqual(f0["_sort"], "2026-07-20")   # no store date -> caption day
        self.assertEqual(f0["date"], "Jul 20, 2026")
        self.assertEqual(f1["_sort"], "2026-07-22")   # store date wins for its frame
        self.assertEqual(f1["date"], "Jul 22, 2026")

    def test_manual_capture_date_override_beats_the_store(self):
        shot = {"id": "p", "images": ["u0", "u1"], "capture_date": "2026-07-01",
                "caption": "Barred Owl\n\n7-20-26", "timestamp": "2026-07-25T12:00:00+0000",
                "image_dates": ["2026-07-20", "2026-07-22"]}
        self.assertEqual([d.isoformat() for d in birds._frame_dates(shot)],
                         ["2026-07-01", "2026-07-01"])

    def test_mixed_date_caption_keeps_first_match_for_the_shot(self):
        self.assertEqual(birds._capture_date("Barred Owl\n\n7-20-26 & 7-22-26", None),
                         "Jul 20, 2026")


class LinkPostOriginalsTestCase(unittest.TestCase):
    """Full-size links survive an edited caption, and frames are paired by
    what they look like, never by list position."""

    def _shot(self, pid, caption, n, ts):
        return {"id": pid, "caption": caption, "timestamp": ts,
                "images": ["https://x/birds/images/%s-%d.jpg" % (pid, k) for k in range(n)]}

    def _rec(self, caption, files, sched, species=None):
        return {"caption": caption, "files": files, "scheduled_at": sched,
                "species": species or [caption.split("\n")[0]] * len(files)}

    def test_edited_caption_still_pairs(self):
        shot = self._shot("p1", "Barred Owl (expelling a pellet)\n\nRea St.\n\n9-20-26",
                          2, "2026-11-11T12:35:00+0000")
        rec = self._rec("Barred Owl\n\nRea St.\n\n9-20-26", ["a.jpg", "b.jpg"],
                        "2026-11-17T20:41:00.000Z")
        self.assertEqual(birds._pair_posts_with_records([shot], [rec]), [(0, 0)])

    def test_different_shooting_day_does_not_pair(self):
        shot = self._shot("p1", "Barred Owl\n\nRea St.\n\n9-21-26", 2, "2026-11-11T12:35:00+0000")
        rec = self._rec("Barred Owl\n\nRea St.\n\n9-20-26", ["a.jpg", "b.jpg"],
                        "2026-11-11T12:35:00.000Z")
        self.assertEqual(birds._pair_posts_with_records([shot], [rec]), [])

    def test_each_record_goes_to_one_post_nearest_slot_wins(self):
        cap = "Red-tailed Hawk\n\nRea St.\n\n9-13-26"
        early = self._shot("p1", cap + " ", 3, "2026-11-08T20:41:00+0000")
        late = self._shot("p2", "Red-tailed Hawk!\n\nRea St.\n\n9-13-26", 3,
                          "2026-11-20T20:41:00+0000")
        rec = self._rec(cap, ["a", "b", "c"], "2026-11-08T20:41:00.000Z")
        self.assertEqual(birds._pair_posts_with_records([late, early], [rec]), [(1, 0)])

    def test_frames_paired_by_content_not_position(self):
        from PIL import Image, ImageDraw

        def pic(x):
            im = Image.new("L", (400, 500), 30)
            ImageDraw.Draw(im).ellipse((x, 100, x + 120, 300), fill=230)
            return im
        shot = self._shot("p1", "c", 2, "t")
        # The archive lists them in the opposite order to the carousel.
        imgs = {shot["images"][0]: pic(40), shot["images"][1]: pic(240),
                "https://s3/originals/by-file/A.jpg": pic(240),
                "https://s3/originals/by-file/B.jpg": pic(40)}
        s3 = mock.Mock()
        s3.generate_presigned_url.side_effect = (
            lambda _op, Params, ExpiresIn: "https://s3/originals/by-file/" + Params["Key"].rsplit("/", 1)[-1])
        with mock.patch("boto3.client", return_value=s3):
            got = birds._assign_frames(shot, ["A.jpg", "B.jpg"], [0, 1],
                                       fetch=lambda u: imgs[u].copy())
        self.assertEqual(got, {0: "B.jpg", 1: "A.jpg"})

    def test_no_confident_match_is_left_alone(self):
        from PIL import Image

        shot = self._shot("p1", "c", 1, "t")
        imgs = {shot["images"][0]: Image.new("L", (400, 500), 30),
                "https://s3/originals/by-file/A.jpg": Image.new("L", (400, 500), 200)}
        s3 = mock.Mock()
        s3.generate_presigned_url.side_effect = (
            lambda _op, Params, ExpiresIn: "https://s3/originals/by-file/" + Params["Key"].rsplit("/", 1)[-1])
        with mock.patch("boto3.client", return_value=s3):
            got = birds._assign_frames(shot, ["A.jpg"], [0], fetch=lambda u: imgs[u].copy())
        self.assertEqual(got, {})


class OriginalCropTestCase(unittest.TestCase):
    """The loupe's crop box: used only when confidently found."""

    def _with(self, crops):
        body = mock.Mock(); body.read.return_value = __import__("json").dumps(crops).encode()
        s3 = mock.Mock(); s3.get_object.return_value = {"Body": body}
        birds._CROPS = None
        return mock.patch("boto3.client", return_value=s3), \
            mock.patch.dict("os.environ", {"BIRDS_USE_S3": "1"})

    def tearDown(self):
        birds._CROPS = None

    def test_box_by_original_filename(self):
        url = "https://x/%s/images/p1-0.jpg" % birds.S3_PREFIX
        a, b = self._with({"p1-0.jpg": {"box": [0.1, 0, 0.8, 1], "score": 0.99, "same": False},
                           "p1-1.jpg": {"box": [0, 0, 1, 1], "score": 0.6, "same": False},
                           "p1-2.jpg": {"box": None, "score": 1.0, "same": True}})
        with a, b:
            self.assertEqual(birds.original_crop(url), [0.1, 0, 0.8, 1])
            self.assertIsNone(birds.original_crop(url.replace("p1-0", "p1-1")))  # weak
            self.assertIsNone(birds.original_crop(url.replace("p1-0", "p1-2")))  # same framing
            self.assertIsNone(birds.original_crop(url.replace("p1-0", "p9-9")))  # unknown


class SpeciesFromLogTestCase(unittest.TestCase):
    """A bird only the second mic heard still gets a species entry."""

    def test_rollup_shape_newest_clip_and_canon(self):
        rows = [
            {"common": "Goldeneye", "t": "2026-11-15T03:41:35-05:00", "conf": 0.85, "audio": "b.m4a", "spec": "b.png", "node": "Side Yard"},
            {"common": "Common Goldeneye", "t": "2026-11-14T19:00:00-05:00", "conf": 0.9, "audio": "a.m4a", "spec": "a.png"},
            {"common": "Gadwall", "t": "2026-11-15T04:15:28-05:00", "conf": 0.67},
            {"t": "2026-11-15T04:00:00-05:00"},
        ]
        canon = lambda n: "Common Goldeneye" if "Goldeneye" in n else n
        out = index._species_from_log(rows, canon)
        self.assertEqual(set(out), {"Common Goldeneye", "Gadwall"})
        g = out["Common Goldeneye"]
        self.assertEqual(g["count"], 2)
        self.assertEqual(g["first"], "2026-11-14T19:00:00-05:00")
        self.assertEqual(g["last"], "2026-11-15T03:41:35-05:00")
        self.assertEqual((g["audio"], g["spec"]), ("b.m4a", "b.png"))
        self.assertEqual(g["maxConf"], 0.9)
        self.assertNotIn("audio", out["Gadwall"])


class YardRhythmTestCase(unittest.TestCase):
    """The live page's small true sentences come from _yard_rhythm."""

    def rows(self, *specs):
        return [{"t": t, "common": c} for t, c in specs]

    def test_streak_and_previous_day(self):
        out = index._yard_rhythm(self.rows(
            ("2026-11-13T07:00:00-05:00", "Carolina Wren"),
            ("2026-11-12T07:00:00-05:00", "Carolina Wren"),
            ("2026-11-11T07:00:00-05:00", "Carolina Wren"),
            ("2026-11-09T07:00:00-05:00", "Carolina Wren"),     # gap breaks the run
            ("2026-11-13T08:00:00-05:00", "Dark-eyed Junco"),
            ("2026-04-02T08:00:00-04:00", "Dark-eyed Junco"),
            ("2026-11-12T09:00:00-05:00", "Blue Jay"),           # not heard today
        ), "2026-11-13")
        self.assertEqual(out["facts"]["Carolina Wren"], {"streak": 3, "prev": "2026-11-12"})
        self.assertEqual(out["facts"]["Dark-eyed Junco"], {"streak": 1, "prev": "2026-04-02"})
        self.assertNotIn("Blue Jay", out["facts"])

    def test_first_song_is_the_median_first_burst(self):
        def burst(day, hm):
            h, m = map(int, hm.split(":"))
            return [("%sT%02d:%02d:00-05:00" % (day, h, m + k), "A") for k in (0, 4, 9)]
        out = index._yard_rhythm(self.rows(
            *burst("2026-11-13", "04:00"),                      # today: not part of "usual"
            ("2026-11-12T02:10:00-05:00", "Tundra Swan"),       # a lone night call
            *burst("2026-11-12", "06:40"),
            *burst("2026-11-11", "06:20"),
            ("2026-11-10T05:40:00-05:00", "A"), ("2026-11-10T06:05:00-05:00", "A"),  # too spread out
            *burst("2026-11-10", "06:30"),
        ), "2026-11-13")
        self.assertEqual(out["firstSong"], "06:30")

    def test_per_hour_is_an_average_over_days_with_recordings(self):
        out = index._yard_rhythm(self.rows(
            ("2026-11-12T07:05:00-05:00", "A"), ("2026-11-12T07:10:00-05:00", "A"),
            ("2026-11-11T07:15:00-05:00", "A"), ("2026-11-11T07:20:00-05:00", "A"),
            ("2026-11-11T07:25:00-05:00", "A"), ("2026-11-11T08:00:00-05:00", "A"),
        ), "2026-11-13")
        self.assertEqual(out["perHour"][7], 2.5)
        self.assertEqual(out["perHour"][8], 0.5)
        self.assertEqual(len(out["perHour"]), 24)

    def test_canon_folds_names(self):
        out = index._yard_rhythm(self.rows(("2026-11-13T07:00:00-05:00", "carolina wren")),
                                 "2026-11-13", canon=lambda n: n.title())
        self.assertIn("Carolina Wren", out["facts"])


class ClipInstantTestCase(unittest.TestCase):
    """One station names clips in local time with a Z; the upload time says
    which reading is real, so dawn birds stop appearing at 1 AM."""

    def _up(self, iso):
        import datetime
        return datetime.datetime.fromisoformat(iso)

    def test_local_named_clip_read_as_local(self):
        import sound_index
        t = sound_index._instant("20261112T063941Z", self._up("2026-11-12T11:39:45+00:00"))
        self.assertEqual(t.isoformat(), "2026-11-12T06:39:41-05:00")

    def test_utc_named_clip_read_as_utc(self):
        import sound_index
        t = sound_index._instant("20261112T113939Z", self._up("2026-11-12T11:39:50+00:00"))
        self.assertEqual(t.isoformat(), "2026-11-12T06:39:39-05:00")

    def test_daylight_time_offset(self):
        import sound_index
        t = sound_index._instant("20260815T063000Z", self._up("2026-08-15T10:30:20+00:00"))
        self.assertEqual(t.isoformat(), "2026-08-15T06:30:00-04:00")

    def test_no_upload_time_falls_back_to_utc(self):
        import sound_index
        self.assertEqual(sound_index._instant("20261112T113939Z").isoformat(),
                         "2026-11-12T06:39:39-05:00")

    def test_late_reupload_falls_back_to_utc(self):
        import sound_index
        t = sound_index._instant("20261112T113939Z", self._up("2026-11-20T00:00:00+00:00"))
        self.assertEqual(t.isoformat(), "2026-11-12T06:39:39-05:00")


class PhotoHideTestCase(unittest.TestCase):
    """Hiding a photo drops it from the public gallery but keeps the entry."""

    def _with_store(self, photos):
        saved = {}
        return (mock.patch.object(birds, "load_photos", return_value=photos),
                mock.patch.object(birds, "_save_curation",
                                  side_effect=lambda path, data: saved.setdefault("d", data)),
                saved)

    def test_hide_then_restore_roundtrip(self):
        photos = [{"id": "abc", "title": "Groundhog", "tags": ["mammal"]}]
        lp, sc, saved = self._with_store(photos)
        with lp, sc:
            p = birds.set_photo("abc", {"hidden": True})
        self.assertTrue(p["hidden"])
        with mock.patch.object(birds, "load_photos", return_value=photos), \
             mock.patch.object(birds, "_save_curation", lambda path, data: None):
            p = birds.set_photo("abc", {"hidden": False})
        self.assertNotIn("hidden", p)

    def test_hidden_photo_leaves_the_public_gallery(self):
        photos = [{"id": "a", "title": "Shown", "tags": ["mammal"], "image": "i", "thumb": "t"},
                  {"id": "b", "title": "Gone", "tags": ["mammal"], "image": "i", "thumb": "t",
                   "hidden": True}]
        with mock.patch.object(birds, "load_photos", return_value=photos):
            body = index.app.test_client().get("/photography").data
        self.assertIn(b"Shown", body)
        self.assertNotIn(b"Gone", body)


class CurateOverridePayloadTestCase(GenericTestBase):
    """Per-image overrides must mean the same thing however they are posted.

    birds.set_override only honours dicts for the per-image maps. The field
    overlay posted a sparse array instead (``var arr = []; arr[idx] = v``),
    which JSON-encodes as a list, so every out-of-area and location edit made
    from the field view — the DEFAULT view of /birds — was discarded while the
    endpoint still answered {"ok": true} and the UI flashed "saved ✓". Nothing
    failed loudly, so nothing caught it.
    """

    def test_sparse_array_normalizes_to_an_index_map(self):
        self.assertEqual(index._as_index_map([None, None, "away"]), {"2": "away"})
        self.assertEqual(index._as_index_map([None, "Rea St.", None]), {"1": "Rea St."})
        # Objects pass through untouched — that shape already worked.
        self.assertEqual(index._as_index_map({"2": "away"}), {"2": "away"})
        # Holes carry no edit, so an all-holes array is an empty map, not a
        # wall of "" that would clear every frame on the post.
        self.assertEqual(index._as_index_map([None, None]), {})
        self.assertEqual(index._as_index_map([]), {})

    def test_route_normalizes_array_payloads_before_saving(self):
        client = index.app.test_client()
        with mock.patch.object(index, "_curate_on", return_value=True), \
             mock.patch.object(birds, "set_override", return_value=None) as saved:
            response = client.post("/curate/override", json={
                "id": "p1",
                "image_areas": [None, None, "away"],
                "image_locations": [None, "Rea St."],
                "images": [None, "Barred Owl"],
            })
        self.assertEqual(response.status_code, 200)
        fields = saved.call_args[0][1]
        self.assertEqual(fields["image_areas"], {"2": "away"})
        self.assertEqual(fields["image_locations"], {"1": "Rea St."})
        self.assertEqual(fields["images"], {"1": "Barred Owl"})

    def test_route_leaves_object_payloads_alone(self):
        client = index.app.test_client()
        with mock.patch.object(index, "_curate_on", return_value=True), \
             mock.patch.object(birds, "set_override", return_value=None) as saved:
            client.post("/curate/override", json={
                "id": "p1", "image_areas": {"2": "away"}, "capture_date": "2026-04-02"})
        fields = saved.call_args[0][1]
        self.assertEqual(fields["image_areas"], {"2": "away"})
        # Scalars are not per-image maps and must not be touched.
        self.assertEqual(fields["capture_date"], "2026-04-02")


class DetailSpeedTestCase(GenericTestBase):
    """The bird detail view: cheap to build, cacheable, originals stay private."""

    def setUp(self):
        super().setUp()
        birds.memo_clear()
        names = birds.species_index()
        self.slug = next(iter(names))

    def tearDown(self):
        birds._CLIENTS.clear()
        birds.memo_clear()

    def test_one_s3_client_for_many_signatures(self):
        s3 = mock.Mock()
        s3.generate_presigned_url.return_value = "https://s3/x?X-Amz-Signature=1"
        url = "https://x/%s/images/p1-0.jpg" % birds.S3_PREFIX
        with mock.patch("boto3.client", return_value=s3) as make, \
             mock.patch.dict("os.environ", {"BIRDS_USE_S3": "1"}):
            for _ in range(50):
                birds.original_url(url)
        self.assertEqual(make.call_count, 1)
        self.assertEqual(s3.generate_presigned_url.call_count, 50)

    def test_reader_json_is_unsigned_and_cacheable(self):
        r = self.test_client.get("/birds/species/%s.json" % self.slug)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(b"X-Amz-Signature", r.data)
        self.assertIn("public", r.headers["Cache-Control"])
        self.assertIn("max-age=300", r.headers["Cache-Control"])
        # served again from the memo, same bytes
        self.assertEqual(self.test_client.get("/birds/species/%s.json" % self.slug).data, r.data)

    def test_curate_json_is_never_cached(self):
        with mock.patch.object(index, "_curate_on", return_value=True):
            r = self.test_client.get("/birds/species/%s.json" % self.slug)
        self.assertEqual(r.status_code, 200)
        self.assertIn("no-store", r.headers["Cache-Control"])
        self.assertNotIn("public", r.headers["Cache-Control"])

    def test_unknown_species_404_and_not_memoised(self):
        r = self.test_client.get("/birds/species/not-a-bird-xyz.json")
        self.assertEqual(r.status_code, 404)
        self.assertNotIn("species_json:not-a-bird-xyz", birds._MEMO)

    def test_original_frames_point_at_the_redirect(self):
        with mock.patch.object(birds, "has_original", return_value=True):
            self.assertEqual(birds.original_path("https://x/%s/images/p1-3.jpg" % birds.S3_PREFIX),
                             "/birds/original/p1-3.jpg")
        with mock.patch.object(birds, "has_original", return_value=False):
            self.assertIsNone(birds.original_path("https://x/%s/images/p1-3.jpg" % birds.S3_PREFIX))

    def test_original_redirect_signs_visible_frames_only(self):
        go = mock.patch.object(birds, "original_url", return_value="https://s3/signed")
        has = mock.patch.object(birds, "has_original", return_value=True)
        hidden = mock.patch.object(birds, "hidden_frame_keys", return_value={"p1-2"})
        excl = mock.patch.object(birds, "load_excluded", return_value={"p9"})
        with go, has, hidden, excl, mock.patch.object(index, "_curate_on", return_value=False):
            ok = self.test_client.get("/birds/original/p1-0.jpg")
            self.assertEqual(ok.status_code, 302)
            self.assertEqual(ok.headers["Location"], "https://s3/signed")
            self.assertIn("private", ok.headers["Cache-Control"])
            self.assertEqual(self.test_client.get("/birds/original/p1-2.jpg").status_code, 404)
            self.assertEqual(self.test_client.get("/birds/original/p9-0.jpg").status_code, 404)
            # nothing outside birds/originals/ can be named
            self.assertEqual(self.test_client.get("/birds/original/..%2Fmanifest.json").status_code, 404)
            self.assertEqual(self.test_client.get("/birds/original/p1-0.png").status_code, 404)
        with go, has, hidden, excl, mock.patch.object(index, "_curate_on", return_value=True):
            self.assertEqual(self.test_client.get("/birds/original/p1-2.jpg").status_code, 302)
        with go, mock.patch.object(birds, "has_original", return_value=False):
            self.assertEqual(self.test_client.get("/birds/original/p1-0.jpg").status_code, 404)

    def test_micro_short_side_and_listing(self):
        from io import BytesIO
        from PIL import Image
        buf = BytesIO(); Image.new("RGB", (640, 427), (90, 120, 60)).save(buf, "JPEG")
        im = Image.open(BytesIO(birds._make_micro(buf.getvalue())))
        self.assertEqual(min(im.size), birds.MICRO_SIDE)
        url = "https://x/%s/images/p1-0.jpg" % birds.S3_PREFIX
        with mock.patch.object(birds, "_MICROS", {"p1-0.jpg"}), \
             mock.patch.object(birds, "_MICROS_AT", 9e18):
            self.assertEqual(birds.micro_url(url), url.replace("/images/", "/thumbs/micro/"))
            self.assertIsNone(birds.micro_url(url.replace("p1-0", "p1-1")))

    def test_focus_point_by_media_id_and_confidence(self):
        table = {"p1-0": [0.2, 0.4, 1.5, 0.8], "p1-1": [0.9, 0.5, 1.5, 0.2], "p1-2": None,
                 "p2-0": [0.5, 0.45, 1.0, 0.9, 0.7, 0.6]}
        with mock.patch.object(birds, "_FOCUS", table), \
             mock.patch.object(birds, "_FOCUS_AT", 9e18):
            # any size of the frame resolves to the same point
            for d in ("thumbs", "images", "thumbs/micro"):
                self.assertEqual(birds.focus_point("https://x/birds/%s/p1-0.jpg" % d), [0.2, 0.4, 1.5])
            self.assertIsNone(birds.focus_point("https://x/birds/thumbs/p1-1.jpg"))  # unsure
            self.assertIsNone(birds.focus_point("https://x/birds/thumbs/p1-2.jpg"))  # no bird
            self.assertIsNone(birds.focus_point("https://x/birds/thumbs/p9-0.jpg"))  # not run
            self.assertIsNone(birds.focus_point(None))
            # newer entries carry the box size, for the stage's zoom-to-fit
            self.assertEqual(birds.focus_point("https://x/birds/thumbs/p2-0.jpg"), [0.5, 0.45, 1.0, 0.7, 0.6])

    def test_new_post_check_syncs_only_for_unseen_posts(self):
        def run(ids, known, excluded=()):
            r = mock.Mock(); r.json.return_value = {"data": [{"id": i} for i in ids]}
            with mock.patch.object(birds, "resolve_token", return_value="t"), \
                 mock.patch.object(birds.requests, "get", return_value=r), \
                 mock.patch.object(birds, "_load_manifest_from_s3",
                                   return_value=[{"id": k} for k in known]), \
                 mock.patch.object(birds, "load_excluded", return_value=set(excluded)), \
                 mock.patch.object(birds, "scheduled_sync") as sync:
                out = birds.new_post_check()
            return out["new"], sync.called
        self.assertEqual(run(["3", "2", "1"], ["2", "1"]), (["3"], True))
        self.assertEqual(run(["2", "1"], ["2", "1"]), ([], False))
        self.assertEqual(run(["3", "2"], ["2"], excluded={"3"}), ([], False))  # hidden post
        self.assertEqual(run(["3"], []), ([], False))   # no manifest: leave it to the daily sync

    def test_photo_subjects_group_and_summarise(self):
        import index
        photos = [
            {"id": "a", "title": "White-tailed Deer", "image": "i/a", "thumb": "t/a", "date": "2026-06-06",
             "tags": ["mammal"], "location": "Rea St"},
            {"id": "b", "title": "White-tailed Deer", "image": "i/b", "thumb": "t/b", "date": "2026-07-01",
             "tags": ["mammal", "deer"], "location": "Nowhere Known"},
            {"id": "c", "title": "", "species": "", "image": "i/c", "date": ""},
        ]
        locs = [{"name": "Rea St.", "lat": 42.6, "lng": -71.1, "area": "local", "match": ["rea st"]}]
        with mock.patch.object(birds, "load_locations", return_value=locs):
            out = index._photo_subjects(photos)
        deer = out["white-tailed-deer"]
        self.assertEqual((deer["kind"], deer["images"], deer["first"], deer["last"]),
                         ("subject", 2, "2026-06-06", "2026-07-01"))
        self.assertEqual(deer["tags"], ["mammal", "deer"])
        self.assertEqual(deer["months"][5:7], [1, 1])
        self.assertEqual([(q["name"], q["mapped"]) for q in deer["places"]],
                         [("Nowhere Known", False), ("Rea St.", True)])
        self.assertEqual([f["pid"] for f in deer["frames"]], ["a", "b"])
        self.assertIn("photo-c", out)                      # untitled: its own subject
        self.assertEqual(index._photo_subject_key(photos[0]), "white-tailed-deer")

    def test_photo_individual_tag_is_one_subject(self):
        import index
        photos = [
            {"id": "a", "title": "Sadie, shaking dry", "image": "i/a", "date": "2026-02-28", "tags": ["mammal", "sadie"]},
            {"id": "b", "title": "Sadie in a sunbeam", "image": "i/b", "date": "2026-06-01", "tags": ["sadie"]},
            {"id": "c", "title": "Eastern Chipmunk", "image": "i/c", "date": "2026-06-06", "tags": ["mammal"]},
        ]
        with mock.patch.object(birds, "load_locations", return_value=[]):
            out = index._photo_subjects(photos)
        self.assertEqual(sorted(out), ["eastern-chipmunk", "sadie"])
        self.assertEqual((out["sadie"]["name"], out["sadie"]["images"]), ("Sadie", 2))
        self.assertEqual([f["cap"] for f in out["sadie"]["frames"]],
                         ["Sadie, shaking dry", "Sadie in a sunbeam"])
        self.assertIsNone(out["eastern-chipmunk"]["frames"][0]["cap"])

    def test_photo_subjects_join_on_title_or_species(self):
        import index
        photos = [
            {"id": "a", "title": "American Beaver", "species": "North American Beaver (Castor canadensis)"},
            {"id": "b", "title": "American Beaver", "species": "American Beaver"},
            {"id": "c", "title": "Beaver dam", "species": "North American Beaver (Castor canadensis)"},
            {"id": "d", "title": "Painted Turtles", "species": "Painted Turtle"},
            {"id": "e", "title": "Painted Turtle"},
            {"id": "f", "title": "Rose"}, {"id": "g", "title": "Rose of Sharon"},
        ]
        idx = index._photo_subject_index(photos)
        self.assertEqual({idx[k] for k in "abc"}, {("american-beaver", "American Beaver")})
        self.assertEqual(idx["d"], idx["e"])
        self.assertEqual(idx["d"][1], "Painted Turtle")            # shorter name wins a tie
        self.assertNotEqual(idx["f"], idx["g"])

    def test_fill_missing_micros_makes_only_the_gaps(self):
        from io import BytesIO
        from PIL import Image
        buf = BytesIO(); Image.new("RGB", (640, 427)).save(buf, "JPEG")
        pre = birds.S3_PREFIX
        listing = {pre + "/thumbs/": ["a-0.jpg", "b-0.jpg", "micro/a-0.jpg"],
                   pre + "/thumbs/micro/": ["a-0.jpg"]}
        s3 = mock.Mock()
        s3.get_paginator.return_value.paginate.side_effect = lambda Bucket, Prefix: [
            {"Contents": [{"Key": Prefix + n} for n in listing[Prefix]]}]
        s3.get_object.return_value = {"Body": BytesIO(buf.getvalue())}
        made, missing = birds.fill_missing_micros(s3)
        self.assertEqual((made, missing), (1, 1))
        self.assertEqual(s3.put_object.call_args.kwargs["Key"], pre + "/thumbs/micro/b-0.jpg")

    def test_curate_save_refreshes_the_gallery_memo(self):
        calls = []
        build = lambda: calls.append(1) or len(calls)
        self.assertEqual(birds.memoed_gallery("t", build), 1)
        self.assertEqual(birds.memoed_gallery("t", build), 1)
        birds.memo_clear()
        self.assertEqual(birds.memoed_gallery("t", build), 2)


class LiveLabelsTestCase(unittest.TestCase):
    """The Live stage's stamp (occasions only) and line (one field note)."""

    def rec(self, sp, t, conf=0.9, node="Back Yard", audio=None):
        return {"common": sp, "t": t, "conf": conf, "node": node,
                "audio": audio or "%s_%s.m4a" % (sp, t)}

    def days(self, sp, start, n, hhmm="09:00", step=1):
        d0 = __import__("datetime").date.fromisoformat(start)
        out = []
        for i in range(0, n, step):
            d = d0 + __import__("datetime").timedelta(days=i)
            out.append(self.rec(sp, "%sT%s:00-05:00" % (d.isoformat(), hhmm)))
        return out

    def note(self, rows, t, sp, **kw):
        idx = LL.LabelIndex(rows, photos=kw.pop("photos", None))
        x = idx.find({"t": t, "audio": "%s_%s.m4a" % (sp, t)})
        return LL.note_for(x, idx, **kw), idx, x

    def test_words(self):
        self.assertEqual(LL.num(4), "four")
        self.assertEqual(LL.num(412), "412")
        self.assertEqual(LL.num(1200), "1,200")
        self.assertEqual(LL.ordinal(2), "second")
        self.assertIsNone(LL.ordinal(13))
        self.assertEqual(LL.plural("titmouse"), "titmice")
        self.assertEqual(LL.plural("goose"), "geese")
        self.assertEqual(LL.plural("finch"), "finches")
        self.assertEqual(LL.plural("chickadee"), "chickadees")
        self.assertEqual(LL.a_an("owl"), "an owl")
        self.assertEqual(LL.a_an("nuthatch"), "a nuthatch")
        self.assertEqual(LL.common_word("Black-capped Chickadee"), "chickadee")

    def test_sun_times_north_andover(self):
        import datetime as dt
        rise, sett = LL.sun_times(dt.date(2026, 11, 15))
        est = dt.timezone(dt.timedelta(hours=-5))
        self.assertEqual(rise.astimezone(est).strftime("%H"), "06")
        self.assertLess(abs(rise.astimezone(est).minute - 36), 4)
        self.assertLess(abs((sett.astimezone(est).hour * 60 + sett.astimezone(est).minute) - (16 * 60 + 21)), 4)

    def test_new_to_the_yard(self):
        n, _, _ = self.note([self.rec("Gadwall", "2026-11-15T10:00:00-05:00")],
                            "2026-11-15T10:00:00-05:00", "Gadwall")
        self.assertEqual(n["stamp"], "new to the yard")

    def test_first_since_a_date_not_a_duration(self):
        rows = self.days("Gadwall", "2026-09-01", 5) + [self.rec("Gadwall", "2026-11-15T10:00:00-05:00")]
        n, _, _ = self.note(rows, "2026-11-15T10:00:00-05:00", "Gadwall")
        self.assertEqual(n["stamp"], "first since sep 5")

    def test_second_visit_counts_days_not_recordings(self):
        rows = [self.rec("Tundra Swan", "2026-11-01T05:%02d:00-05:00" % m) for m in range(10)]
        rows.append(self.rec("Tundra Swan", "2026-11-12T10:00:00-05:00"))
        n, _, _ = self.note(rows, "2026-11-12T10:00:00-05:00", "Tundra Swan")
        self.assertEqual(n["stamp"], "second visit")

    def test_owl_at_night_is_not_an_occasion(self):
        owl = self.days("Barred Owl", "2026-10-01", 30, "23:00")
        owl.append(self.rec("Barred Owl", "2026-11-14T23:30:00-05:00"))
        n, _, _ = self.note(owl, "2026-11-14T23:30:00-05:00", "Barred Owl")
        self.assertNotEqual(n["stamp"], "night voice")
        day = self.days("Blue Jay", "2026-10-01", 30, "10:00")
        day.append(self.rec("Blue Jay", "2026-11-14T23:30:00-05:00"))
        n, _, _ = self.note(day, "2026-11-14T23:30:00-05:00", "Blue Jay")
        self.assertEqual(n["stamp"], "night voice")
        self.assertNotIn(n["kind"], ("habit", "offhabit"))   # the stamp said it

    def test_first_voice_skips_a_lone_night_call(self):
        rows = (self.days("Tundra Swan", "2026-11-10", 3) + self.days("Northern Cardinal", "2026-11-10", 3)
                + self.days("Blue Jay", "2026-11-10", 3, "10:00"))
        rows += [self.rec("Tundra Swan", "2026-11-14T02:00:00-05:00"),
                 self.rec("Northern Cardinal", "2026-11-14T06:10:00-05:00"),
                 self.rec("Blue Jay", "2026-11-14T06:20:00-05:00")]
        idx = LL.LabelIndex(rows)
        st = {x.sp: LL.stamp_for(x, idx.facts(x), idx) for x in idx.recs if x.day.day == 14}
        self.assertEqual(st["Northern Cardinal"], ("voice", "first call"))
        self.assertNotEqual(st["Tundra Swan"], ("voice", "first call"))
        self.assertNotEqual(st["Blue Jay"], ("voice", "first call"))

    def test_reel_pick_note_is_todays_not_yesterdays(self):
        # The crow opened yesterday; today the robin did. A reel pick of the
        # crow must not wear yesterday's "first call".
        import index
        from unittest import mock
        rows = (self.days("American Crow", "2026-10-20", 25, "12:00")
                + self.days("American Robin", "2026-10-20", 25, "12:00"))
        rows += [self.rec("American Crow", "2026-11-18T06:19:00-05:00"),
                 self.rec("American Robin", "2026-11-19T06:27:00-05:00"),
                 self.rec("American Crow", "2026-11-19T07:36:00-05:00")]
        idx = LL.LabelIndex(rows)
        view = {"dayrecs": [dict(r, display=r["common"]) for r in rows[-3:]],
                "species": [{"display": "American Crow"}, {"display": "American Robin"}]}
        with mock.patch.object(index, "_label_index", return_value=idx), \
                mock.patch.object(index, "_sound_log_merged", return_value={"generated": "t-reel"}):
            index._attach_notes(view, {})
        self.assertEqual(view["dayrecs"][0]["note"]["stamp"], "first call")   # yesterday's own clip keeps it
        crow = view["species"][0].get("note") or {}
        self.assertNotEqual(crow.get("stamp"), "first call")
        self.assertEqual(view["species"][1]["note"]["stamp"], "first call")

    def test_both_mics_is_a_line_not_a_stamp(self):
        rows = self.days("Blue Jay", "2026-10-01", 40, "15:30") + [
            self.rec("Blue Jay", "2026-11-14T15:00:00-05:00", node="Back Yard"),
            self.rec("Blue Jay", "2026-11-14T15:00:05-05:00", node="Side Yard")]
        n, _, _ = self.note(rows, "2026-11-14T15:00:05-05:00", "Blue Jay", shot=True)
        self.assertEqual(n["stamp"], "")
        self.assertEqual(n["line"], "Both mics caught this one.")

    def test_never_photographed_line(self):
        rows = [self.rec("Gadwall", "2026-11-%02dT10:%02d:00-05:00" % (1 + i // 10, i % 10)) for i in range(40)]
        n, _, _ = self.note(rows, rows[-1]["t"], "Gadwall")
        self.assertEqual(n["line"], "Heard 40 times. Never once photographed.")

    def test_regular_since_the_mic_went_up(self):
        rows = self.days("White-breasted Nuthatch", "2026-07-18", 30)
        import datetime as dt
        n, _, _ = self.note(rows, rows[-1]["t"], "White-breasted Nuthatch",
                            photos={"White-breasted Nuthatch": []}, shot=True)
        self.assertEqual(n["line"], "Here every day since the mic went up.")

    def test_run_of_one_bird_keeps_its_line_and_each_line_once_a_day(self):
        rows = self.days("Blue Jay", "2026-10-01", 45)
        rows += [self.rec("Blue Jay", "2026-11-15T15:00:%02d-05:00" % s) for s in (0, 20, 40)]
        rows += [self.rec("Gadwall", "2026-11-15T15:05:00-05:00"),
                 self.rec("Blue Jay", "2026-11-15T15:10:00-05:00")]
        idx = LL.LabelIndex(rows, photos={"Blue Jay": [__import__("datetime").date(2026, 9, 7)]})
        today = [x for x in idx.recs if x.local.strftime("%Y-%m-%d") == "2026-11-15"]
        notes = LL.notes_for_stage(idx, today, shot_of=lambda sp: sp == "Blue Jay")
        lines = [notes[id(x)]["line"] for x in today]
        self.assertEqual(len(set(lines[:3])), 1)              # one arrival, one line
        self.assertTrue(lines[0])
        self.assertNotEqual(lines[4], lines[0])               # said once a day

    def test_no_banned_phrase_in_the_module(self):
        src = open(LL.__file__).read().lower()
        for bad in ("checking in", "unmistakable", "most heard today", "clear as a bell",
                    "days straight", "call today", "first of the day", "up before the sun",
                    "dawn chorus"):
            self.assertNotIn(bad, src)


if __name__ == "__main__":
    unittest.main()


class ShareTestCase(GenericTestBase):
    """Multi-select share links: curate-only to create, public to view."""
    IMG = "https://%s.s3.amazonaws.com/birds/images/123-0.jpg" % birds.S3_BUCKET

    def setUp(self):
        super().setUp()
        self.store = {}
        p1 = mock.patch.object(birds, "_read_repo_curation",
                               side_effect=lambda path, d: dict(self.store) if path == birds.SHARES_FILE else d())
        def save(path, data):
            self.store.clear(); self.store.update(data)
        p2 = mock.patch.object(birds, "_atomic_write_json", side_effect=lambda path, data, **kw: save(path, data))
        p3 = mock.patch.dict("os.environ", {"BIRDS_USE_S3": ""})
        for p in (p1, p2, p3):
            p.start(); self.addCleanup(p.stop)

    def _curate(self, on=True):
        return mock.patch.object(index, "_curate_on", return_value=on)

    def test_create_requires_curate(self):
        with self._curate(False):
            r = self.test_client.post("/share", json={"items": [{"full": self.IMG}]})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.store, {})

    def test_create_view_rename_delete(self):
        with self._curate():
            r = self.test_client.post("/share", json={"items": [
                {"full": self.IMG, "species": "Mallard"},
                {"full": "https://evil.example.com/x.jpg"},     # not our bucket: dropped
                {"full": self.IMG},                             # duplicate: dropped
            ]}).get_json()
        self.assertEqual(r["count"], 1)
        sid = r["id"]
        self.assertTrue(r["url"].endswith("/s/" + sid))
        with self._curate(False):
            page = self.test_client.get("/s/" + sid)
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Mallard", page.data)
        self.assertIn(self.IMG.encode(), page.data)
        self.assertNotIn(b"delete link", page.data)            # visitors can't manage it
        with self._curate():
            self.assertEqual(self.test_client.post("/share/" + sid, json={"title": "Pond"}).status_code, 200)
            self.assertIn(b"Pond", self.test_client.get("/s").data)
            self.assertTrue(self.test_client.post("/share/" + sid, json={"delete": True}).get_json()["ok"])
        self.assertEqual(self.test_client.get("/s/" + sid).status_code, 404)

    def test_empty_or_foreign_selection_is_rejected(self):
        with self._curate():
            r = self.test_client.post("/share", json={"items": [{"full": "https://evil.example.com/x.jpg"}]})
        self.assertEqual(r.status_code, 400)

    def test_reorder_cover_and_remove(self):
        imgs = [self.IMG.replace("123-0", "123-%d" % n) for n in range(3)]
        with self._curate():
            sid = self.test_client.post("/share", json={"items": [{"full": u} for u in imgs]}).get_json()["id"]
            r = self.test_client.post("/share/" + sid, json={"order": [imgs[2], imgs[0]], "cover": imgs[0]})
            self.assertEqual(r.get_json()["count"], 2)                 # imgs[1] removed
            share = birds.get_share(sid)
            self.assertEqual([i["full"] for i in share["items"]], [imgs[2], imgs[0]])
            self.assertEqual(birds.share_cover(share)["full"], imgs[0])
            page = self.test_client.get("/s/" + sid).data.decode()
            self.assertIn('class="sh-cover" id="sh-cover" src="%s"' % imgs[0], page)
            self.assertIn('og:image" content="%s"' % imgs[0], page)
            # removing the cover falls back to the first photo; emptying is refused
            self.test_client.post("/share/" + sid, json={"order": [imgs[2]]})
            self.assertEqual(birds.share_cover(birds.get_share(sid))["full"], imgs[2])
            self.assertEqual(self.test_client.post("/share/" + sid, json={"order": []}).status_code, 400)

    def test_bad_ids_404(self):
        for sid in ("../etc", "x", "ABCDEFGHIJKLMNOPQRS"):
            self.assertEqual(self.test_client.get("/s/" + sid).status_code, 404)

    def test_index_is_curate_only(self):
        with self._curate(False):
            self.assertEqual(self.test_client.get("/s").status_code, 404)

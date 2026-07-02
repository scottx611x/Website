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

    def test_photography_route(self):
        # Photography is hidden for now.
        self.assertEqual(self.test_client.get("/photography").status_code, 404)

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

    def test_map_points_matches_aliases(self):
        places = [{"name": "Rea St.", "lat": 42.67, "lng": -71.1, "area": "local",
                   "match": ["rea st"]}]
        shots = [{"id": "a", "images": ["u1", "u2"], "species": "Barred Owl",
                  "image_locations": ["Rea St.", "Rea Street Extension"]}]
        pts = birds.map_points(shots, places)
        self.assertEqual(len(pts), 1)
        self.assertEqual(pts[0]["count"], 2)  # alias prefix folds the Extension in
        self.assertEqual(pts[0]["top"], ["Barred Owl"])

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
        # Every lifer carries its first-sighting photo for the timeline card.
        for entry in series["accum"]:
            self.assertTrue(entry["img"])
            self.assertTrue(entry["fam"])
        for day, val in series["per_day"].items():
            self.assertGreaterEqual(val["n"], len(val["sp"]) and 1)
            self.assertTrue(val["img"])

    def test_sort_posted_leads_with_newest_instagram_posts(self):
        shots = birds.load_gallery(shuffle=False)
        frames = birds.sort_frames(birds.all_photos_shuffled(shots), "posted")
        newest_post = max(s.get("timestamp") or "" for s in shots)
        self.assertEqual(frames[0]["_posted"], newest_post)

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

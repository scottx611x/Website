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

    def test_effect_route(self):
        for name in index.EFFECTS:
            response = self.test_client.get("/effects/{}".format(name))
            self.assertEqual(response.status_code, 200)

    def test_unknown_effect_404(self):
        self.assertEqual(self.test_client.get("/effects/nope").status_code, 404)

    def test_blog_list_route(self):
        self.assertEqual(self.test_client.get("/blog").status_code, 200)

    def test_blog_post_route(self):
        slug = blog.list_posts()[0]["slug"]
        response = self.test_client.get("/blog/{}".format(slug))
        self.assertEqual(response.status_code, 200)

    def test_missing_blog_post_404(self):
        self.assertEqual(self.test_client.get("/blog/nope").status_code, 404)

    def test_photography_route(self):
        self.assertEqual(self.test_client.get("/photography").status_code, 200)

    def test_projects_route(self):
        response = self.test_client.get("/projects")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"github.com/scottx611x", response.data)

    def test_birds_route(self):
        self.assertEqual(self.test_client.get("/birds").status_code, 200)

    def test_birds_subdomain_serves_gallery_at_root(self):
        response = self.test_client.get(
            "/", headers={"Host": "birds.scott-ouellette.com"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Birds of North Andover", response.data)

    def test_archive_route(self):
        self.assertEqual(self.test_client.get("/archive").status_code, 200)

    def test_archive_effect_routes(self):
        for name in index.EFFECTS:
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

    def test_ticker_species_dedupes(self):
        shots = [{"species": s} for s in ["Barred Owls", "Baby Barred Owl", "Osprey"]]
        self.assertEqual(birds.ticker_species(shots), ["Barred Owl", "Osprey"])

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

    def test_order_gallery_declumps_species(self):
        shots = [{"species": s, "weight": 0.5} for s in ["A", "A", "B", "B", "C"]]
        out = birds.order_gallery(shots)
        self.assertEqual(len(out), 5)
        adjacent_dupes = any(
            out[i]["species"] == out[i + 1]["species"] for i in range(len(out) - 1)
        )
        self.assertFalse(adjacent_dupes)

    def test_frame_captions_map_each_carousel_image(self):
        caption = "Barred Owl - Rea St.\nNorthern Flicker - Weir Hill\n\n3-15-26"
        caps = birds._frame_captions(caption, 2, "Mar 15, 2026")
        self.assertEqual(caps, ["Barred Owl · Mar 15, 2026", "Northern Flicker · Mar 15, 2026"])

    def test_frame_captions_fallback_when_counts_differ(self):
        caption = "Barred Owl\n\nRea St.\n\n4-2-26"
        caps = birds._frame_captions(caption, 3, "Apr 2, 2026")
        self.assertEqual(caps, ["Barred Owl · Apr 2, 2026"] * 3)

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

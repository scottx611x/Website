import unittest
import requests

import index


class SanityTestCase(unittest.TestCase):

    def test_site_is_not_down(self):
        response = requests.get("https://www.scott-ouellette.com")
        self.assertEqual(response.status_code, 200)


class RoutesTestCase(unittest.TestCase):

    def setUp(self):
        self.app = index.app
        self.test_client = self.app.test_client()

    def test_index_route(self):
        response = self.test_client.get('/')
        self.assertEquals(response.status_code, 200)

    def test_voronoi_route(self):
        response = self.test_client.get('/voronoi')
        self.assertEquals(response.status_code, 200)

    def test_collision_route(self):
        response = self.test_client.get('/collision')
        self.assertEquals(response.status_code, 200)

    def test_tiltshift_route(self):
        response = self.test_client.get('/tilt-shift')
        self.assertEquals(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()

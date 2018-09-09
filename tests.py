import unittest
import requests

import index


class GenericTestBase(unittest.TestCase):

    def setUp(self):
        self.app = index.app
        self.test_client = self.app.test_client()

class RoutesTestCase(GenericTestBase):

    def test_index_route(self):
        for i in xrange(10):
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


class UtilsTestCase(GenericTestBase):

    def test_that_index_template_is_different_for_every_get(self):
        prior_data = None
        for i in xrange(10):
            response = self.test_client.get('/')
            self.assertNotEqual(prior_data, response.data)
            prior_data = response.data


if __name__ == '__main__':
    unittest.main()

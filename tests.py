import unittest

import requests


class SanityTestCase(unittest.TestCase):

    def test_site_is_not_down(self):
        response = requests.get("https://www.scott-ouellette.com")
        self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main()

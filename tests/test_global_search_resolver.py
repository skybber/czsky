import unittest
from unittest.mock import patch

from app.commons.global_search_resolver import resolve_global_object


class GlobalSearchResolverTestCase(unittest.TestCase):
    def test_returns_first_match_in_global_search_order(self):
        with patch("app.commons.global_search_resolver.search_constellation", return_value="constellation"), \
             patch("app.commons.global_search_resolver.search_dso", return_value="dso"), \
             patch("app.commons.global_search_resolver.search_double_star", return_value=None), \
             patch("app.commons.global_search_resolver._search_star_safe", return_value=(None, None)), \
             patch("app.commons.global_search_resolver.search_earth_moon", return_value=False), \
             patch("app.commons.global_search_resolver.search_planet", return_value=None), \
             patch("app.commons.global_search_resolver.search_planet_moon", return_value=None), \
             patch("app.commons.global_search_resolver.search_comet", return_value=None), \
             patch("app.commons.global_search_resolver.search_minor_planet", return_value=None):
            result = resolve_global_object("M1")

        self.assertEqual(result["object_type"], "constellation")
        self.assertEqual(result["object"], "constellation")

    def test_returns_none_for_empty_query(self):
        self.assertIsNone(resolve_global_object("  "))

    def test_returns_earth_moon_payload_without_model(self):
        with patch("app.commons.global_search_resolver.search_constellation", return_value=None), \
             patch("app.commons.global_search_resolver.search_dso", return_value=None), \
             patch("app.commons.global_search_resolver.search_double_star", return_value=None), \
             patch("app.commons.global_search_resolver._search_star_safe", return_value=(None, None)), \
             patch("app.commons.global_search_resolver.search_earth_moon", return_value=True), \
             patch("app.commons.global_search_resolver.search_planet", return_value=None), \
             patch("app.commons.global_search_resolver.search_planet_moon", return_value=None), \
             patch("app.commons.global_search_resolver.search_comet", return_value=None), \
             patch("app.commons.global_search_resolver.search_minor_planet", return_value=None):
            result = resolve_global_object("moon")

        self.assertEqual(result["object_type"], "earth_moon")
        self.assertEqual(result["object"]["identifier"], "moon")

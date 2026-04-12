import asyncio
import unittest
from datetime import datetime
from unittest.mock import patch

import app.mcp_server as mcp_server
from flask import Flask, current_app


class _DummyDso:
    def __init__(self, dso_id, identifier, title, dso_type, magnitude, constellation="AND"):
        self.id = dso_id
        self.name = identifier
        self._title = title
        self.type = dso_type
        self.mag = magnitude
        self.constellation = constellation
        self.subtype = None
        self.surface_bright = None
        self.position_angle = None
        self.major_axis = None
        self.minor_axis = None
        self.distance = None
        self.ra = 1.0
        self.dec = 2.0

    def denormalized_name(self):
        return self._title

    def get_constellation_iau_code(self):
        return self.constellation

    def ra_str_short(self):
        return "01:00"

    def dec_str_short(self):
        return "+02:00"


class _DummyDoubleStar:
    def __init__(self, star_id, common_id, title, magnitude, constellation="ORI"):
        self.id = star_id
        self.common_cat_id = common_id
        self.wds_number = "WDS1"
        self._title = title
        self.mag_first = magnitude
        self.constellation = constellation
        self.components = None
        self.pos_angle = None
        self.separation = None
        self.mag_second = None
        self.delta_mag = None
        self.spectral_type = None
        self.ra_first = 10.0
        self.dec_first = -5.0

    def get_common_name(self):
        return self._title

    def get_constellation_iau_code(self):
        return self.constellation

    def ra_first_str_short(self):
        return "10:00"

    def dec_first_str_short(self):
        return "-05:00"


class _DummyWishListItem:
    def __init__(self, item_id, order, created, updated, dso=None, double_star=None):
        self.id = item_id
        self.order = order
        self.create_date = created
        self.update_date = updated
        self.deepsky_object = dso
        self.double_star = double_star
        self.dso_id = dso.id if dso else None
        self.double_star_id = double_star.id if double_star else None


class McpServerTestCase(unittest.TestCase):
    def test_returns_not_found_payload(self):
        with patch("app.mcp_server.get_app") as get_app_mock, \
             patch("app.mcp_server.resolve_global_object", return_value=None):
            app = get_app_mock.return_value
            app.app_context.return_value.__enter__.return_value = None
            app.app_context.return_value.__exit__.return_value = None
            app.test_request_context.return_value.__enter__.return_value = None
            app.test_request_context.return_value.__exit__.return_value = None

            result = mcp_server.resolve_sky_object("unknown")

        self.assertFalse(result["found"])
        self.assertIsNone(result["result"])

    def test_formats_found_payload(self):
        resolved = {"object_type": "planet", "matched_by": "planet", "object": object()}
        formatted = {"object_type": "planet", "identifier": "SATURN"}

        with patch("app.mcp_server.get_app") as get_app_mock, \
             patch("app.mcp_server.resolve_global_object", return_value=resolved), \
             patch("app.mcp_server.format_resolved_object", return_value=formatted):
            app = get_app_mock.return_value
            app.app_context.return_value.__enter__.return_value = None
            app.app_context.return_value.__exit__.return_value = None
            app.test_request_context.return_value.__enter__.return_value = None
            app.test_request_context.return_value.__exit__.return_value = None

            result = mcp_server.resolve_sky_object("Saturn")

        self.assertTrue(result["found"])
        self.assertEqual(result["result"]["identifier"], "SATURN")

    def test_returns_comet_recent_observations_payload(self):
        comet = type(
            "Comet",
            (),
            {"id": 42, "comet_id": "88PHowell", "designation": "88P/Howell"},
        )()
        resolved = {"object_type": "comet", "matched_by": "comet", "object": comet}
        observations = [{"obs_date": "2026-03-25 12:14:24", "magnitude": 10.5}]

        with patch("app.mcp_server.get_app") as get_app_mock, \
             patch("app.mcp_server.resolve_global_object", return_value=resolved), \
             patch("app.mcp_server.fetch_recent_cobs_observations", return_value=observations):
            app = get_app_mock.return_value
            app.app_context.return_value.__enter__.return_value = None
            app.app_context.return_value.__exit__.return_value = None
            app.test_request_context.return_value.__enter__.return_value = None
            app.test_request_context.return_value.__exit__.return_value = None

            result = mcp_server.get_comet_recent_observations_payload("88P/Howell")

        self.assertTrue(result["found"])
        self.assertEqual(result["result"]["identifier"], "88PHowell")
        self.assertEqual(
            result["result"]["recent_cobs_observations"][0]["obs_date"],
            "2026-03-25 12:14:24",
        )


class McpWishlistPayloadTestCase(unittest.TestCase):
    def setUp(self):
        dso_1 = _DummyDso(1, "M31", "M 31", "Galaxy", 3.4, constellation="AND")
        dso_2 = _DummyDso(2, "NGC7000", "NGC 7000", "Nebula", 4.0, constellation="CYG")
        dbl_1 = _DummyDoubleStar(101, "STF 13", "STF 13", 7.1, constellation="ORI")

        self.item_1 = _DummyWishListItem(
            item_id=1,
            order=1,
            created=datetime(2026, 4, 10, 20, 0, 0),
            updated=datetime(2026, 4, 10, 20, 30, 0),
            dso=dso_1,
        )
        self.item_2 = _DummyWishListItem(
            item_id=2,
            order=2,
            created=datetime(2026, 4, 11, 20, 0, 0),
            updated=datetime(2026, 4, 11, 20, 30, 0),
            double_star=dbl_1,
        )
        self.item_3 = _DummyWishListItem(
            item_id=3,
            order=3,
            created=datetime(2026, 4, 12, 20, 0, 0),
            updated=datetime(2026, 4, 12, 20, 30, 0),
            dso=dso_2,
        )
        self.wishlist = type("WishList", (), {"id": 77})()

    def test_wishlist_list_payload_paginates(self):
        with patch("app.mcp_server._resolve_wishlist_user_id", return_value=5), \
             patch("app.mcp_server._load_wishlist_items_for_user",
                   return_value=(self.wishlist, [self.item_1, self.item_2, self.item_3])), \
             patch(
                 "app.mcp_server._load_observed_sets_for_user_wishlist",
                 return_value=({1}, {101}),
             ):
            result = mcp_server.wishlist_list_payload(user_id=5, limit=2, sort="addedAt:desc")

        self.assertTrue(result["hasMore"])
        self.assertEqual(result["nextCursor"], "2")
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0]["wishlistItemId"], "w_3")
        self.assertEqual(result["items"][1]["wishlistItemId"], "w_2")

    def test_wishlist_get_payload_found_and_missing(self):
        with patch("app.mcp_server._resolve_wishlist_user_id", return_value=5), \
             patch("app.mcp_server._load_wishlist_items_for_user",
                   return_value=(self.wishlist, [self.item_1, self.item_2, self.item_3])), \
             patch(
                 "app.mcp_server._load_observed_sets_for_user_wishlist",
                 return_value=({1}, {101}),
             ):
            found = mcp_server.wishlist_get_payload("w_2", user_id=5)
            missing = mcp_server.wishlist_get_payload("w_999", user_id=5)

        self.assertTrue(found["found"])
        self.assertEqual(found["item"]["itemType"], "double_star")
        self.assertFalse(missing["found"])
        self.assertIsNone(missing["item"])

    def test_wishlist_stats_payload_counts_items(self):
        with patch("app.mcp_server._resolve_wishlist_user_id", return_value=5), \
             patch("app.mcp_server._load_wishlist_items_for_user",
                   return_value=(self.wishlist, [self.item_1, self.item_2, self.item_3])), \
             patch(
                 "app.mcp_server._load_observed_sets_for_user_wishlist",
                 return_value=({1}, {101}),
             ):
            result = mcp_server.wishlist_stats_payload(user_id=5)

        self.assertEqual(result["total"], 3)
        self.assertEqual(result["observed"], 2)
        self.assertEqual(result["unobserved"], 1)
        self.assertEqual(result["byItemType"]["dso"], 2)
        self.assertEqual(result["byItemType"]["double_star"], 1)

    def test_scope_check_rejects_missing_scope(self):
        token = type("AccessToken", (), {"scopes": ["profile:read"]})()
        with patch("app.mcp_server._get_access_token", return_value=token):
            with self.assertRaises(PermissionError):
                mcp_server._require_scope_if_available("wishlist:read")

    def test_resolve_wishlist_user_id_accepts_explicit_stub_user(self):
        with patch("app.mcp_server._get_access_token", return_value=None), \
             patch.dict("os.environ", {}, clear=True):
            resolved = mcp_server._resolve_wishlist_user_id(user_id=12)
        self.assertEqual(resolved, 12)

    def test_wishlist_list_formats_items_inside_app_context(self):
        def _summary_with_current_app(*_args, **_kwargs):
            # Raises RuntimeError when called outside Flask app context.
            _ = current_app.name
            return {
                "item": {
                    "wishlistItemId": "w_1",
                    "itemType": "dso",
                    "objectType": "galaxy",
                    "constellation": "AND",
                    "observed": False,
                },
                "added_at": datetime(2026, 4, 10, 20, 0, 0),
                "updated_at": datetime(2026, 4, 10, 20, 30, 0),
                "magnitude": 3.4,
                "name_sort": "m 31",
            }

        fake_app = Flask("mcp-test-app")

        with patch("app.mcp_server.get_app", return_value=fake_app), \
             patch("app.mcp_server._resolve_wishlist_user_id", return_value=5), \
             patch("app.mcp_server._load_wishlist_items_for_user",
                   return_value=(self.wishlist, [self.item_1])), \
             patch(
                 "app.mcp_server._load_observed_sets_for_user_wishlist",
                 return_value=(set(), set()),
             ), \
             patch("app.mcp_server._build_wishlist_item_summary", side_effect=_summary_with_current_app):
            result = mcp_server.wishlist_list_payload(user_id=5, limit=1)

        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["wishlistItemId"], "w_1")


class McpAuthBridgeTestCase(unittest.TestCase):
    def test_build_base_url_normalizes_bind_all_host(self):
        self.assertEqual(mcp_server._build_base_url("0.0.0.0", 8001), "http://127.0.0.1:8001")

    def test_build_base_url_wraps_ipv6_host(self):
        self.assertEqual(mcp_server._build_base_url("::1", 8001), "http://[::1]:8001")

    def test_build_mcp_auth_kwargs_can_be_disabled(self):
        with patch.dict("os.environ", {"MCP_ENABLE_TOKEN_AUTH": "0"}, clear=False):
            kwargs = mcp_server._build_mcp_auth_kwargs("127.0.0.1", 8001)
        self.assertEqual(kwargs, {})

    def test_token_verifier_maps_valid_db_token(self):
        with patch.dict("os.environ", {"MCP_ENABLE_TOKEN_AUTH": "1"}, clear=False), \
             patch(
                 "app.mcp_server._verify_db_mcp_token",
                 return_value={
                     "user_id": 42,
                     "scopes": ["wishlist:read"],
                     "token_id": "tok_1",
                 },
             ):
            kwargs = mcp_server._build_mcp_auth_kwargs("127.0.0.1", 8001)
            token_verifier = kwargs["token_verifier"]
            auth_token = asyncio.run(token_verifier.verify_token("czmcp_abc.def"))

        self.assertIsNotNone(auth_token)
        self.assertEqual(auth_token.client_id, "user:42")
        self.assertEqual(auth_token.user_id, 42)
        self.assertEqual(auth_token.scopes, ["wishlist:read"])
        self.assertEqual(auth_token.token_id, "tok_1")

    def test_token_verifier_rejects_invalid_token(self):
        with patch.dict("os.environ", {"MCP_ENABLE_TOKEN_AUTH": "1"}, clear=False), \
             patch("app.mcp_server._verify_db_mcp_token", return_value=None):
            kwargs = mcp_server._build_mcp_auth_kwargs("127.0.0.1", 8001)
            token_verifier = kwargs["token_verifier"]
            auth_token = asyncio.run(token_verifier.verify_token("czmcp_invalid"))

        self.assertIsNone(auth_token)

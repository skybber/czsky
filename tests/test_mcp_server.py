import asyncio
import unittest
from datetime import datetime
from unittest.mock import patch

import app.mcp_server as mcp_server
from app.mcp.tools import observation_log as observation_log_tools
from app.mcp.tools import observing_session as observing_session_tools
from app.mcp.tools import sky_objects as sky_object_tools
from app.mcp.tools import session_plan as session_plan_tools
from app.mcp.tools import wishlist as wishlist_tools
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

    def test_resolve_many_returns_per_query_payloads(self):
        resolved = {"object_type": "planet", "matched_by": "planet", "object": object()}

        with patch("app.mcp_server.get_app") as get_app_mock, \
             patch("app.mcp_server.resolve_global_object", side_effect=[resolved, None]), \
             patch(
                 "app.mcp_server.format_resolved_object",
                 return_value={"object_type": "planet", "identifier": "SATURN"},
             ):
            app = get_app_mock.return_value
            app.app_context.return_value.__enter__.return_value = None
            app.app_context.return_value.__exit__.return_value = None
            app.test_request_context.return_value.__enter__.return_value = None
            app.test_request_context.return_value.__exit__.return_value = None

            result = mcp_server.resolve_sky_objects_payload(["Saturn", "unknown"])

        self.assertEqual(
            result,
            {
                "results": [
                    {
                        "query": "Saturn",
                        "found": True,
                        "result": {"object_type": "planet", "identifier": "SATURN"},
                    },
                    {
                        "query": "unknown",
                        "found": False,
                        "result": None,
                    },
                ]
            },
        )

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
        with patch("app.mcp_server._resolve_mcp_user_id", return_value=5), \
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
        with patch("app.mcp_server._resolve_mcp_user_id", return_value=5), \
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
        with patch("app.mcp_server._resolve_mcp_user_id", return_value=5), \
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

    def test_resolve_mcp_user_id_accepts_explicit_stub_user(self):
        with patch("app.mcp_server._get_access_token", return_value=None), \
             patch.dict("os.environ", {}, clear=True):
            resolved = mcp_server._resolve_mcp_user_id(user_id=12)
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
             patch("app.mcp_server._resolve_mcp_user_id", return_value=5), \
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

    def test_wishlist_contains_payload_matches_item_for_current_user(self):
        fake_app = Flask("mcp-test-app")
        resolved = {
            "object_type": "dso",
            "object": type("Dso", (), {"id": 1})(),
        }

        with patch("app.mcp_server.get_app", return_value=fake_app), \
             patch("app.mcp_server._resolve_mcp_user_id", return_value=5), \
             patch("app.mcp_server.resolve_global_object", return_value=resolved), \
             patch("app.mcp_server._load_wishlist_items_for_user",
                   return_value=(self.wishlist, [self.item_1])):
            result = mcp_server.wishlist_contains_payload(query="M31", user_id=5)

        self.assertTrue(result["contains"])
        self.assertEqual(result["reason"], "in_wishlist")
        self.assertEqual(result["wishlistItemId"], "w_1")
        self.assertEqual(result["objectId"], "dso:1")

    def test_wishlist_contains_payload_does_not_match_other_items(self):
        fake_app = Flask("mcp-test-app")
        resolved = {
            "object_type": "dso",
            "object": type("Dso", (), {"id": 1})(),
        }

        with patch("app.mcp_server.get_app", return_value=fake_app), \
             patch("app.mcp_server._resolve_mcp_user_id", return_value=5), \
             patch("app.mcp_server.resolve_global_object", return_value=resolved), \
             patch(
                 "app.mcp_server._load_wishlist_items_for_user",
                 return_value=(self.wishlist, [self.item_2]),
             ) as load_items_mock:
            result = mcp_server.wishlist_contains_payload(query="M31", user_id=5)

        load_items_mock.assert_called_once_with(5)
        self.assertFalse(result["contains"])
        self.assertEqual(result["reason"], "not_in_wishlist")

    def test_wishlist_find_payload_returns_item_for_current_user(self):
        fake_app = Flask("mcp-test-app")
        resolved = {
            "object_type": "dso",
            "object": type("Dso", (), {"id": 1})(),
        }

        expected_item = {
            "wishlistItemId": "w_1",
            "objectId": "dso:1",
            "identifier": "M31",
            "name": "M 31",
            "itemType": "dso",
            "objectType": "Galaxy",
            "constellation": "AND",
            "magnitude": 3.4,
            "order": 1,
            "observed": False,
            "addedAt": "2026-04-10T20:00:00",
            "updatedAt": "2026-04-10T20:30:00",
        }

        with patch("app.mcp_server.get_app", return_value=fake_app), \
             patch("app.mcp_server._resolve_mcp_user_id", return_value=5), \
             patch("app.mcp_server.resolve_global_object", return_value=resolved), \
             patch(
                 "app.mcp_server._load_wishlist_items_for_user",
                 return_value=(self.wishlist, [self.item_1]),
             ), \
             patch(
                 "app.mcp_server._load_observed_sets_for_user_wishlist",
                 return_value=(set(), set()),
             ), \
             patch("app.mcp_server._build_wishlist_item_detail", return_value=expected_item):
            result = mcp_server.wishlist_find_payload(query="M31", user_id=5)

        self.assertTrue(result["found"])
        self.assertEqual(result["reason"], "in_wishlist")
        self.assertEqual(result["item"]["wishlistItemId"], "w_1")


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


class McpWishlistWriteBridgeTestCase(unittest.TestCase):
    def test_parse_wishlist_object_id_accepts_supported_format(self):
        self.assertEqual(mcp_server._parse_wishlist_object_id("dso:12"), ("dso", 12))
        self.assertEqual(mcp_server._parse_wishlist_object_id("double_star:34"), ("double_star", 34))

    def test_parse_wishlist_object_id_rejects_invalid_format(self):
        with self.assertRaises(ValueError):
            mcp_server._parse_wishlist_object_id("planet:1")

    def test_wishlist_add_payload_passes_write_scope(self):
        expected = {"added": True}
        with patch(
            "app.mcp_server.mcp_wishlist_write_payloads.wishlist_add_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.wishlist_add_payload(object_id="dso:1", user_id=5)

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "wishlist:write")

    def test_wishlist_remove_payload_passes_write_scope(self):
        expected = {"removed": True}
        with patch(
            "app.mcp_server.mcp_wishlist_write_payloads.wishlist_remove_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.wishlist_remove_payload(wishlist_item_id="w_1", user_id=5)

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "wishlist:write")

    def test_wishlist_bulk_add_payload_passes_write_scope(self):
        expected = {"total": 1, "added": 1, "skipped": 0, "results": []}
        with patch(
            "app.mcp_server.mcp_wishlist_write_payloads.wishlist_bulk_add_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.wishlist_bulk_add_payload(objects=["M31"], user_id=5)

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "wishlist:write")

    def test_wishlist_bulk_remove_payload_passes_write_scope(self):
        expected = {"total": 1, "removed": 1, "notRemoved": 0, "results": []}
        with patch(
            "app.mcp_server.mcp_wishlist_write_payloads.wishlist_bulk_remove_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.wishlist_bulk_remove_payload(wishlist_item_ids=["w_1"], user_id=5)

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "wishlist:write")

    def test_wishlist_export_payload_passes_read_scope(self):
        expected = {"format": "json", "content": "{}", "total": 0}
        with patch(
            "app.mcp_server.mcp_wishlist_write_payloads.wishlist_export_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.wishlist_export_payload(format="json", user_id=5)

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "wishlist:read")

    def test_wishlist_import_payload_passes_write_scope(self):
        expected = {"format": "json", "processed": 0, "added": 0, "skipped": 0, "errors": 0, "results": []}
        with patch(
            "app.mcp_server.mcp_wishlist_write_payloads.wishlist_import_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.wishlist_import_payload(content='{"items":[]}', format="json", user_id=5)

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "wishlist:write")


class McpSessionPlanBridgeTestCase(unittest.TestCase):
    def test_session_plan_create_payload_passes_write_scope(self):
        expected = {"created": True, "sessionPlanId": 10}
        with patch(
            "app.mcp_server.mcp_session_plan_payloads.session_plan_create_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.session_plan_create_payload(
                for_date="2026-05-10",
                location_name="Prague",
                title="Test",
                user_id=5,
            )

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "sessionplan:write")
        self.assertEqual(payload_mock.call_args.kwargs["location_name"], "Prague")

    def test_session_plan_get_payload_passes_read_scope(self):
        expected = {"found": True, "sessionPlan": {"sessionPlanId": 10}}
        with patch(
            "app.mcp_server.mcp_session_plan_payloads.session_plan_get_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.session_plan_get_payload(session_plan_id=10, user_id=5)

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "sessionplan:read")

    def test_session_plan_list_payload_passes_read_scope(self):
        expected = {"total": 1, "sessionPlans": []}
        with patch(
            "app.mcp_server.mcp_session_plan_payloads.session_plan_list_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.session_plan_list_payload(
                for_date="2026-05-10",
                include_archived=True,
                user_id=5,
            )

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "sessionplan:read")

    def test_session_plan_create_payload_accepts_location_id(self):
        expected = {"created": True, "sessionPlanId": 11}
        with patch(
            "app.mcp_server.mcp_session_plan_payloads.session_plan_create_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.session_plan_create_payload(
                for_date="2026-05-10",
                location_id=12,
                title="Plan with id",
                user_id=5,
            )

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["location_id"], 12)

    def test_observing_session_create_payload_passes_write_scope(self):
        expected = {"created": True, "observingSessionId": 10}
        with patch(
            "app.mcp_server.mcp_observing_session_payloads.observing_session_create_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.observing_session_create_payload(
                date_from="2026-05-10T21:30:00",
                date_to="2026-05-11T01:15:00",
                location_name="Prague",
                title="Night session",
                user_id=5,
            )

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "observingsession:write")
        self.assertEqual(payload_mock.call_args.kwargs["location_name"], "Prague")

    def test_observing_session_set_active_payload_passes_write_scope(self):
        expected = {"updated": True, "observingSessionId": 10, "isActive": True}
        with patch(
            "app.mcp_server.mcp_observing_session_payloads.observing_session_set_active_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.observing_session_set_active_payload(
                observing_session_id=10,
                is_active=True,
                user_id=5,
            )

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "observingsession:write")

    def test_observing_session_get_active_payload_passes_read_scope(self):
        expected = {"found": True, "observingSession": {"observingSessionId": 10}}
        with patch(
            "app.mcp_server.mcp_observing_session_payloads.observing_session_get_active_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.observing_session_get_active_payload(user_id=5)

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "observingsession:read")

    def test_observation_log_upsert_payload_passes_write_scope(self):
        expected = {"upserted": True, "observationId": 22}
        with patch(
            "app.mcp_server.mcp_observation_log_payloads.observation_log_upsert_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.observation_log_upsert_payload(
                query="M31",
                notes="nice core",
                user_id=5,
            )

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "observationlog:write")

    def test_session_plan_get_id_by_date_payload_passes_read_scope(self):
        expected = {"found": True, "sessionPlanId": 10, "sessionPlanIds": [10], "total": 1}
        with patch(
            "app.mcp_server.mcp_session_plan_payloads.session_plan_get_id_by_date_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.session_plan_get_id_by_date_payload(
                for_date="2026-05-10",
                user_id=5,
            )

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "sessionplan:read")

    def test_session_plan_add_item_payload_passes_write_scope(self):
        expected = {"added": True, "sessionPlanItemId": 77}
        with patch(
            "app.mcp_server.mcp_session_plan_payloads.session_plan_add_item_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.session_plan_add_item_payload(
                session_plan_id=10,
                query="M1",
                user_id=5,
            )

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "sessionplan:write")

    def test_session_plan_items_payload_passes_read_scope(self):
        expected = {"found": True, "items": [], "total": 0}
        with patch(
            "app.mcp_server.mcp_session_plan_payloads.session_plan_items_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.session_plan_items_payload(
                session_plan_id=10,
                object_types=["dso"],
                dso_list_id=7,
                user_id=5,
            )

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "sessionplan:read")

    def test_session_plan_add_items_payload_passes_write_scope(self):
        expected = {"addedCount": 2, "results": []}
        with patch(
            "app.mcp_server.mcp_session_plan_payloads.session_plan_add_items_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.session_plan_add_items_payload(
                session_plan_id=10,
                queries=["M1", "M31"],
                user_id=5,
            )

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "sessionplan:write")

    def test_session_plan_remove_items_payload_passes_write_scope(self):
        expected = {"removedCount": 1, "results": []}
        with patch(
            "app.mcp_server.mcp_session_plan_payloads.session_plan_remove_items_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.session_plan_remove_items_payload(
                session_plan_id=10,
                queries=["M1", "M31"],
                user_id=5,
            )

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "sessionplan:write")

    def test_session_plan_clear_payload_passes_write_scope(self):
        expected = {"cleared": True, "removedCount": 2}
        with patch(
            "app.mcp_server.mcp_session_plan_payloads.session_plan_clear_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.session_plan_clear_payload(
                session_plan_id=10,
                user_id=5,
            )

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "sessionplan:write")

    def test_session_plan_remove_item_payload_passes_write_scope(self):
        expected = {"removed": True, "sessionPlanItemId": 77}
        with patch(
            "app.mcp_server.mcp_session_plan_payloads.session_plan_remove_item_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.session_plan_remove_item_payload(
                session_plan_id=10,
                query="M1",
                user_id=5,
            )

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "sessionplan:write")

    def test_dso_list_sources_payload_passes_read_scope(self):
        expected = {"sources": [], "catalogues": [], "dsoLists": []}
        with patch(
            "app.mcp_server.mcp_dso_payloads.dso_list_sources_payload",
            return_value=expected,
        ) as payload_mock:
            result = mcp_server.dso_list_sources_payload(user_id=5)

        self.assertEqual(result, expected)
        self.assertEqual(payload_mock.call_args.kwargs["required_scope"], "dso:read")


class _DummyToolServer:
    def __init__(self):
        self.tool_names = []

    def tool(self, name=None):
        def decorator(fn):
            self.tool_names.append(name or fn.__name__)
            return fn

        return decorator


class McpWishlistToolsRegistrationTestCase(unittest.TestCase):
    def test_registers_contains_and_find_tools(self):
        server = _DummyToolServer()

        def _noop(**_kwargs):
            return {}

        wishlist_tools.register_tools(
            server,
            wishlist_list_resolver=_noop,
            wishlist_stats_resolver=_noop,
            wishlist_contains_resolver=_noop,
            wishlist_find_resolver=_noop,
            wishlist_add_resolver=_noop,
            wishlist_remove_resolver=_noop,
            wishlist_bulk_add_resolver=_noop,
            wishlist_bulk_remove_resolver=_noop,
            wishlist_export_resolver=_noop,
            wishlist_import_resolver=_noop,
        )

        self.assertIn("wishlist.contains", server.tool_names)
        self.assertIn("wishlist.find", server.tool_names)
        self.assertNotIn("wishlist.get", server.tool_names)


class McpSessionPlanToolsRegistrationTestCase(unittest.TestCase):
    def test_registers_session_plan_tools(self):
        server = _DummyToolServer()

        def _noop(**_kwargs):
            return {}

        session_plan_tools.register_tools(
            server,
            session_plan_create_resolver=_noop,
            session_plan_get_resolver=_noop,
            session_plan_list_resolver=_noop,
            session_plan_get_id_by_date_resolver=_noop,
            session_plan_items_resolver=_noop,
            session_plan_add_item_resolver=_noop,
            session_plan_add_items_resolver=_noop,
            session_plan_remove_item_resolver=_noop,
            session_plan_remove_items_resolver=_noop,
            session_plan_clear_resolver=_noop,
            dso_list_get_id_by_name_resolver=_noop,
        )

        self.assertIn("session_plan.create", server.tool_names)
        self.assertIn("session_plan.get", server.tool_names)
        self.assertIn("session_plan.list", server.tool_names)
        self.assertIn("session_plan.get_id_by_date", server.tool_names)
        self.assertIn("session_plan.items", server.tool_names)
        self.assertIn("session_plan.add_item", server.tool_names)
        self.assertIn("session_plan.add_items", server.tool_names)
        self.assertIn("session_plan.remove_item", server.tool_names)
        self.assertIn("session_plan.remove_items", server.tool_names)
        self.assertIn("session_plan.clear", server.tool_names)


class McpObservationLogToolsRegistrationTestCase(unittest.TestCase):
    def test_registers_observation_log_tools(self):
        server = _DummyToolServer()

        def _noop(**_kwargs):
            return {}

        observation_log_tools.register_tools(
            server,
            observation_log_upsert_resolver=_noop,
        )

        self.assertIn("observation_log.upsert", server.tool_names)


class McpObservingSessionToolsRegistrationTestCase(unittest.TestCase):
    def test_registers_observing_session_tools(self):
        server = _DummyToolServer()

        def _noop(**_kwargs):
            return {}

        observing_session_tools.register_tools(
            server,
            observing_session_create_resolver=_noop,
            observing_session_set_active_resolver=_noop,
            observing_session_get_active_resolver=_noop,
        )

        self.assertIn("observing_session.create", server.tool_names)
        self.assertIn("observing_session.set_active", server.tool_names)
        self.assertIn("observing_session.get_active", server.tool_names)


class McpSkyObjectToolsRegistrationTestCase(unittest.TestCase):
    def test_registers_resolve_many_tool(self):
        server = _DummyToolServer()

        def _noop(*_args, **_kwargs):
            return {}

        sky_object_tools.register_tools(
            server,
            resolve_sky_object_resolver=_noop,
            resolve_sky_objects_resolver=_noop,
            comet_observations_resolver=_noop,
        )

        self.assertIn("resolve_sky_object", server.tool_names)
        self.assertIn("resolve_sky_objects", server.tool_names)
        self.assertIn("get_comet_recent_observations", server.tool_names)


class McpDsoToolsRegistrationTestCase(unittest.TestCase):
    def test_registers_list_sources_tool(self):
        server = _DummyToolServer()

        def _noop(**_kwargs):
            return {}

        from app.mcp.tools import dso as dso_tools

        dso_tools.register_tools(
            server,
            dso_find_resolver=_noop,
            dso_list_sources_resolver=_noop,
        )

        self.assertIn("dso.find", server.tool_names)
        self.assertIn("dso.list_sources", server.tool_names)

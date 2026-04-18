import unittest

from app.mcp import wishlist_write_payloads


class McpWishlistWritePayloadsTestCase(unittest.TestCase):
    def test_wishlist_export_csv_uses_query_column(self):
        exported = wishlist_write_payloads.wishlist_export_payload(
            export_format="csv",
            user_id=5,
            require_scope_if_available_func=lambda _scope: None,
            required_scope="wishlist:read",
            resolve_mcp_user_id_func=lambda user_id: user_id or 0,
            load_wishlist_items_for_user_func=lambda _user_id: (type("WishList", (), {"id": 7})(), [object()]),
            load_observed_sets_for_user_wishlist_func=lambda _user_id, _wish_list_id: (set(), set()),
            build_wishlist_item_detail_func=lambda _item, _observed_dso_ids, _observed_double_star_ids: {
                "objectId": "dso:1",
                "query": "M 31",
                "wishlistItemId": "w_1",
                "identifier": "M31",
                "name": "Andromeda Galaxy",
                "itemType": "dso",
                "objectType": "dso",
                "constellation": "AND",
                "magnitude": 3.4,
                "observed": False,
                "addedAt": "2026-04-10T20:00:00",
                "updatedAt": "2026-04-10T20:30:00",
            },
        )

        rows = exported["content"].splitlines()
        self.assertEqual(
            rows[1],
            "dso:1,M 31,w_1,M31,Andromeda Galaxy,dso,dso,AND,3.4,False,2026-04-10T20:00:00,2026-04-10T20:30:00",
        )

import unittest

from app.main.usersettings.mcp_token_service import (
    build_plain_mcp_token,
    normalize_scope,
    parse_plain_mcp_token,
)


class McpTokenServiceTestCase(unittest.TestCase):
    def test_normalize_scope_defaults_to_wishlist_read(self):
        self.assertEqual(normalize_scope(None), "wishlist:read")
        self.assertEqual(normalize_scope(""), "wishlist:read")
        self.assertEqual(normalize_scope("   "), "wishlist:read")

    def test_normalize_scope_deduplicates_values(self):
        self.assertEqual(
            normalize_scope("wishlist:read wishlist:read profile:read"),
            "wishlist:read profile:read",
        )

    def test_build_and_parse_plain_token(self):
        token_value = build_plain_mcp_token("abc123", "s3cr3t")
        self.assertEqual(token_value, "czmcp_abc123.s3cr3t")

        parsed = parse_plain_mcp_token(token_value)
        self.assertEqual(parsed, ("abc123", "s3cr3t"))

    def test_parse_plain_token_rejects_invalid_format(self):
        self.assertIsNone(parse_plain_mcp_token(""))
        self.assertIsNone(parse_plain_mcp_token("abc123.s3cr3t"))
        self.assertIsNone(parse_plain_mcp_token("czmcp_abc123"))
        self.assertIsNone(parse_plain_mcp_token("czmcp_.secret"))

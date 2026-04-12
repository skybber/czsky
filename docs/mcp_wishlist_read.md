# MCP Wishlist Read Extension (Draft)

This document defines the first read-only user extension for the CzSkY MCP sidecar.

## Extension metadata

- Extension id: `com.czsky/wishlist-read`
- Version: `0.1.0`
- Tools:
  - `wishlist.list`
  - `wishlist.get`
  - `wishlist.stats`

Example capability advertisement:

```json
{
  "extensions": {
    "com.czsky/wishlist-read": {
      "version": "0.1.0",
      "features": ["wishlist.list", "wishlist.get", "wishlist.stats"]
    }
  }
}
```

## Authentication and authorization

Preferred runtime mode:

1. MCP transport authenticates with OAuth bearer token.
2. Tool handlers read auth context from MCP middleware.
3. Required scope for all three tools: `wishlist:read`.
4. User identity is inferred from token claims (`user_id`, `sub`, `subject`, `uid`) or token `client_id`.

Current stub fallback for local/dev use:

1. Disable transport auth (`MCP_ENABLE_TOKEN_AUTH=0`) to allow stub mode.
2. In stub mode, pass `user_id` input to the tool.
3. If `user_id` is omitted, server can fall back to env `MCP_USER_ID`.

Security note: production clients should rely on bearer tokens and avoid passing `user_id` manually.

## Tool contract summary

### `wishlist.list`

Returns paginated wishlist rows for the current user.

Input fields:

- `user_id` (optional in token mode)
- `cursor` (optional offset cursor)
- `limit` (1..100)
- `sort`: `addedAt:desc` | `addedAt:asc` | `magnitude:asc` | `name:asc`
- `observed` (optional bool filter)
- `object_types` (optional filter list)
- `constellations` (optional filter list)

Output:

- `items` (list of normalized rows)
- `nextCursor`
- `hasMore`

### `wishlist.get`

Returns one wishlist row by id.

Input fields:

- `wishlist_item_id` (`w_<id>` or numeric string)
- `user_id` (optional in token mode)

Output:

- `found`
- `item` (null when not found)

### `wishlist.stats`

Returns aggregate counters for the wishlist.

Input fields:

- `user_id` (optional in token mode)

Output:

- `total`
- `observed`
- `unobserved`
- `byItemType`
- `byObjectType`
- `updatedAt`

## Schemas

JSON schemas are stored under `docs/mcp_schemas/`:

- `wishlist.list.input.v1.json`
- `wishlist.list.output.v1.json`
- `wishlist.get.input.v1.json`
- `wishlist.get.output.v1.json`
- `wishlist.stats.input.v1.json`
- `wishlist.stats.output.v1.json`

import unittest
from unittest.mock import Mock, patch

from app.mcp import session_plan_payloads


class _DummyContextManager:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyApp:
    def app_context(self):
        return _DummyContextManager()

    def test_request_context(self, *_args, **_kwargs):
        return _DummyContextManager()


class _DummyItem:
    def __init__(self, item_id):
        self.id = item_id


class SessionPlanAddItemsPayloadTestCase(unittest.TestCase):
    def test_add_items_returns_per_item_results_and_commits_once(self):
        session_plan = object()
        db_session = Mock()
        new_item_1 = _DummyItem(101)
        existing_item = _DummyItem(55)

        resolved_targets = [
            ({"query": "M1", "objectType": "dso", "targetId": 1, "objectId": "dso:1", "targetObject": object()}, None),
            ({"query": "M31", "objectType": "dso", "targetId": 2, "objectId": "dso:2", "targetObject": object()}, None),
            (None, "not_found"),
        ]
        existing_items = [None, existing_item]

        with patch("app.mcp.session_plan_payloads._load_owned_active_session_plan", return_value=session_plan), \
             patch("app.mcp.session_plan_payloads._resolve_session_plan_target", side_effect=resolved_targets), \
             patch("app.mcp.session_plan_payloads._find_session_plan_item", side_effect=existing_items), \
             patch("app.mcp.session_plan_payloads._create_session_plan_item", return_value=(new_item_1, None)), \
             patch("app.mcp.session_plan_payloads._safe_reorder_session_plan") as reorder_mock, \
             patch("app.db.session", db_session):
            result = session_plan_payloads.session_plan_add_items_payload(
                session_plan_id=10,
                queries=["M1", "M31", "Unknown"],
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="sessionplan:write",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
                resolve_global_object_func=lambda query: None,
            )

        self.assertEqual(result["sessionPlanId"], 10)
        self.assertEqual(result["addedCount"], 1)
        self.assertEqual(
            result["results"],
            [
                {
                    "query": "M1",
                    "added": True,
                    "reason": "added",
                    "sessionPlanItemId": 101,
                    "objectId": "dso:1",
                },
                {
                    "query": "M31",
                    "added": False,
                    "reason": "already_exists",
                    "sessionPlanItemId": 55,
                    "objectId": "dso:2",
                },
                {
                    "query": "Unknown",
                    "added": False,
                    "reason": "not_found",
                    "sessionPlanItemId": None,
                    "objectId": None,
                },
            ],
        )
        db_session.add.assert_called_once_with(new_item_1)
        db_session.commit.assert_called_once_with()
        reorder_mock.assert_called_once_with(session_plan)

    def test_add_items_skips_commit_when_nothing_is_added(self):
        session_plan = object()
        db_session = Mock()

        with patch("app.mcp.session_plan_payloads._load_owned_active_session_plan", return_value=session_plan), \
             patch("app.mcp.session_plan_payloads._resolve_session_plan_target", return_value=(None, "not_found")), \
             patch("app.mcp.session_plan_payloads._safe_reorder_session_plan") as reorder_mock, \
             patch("app.db.session", db_session):
            result = session_plan_payloads.session_plan_add_items_payload(
                session_plan_id=10,
                queries=["Unknown"],
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="sessionplan:write",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
                resolve_global_object_func=lambda query: None,
            )

        self.assertEqual(result["addedCount"], 0)
        db_session.add.assert_not_called()
        db_session.commit.assert_not_called()
        reorder_mock.assert_not_called()

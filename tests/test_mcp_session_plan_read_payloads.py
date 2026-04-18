import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.mcp import dso_payloads, session_plan_payloads
from app.mcp.server import get_app as get_real_app


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


class _DummyLocation:
    def __init__(self, name):
        self.name = name


class _DummyDso:
    def __init__(self, dso_id, name, dso_type="GX", mag=5.5):
        self.id = dso_id
        self.name = name
        self.type = dso_type
        self.mag = mag
        self.constellation_id = None

    def denormalized_name(self):
        return self.name


class _DummySessionPlanItem:
    def __init__(self, item_id, order, dso=None):
        self.id = item_id
        self.order = order
        self.dso_id = dso.id if dso else None
        self.deepsky_object = dso
        self.double_star = None
        self.double_star_id = None
        self.comet = None
        self.comet_id = None
        self.minor_planet = None
        self.minor_planet_id = None
        self.planet = None
        self.planet_id = None
        self.constell_id = None

    def get_ra(self):
        return 1.0

    def get_dec(self):
        return 2.0

    def get_ra_str_short(self):
        return "01:00"

    def get_dec_str_short(self):
        return "+02:00"


class _DummySessionPlan:
    def __init__(self, items=None):
        self.id = 10
        self.title = "Test Plan"
        self.for_date = SimpleNamespace(isoformat=lambda: "2026-05-10T00:00:00")
        self.is_archived = False
        self.is_public = False
        self.is_anonymous = False
        self.location_id = 4
        self.location = _DummyLocation("Prague")
        self.location_position = None
        self.session_plan_items = items or []

    def find_dso_item_by_id(self, dso_id):
        for item in self.session_plan_items:
            if item.dso_id == dso_id:
                return item
        return None

    def find_double_star_item_by_id(self, _target_id):
        return None

    def find_comet_item_by_id(self, _target_id):
        return None

    def find_minor_planet_item_by_id(self, _target_id):
        return None

    def find_planet_item_by_id(self, _target_id):
        return None


class _DummyQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter_by(self, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None

    def with_entities(self, *_args, **_kwargs):
        return self


class McpSessionPlanReadPayloadsTestCase(unittest.TestCase):
    def test_session_plan_get_payload_serializes_items(self):
        session_plan = _DummySessionPlan(items=[_DummySessionPlanItem(101, 1, dso=_DummyDso(1, "M31"))])

        with patch("app.mcp.session_plan_payloads._load_owned_session_plan", return_value=session_plan), \
             patch(
                 "app.mcp.session_plan_payloads._get_session_plan_astronomical_night",
                 return_value={
                     "astronomicalNightStart": "2026-05-10T22:00:00+02:00",
                     "astronomicalNightEnd": "2026-05-11T03:30:00+02:00",
                 },
             ):
            result = session_plan_payloads.session_plan_get_payload(
                session_plan_id=10,
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="sessionplan:read",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
            )

        self.assertTrue(result["found"])
        self.assertEqual(result["sessionPlan"]["sessionPlanId"], 10)
        self.assertEqual(result["sessionPlan"]["itemCount"], 1)
        self.assertEqual(result["sessionPlan"]["items"][0]["objectId"], "dso:1")
        self.assertEqual(result["sessionPlan"]["astronomicalNightStart"], "2026-05-10T22:00:00+02:00")
        self.assertEqual(result["sessionPlan"]["astronomicalNightEnd"], "2026-05-11T03:30:00+02:00")

    def test_session_plan_items_payload_filters_by_dso_list(self):
        item_in_list = _DummySessionPlanItem(101, 1, dso=_DummyDso(1, "M31"))
        item_outside_list = _DummySessionPlanItem(102, 2, dso=_DummyDso(2, "M42"))
        session_plan = _DummySessionPlan(items=[item_in_list, item_outside_list])

        with get_real_app().app_context():
            with patch("app.mcp.session_plan_payloads._load_owned_session_plan", return_value=session_plan), \
                 patch("app.models.DsoList.query", _DummyQuery([SimpleNamespace(id=7, hidden=False)])), \
                 patch("app.models.DsoListItem.query", _DummyQuery([(1,)])):
                result = session_plan_payloads.session_plan_items_payload(
                    session_plan_id=10,
                    object_types=["dso"],
                    dso_list_id=7,
                    user_id=5,
                    require_scope_if_available_func=lambda _scope: None,
                    required_scope="sessionplan:read",
                    resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                    get_app=lambda: _DummyApp(),
                )

        self.assertTrue(result["found"])
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["identifier"], "M31")

    def test_session_plan_remove_items_payload_commits_once(self):
        session_plan = _DummySessionPlan(items=[_DummySessionPlanItem(101, 1, dso=_DummyDso(1, "M31"))])
        db_session = Mock()

        with patch("app.mcp.session_plan_payloads._load_owned_active_session_plan", return_value=session_plan), \
             patch(
                 "app.mcp.session_plan_payloads._resolve_session_plan_target",
                 side_effect=[
                     ({"query": "M31", "objectType": "dso", "targetId": 1, "objectId": "dso:1"}, None),
                     (None, "not_found"),
                 ],
             ), \
             patch("app.db.session", db_session):
            result = session_plan_payloads.session_plan_remove_items_payload(
                session_plan_id=10,
                queries=["M31", "Unknown"],
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="sessionplan:write",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
                resolve_global_object_func=lambda _query: None,
            )

        self.assertEqual(result["removedCount"], 1)
        db_session.delete.assert_called_once()
        db_session.commit.assert_called_once_with()

    def test_session_plan_clear_payload_deletes_all_items(self):
        session_plan = _DummySessionPlan(
            items=[
                _DummySessionPlanItem(101, 1, dso=_DummyDso(1, "M31")),
                _DummySessionPlanItem(102, 2, dso=_DummyDso(2, "M42")),
            ]
        )
        db_session = Mock()

        with patch("app.mcp.session_plan_payloads._load_owned_active_session_plan", return_value=session_plan), \
             patch("app.db.session", db_session):
            result = session_plan_payloads.session_plan_clear_payload(
                session_plan_id=10,
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="sessionplan:write",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
            )

        self.assertTrue(result["cleared"])
        self.assertEqual(result["removedCount"], 2)
        self.assertEqual(db_session.delete.call_count, 2)
        db_session.commit.assert_called_once_with()

    def test_session_plan_clear_payload_skips_commit_for_empty_plan(self):
        session_plan = _DummySessionPlan(items=[])
        db_session = Mock()

        with patch("app.mcp.session_plan_payloads._load_owned_active_session_plan", return_value=session_plan), \
             patch("app.db.session", db_session):
            result = session_plan_payloads.session_plan_clear_payload(
                session_plan_id=10,
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="sessionplan:write",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
            )

        self.assertTrue(result["cleared"])
        self.assertEqual(result["removedCount"], 0)
        db_session.delete.assert_not_called()
        db_session.commit.assert_not_called()

    def test_session_plan_list_payload_returns_summary_rows(self):
        session_plan = _DummySessionPlan(items=[_DummySessionPlanItem(101, 1, dso=_DummyDso(1, "M31"))])

        with get_real_app().app_context():
            with patch("app.models.SessionPlan.query", _DummyQuery([session_plan])), \
                 patch(
                     "app.mcp.session_plan_payloads._get_session_plan_astronomical_night",
                     return_value={
                         "astronomicalNightStart": "2026-05-10T22:00:00+02:00",
                         "astronomicalNightEnd": "2026-05-11T03:30:00+02:00",
                     },
                 ):
                result = session_plan_payloads.session_plan_list_payload(
                    for_date=None,
                    include_archived=False,
                    user_id=5,
                    require_scope_if_available_func=lambda _scope: None,
                    required_scope="sessionplan:read",
                    resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                    get_app=lambda: _DummyApp(),
                )

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["sessionPlans"][0]["itemCount"], 1)
        self.assertEqual(result["sessionPlans"][0]["astronomicalNightStart"], "2026-05-10T22:00:00+02:00")
        self.assertEqual(result["sessionPlans"][0]["astronomicalNightEnd"], "2026-05-11T03:30:00+02:00")


class McpDsoSourcesPayloadsTestCase(unittest.TestCase):
    def test_dso_list_sources_payload_returns_catalogues_and_dso_lists(self):
        catalogue = SimpleNamespace(id=1, code="M", name="Messier", descr="Classic list")
        dso_list = SimpleNamespace(id=7, name="Caldwell", long_name="Caldwell Catalogue", hidden=False)

        with get_real_app().app_context():
            with patch("app.models.Catalogue.query", _DummyQuery([catalogue])), \
                 patch("app.models.DsoList.query", _DummyQuery([dso_list])):
                result = dso_payloads.dso_list_sources_payload(
                    user_id=5,
                    require_scope_if_available_func=lambda _scope: None,
                    required_scope="dso:read",
                    resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                    get_app=lambda: _DummyApp(),
                )

        self.assertEqual(result["catalogues"][0]["sourceValue"], "M")
        self.assertEqual(result["dsoLists"][0]["sourceValue"], "dso_list:7")
        self.assertEqual(result["sources"][0]["sourceValue"], "WL")

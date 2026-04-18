import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from app.mcp import observation_log_payloads


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


class _DummyObservingSession:
    def __init__(self, **kwargs):
        self.id = kwargs.pop("id", 99)
        self.default_telescope_id = kwargs.pop("default_telescope_id", None)
        self.date_from = kwargs.pop("date_from", datetime(2026, 5, 10, 21, 0, 0))
        self.date_to = kwargs.pop("date_to", datetime(2026, 5, 11, 3, 0, 0))
        self.is_finished = kwargs.pop("is_finished", False)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def find_observation_by_dso_id(self, target_id):
        return getattr(self, "existing_dso", None) if getattr(self, "existing_dso_id", None) == target_id else None

    def find_observation_by_double_star_id(self, target_id):
        return getattr(self, "existing_double_star", None) if getattr(self, "existing_double_star_id", None) == target_id else None

    def find_observation_by_planet_id(self, target_id):
        return getattr(self, "existing_planet", None) if getattr(self, "existing_planet_id", None) == target_id else None

    def find_observation_by_planet_moon_id(self, target_id):
        return getattr(self, "existing_planet_moon", None) if getattr(self, "existing_planet_moon_id", None) == target_id else None

    def find_observation_by_comet_id(self, target_id):
        return getattr(self, "existing_comet", None) if getattr(self, "existing_comet_id", None) == target_id else None

    def find_observation_by_minor_planet_id(self, target_id):
        return getattr(self, "existing_minor_planet", None) if getattr(self, "existing_minor_planet_id", None) == target_id else None


class _DummyObservation:
    def __init__(self, **kwargs):
        self.id = kwargs.pop("id", 501)
        self.deepsky_objects = []
        for key, value in kwargs.items():
            setattr(self, key, value)


class ObservationLogPayloadsTestCase(unittest.TestCase):
    def test_upsert_creates_new_dso_observation_in_active_session(self):
        db_session = Mock()
        session = _DummyObservingSession(default_telescope_id=42)
        target = object()
        setattr(target, "id", 7)

        with patch("app.mcp.observation_log_payloads._load_owned_active_observing_session", return_value=session), \
             patch("app.mcp.observation_log_payloads._create_observation_for_target", return_value=_DummyObservation(id=77)) as create_mock, \
             patch("app.mcp.observation_log_payloads._resolve_observation_target", return_value=({"objectType": "dso", "targetId": 7, "targetObject": target, "objectId": "dso:7"}, None)), \
             patch("app.db.session", db_session):
            result = observation_log_payloads.observation_log_upsert_payload(
                object_id=None,
                query="M31",
                observing_session_id=None,
                notes="nice core",
                date_from=None,
                telescope_id=None,
                eyepiece_id=None,
                filter_id=None,
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="observationlog:write",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
                resolve_global_object_func=lambda query: None,
                parse_observation_object_id_func=lambda object_id: None,
            )

        self.assertTrue(result["upserted"])
        self.assertTrue(result["created"])
        self.assertEqual(result["objectType"], "dso")
        create_mock.assert_called_once()
        db_session.commit.assert_called_once_with()

    def test_upsert_updates_existing_observation(self):
        db_session = Mock()
        existing = _DummyObservation(id=88, notes="old", telescope_id=1, eyepiece_id=2, filter_id=3, date_from=datetime(2026, 5, 10, 21, 0, 0), date_to=datetime(2026, 5, 10, 21, 0, 0))
        session = _DummyObservingSession(existing_dso=existing, existing_dso_id=7)
        target = object()
        setattr(target, "id", 7)

        with patch("app.mcp.observation_log_payloads._load_owned_observing_session", return_value=session), \
             patch("app.mcp.observation_log_payloads._resolve_observation_target", return_value=({"objectType": "dso", "targetId": 7, "targetObject": target, "objectId": "dso:7"}, None)), \
             patch("app.db.session", db_session):
            result = observation_log_payloads.observation_log_upsert_payload(
                object_id="dso:7",
                query=None,
                observing_session_id=99,
                notes="updated",
                date_from="2026-05-10T22:10:00",
                telescope_id=11,
                eyepiece_id=None,
                filter_id=13,
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="observationlog:write",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
                resolve_global_object_func=lambda query: None,
                parse_observation_object_id_func=observation_log_payloads.parse_observation_object_id,
            )

        self.assertTrue(result["updated"])
        self.assertEqual(existing.notes, "updated")
        self.assertEqual(existing.telescope_id, 11)
        self.assertEqual(existing.filter_id, 13)
        db_session.add.assert_called_once_with(existing)
        db_session.commit.assert_called_once_with()

    def test_upsert_returns_no_active_session(self):
        with patch("app.mcp.observation_log_payloads._load_owned_active_observing_session", return_value=None), \
             patch("app.mcp.observation_log_payloads._resolve_observation_target", return_value=({"objectType": "planet", "targetId": 3, "targetObject": object(), "objectId": "planet:3"}, None)):
            result = observation_log_payloads.observation_log_upsert_payload(
                object_id=None,
                query="Saturn",
                observing_session_id=None,
                notes=None,
                date_from=None,
                telescope_id=None,
                eyepiece_id=None,
                filter_id=None,
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="observationlog:write",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
                resolve_global_object_func=lambda query: None,
                parse_observation_object_id_func=lambda object_id: None,
            )

        self.assertFalse(result["upserted"])
        self.assertEqual(result["reason"], "no_active_observing_session")

    def test_upsert_returns_invalid_arguments_when_query_and_object_id_conflict(self):
        session = _DummyObservingSession()
        with patch("app.mcp.observation_log_payloads._load_owned_active_observing_session", return_value=session):
            result = observation_log_payloads.observation_log_upsert_payload(
                object_id="dso:7",
                query="M31",
                observing_session_id=None,
                notes=None,
                date_from=None,
                telescope_id=None,
                eyepiece_id=None,
                filter_id=None,
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="observationlog:write",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
                resolve_global_object_func=lambda query: None,
                parse_observation_object_id_func=observation_log_payloads.parse_observation_object_id,
            )

        self.assertFalse(result["upserted"])
        self.assertEqual(result["reason"], "invalid_arguments")

    def test_upsert_rejects_finished_session(self):
        session = _DummyObservingSession(is_finished=True)
        target = object()
        setattr(target, "id", 3)
        with patch("app.mcp.observation_log_payloads._load_owned_observing_session", return_value=session), \
             patch("app.mcp.observation_log_payloads._resolve_observation_target", return_value=({"objectType": "planet", "targetId": 3, "targetObject": target, "objectId": "planet:3"}, None)):
            result = observation_log_payloads.observation_log_upsert_payload(
                object_id="planet:3",
                query=None,
                observing_session_id=99,
                notes=None,
                date_from=None,
                telescope_id=None,
                eyepiece_id=None,
                filter_id=None,
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="observationlog:write",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
                resolve_global_object_func=lambda query: None,
                parse_observation_object_id_func=observation_log_payloads.parse_observation_object_id,
            )

        self.assertFalse(result["upserted"])
        self.assertEqual(result["reason"], "session_finished")


class ObservationObjectIdParsingTestCase(unittest.TestCase):
    def test_parse_observation_object_id_supports_planet_moon(self):
        self.assertEqual(observation_log_payloads.parse_observation_object_id("planet_moon:12"), ("planet_moon", 12))

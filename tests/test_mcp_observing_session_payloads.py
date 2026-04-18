import unittest
from unittest.mock import Mock, patch

from app.mcp import observing_session_payloads
from app.models import Seeing, Transparency


class _DummyContextManager:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyApp:
    def app_context(self):
        return _DummyContextManager()


class _DummyObservingSession:
    def __init__(self, **kwargs):
        self.id = kwargs.pop("id", 501)
        for key, value in kwargs.items():
            setattr(self, key, value)


class ObservingSessionCreatePayloadTestCase(unittest.TestCase):
    def test_create_returns_created_payload_and_commits(self):
        db_session = Mock()

        with patch(
            "app.mcp.observing_session_payloads._resolve_location_for_session_plan_create",
            return_value=(42, None, None, []),
        ), patch(
            "app.mcp.observing_session_payloads._deactivate_all_user_observing_sessions"
        ) as deactivate_mock, patch(
            "app.db.session",
            db_session,
        ), patch(
            "app.models.ObservingSession",
            side_effect=lambda **kwargs: _DummyObservingSession(**kwargs),
        ):
            result = observing_session_payloads.observing_session_create_payload(
                date_from="2026-05-10T21:30:00",
                date_to="2026-05-11T01:15:00",
                location_id=None,
                location_name="Prague",
                location=None,
                title=" Session ",
                sqm="21.5",
                faintest_star="6.2",
                seeing="GOOD",
                transparency="AVERAGE",
                weather=" clear ",
                equipment=" dob ",
                notes=" notes ",
                is_public=True,
                is_finished=False,
                is_active=True,
                rating=3,
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="observingsession:write",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
            )

        self.assertEqual(result["reason"], "created")
        self.assertEqual(result["observingSessionId"], 501)
        self.assertEqual(result["locationId"], 42)
        self.assertTrue(result["isActive"])
        created_session = db_session.add.call_args.args[0]
        self.assertEqual(created_session.title, "Session")
        self.assertEqual(created_session.sqm, 21.5)
        self.assertEqual(created_session.faintest_star, 6.2)
        self.assertEqual(created_session.seeing, Seeing.GOOD)
        self.assertEqual(created_session.transparency, Transparency.AVERAGE)
        self.assertEqual(created_session.weather, "clear")
        self.assertEqual(created_session.equipment, "dob")
        self.assertEqual(created_session.notes, "notes")
        self.assertEqual(created_session.rating, 6)
        self.assertIsNone(created_session.default_telescope_id)
        deactivate_mock.assert_called_once_with(resolved_user_id=5)
        db_session.commit.assert_called_once_with()

    def test_create_returns_location_not_found(self):
        with patch(
            "app.mcp.observing_session_payloads._resolve_location_for_session_plan_create",
            return_value=(None, None, "location_not_found", []),
        ), patch("app.db.session") as db_session:
            result = observing_session_payloads.observing_session_create_payload(
                date_from="2026-05-10T21:30:00",
                date_to="2026-05-11T01:15:00",
                location_id=None,
                location_name="Unknown",
                location=None,
                title=None,
                sqm=None,
                faintest_star=None,
                seeing=None,
                transparency=None,
                weather=None,
                equipment=None,
                notes=None,
                is_public=False,
                is_finished=False,
                is_active=False,
                rating=None,
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="observingsession:write",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
            )

        self.assertFalse(result["created"])
        self.assertEqual(result["reason"], "location_not_found")
        self.assertEqual(result["title"], "Unknown")
        db_session.add.assert_not_called()
        db_session.commit.assert_not_called()

    def test_create_returns_location_ambiguous_with_candidates(self):
        candidates = [{"locationId": 1, "locationName": "Prague"}]
        with patch(
            "app.mcp.observing_session_payloads._resolve_location_for_session_plan_create",
            return_value=(None, None, "location_ambiguous", candidates),
        ):
            result = observing_session_payloads.observing_session_create_payload(
                date_from="2026-05-10T21:30:00",
                date_to="2026-05-11T01:15:00",
                location_id=None,
                location_name="Prag",
                location=None,
                title=None,
                sqm=None,
                faintest_star=None,
                seeing=None,
                transparency=None,
                weather=None,
                equipment=None,
                notes=None,
                is_public=False,
                is_finished=False,
                is_active=False,
                rating=None,
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="observingsession:write",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
            )

        self.assertFalse(result["created"])
        self.assertEqual(result["reason"], "location_ambiguous")
        self.assertEqual(result["candidates"], candidates)

    def test_create_rejects_reversed_date_range(self):
        result = observing_session_payloads.observing_session_create_payload(
            date_from="2026-05-11T01:15:00",
            date_to="2026-05-10T21:30:00",
            location_id=None,
            location_name="Prague",
            location=None,
            title=None,
            sqm=None,
            faintest_star=None,
            seeing=None,
            transparency=None,
            weather=None,
            equipment=None,
            notes=None,
            is_public=False,
            is_finished=False,
            is_active=True,
            rating=None,
            user_id=5,
            require_scope_if_available_func=lambda _scope: None,
            required_scope="observingsession:write",
            resolve_mcp_user_id_func=lambda user_id: user_id or 0,
            get_app=lambda: _DummyApp(),
        )

        self.assertFalse(result["created"])
        self.assertEqual(result["reason"], "invalid_date_range")
        self.assertTrue(result["isActive"])

    def test_create_rejects_range_longer_than_one_night(self):
        result = observing_session_payloads.observing_session_create_payload(
            date_from="2026-05-10T21:30:00",
            date_to="2026-05-12T01:15:00",
            location_id=None,
            location_name="Prague",
            location=None,
            title=None,
            sqm=None,
            faintest_star=None,
            seeing=None,
            transparency=None,
            weather=None,
            equipment=None,
            notes=None,
            is_public=False,
            is_finished=False,
            is_active=False,
            rating=None,
            user_id=5,
            require_scope_if_available_func=lambda _scope: None,
            required_scope="observingsession:write",
            resolve_mcp_user_id_func=lambda user_id: user_id or 0,
            get_app=lambda: _DummyApp(),
        )

        self.assertFalse(result["created"])
        self.assertEqual(result["reason"], "invalid_date_range")

    def test_create_finished_session_forces_inactive(self):
        db_session = Mock()

        with patch(
            "app.mcp.observing_session_payloads._resolve_location_for_session_plan_create",
            return_value=(42, None, None, []),
        ), patch(
            "app.mcp.observing_session_payloads._deactivate_all_user_observing_sessions"
        ) as deactivate_mock, patch(
            "app.db.session",
            db_session,
        ), patch(
            "app.models.ObservingSession",
            side_effect=lambda **kwargs: _DummyObservingSession(**kwargs),
        ):
            result = observing_session_payloads.observing_session_create_payload(
                date_from="2026-05-10T21:30:00",
                date_to="2026-05-11T01:15:00",
                location_id=42,
                location_name=None,
                location=None,
                title="Finished",
                sqm=None,
                faintest_star=None,
                seeing=None,
                transparency=None,
                weather=None,
                equipment=None,
                notes=None,
                is_public=False,
                is_finished=True,
                is_active=True,
                rating=None,
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="observingsession:write",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
            )

        self.assertTrue(result["created"])
        self.assertFalse(result["isActive"])
        self.assertTrue(result["isFinished"])
        deactivate_mock.assert_not_called()

    def test_create_defaults_seeing_transparency_and_rating(self):
        db_session = Mock()

        with patch(
            "app.mcp.observing_session_payloads._resolve_location_for_session_plan_create",
            return_value=(None, "49.0,14.0", None, []),
        ), patch(
            "app.db.session",
            db_session,
        ), patch(
            "app.models.ObservingSession",
            side_effect=lambda **kwargs: _DummyObservingSession(**kwargs),
        ):
            observing_session_payloads.observing_session_create_payload(
                date_from="2026-05-10T21:30:00",
                date_to="2026-05-10T23:15:00",
                location_id=None,
                location_name=None,
                location="49.0,14.0",
                title=None,
                sqm=None,
                faintest_star=None,
                seeing=None,
                transparency="",
                weather="",
                equipment="",
                notes="",
                is_public=False,
                is_finished=False,
                is_active=False,
                rating="",
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="observingsession:write",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
            )

        created_session = db_session.add.call_args.args[0]
        self.assertEqual(created_session.seeing, Seeing.AVERAGE)
        self.assertEqual(created_session.transparency, Transparency.AVERAGE)
        self.assertEqual(created_session.rating, 0)
        self.assertEqual(created_session.location_position, "49.0,14.0")



class ObservingSessionActivePayloadTestCase(unittest.TestCase):
    def test_set_active_activates_session_and_commits(self):
        db_session = Mock()
        observing_session = _DummyObservingSession(id=12, is_active=False, is_finished=False)

        with patch(
            "app.mcp.observing_session_payloads._load_owned_observing_session",
            return_value=observing_session,
        ), patch(
            "app.mcp.observing_session_payloads._deactivate_all_user_observing_sessions"
        ) as deactivate_mock, patch(
            "app.db.session",
            db_session,
        ):
            result = observing_session_payloads.observing_session_set_active_payload(
                observing_session_id=12,
                is_active=True,
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="observingsession:write",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
            )

        self.assertTrue(result["updated"])
        self.assertTrue(result["isActive"])
        deactivate_mock.assert_called_once_with(resolved_user_id=5)
        db_session.add.assert_called_once_with(observing_session)
        db_session.commit.assert_called_once_with()

    def test_set_active_deactivates_session(self):
        db_session = Mock()
        observing_session = _DummyObservingSession(id=12, is_active=True, is_finished=False)

        with patch(
            "app.mcp.observing_session_payloads._load_owned_observing_session",
            return_value=observing_session,
        ), patch(
            "app.mcp.observing_session_payloads._deactivate_all_user_observing_sessions"
        ) as deactivate_mock, patch(
            "app.db.session",
            db_session,
        ):
            result = observing_session_payloads.observing_session_set_active_payload(
                observing_session_id=12,
                is_active=False,
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="observingsession:write",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
            )

        self.assertTrue(result["updated"])
        self.assertFalse(result["isActive"])
        deactivate_mock.assert_not_called()
        db_session.add.assert_called_once_with(observing_session)
        db_session.commit.assert_called_once_with()

    def test_set_active_rejects_finished_session(self):
        db_session = Mock()
        observing_session = _DummyObservingSession(id=12, is_active=False, is_finished=True)

        with patch(
            "app.mcp.observing_session_payloads._load_owned_observing_session",
            return_value=observing_session,
        ), patch("app.db.session", db_session):
            result = observing_session_payloads.observing_session_set_active_payload(
                observing_session_id=12,
                is_active=True,
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="observingsession:write",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
            )

        self.assertFalse(result["updated"])
        self.assertEqual(result["reason"], "session_finished")
        db_session.add.assert_not_called()
        db_session.commit.assert_not_called()

    def test_set_active_returns_not_found(self):
        db_session = Mock()

        with patch(
            "app.mcp.observing_session_payloads._load_owned_observing_session",
            return_value=None,
        ), patch("app.db.session", db_session):
            result = observing_session_payloads.observing_session_set_active_payload(
                observing_session_id=12,
                is_active=True,
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="observingsession:write",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
            )

        self.assertFalse(result["updated"])
        self.assertEqual(result["reason"], "observing_session_not_found")
        db_session.add.assert_not_called()
        db_session.commit.assert_not_called()

    def test_get_active_returns_summary(self):
        observing_session = _DummyObservingSession(
            id=12,
            title="Night session",
            date_from=None,
            date_to=None,
            location_id=4,
            location_position=None,
            is_public=False,
            is_finished=False,
            is_active=True,
        )

        with patch(
            "app.mcp.observing_session_payloads._load_owned_active_observing_session",
            return_value=observing_session,
        ):
            result = observing_session_payloads.observing_session_get_active_payload(
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="observingsession:read",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
            )

        self.assertTrue(result["found"])
        self.assertEqual(result["reason"], "found")
        self.assertEqual(result["observingSession"]["observingSessionId"], 12)
        self.assertTrue(result["observingSession"]["isActive"])

    def test_get_active_returns_not_found(self):
        with patch(
            "app.mcp.observing_session_payloads._load_owned_active_observing_session",
            return_value=None,
        ):
            result = observing_session_payloads.observing_session_get_active_payload(
                user_id=5,
                require_scope_if_available_func=lambda _scope: None,
                required_scope="observingsession:read",
                resolve_mcp_user_id_func=lambda user_id: user_id or 0,
                get_app=lambda: _DummyApp(),
            )

        self.assertFalse(result["found"])
        self.assertEqual(result["reason"], "no_active_session")
        self.assertIsNone(result["observingSession"])

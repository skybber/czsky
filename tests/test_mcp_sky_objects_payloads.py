import unittest

from app.mcp import sky_objects_payloads


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


class McpSkyObjectsPayloadsTestCase(unittest.TestCase):
    def test_resolve_many_returns_per_item_results(self):
        resolved_objects = {
            "M31": {"object_type": "dso", "object": object()},
            "Saturn": {"object_type": "planet", "object": object()},
        }

        result = sky_objects_payloads.resolve_sky_objects_payload(
            queries=[" M31 ", "unknown", "", "Saturn"],
            get_app=lambda: _DummyApp(),
            resolve_global_object=lambda query: resolved_objects.get(query),
            format_resolved_object=lambda query, resolved: {
                "identifier": query,
                "object_type": resolved["object_type"],
            },
        )

        self.assertEqual(
            result,
            {
                "results": [
                    {
                        "query": "M31",
                        "found": True,
                        "result": {"identifier": "M31", "object_type": "dso"},
                    },
                    {
                        "query": "unknown",
                        "found": False,
                        "result": None,
                    },
                    {
                        "query": "",
                        "found": False,
                        "result": None,
                    },
                    {
                        "query": "Saturn",
                        "found": True,
                        "result": {"identifier": "Saturn", "object_type": "planet"},
                    },
                ]
            },
        )

    def test_resolve_many_rejects_empty_queries(self):
        with self.assertRaises(ValueError):
            sky_objects_payloads.resolve_sky_objects_payload(
                queries=[],
                get_app=lambda: _DummyApp(),
                resolve_global_object=lambda _query: None,
                format_resolved_object=lambda _query, _resolved: {},
            )

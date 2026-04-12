import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.commons.mcp_sky_object_formatters import format_resolved_object


class McpSkyObjectFormattersTestCase(unittest.TestCase):
    def test_formats_earth_moon(self):
        result = format_resolved_object(
            "moon",
            {
                "matched_by": "earth_moon",
                "object_type": "earth_moon",
                "object": {"identifier": "moon", "title": "Moon"},
            },
        )

        self.assertEqual(result["object_type"], "earth_moon")
        self.assertEqual(result["summary"]["planet"], "Earth")

    def test_formats_planet_moon(self):
        planet = SimpleNamespace(iau_code="JUPITER", get_localized_name=lambda: "Jupiter")
        planet_moon = SimpleNamespace(name="Io", iau_number=1, planet=planet)

        result = format_resolved_object(
            "Io",
            {
                "matched_by": "planet_moon",
                "object_type": "planet_moon",
                "object": planet_moon,
            },
        )

        self.assertEqual(result["title"], "Io")
        self.assertEqual(result["details"]["planet"], "Jupiter")

    def test_formats_dso_aliases(self):
        dso = SimpleNamespace(
            id=7,
            master_id=None,
            constellation_id=None,
            denormalized_name=lambda: "M 1",
            common_name="Crab Nebula",
            name="M1",
            ra=1.0,
            dec=2.0,
            ra_str=lambda: "01:00:00.0",
            dec_str=lambda: "+02:00:00.0",
            get_constellation_iau_code=lambda: "Tau",
            mag=8.4,
            major_axis=7.0,
            minor_axis=5.0,
            type="SNR",
            subtype=None,
            surface_bright=None,
            position_angle=None,
            axis_ratio=None,
            distance=None,
            catalogue_id=1,
            descr="desc",
            import_source=1,
        )
        child = SimpleNamespace(name="NGC1952")

        child_query = SimpleNamespace(all=lambda: [child])
        with patch("app.commons.mcp_sky_object_formatters.DeepskyObject.query") as query_mock, \
             patch(
                 "app.commons.mcp_sky_object_formatters.get_dso_descriptions_with_master_fallback",
                 return_value=(SimpleNamespace(text="Editor text"), [("<100", "Small scope")], None),
             ):
            query_mock.filter_by.return_value = child_query
            result = format_resolved_object(
                "M1",
                {
                    "matched_by": "dso",
                    "object_type": "dso",
                    "object": dso,
                },
            )

        self.assertEqual(result["identifier"], "M1")
        self.assertIn("NGC 1952", result["aliases"])
        self.assertEqual(result["details"]["editor_description"], "Editor text")
        self.assertEqual(result["details"]["aperture_descriptions"][0]["aperture_class"], "<100")

    def test_formats_comet_with_recent_cobs_observations(self):
        comet = SimpleNamespace(
            id=42,
            designation="C/2023 A3",
            comet_id="C2023A3",
            orbit_type="C",
            perihelion_distance_au=0.39,
            eccentricity=1.0,
            inclination_degrees=139.0,
            is_disintegrated=False,
            cur_ra=1.0,
            cur_dec=2.0,
            cur_ra_str=lambda: "01:00:00.0",
            cur_dec_str=lambda: "+02:00:00.0",
            cur_constell=lambda: None,
            cur_constellation_iau_code=lambda: "Ser",
            displayed_mag=lambda: "7.5",
        )

        with patch(
            "app.commons.mcp_sky_object_formatters.fetch_recent_cobs_observations",
            return_value=[
                {
                    "obs_date": "2025-10-01 20:15:00",
                    "magnitude": 7.5,
                    "coma_diameter": 4.0,
                    "comment": "Good visibility",
                }
            ],
        ):
            result = format_resolved_object(
                "C/2023 A3",
                {
                    "matched_by": "comet",
                    "object_type": "comet",
                    "object": comet,
                },
            )

        self.assertEqual(result["identifier"], "C2023A3")
        self.assertEqual(result["details"]["recent_cobs_observations"][0]["obs_date"], "2025-10-01 20:15:00")
        self.assertEqual(result["details"]["recent_cobs_observations"][0]["comment"], "Good visibility")

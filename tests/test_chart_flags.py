import unittest
from types import SimpleNamespace

from app.commons.chart_generator import FlagValue, _get_chart_legend_flags


def _form(**overrides):
    fields = [
        'dss_layer', 'is_equatorial', 'mirror_x', 'mirror_y', 'show_comet_tail', 'show_constell_borders',
        'show_constell_shapes', 'show_dso', 'show_dso_mag', 'show_equatorial_grid', 'show_horizontal_grid',
        'show_milky_way', 'show_picker', 'show_solar_system', 'show_star_labels', 'show_telrad',
    ]
    values = {name: 'false' for name in fields}
    values['dss_layer'] = ''
    values.update(overrides)
    return SimpleNamespace(**{name: SimpleNamespace(data=value) for name, value in values.items()})


class ChartFlagsTestCase(unittest.TestCase):
    def test_telrad_is_in_chart_flags_for_scene_widgets(self):
        chart_flags, legend_flags = _get_chart_legend_flags(_form(show_telrad='true'))

        self.assertIn(FlagValue.FOV_TELRAD.value, chart_flags)
        self.assertIn(FlagValue.FOV_TELRAD.value, legend_flags)

    def test_telrad_off_is_not_in_flags(self):
        chart_flags, legend_flags = _get_chart_legend_flags(_form(show_telrad='false'))

        self.assertNotIn(FlagValue.FOV_TELRAD.value, chart_flags)
        self.assertNotIn(FlagValue.FOV_TELRAD.value, legend_flags)


if __name__ == '__main__':
    unittest.main()

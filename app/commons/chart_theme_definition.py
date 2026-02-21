from collections import OrderedDict
import hashlib
import json

from flask import (
    current_app,
)

MAX_LINE_SPACE = 10.0
MAX_LINE_WIDTH = 3.0
MAX_FONT_SIZE = 20.0
MAX_FONT_SCALE = 5.0


class ChartThemeDefinition:
    def __init__(self):
        self.background_color = None
        self.bayer_label_font_scale = None
        self.cardinal_directions_color = None
        self.cardinal_directions_font_scale = None
        self.comet_highlight_color = None
        self.comet_tail_color = None
        self.comet_tail_length = None
        self.comet_tail_half_angle_deg = None
        self.comet_tail_side_scale = None
        self.constellation_border_color = None
        self.constellation_border_linewidth = None
        self.constellation_hl_border_color = None
        self.constellation_lines_color = None
        self.constellation_linespace = None
        self.constellation_linewidth = None
        self.draw_color = None
        self.dso_color = None
        self.dso_dynamic_brightness = None
        self.dso_linewidth = None
        self.ext_label_font_scale = None
        self.eyepiece_color = None
        self.eyepiece_linewidth = None
        self.flamsteed_label_font_scale = None
        self.font_size = None
        self.galaxy_cluster_color = None
        self.galaxy_cluster_linewidth = None
        self.galaxy_color = None
        self.grid_color = None
        self.grid_linewidth = None
        self.highlight_color = None
        self.highlight_label_font_scale = None
        self.highlight_linewidth = None
        self.horizon_color = None
        self.horizon_linewidth = None
        self.jupiter_color = None
        self.label_color = None
        self.legend_font_scale = None
        self.legend_linewidth = None
        self.light_mode = None
        self.mars_color = None
        self.mercury_color = None
        self.milky_way_color = None
        self.milky_way_linewidth = None
        self.moon_color = None
        self.nebula_color = None
        self.nebula_linewidth = None
        self.neptune_color = None
        self.open_cluster_linewidth = None
        self.outlined_dso_label_font_scale = None
        self.picker_color = None
        self.picker_linewidth = None
        self.picker_radius = None
        self.pluto_color = None
        self.saturn_color = None
        self.show_nebula_outlines = None
        self.star_cluster_color = None
        self.star_colors = None
        self.star_mag_shift = None
        self.sun_color = None
        self.telrad_color = None
        self.telrad_linewidth = None
        self.uranus_color = None
        self.venus_color = None

    def validate_set(self, defs, errors=None):
        self.background_color = self._parse_color(defs, 'background_color', self.background_color, errors)
        self.bayer_label_font_scale = self._parse_font_scale(defs, 'bayer_label_font_scale', self.bayer_label_font_scale, errors)
        self.cardinal_directions_color = self._parse_color(defs, 'cardinal_directions_color', self.cardinal_directions_color, errors)
        self.cardinal_directions_font_scale = self._parse_font_scale(defs, 'cardinal_directions_font_scale', self.cardinal_directions_font_scale, errors)
        self.comet_highlight_color = self._parse_color(defs, 'comet_highlight_color', self.comet_highlight_color, errors)
        self.comet_tail_color = self._parse_color(defs, 'comet_tail_color', self.comet_tail_color, errors)
        self.comet_tail_length = self._parse_float(defs, 'comet_tail_length', self.comet_tail_length, errors)
        self.comet_tail_half_angle_deg = self._parse_float(defs, 'comet_tail_half_angle_deg', self.comet_tail_half_angle_deg, errors)
        self.comet_tail_side_scale = self._parse_float(defs, 'comet_tail_side_scale', self.comet_tail_side_scale, errors)
        self.constellation_border_color = self._parse_color(defs, 'constellation_border_color', self.constellation_border_color, errors)
        self.constellation_border_linewidth = self._parse_linewidth(defs, 'constellation_border_linewidth', self.constellation_border_linewidth, errors)
        self.constellation_hl_border_color = self._parse_color(defs, 'constellation_hl_border_color', self.constellation_hl_border_color, errors)
        self.constellation_lines_color = self._parse_color(defs, 'constellation_lines_color', self.constellation_lines_color, errors)
        self.constellation_linespace = self._parse_linespace(defs, 'constellation_linespace', self.constellation_linespace, errors)
        self.constellation_linewidth = self._parse_linewidth(defs, 'constellation_linewidth', self.constellation_linewidth, errors)
        self.draw_color = self._parse_color(defs, 'draw_color', self.draw_color, errors)
        self.dso_color = self._parse_color(defs, 'dso_color', self.dso_color, errors)
        self.dso_dynamic_brightness = self._parse_bool(defs, 'dso_dynamic_brightness', self.dso_dynamic_brightness, errors)
        self.dso_linewidth = self._parse_linewidth(defs, 'dso_linewidth', self.dso_linewidth, errors)
        self.ext_label_font_scale = self._parse_font_scale(defs, 'ext_label_font_scale', self.ext_label_font_scale, errors)
        self.eyepiece_color = self._parse_color(defs, 'eyepiece_color', self.eyepiece_color, errors)
        self.eyepiece_linewidth = self._parse_linewidth(defs, 'eyepiece_linewidth', self.eyepiece_linewidth, errors)
        self.flamsteed_label_font_scale = self._parse_font_scale(defs, 'flamsteed_label_font_scale', self.flamsteed_label_font_scale, errors)
        self.font_size = self._parse_font_size(defs, 'font_size', self.font_size, errors)
        self.galaxy_cluster_color = self._parse_color(defs, 'galaxy_cluster_color', self.galaxy_cluster_color, errors)
        self.galaxy_cluster_linewidth = self._parse_linewidth(defs, 'galaxy_cluster_linewidth', self.galaxy_cluster_linewidth, errors)
        self.galaxy_color = self._parse_color(defs, 'galaxy_color', self.galaxy_color, errors)
        self.grid_color = self._parse_color(defs, 'grid_color', self.grid_color, errors)
        self.grid_linewidth = self._parse_linewidth(defs, 'grid_linewidth', self.grid_linewidth, errors)
        self.highlight_color = self._parse_color(defs, 'highlight_color', self.highlight_color, errors)
        self.highlight_label_font_scale = self._parse_font_scale(defs, 'highlight_label_font_scale', self.highlight_label_font_scale, errors)
        self.highlight_linewidth = self._parse_linewidth(defs, 'highlight_linewidth', self.highlight_linewidth, errors)
        self.horizon_color = self._parse_color(defs, 'horizon_color', self.horizon_color, errors)
        self.horizon_linewidth = self._parse_linewidth(defs, 'horizon_linewidth', self.horizon_linewidth, errors)
        self.jupiter_color = self._parse_color(defs, 'jupiter_color', self.jupiter_color, errors)
        self.label_color = self._parse_color(defs, 'label_color', self.label_color, errors)
        self.legend_font_scale = self._parse_font_scale(defs, 'legend_font_scale', self.legend_font_scale, errors)
        self.legend_linewidth = self._parse_linewidth(defs, 'legend_linewidth', self.legend_linewidth, errors)
        self.light_mode = self._parse_bool(defs, 'light_mode', self.light_mode, errors)
        self.mars_color = self._parse_color(defs, 'mars_color', self.mars_color, errors)
        self.mercury_color = self._parse_color(defs, 'mercury_color', self.mercury_color, errors)
        self.milky_way_color = self._parse_color(defs, 'milky_way_color', self.milky_way_color, errors)
        self.milky_way_linewidth = self._parse_linewidth(defs, 'milky_way_linewidth', self.milky_way_linewidth, errors)
        self.moon_color = self._parse_color(defs, 'moon_color', self.moon_color, errors)
        self.nebula_color = self._parse_color(defs, 'nebula_color', self.nebula_color, errors)
        self.nebula_linewidth = self._parse_linewidth(defs, 'nebula_linewidth', self.nebula_linewidth, errors)
        self.neptune_color = self._parse_color(defs, 'neptune_color', self.neptune_color, errors)
        self.open_cluster_linewidth = self._parse_linewidth(defs, 'open_cluster_linewidth', self.open_cluster_linewidth, errors)
        self.outlined_dso_label_font_scale = self._parse_font_scale(defs, 'outlined_dso_label_font_scale', self.outlined_dso_label_font_scale, errors)
        self.picker_color = self._parse_color(defs, 'picker_color', self.picker_color, errors)
        self.picker_linewidth = self._parse_linewidth(defs, 'picker_linewidth', self.picker_linewidth, errors)
        self.picker_radius = self._parse_float(defs, 'picker_radius', self.picker_radius, errors)
        self.pluto_color = self._parse_color(defs, 'pluto_color', self.pluto_color, errors)
        self.saturn_color = self._parse_color(defs, 'saturn_color', self.saturn_color, errors)
        self.show_nebula_outlines = self._parse_bool(defs, 'show_nebula_outlines', self.show_nebula_outlines, errors)
        self.star_cluster_color = self._parse_color(defs, 'star_cluster_color', self.star_cluster_color, errors)
        self.star_colors = self._parse_bool(defs, 'star_colors', self.star_colors, errors)
        self.star_mag_shift = self._parse_float_with_min_max(defs, 'star_mag_shift', self.star_mag_shift, 0, 5, errors)
        self.sun_color = self._parse_color(defs, 'sun_color', self.sun_color, errors)
        self.telrad_color = self._parse_color(defs, 'telrad_color', self.telrad_color, errors)
        self.telrad_linewidth = self._parse_linewidth(defs, 'telrad_linewidth', self.telrad_linewidth, errors)
        self.uranus_color = self._parse_color(defs, 'uranus_color', self.uranus_color, errors)
        self.venus_color = self._parse_color(defs, 'venus_color', self.venus_color, errors)

    def fill_config(self, config):
        config.background_color = self.background_color
        config.bayer_label_font_scale = self.bayer_label_font_scale
        config.cardinal_directions_color = self.cardinal_directions_color
        config.cardinal_directions_font_scale = self.cardinal_directions_font_scale
        if hasattr(config, 'comet_highlight_color'):
            config.comet_highlight_color = self.comet_highlight_color
        if hasattr(config, 'comet_tail_color'):
            config.comet_tail_color = self.comet_tail_color
        if hasattr(config, 'comet_tail_length'):
            config.comet_tail_length = self.comet_tail_length
        if hasattr(config, 'comet_tail_half_angle_deg'):
            config.comet_tail_half_angle_deg = self.comet_tail_half_angle_deg
        if hasattr(config, 'comet_tail_side_scale'):
            config.comet_tail_side_scale = self.comet_tail_side_scale
        config.constellation_border_color = self.constellation_border_color
        config.constellation_border_linewidth = self.constellation_border_linewidth
        config.constellation_hl_border_color = self.constellation_hl_border_color
        config.constellation_lines_color = self.constellation_lines_color
        config.constellation_linespace = self.constellation_linespace
        config.constellation_linewidth = self.constellation_linewidth
        config.draw_color = self.draw_color
        config.dso_color = self.dso_color
        config.dso_dynamic_brightness = self.dso_dynamic_brightness
        config.dso_linewidth = self.dso_linewidth
        config.ext_label_font_scale = self.ext_label_font_scale
        config.eyepiece_color = self.eyepiece_color
        config.eyepiece_linewidth = self.eyepiece_linewidth
        config.flamsteed_label_font_scale = self.flamsteed_label_font_scale
        config.font_size = self.font_size
        config.galaxy_cluster_color = self.galaxy_cluster_color
        config.galaxy_cluster_linewidth = self.galaxy_cluster_linewidth
        config.galaxy_color = self.galaxy_color
        config.grid_color = self.grid_color
        config.grid_linewidth = self.grid_linewidth
        config.highlight_color = self.highlight_color
        config.highlight_label_font_scale = self.highlight_label_font_scale
        config.highlight_linewidth = self.highlight_linewidth
        config.horizon_color = self.horizon_color
        config.horizon_linewidth = self.horizon_linewidth
        config.jupiter_color = self.jupiter_color
        config.label_color = self.label_color
        config.legend_font_scale = self.legend_font_scale
        config.legend_linewidth = self.legend_linewidth
        config.light_mode = self.light_mode
        config.mars_color = self.mars_color
        config.mercury_color = self.mercury_color
        config.milky_way_color = self.milky_way_color
        if self.milky_way_linewidth is not None:
            config.milky_way_linewidth = self.milky_way_linewidth
        config.moon_color = self.moon_color
        config.nebula_color = self.nebula_color
        config.nebula_linewidth = self.nebula_linewidth
        config.neptune_color = self.neptune_color
        config.open_cluster_linewidth = self.open_cluster_linewidth
        config.outlined_dso_label_font_scale = self.outlined_dso_label_font_scale
        config.picker_color = self.picker_color
        config.picker_linewidth = self.picker_linewidth
        config.picker_radius = self.picker_radius
        config.pluto_color = self.pluto_color
        config.saturn_color = self.saturn_color
        config.show_nebula_outlines = self.show_nebula_outlines
        config.star_cluster_color = self.star_cluster_color
        config.star_colors = self.star_colors
        config.star_mag_shift = self.star_mag_shift
        config.sun_color = self.sun_color
        config.telrad_color = self.telrad_color
        config.telrad_linewidth = self.telrad_linewidth
        config.uranus_color = self.uranus_color
        config.venus_color = self.venus_color

    def _parse_bool(self, defs, field_name, default_value, errors):
        value = defs.get(field_name)
        if value is not None:
            value = value.strip()
            if value.upper() == 'TRUE':
                return True
            if value.upper() == 'FALSE':
                return False
            if errors is not None:
                errors.append(f"Invalid boolean value '{value}' for field '{field_name}'")
        return default_value

    def _parse_color(self, defs, field_name, default_value, errors):
        value = defs.get(field_name)
        if value is None:
            return default_value
        value = value.strip()
        ok = False
        if value.startswith('#'):
            value_hex = value[1:]
            try:
                r, g, b = [int(value_hex[i:i + 2], 16) / 255.0 for i in range(0, len(value_hex), 2)]
                ok = True
            except ValueError:
                pass
        elif value.startswith('(') and value.endswith(')'):
            rgb = value[1:-1].split(',')
            if len(rgb) == 3:
                try:
                    r, g, b = float(rgb[0]), float(rgb[1]), float(rgb[2])
                    ok = True
                except ValueError:
                    pass
        if not ok:
            if errors is not None:
                errors.append(f"Invalid color format '{value}' for field '{field_name}'")
            return default_value
        return r, g, b

    def _parse_float(self, defs, field_name, default_value, errors):
        value = defs.get(field_name)
        if value is None:
            return default_value
        value = value.strip()
        try:
            f = float(value)
        except ValueError:
            if errors is not None:
                errors.append(f"Invalid float value '{value}' for field '{field_name}'")
            f = default_value
        return f

    def _parse_float_with_min_max(self, defs, field_name, default_value, min_value, max_value, errors):
        result = self._parse_float(defs, field_name, default_value, errors)
        if result is not None and (result < min_value or result > max_value):
            if errors is not None:
                errors.append(f"Value '{result}' for field '{field_name}' must be between {min_value} and {max_value}")
            return default_value
        return result

    def _parse_linespace(self, defs, field_name, default_value, errors):
        return self._parse_float_with_min_max(defs, field_name, default_value, 0, MAX_LINE_SPACE, errors)

    def _parse_linewidth(self, defs, field_name, default_value, errors):
        return self._parse_float_with_min_max(defs, field_name, default_value, 0, MAX_LINE_WIDTH, errors)

    def _parse_font_size(self, defs, field_name, default_value, errors):
        return self._parse_float_with_min_max(defs, field_name, default_value, 0, MAX_FONT_SIZE, errors)

    def _parse_font_scale(self, defs, field_name, default_value, errors):
        return self._parse_float_with_min_max(defs, field_name, default_value, 0, MAX_FONT_SCALE, errors)

    def to_scene_theme_dict(self):
        # Stable data contract for JS renderer.
        return {
            'schema': 'scene_theme_v1',
            'colors': {
                'background': self.background_color,
                'draw': self.draw_color,
                'label': self.label_color,
                'grid': self.grid_color,
                'constellation_lines': self.constellation_lines_color,
                'constellation_borders': self.constellation_border_color,
                'constellation_hl_borders': self.constellation_hl_border_color,
                'dso': self.dso_color,
                'galaxy': self.galaxy_color,
                'milky_way': self.milky_way_color,
                'nebula': self.nebula_color,
                'star_cluster': self.star_cluster_color,
                'highlight': self.highlight_color,
                'horizon': self.horizon_color,
                'cardinal_directions': self.cardinal_directions_color,
                'sun': self.sun_color,
                'moon': self.moon_color,
                'mercury': self.mercury_color,
                'venus': self.venus_color,
                'mars': self.mars_color,
                'jupiter': self.jupiter_color,
                'saturn': self.saturn_color,
                'uranus': self.uranus_color,
                'neptune': self.neptune_color,
                'picker': self.picker_color,
                'telrad': self.telrad_color,
                'eyepiece': self.eyepiece_color,
            },
            'line_widths': {
                'grid': self.grid_linewidth,
                'constellation': self.constellation_linewidth,
                'constellation_border': self.constellation_border_linewidth,
                'dso': self.dso_linewidth,
                'nebula': self.nebula_linewidth,
                'highlight': self.highlight_linewidth,
                'horizon': self.horizon_linewidth,
                'legend': self.legend_linewidth,
                'picker': self.picker_linewidth,
                'telrad': self.telrad_linewidth,
                'eyepiece': self.eyepiece_linewidth,
                'open_cluster': self.open_cluster_linewidth,
                'galaxy_cluster': self.galaxy_cluster_linewidth,
                'milky_way': self.milky_way_linewidth,
            },
            'font_scales': {
                'font_size': self.font_size,
                'legend_font_scale': self.legend_font_scale,
                'bayer_label_font_scale': self.bayer_label_font_scale,
                'flamsteed_label_font_scale': self.flamsteed_label_font_scale,
                'ext_label_font_scale': self.ext_label_font_scale,
                'outlined_dso_label_font_scale': self.outlined_dso_label_font_scale,
                'cardinal_directions_font_scale': self.cardinal_directions_font_scale,
                'highlight_label_font_scale': self.highlight_label_font_scale,
            },
            'sizes': {
                'picker_radius': self.picker_radius,
                'star_mag_shift': self.star_mag_shift,
                'constellation_linespace': self.constellation_linespace,
            },
            'flags': {
                'light_mode': self.light_mode,
                'star_colors': self.star_colors,
                'dso_dynamic_brightness': self.dso_dynamic_brightness,
                'show_nebula_outlines': self.show_nebula_outlines,
            },
            'units': {
                'color': 'rgb_0_1',
                'line': 'mm',
                'angles': 'rad',
                'font': 'scale',
            },
        }

    def scene_theme_hash(self):
        serialized = json.dumps(self.to_scene_theme_dict(), sort_keys=True, separators=(',', ':'))
        return hashlib.sha1(serialized.encode('utf-8')).hexdigest()

    @classmethod
    def create_from_template(cls, t, errors=None):
        is_head = True
        theme_props = {}
        for l in t.splitlines():
            l = l.strip()
            if not l or l.startswith('#'):
                continue
            if is_head:
                is_head = False
                if l.startswith('EXTENDS'):
                    extd = l.split()
                    if len(extd) > 1 and extd[0] == 'EXTENDS':
                        for ext in extd[1:]:
                            if ext == 'base_theme':
                                ctd = BASE_THEME_DEF
                            else:
                                ctd = COMMON_THEMES.get(ext)
                            if ctd:
                                for attr, value in vars(ctd).items():
                                    theme_props[attr] = str(value)
                            else:
                                current_app.logger.warning('Unknown base theme {}'.format(ext))
                        continue
                    current_app.logger.warning('Invalid chart theme EXTENDS expression {}'.format(l))
                    continue
            kv = l.split('=')
            if len(kv) == 2:
                k, v = kv
                if k:
                    theme_props[k] = v
        result = ChartThemeDefinition()
        result.validate_set(theme_props, errors)
        return result


def _parse_theme(theme_str):
    theme_dict = OrderedDict()
    for line in theme_str.strip().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('EXTENDS'):
            extends = line[len('EXTENDS'):].strip()
            theme_dict['__extends__'] = extends
            continue
        if '=' in line:
            key, value = line.split('=', 1)
            theme_dict[key.strip()] = value.strip()
    return theme_dict


def _merge_themes(base_theme_str, derived_theme_str):
    base_theme = _parse_theme(base_theme_str)
    derived_theme = _parse_theme(derived_theme_str)
    extends = derived_theme.pop('__extends__', None)
    if extends and extends != 'base_theme':
        raise ValueError("Only 'EXTENDS base_theme' is supported")

    merged_theme = OrderedDict()
    for key in base_theme.keys():
        if key in derived_theme:
            merged_theme[key] = derived_theme[key]
        else:
            merged_theme[key] = base_theme[key]
    for key in derived_theme.keys():
        if key not in base_theme:
            merged_theme[key] = derived_theme[key]
    lines = []
    for key in merged_theme.keys():
        value = merged_theme[key]
        lines.append(f'# {key}={value}')
    return '\n'.join(lines)

BASE_THEME_TEMPL = '''
bayer_label_font_scale=1.0
cardinal_directions_color=(0.8, 0.2, 0.102)
cardinal_directions_font_scale=1.3
constellation_border_linewidth=0.2
constellation_linespace=2.0
constellation_linewidth=0.4
dso_linewidth=0.4
comet_highlight_color=(0.2, 0.5, 0.0)
comet_tail_color=(0.5, 0.5, 0.5)
comet_tail_length=6.0
comet_tail_half_angle_deg=15.0
comet_tail_side_scale=0.8
earth_color=(0.2, 0.6, 1.0)
ext_label_font_scale=1.2
eyepiece_linewidth=0.3
flamsteed_label_font_scale=0.9
font_size=3.3
galaxy_cluster_linewidth=0.3
grid_linewidth=0.1
highlight_label_font_scale=1.0
highlight_linewidth=0.3
horizon_linewidth=1.0
jupiter_color=(0.9, 0.6, 0.5)
legend_font_scale=1.1
legend_linewidth=0.2
mars_color=(0.8, 0.4, 0.1)
mercury_color=(0.5, 0.5, 0.5)
moon_color=(0.8, 0.8, 0.8)
nebula_linewidth=0.25
neptune_color=(0.3, 0.5, 0.9)
open_cluster_linewidth=0.3
outlined_dso_label_font_scale=1.1
picker_linewidth=0.4
picker_radius=4.0
pluto_color=(0.7, 0.6, 0.5)
saturn_color=(0.9, 0.8, 0.5)
show_nebula_outlines=True
star_colors=True
star_mag_shift=0.0
sun_color=(1.0, 1.0, 0.0)
telrad_linewidth=0.3
uranus_color=(0.6, 0.8, 1.0)
venus_color=(0.9, 0.8, 0.6)
'''


DARK_THEME_TEMPL = '''
EXTENDS base_theme
light_mode=False
background_color=(0.01, 0.01, 0.04)
cardinal_directions_color=(0.8, 0.2, 0.102)
constellation_border_color=(0.4, 0.36, 0.09)
constellation_hl_border_color=(0.6, 0.5, 0.14)
constellation_lines_color=(0.12, 0.27, 0.3)
draw_color=(1.0, 1.0, 1.0)
dso_color=(0.6, 0.6, 0.6)
comet_highlight_color=(0.2, 0.4, 0.2)
comet_tail_color=(0.6, 0.6, 0.6)
dso_dynamic_brightness=True
eyepiece_color=(0.5, 0.3, 0.0)
galaxy_cluster_color=(0.6, 0.2, 0.2)
galaxy_color=(0.6, 0.2, 0.2)
grid_color=(0.21, 0.31, 0.36)
highlight_color=(0.15, 0.3, 0.6)
horizon_color=(0.24, 0.21, 0.14)
jupiter_color=(0.9, 0.6, 0.5)
label_color=(0.7, 0.7, 0.7)
mars_color=(0.8, 0.4, 0.1)
mercury_color=(0.5, 0.5, 0.5)
milky_way_color=(0.05, 0.07, 0.1)
moon_color=(0.8, 0.8, 0.8)
nebula_color=(0.2, 0.6, 0.2)
neptune_color=(0.3, 0.5, 0.9)
picker_color=(0.5, 0.5, 0.0)
pluto_color=(0.7, 0.6, 0.5)
saturn_color=(0.9, 0.8, 0.5)
star_cluster_color=(0.6, 0.6, 0.0)
sun_color=(1.0, 1.0, 0.0)
telrad_color=(0.5, 0.0, 0.0)
uranus_color=(0.6, 0.8, 1.0)
venus_color=(0.9, 0.8, 0.6)
'''

NIGHT_THEME_TEMPL = '''
EXTENDS base_theme
light_mode=False
background_color=(0.01, 0.01, 0.01)
cardinal_directions_color=(0.8, 0.2, 0.102)
constellation_border_color=(0.4, 0.19, 0.05)
constellation_hl_border_color=(0.6, 0.26, 0.06)
constellation_lines_color=(0.37, 0.12, 0.0)
draw_color=(1.0, 0.5, 0.5)
dso_color=(0.6, 0.15, 0.0)
comet_highlight_color=(0.6, 0.15, 0.0)
comet_tail_color=(0.6, 0.15, 0.0)
dso_dynamic_brightness=False
earth_color=(0.54, 0.0, 0.0)
eyepiece_color=(0.5, 0.0, 0.0)
galaxy_cluster_color=(0.6, 0.15, 0.0)
galaxy_color=(0.6, 0.15, 0.0)
grid_color=(0.3, 0.12, 0.12)
highlight_color=(0.4, 0.2, 0.1)
horizon_color=(0.5, 0.22, 0.22)
jupiter_color=(0.66, 0.0, 0.0)
label_color=(0.7, 0.3, 0.3)
mars_color=(0.46, 0.0, 0.0)
mercury_color=(0.5, 0.0, 0.0)
milky_way_color=(0.075, 0.015, 0.015)
moon_color=(0.80, 0.0, 0.0)
nebula_color=(0.6, 0.15, 0.0)
neptune_color=(0.49, 0.0, 0.0)
picker_color=(0.5, 0.1, 0.0)
pluto_color=(0.61, 0.0, 0.0)
saturn_color=(0.80, 0.0, 0.0)
star_cluster_color=(0.6, 0.15, 0.0)
star_colors=False
sun_color=(0.93, 0.0, 0.0)
telrad_color=(0.5, 0.0, 0.0)
uranus_color=(0.77, 0.0, 0.0)
venus_color=(0.81, 0.0, 0.0)
'''

LIGHT_THEME_TEMPL = '''
EXTENDS base_theme
light_mode=True
background_color=(1.0, 1.0, 1.0)
cardinal_directions_color=(0.8, 0.2, 0.102)
constellation_border_color=(0.4, 0.35, 0.05)
constellation_hl_border_color=(0.4, 0.4, 0.4)
constellation_lines_color=(0.4, 0.56, 0.64)
draw_color=(0.0, 0.0, 0.0)
dso_color=(0.3, 0.3, 0.3)
comet_highlight_color=(0.3, 0.6, 0.3)
comet_tail_color=(0.3, 0.3, 0.3)
dso_dynamic_brightness=False
eyepiece_color=(0.5, 0.0, 0.0)
galaxy_cluster_color=(0.3, 0.3, 0.3)
galaxy_color=(0.3, 0.0, 0.0)
grid_color=(0.6, 0.6, 0.6)
highlight_color=(0.1, 0.2, 0.4)
horizon_color=(0.6, 0.6, 0.3)
jupiter_color=(0.9, 0.6, 0.5)
label_color=(0.2, 0.2, 0.2)
mars_color=(0.8, 0.4, 0.1)
mercury_color=(0.5, 0.5, 0.5)
milky_way_color=(0.836, 0.945, 0.992)
moon_color=(0.8, 0.8, 0.8)
nebula_color=(0.0, 0.3, 0.0)
neptune_color=(0.3, 0.5, 0.9)
picker_color=(0.2, 0.2, 0.0)
pluto_color=(0.7, 0.6, 0.5)
saturn_color=(0.9, 0.8, 0.5)
star_cluster_color=(0.3, 0.3, 0.0)
star_colors=False
sun_color=(1.0, 1.0, 0.0)
telrad_color=(0.5, 0.0, 0.0)
uranus_color=(0.6, 0.8, 1.0)
venus_color=(0.9, 0.8, 0.6)
'''

BASE_THEME_DEF = ChartThemeDefinition.create_from_template(BASE_THEME_TEMPL)

COMMON_THEME_TEMPLATES = {
    'base_theme': BASE_THEME_TEMPL,
    'dark_theme': DARK_THEME_TEMPL,
    'night_theme': NIGHT_THEME_TEMPL,
    'light_theme': LIGHT_THEME_TEMPL
}

COMMON_THEMES = {
    'dark_theme': ChartThemeDefinition.create_from_template(DARK_THEME_TEMPL),
    'night_theme': ChartThemeDefinition.create_from_template(NIGHT_THEME_TEMPL),
    'light_theme': ChartThemeDefinition.create_from_template(LIGHT_THEME_TEMPL)
}

MERGED_DARK_THEME_TEMPL = 'EXTENDS dark_theme\n' + _merge_themes(BASE_THEME_TEMPL, DARK_THEME_TEMPL)
MERGED_LIGHT_THEME_TEMPL = 'EXTENDS light_theme\n' + _merge_themes(BASE_THEME_TEMPL, LIGHT_THEME_TEMPL)
MERGED_NIGHT_THEME_TEMPL = 'EXTENDS night_theme\n' + _merge_themes(BASE_THEME_TEMPL, NIGHT_THEME_TEMPL)

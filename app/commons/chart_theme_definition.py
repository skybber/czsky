from flask import (
    current_app,
)


class ChartThemeDefinition:
    def __init__(self):
        self.show_nebula_outlines = None
        self.star_colors = None
        self.light_mode = None
        self.background_color = None
        self.draw_color = None
        self.label_color = None
        self.constellation_lines_color = None
        self.constellation_border_color = None
        self.constellation_hl_border_color = None
        self.dso_color = None
        self.nebula_color = None
        self.galaxy_color = None
        self.star_cluster_color = None
        self.galaxy_cluster_color = None
        self.grid_color = None
        self.constellation_linewidth = None
        self.constellation_border_linewidth = None
        self.constellation_linespace = None
        self.open_cluster_linewidth = None
        self.galaxy_cluster_linewidth = None
        self.nebula_linewidth = None
        self.dso_linewidth = None
        self.legend_linewidth = None
        self.grid_linewidth = None
        self.font_size = None
        self.highlight_color = None
        self.highlight_linewidth = None
        self.dso_dynamic_brightness = None
        self.legend_font_scale = None
        self.milky_way_color = None
        self.enhanced_milky_way_fade = None
        self.telrad_linewidth = None
        self.telrad_color = None
        self.eyepiece_linewidth = None
        self.eyepiece_color = None
        self.picker_radius = None
        self.picker_linewidth = None
        self.picker_color = None
        self.ext_label_font_scale = None
        self.bayer_label_font_scale = None
        self.flamsteed_label_font_scale = None
        self.outlined_dso_label_font_scale = None
        self.highlight_label_font_scale = None

    def validate_set(self, defs, errors=None):
        self.show_nebula_outlines = self._parse_bool(defs.get('show_nebula_outlines'), self.show_nebula_outlines, errors)
        self.star_colors = self._parse_bool(defs.get('star_colors'), self.star_colors, errors)
        self.light_mode = self._parse_bool(defs.get('light_mode'), self.light_mode, errors)
        self.background_color = self._parse_color(defs.get('background_color'), self.background_color, errors)
        self.draw_color = self._parse_color(defs.get('draw_color'), self.draw_color, errors)
        self.label_color = self._parse_color(defs.get('label_color'), self.label_color, errors)
        self.constellation_lines_color = self._parse_color(defs.get('constellation_lines_color'), self.constellation_lines_color, errors)
        self.constellation_border_color = self._parse_color(defs.get('constellation_border_color'), self.constellation_border_color, errors)
        self.constellation_hl_border_color = self._parse_color(defs.get('constellation_hl_border_color'), self.constellation_hl_border_color, errors)
        self.dso_color = self._parse_color(defs.get('dso_color'), self.dso_color, errors)
        self.nebula_color = self._parse_color(defs.get('nebula_color'), self.nebula_color, errors)
        self.galaxy_color = self._parse_color(defs.get('galaxy_color'), self.galaxy_color, errors)
        self.star_cluster_color = self._parse_color(defs.get('star_cluster_color'), self.star_cluster_color, errors)
        self.galaxy_cluster_color = self._parse_color(defs.get('galaxy_cluster_color'), self.galaxy_cluster_color, errors)
        self.grid_color = self._parse_color(defs.get('grid_color'), self.grid_color, errors)
        self.constellation_linewidth = self._parse_linewidth(defs.get('constellation_linewidth'), self.constellation_linewidth, errors)
        self.constellation_border_linewidth = self._parse_linewidth(defs.get('constellation_border_linewidth'), self.constellation_border_linewidth, errors)
        self.constellation_linespace = self._parse_linespace(defs.get('constellation_linespace'), self.constellation_linespace, errors)
        self.open_cluster_linewidth = self._parse_linewidth(defs.get('open_cluster_linewidth'), self.open_cluster_linewidth, errors)
        self.galaxy_cluster_linewidth = self._parse_linewidth(defs.get('galaxy_cluster_linewidth'), self.galaxy_cluster_linewidth, errors)
        self.nebula_linewidth = self._parse_linewidth(defs.get('nebula_linewidth'), self.nebula_linewidth, errors)
        self.dso_linewidth = self._parse_linewidth(defs.get('dso_linewidth'), self.dso_linewidth, errors)
        self.legend_linewidth = self._parse_linewidth(defs.get('legend_linewidth'), self.legend_linewidth, errors)
        self.grid_linewidth = self._parse_linewidth(defs.get('grid_linewidth'), self.grid_linewidth, errors)
        self.font_size = self._parse_font_size(defs.get('font_size'), self.font_size, errors)
        self.highlight_color = self._parse_color(defs.get('highlight_color'), self.highlight_color, errors)
        self.highlight_linewidth = self._parse_linewidth(defs.get('highlight_linewidth'), self.highlight_linewidth, errors)
        self.dso_dynamic_brightness = self._parse_dynamic_brightness(defs.get('dso_dynamic_brightness'), self.dso_dynamic_brightness, errors)
        self.legend_font_scale = self._parse_font_scale(defs.get('legend_font_scale'), self.legend_font_scale, errors)
        self.milky_way_color = self._parse_color(defs.get('milky_way_color'), self.milky_way_color, errors)
        self.enhanced_milky_way_fade = self._parse_float(defs.get('enhanced_milky_way_fade'), self.enhanced_milky_way_fade, errors)
        self.telrad_linewidth = self._parse_linewidth(defs.get('telrad_linewidth'), self.telrad_linewidth, errors)
        self.telrad_color = self._parse_color(defs.get('telrad_color'), self.telrad_color, errors)
        self.eyepiece_linewidth = self._parse_linewidth(defs.get('eyepiece_linewidth'), self.eyepiece_linewidth, errors)
        self.eyepiece_color = self._parse_color(defs.get('eyepiece_color'), self.eyepiece_color, errors)
        self.picker_radius = self._parse_float(defs.get('picker_radius'), self.picker_radius, errors)
        self.picker_linewidth = self._parse_linewidth(defs.get('picker_linewidth'), self.picker_linewidth, errors)
        self.picker_color = self._parse_color(defs.get('picker_color'), self.picker_color, errors)
        self.ext_label_font_scale = self._parse_font_scale(defs.get('ext_label_font_scale'), self.ext_label_font_scale, errors)
        self.bayer_label_font_scale = self._parse_font_scale(defs.get('bayer_label_font_scale'), self.bayer_label_font_scale, errors)
        self.flamsteed_label_font_scale = self._parse_font_scale(defs.get('flamsteed_label_font_scale'), self.flamsteed_label_font_scale, errors)
        self.outlined_dso_label_font_scale = self._parse_font_scale(defs.get('outlined_dso_label_font_scale'), self.outlined_dso_label_font_scale, errors)
        self.highlight_label_font_scale = self._parse_font_scale(defs.get('highlight_label_font_scale'), self.highlight_label_font_scale, errors)

    def _parse_bool(self, value, default_value, errors):
        if value is not None:
            value = value.strip()
            if value.upper() == 'TRUE':
                return True
            if value.upper() == 'FALSE':
                return False
            if errors is not None:
                errors.append('Invalid boolean value {}'.format(value))
        return default_value

    def _parse_color(self, value, default_value, errors):
        if value is None:
            return default_value
        value = value.strip()
        ok = False
        if value.startswith('#'):
            value = value[1:]
            try:
                r, g, b = [int(value[i:i + 2], 16) / 255.0 for i in range(0, len(value), 2)]
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
                errors.append('Invalid color format {}'.format(value))
            return default_value
        return r, g, b

    def _parse_float(self, value, default_value, errors):
        if value is None:
            return default_value
        value = value.strip()
        try:
            f = float(value)
        except ValueError:
            if errors is not None:
                errors.append('Invalid float value {}'.format(value))
            f = default_value
        return f

    def _parse_linespace(self, value, default_value, errors):
        return self._parse_float(value, default_value, errors)

    def _parse_linewidth(self, value, default_value, errors):
        return self._parse_float(value, default_value, errors)

    def _parse_dynamic_brightness(self, value, default_value, errors):
        return self._parse_float(value, default_value, errors)

    def _parse_font_size(self, value, default_value, errors):
        return self._parse_float(value, default_value, errors)

    def _parse_font_scale(self, value, default_value, errors):
        return self._parse_float(value, default_value, errors)

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
                                current_app.logger.warn('Unknown base theme {}'.format(ext))
                        continue
                    current_app.logger.warn('Invalid chart theme EXTENDS expression {}'.format(l))
                    continue
            kv = l.split('=')
            if len(kv) == 2:
                k, v = kv
                if k:
                    theme_props[k] = v
        result = ChartThemeDefinition()
        result.validate_set(theme_props, errors)
        return result


BASE_THEME_TEMPL = '''
show_nebula_outlines=True
star_colors=True
constellation_linewidth=0.2
constellation_border_linewidth=0.15
constellation_linespace=2.0
open_cluster_linewidth=0.3
galaxy_cluster_linewidth=0.3
nebula_linewidth=0.25
dso_linewidth=0.4
legend_linewidth=0.2
grid_linewidth=0.1
font_size=3.3
highlight_linewidth=0.3
dso_dynamic_brightness=True
legend_font_scale=1.4
telrad_linewidth=0.3
eyepiece_linewidth=0.3
picker_radius=4.0
picker_linewidth=0.4
ext_label_font_scale=1.2
bayer_label_font_scale=1.2
flamsteed_label_font_scale=0.9
outlined_dso_label_font_scale=1.1
highlight_label_font_scale=1.0
'''


BASE_THEME_DEF = ChartThemeDefinition.create_from_template(BASE_THEME_TEMPL)

DARK_THEME_TEMPL = '''
EXTENDS base_theme
light_mode=False
background_color=(0.005, 0.005, 0.02)
draw_color=(1.0, 1.0, 1.0)
label_color=(0.7, 0.7, 0.7)
constellation_lines_color=(0.12, 0.27, 0.3)
constellation_border_color=(0.3, 0.27, 0.07)
constellation_hl_border_color=(0.6, 0.5, 0.14)
dso_color=(0.6, 0.6, 0.6)
nebula_color=(0.2, 0.6, 0.2)
galaxy_color=(0.6, 0.2, 0.2)
star_cluster_color=(0.6, 0.6, 0.0)
galaxy_cluster_color=(0.6, 0.2, 0.2)
grid_color=(0.12, 0.18, 0.20)
highlight_color=(0.15, 0.3, 0.6)
milky_way_color=(0.05, 0.07, 0.1)
telrad_color=(0.5, 0.0, 0.0)
eyepiece_color=(0.5, 0.3, 0.0)
picker_color=(0.5, 0.5, 0.0)
'''

NIGHT_THEME_TEMPL = '''
EXTENDS base_theme
light_mode=False
star_colors=False
background_color=(0.01, 0.01, 0.01)
draw_color=(1.0, 0.5, 0.5)
label_color=(0.7, 0.3, 0.3)
constellation_lines_color=(0.37, 0.12, 0.0)
constellation_border_color=(0.4, 0.19, 0.05)
constellation_hl_border_color=(0.6, 0.26, 0.06)
dso_color=(0.6, 0.15, 0.0)
nebula_color=(0.6, 0.15, 0.0)
galaxy_color=(0.6, 0.15, 0.0)
star_cluster_color=(0.6, 0.15, 0.0)
galaxy_cluster_color=(0.6, 0.15, 0.0)
grid_color=(0.2, 0.06, 0.06)
highlight_color=(0.4, 0.2, 0.1)
milky_way_color=(0.075, 0.015, 0.015)
telrad_color=(0.5, 0.0, 0.0)
eyepiece_color=(0.5, 0.0, 0.0)
picker_color=(0.5, 0.1, 0.0)
'''

LIGHT_THEME_TEMPL = '''
EXTENDS base_theme
light_mode=True
star_colors=False
background_color=(1.0, 1.0, 1.0)
draw_color=(0.0, 0.0, 0.0)
label_color=(0.2, 0.2, 0.2)
constellation_lines_color=(0.4, 0.56, 0.64)
constellation_border_color=(0.4, 0.35, 0.05)
constellation_hl_border_color=(0.4, 0.4, 0.4)
dso_color=(0.3, 0.3, 0.3)
nebula_color=(0.0, 0.3, 0.0)
galaxy_color=(0.3, 0.0, 0.0)
star_cluster_color=(0.3, 0.3, 0.0)
galaxy_cluster_color=(0.3, 0.3, 0.3)
grid_color=(0.7, 0.7, 0.7)
highlight_color=(0.1, 0.2, 0.4)
milky_way_color=(0.836, 0.945, 0.992)
telrad_color=(0.5, 0.0, 0.0)
eyepiece_color=(0.5, 0.0, 0.0)
picker_color=(0.2, 0.2, 0.0)
'''

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

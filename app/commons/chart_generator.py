import base64
import os
import json
from datetime import timedelta
from datetime import datetime
from io import BytesIO
from math import pi, sqrt, sin, cos, acos
from time import time
import numpy as np
import ctypes as ct
import cairo
from skyfield.api import load
from enum import Enum
import threading

# Do not remove - it initializes pillow avif
import pillow_avif

import fchart3

from flask import (
    current_app,
    request,
    session,
    url_for,
)
from flask_login import current_user

from app.models import (
    DsoList,
    Eyepiece,
    ObservingSession,
    SessionPlan,
    Telescope, BODY_KEY_DICT,
)

from .planet_utils import create_solar_system_body_obj

from .utils import to_float
from .chart_theme_definition import COMMON_THEMES

MOBILE_WIDTH = 768

used_catalogs = None
dso_name_cache = None
dso_hide_filter = None

MAX_IMG_WIDTH = 3000
MAX_IMG_HEIGHT = 3000

A4_WIDTH = 800

FIELD_SIZES = (0.25, 0.375, 0.5, 0.75, 1, 1.5, 2, 3, 4, 6, 8, 12, 16, 23, 30, 45, 60, 80, 100, 140, 180)

STR_GUI_FIELD_SIZES = ','.join(str(x) for x in FIELD_SIZES)

MAG_SCALES = [(14, 16), # 0.25
              (14, 16), # 0.375
              (13, 16), # 0.5
              (13, 16), # 0.75
              (12, 16), # 1
              (12, 16), # 1.5
              (11, 15), # 2
              (11, 15), # 3
              (10, 13), # 4
              (10, 13), # 6
              (8, 11), # 8
              (8, 11), # 12
              (7, 10), # 16
              (7, 10), # 23
              (6, 9), # 30
              (6, 9), # 45
              (6, 8), # 60
              (6, 8), # 80
              (5, 7), # 100
              (5, 7), # 140
              (5, 7), # 180
              ]

DSO_MAG_SCALES = [(10, 18), # 0.25
                  (10, 18), # 0.375
                  (10, 18), # 0.5
                  (10, 18), # 0.75
                  (10, 18), # 1
                  (10, 18), # 1.5
                  (10, 18), # 2
                  (10, 18), # 3
                  (10, 18), # 4
                  (10, 18), # 6
                  (9, 16), # 8
                  (8, 15), # 12
                  (7, 14), # 16
                  (7, 13), # 23
                  (7, 12), # 30
                  (7, 12), # 45
                  (7, 11), # 60
                  (7, 11), # 80
                  (6, 10), # 100
                  (6, 10), # 140
                  (5, 9),  # 180
                  ]

class FlagValue(Enum):
    CONSTELL_BORDERS = 'B'
    CONSTELL_SHAPES = 'C'
    SHOW_DEEPSKY = 'D'
    SHOW_SOLAR_SYSTEM = 'O'
    SHOW_EQUATORIAL_GRID = 'E'
    SHOW_DSO_MAG = 'M'
    SHOW_STAR_MAG = 'N'
    SHOW_PICKER = 'P'
    DSS_COLORED = 'Sc'
    DSS_BLUE = 'Sb'
    FOV_TELRAD = 'T'
    MIRROR_X = 'X'
    MIRROR_Y = 'Y'

free_mem_counter = 0
NO_FREE_MEM_CYCLES = 200

FORCE_SHOWING_DSOS = ['NGC 1909', 'IC443']

ADD_SHOW_CATALOGS = ['Berk', 'King']

PICKER_RADIUS = 4.0

DEFAULT_SCREEN_FONT_SIZE = 3.3
DEFAULT_PDF_FONT_SIZE = 3.0

chart_font_face = None
chart_font_face_initialized = False

pdf_font_face = None
pdf_font_face_initialized = False

skyfield_ts = load.timescale()

catalog_lock = threading.Lock()

solsys_bodies = None
solsys_last_updated = None

class ChartControl:
    def __init__(self, chart_fsz=None, mag_scale=None, mag_ranges=None, mag_range_values=None,
                 dso_mag_scale=None, dso_mag_ranges=None, dso_mag_range_values=None, theme=None, gui_field_sizes=None,
                 chart_mlim=None, chart_flags=None, legend_flags=None, chart_pdf_flags=None,
                 chart_dso_list_menu=None, has_date_from_to=False, date_from=None, date_to=None, back_search_url_b64=None,
                 show_not_found=None, cancel_selection_url=None, equipment_telescopes=None, equipment_eyepieces=None,
                 eyepiece_fov=None):
        self.chart_fsz = chart_fsz
        self.mag_scale = mag_scale
        self.mag_ranges = mag_ranges
        self.mag_range_values = mag_range_values
        self.dso_mag_scale = dso_mag_scale
        self.dso_mag_ranges = dso_mag_ranges
        self.dso_mag_range_values = dso_mag_range_values
        self.theme = theme
        self.gui_field_sizes = gui_field_sizes
        self.chart_mlim = chart_mlim
        self.chart_flags = chart_flags
        self.legend_flags = legend_flags
        self.chart_pdf_flags = chart_pdf_flags
        self.chart_dso_list_menu = chart_dso_list_menu
        self.has_date_from_to = has_date_from_to
        self.date_from = date_from
        self.date_to = date_to
        self.back_search_url_b64 = back_search_url_b64
        self.show_not_found = show_not_found
        self.cancel_selection_url = cancel_selection_url
        self.equipment_telescopes = equipment_telescopes
        self.equipment_eyepieces = equipment_eyepieces
        self.eyepiece_fov = eyepiece_fov


def _load_used_catalogs():
    global used_catalogs, catalog_lock
    if used_catalogs is None:
        with catalog_lock:
            if used_catalogs is None:
                data_dir = os.path.join(fchart3.get_catalogs_dir())
                extra_data_dir = os.path.join(os.getcwd(), 'data/')
                supplements = [
                                # LDN replaces some outlines with some DSO (Veil) with rect
                                # 'Lynds Catalogue of Bright Nebulae.sup',
                                'M31 global clusters, Revised Bologna Catalogue v5.sup',
                                'M33 global clusters,  2007 catalog.sup',
                                'VDB, catalogue of reflection nebulae.sup']
                used_catalogs = fchart3.UsedCatalogs(data_dir,
                                                     extra_data_dir,
                                                     supplements=[ os.path.join(extra_data_dir, 'supplements', s) for s in supplements ],
                                                     limit_magnitude_deepsky=100.0,
                                                     force_asterisms=False,
                                                     force_unknown=False,
                                                     show_catalogs=ADD_SHOW_CATALOGS,
                                                     use_pgc_catalog=True,
                                                     enhanced_mw_optim_max_col_diff=18/255.0)
                global dso_name_cache
                dso_name_cache = {}
    return used_catalogs


def _get_dso_hide_filter():
    global dso_hide_filter
    if not dso_hide_filter:
        dso_hide_filter = []
        with open(os.path.join(os.getcwd(), 'data/dso_hide_filter.csv'), 'r') as ifile:
            lines = ifile.readlines()
            for line in lines:
                dso = _find_dso_by_name(line.strip())
                if dso:
                    dso_hide_filter.append(dso)
    return dso_hide_filter


def _fill_config_from_chart_theme(config, theme):
    config.show_nebula_outlines = theme.show_nebula_outlines
    config.star_colors = theme.star_colors
    config.light_mode = theme.light_mode
    config.background_color = theme.background_color
    config.draw_color = theme.draw_color
    config.label_color = theme.label_color
    config.constellation_lines_color = theme.constellation_lines_color
    config.constellation_border_color = theme.constellation_border_color
    config.constellation_hl_border_color = theme.constellation_hl_border_color
    config.dso_color = theme.dso_color
    config.nebula_color = theme.nebula_color
    config.galaxy_color = theme.galaxy_color
    config.star_cluster_color = theme.star_cluster_color
    config.galaxy_cluster_color = theme.galaxy_cluster_color
    config.grid_color = theme.grid_color
    config.constellation_linewidth = theme.constellation_linewidth
    config.constellation_border_linewidth = theme.constellation_border_linewidth
    config.constellation_linespace = theme.constellation_linespace
    config.open_cluster_linewidth = theme.open_cluster_linewidth
    config.galaxy_cluster_linewidth = theme.galaxy_cluster_linewidth
    config.nebula_linewidth = theme.nebula_linewidth
    config.dso_linewidth = theme.dso_linewidth
    config.legend_linewidth = theme.legend_linewidth
    config.grid_linewidth = theme.grid_linewidth
    config.font_size = theme.font_size
    config.highlight_color = theme.highlight_color
    config.highlight_linewidth = theme.highlight_linewidth
    config.dso_dynamic_brightness = theme.dso_dynamic_brightness
    config.legend_font_scale = theme.legend_font_scale
    config.milky_way_color = theme.milky_way_color
    config.enhanced_milky_way_fade = theme.enhanced_milky_way_fade
    config.telrad_linewidth = theme.telrad_linewidth
    config.telrad_color = theme.telrad_color
    config.eyepiece_linewidth = theme.eyepiece_linewidth
    config.eyepiece_color = theme.eyepiece_color
    config.picker_radius = theme.picker_radius
    config.picker_linewidth = theme.picker_linewidth
    config.picker_color = theme.picker_color
    config.ext_label_font_scale = theme.ext_label_font_scale
    config.bayer_label_font_scale = theme.bayer_label_font_scale
    config.flamsteed_label_font_scale = theme.flamsteed_label_font_scale
    config.outlined_dso_label_font_scale = theme.outlined_dso_label_font_scale
    config.highlight_label_font_scale = theme.highlight_label_font_scale
    config.mercury_color = theme.mercury_color
    config.venus_color = theme.venus_color
    config.mars_color = theme.mars_color
    config.jupiter_color = theme.jupiter_color
    config.saturn_color = theme.saturn_color
    config.uranus_color = theme.uranus_color
    config.neptune_color = theme.neptune_color
    config.pluto_color = theme.pluto_color
    config.sun_color = theme.sun_color
    config.moon_color = theme.moon_color


def _setup_dark_theme(config, width):
    _fill_config_from_chart_theme(config, COMMON_THEMES['dark_theme'])


def _setup_night_theme(config, width):
    _fill_config_from_chart_theme(config, COMMON_THEMES['night_theme'])


def _setup_light_theme(config, width):
    _fill_config_from_chart_theme(config, COMMON_THEMES['light_theme'])


def _setup_skymap_graphics(config, fld_size, width, font_size, force_light_mode=False, is_pdf=False):
    if force_light_mode or session.get('theme', '') == 'light':
        _setup_light_theme(config, width)
    elif session.get('theme', '') == 'night':
        _setup_night_theme(config, width)
    else:
        _setup_dark_theme(config, width)

    if is_pdf:
        font = _get_pdf_font_face()
    else:
        font = _get_chart_font_face()
    if font is None:
        font = 'sans'

    config.no_margin = True
    config.font = font
    config.font_size = font_size
    config.show_enhanced_milky_way = True

    if fld_size >= 60 or (fld_size >= 40 and width and width <= MOBILE_WIDTH):
        config.constellation_linespace = 1.5
        config.show_star_labels = False
    else:
        config.constellation_linespace = 2.0

    if fld_size <= 10:
        config.show_enhanced_milky_way = False
    elif config.show_enhanced_milky_way:
        fade = (fld_size - 10) / (70-10)
        # shift background color little bit by fraction of MW color (bg_shift_frac)
        bg_shift_frac = 0.10
        bg_r, bg_g, bg_b = config.background_color[0] + (config.milky_way_color[0]-config.background_color[0]) * bg_shift_frac, \
                           config.background_color[1] + (config.milky_way_color[1]-config.background_color[1]) * bg_shift_frac, \
                           config.background_color[2] + (config.milky_way_color[2]-config.background_color[2]) * bg_shift_frac
        if fade > 1:
            fade = 1
        if fade > 0:
            config.show_enhanced_milky_way = True
            mw_scale_fac = 3.0
            config.enhanced_milky_way_fade = (bg_r, (config.milky_way_color[0] - bg_r) * fade * mw_scale_fac,
                                              bg_g, (config.milky_way_color[1] - bg_g) * fade * mw_scale_fac,
                                              bg_b, (config.milky_way_color[2] - bg_b) * fade * mw_scale_fac)

            config.milky_way_color = (bg_r + (config.milky_way_color[0]-bg_r) * fade,
                                      bg_g + (config.milky_way_color[1]-bg_g) * fade,
                                      bg_b + (config.milky_way_color[2]-bg_b) * fade)
        else:
            config.show_enhanced_milky_way = False


def _fld_filter_trajectory(trajectory, gui_fld_size, width):
    if not trajectory:
        return trajectory

    dra = trajectory[-1][0] - trajectory[0][0]
    ddec = trajectory[-1][1] - trajectory[0][1]
    if dra != 0 or ddec != 0:
        dd = sqrt(dra*dra + ddec*ddec) * 180.0 / pi
        px_per_deg = width / gui_fld_size
        ticks_per_deg = len(trajectory) / dd
        px_per_tick = px_per_deg / ticks_per_deg
        fac = px_per_tick / 25

        if fac >= 1:
            return trajectory
        if fac > 0.5:
            m = 2
        elif fac > 0.25:
            m = 4
        elif fac > 0.2:
            m = 5
        else:
            m = 10

        flt_trajectory = []
        i = 0
        while i < len(trajectory) - 1:
            if (i + m < len(trajectory) - 1) or (i + m - len(trajectory) + 1 < m * 0.6):
                j = 0
                while j < m and trajectory[i+j][2] is None:
                    j += 1
                if j == m:
                    flt_trajectory.append(trajectory[i])
                else:
                    flt_trajectory.append(trajectory[i+j])
            i += m

        flt_trajectory.append(trajectory[-1])
        return flt_trajectory


def _get_solsys_bodies():
    global solsys_bodies, solsys_last_updated

    current_time = time()

    if solsys_last_updated is None or (current_time - solsys_last_updated) > 600:
        ts = load.timescale(builtin=True)
        t = ts.now()

        solsys_bodies = []

        for body_enum in fchart3.SolarSystemBody:
            if body_enum != fchart3.SolarSystemBody.EARTH:
                solsys_body_obj = create_solar_system_body_obj(body_enum, t);
                solsys_bodies.append(solsys_body_obj)

        solsys_last_updated = current_time

    return solsys_bodies

def common_chart_pos_img(obj_ra, obj_dec, ra, dec, dso_names=None, visible_objects=None, highlights_dso_list=None,
                         observed_dso_ids=None, highlights_pos_list=None, trajectory=None, hl_constellation=None):
    gui_fld_size, maglim, dso_maglim = get_fld_size_mags_from_request()

    width = request.args.get('width', type=int)
    height = request.args.get('height', type=int)

    if width > MAX_IMG_WIDTH:
        width = MAX_IMG_WIDTH
    if height > MAX_IMG_HEIGHT:
        height = MAX_IMG_HEIGHT

    trajectory = _fld_filter_trajectory(trajectory, gui_fld_size, width)

    flags = request.args.get('flags')

    img_bytes = BytesIO()
    img_formats = current_app.config.get('CHART_IMG_FORMATS')

    img_format = _create_chart(img_bytes, visible_objects, obj_ra, obj_dec, float(ra), float(dec), gui_fld_size, width, height,
                               maglim, dso_maglim, show_legend=False, dso_names=dso_names, flags=flags, highlights_dso_list=highlights_dso_list,
                               observed_dso_ids=observed_dso_ids, highlights_pos_list=highlights_pos_list, trajectory=trajectory,
                               hl_constellation=hl_constellation, img_formats=img_formats)
    img_bytes.seek(0)
    if img_format == 'jpg':
        out_img_format = 'jpeg'
    else:
        out_img_format = img_format
    return img_bytes, out_img_format


def common_chart_legend_img(obj_ra, obj_dec, ra, dec):
    gui_fld_size, maglim, dso_maglim = get_fld_size_mags_from_request()

    width = request.args.get('width', type=int)
    height = request.args.get('height', type=int)

    if width > MAX_IMG_WIDTH:
        width = MAX_IMG_WIDTH
    if height > MAX_IMG_HEIGHT:
        height = MAX_IMG_HEIGHT

    flags = request.args.get('flags')

    eyepiece_fov = to_float(request.args.get('epfov'), None)

    img_bytes = BytesIO()
    _create_chart_legend(img_bytes, float(ra), float(dec), width, height, gui_fld_size, maglim, dso_maglim, eyepiece_fov,
                         flags=flags, img_format='png')
    img_bytes.seek(0)
    return img_bytes


def common_chart_pdf_img(obj_ra, obj_dec, ra, dec, dso_names=None, visible_objects=None, highlights_dso_list=None,
                         observed_dso_ids=None, trajectory=None, highlights_pos_list=None):
    gui_fld_size, maglim, dso_maglim = get_fld_size_mags_from_request()

    trajectory = _fld_filter_trajectory(trajectory, gui_fld_size, A4_WIDTH)

    flags = request.args.get('flags')

    landscape = request.args.get('landscape', 'true') == 'true'

    eyepiece_fov = to_float(request.args.get('epfov'), None)

    img_bytes = BytesIO()
    _create_chart_pdf(img_bytes, visible_objects, obj_ra, obj_dec, float(ra), float(dec), gui_fld_size, maglim, dso_maglim,
                      landscape=landscape, dso_names=dso_names, flags=flags, highlights_dso_list=highlights_dso_list,
                      highlights_pos_list=highlights_pos_list, observed_dso_ids=observed_dso_ids, trajectory=trajectory,
                      eyepiece_fov=eyepiece_fov)
    img_bytes.seek(0)
    return img_bytes


def common_ra_dec_fsz_from_request(form):
    ra = request.args.get('ra', None)
    dec = request.args.get('dec', None)
    fsz = request.args.get('fsz', None)
    if ra and dec and fsz:
        form.ra.data = float(ra)
        form.dec.data = float(dec)
        gui_fld_size = to_float(fsz, FIELD_SIZES[-1])
        for i in range(len(FIELD_SIZES)-1, -1, -1):
            if gui_fld_size >= FIELD_SIZES[i]:
                form.radius.data = i
                break
        else:
            form.radius.data = len(FIELD_SIZES)
        return True
    return False


def common_prepare_chart_data(form, cancel_selection_url=None):
    fld_size = FIELD_SIZES[form.radius.data]

    cur_mag_scale = MAG_SCALES[form.radius.data]
    cur_dso_mag_scale = DSO_MAG_SCALES[form.radius.data]

    if request.method == 'GET':
        _, pref_maglim, pref_dso_maglim = _get_fld_size_maglim(form.radius.data)
        form.maglim.data = pref_maglim
        form.dso_maglim.data = pref_dso_maglim

        if request.args.get('splitview', 'false') == 'true':
            form.splitview.data = 'true'
        if request.args.get('fullscreen', 'false') == 'true':
            form.fullscreen.data = 'true'
        if request.args.get('epfov'):
            form.eyepiece_fov.data = request.args.get('epfov')
        else:
            form.eyepiece_fov.data = session.get('chart_eyepiece_fov', form.eyepiece_fov.data)

        if request.args.get('dss', 'false') == 'true':
            session['chart_dss_layer'] = 'blue' if session.get('theme', '') == 'night' else 'colored'

        if session.get('theme', '') == 'night' and session.get('chart_dss_layer','') == 'blue':
            session['chart_dss_layer'] = 'colored'

        form.show_telrad.data = session.get('chart_show_telrad', form.show_telrad.data)
        form.show_picker.data = session.get('chart_show_picker', form.show_picker.data)
        form.show_constell_shapes.data = session.get('chart_show_constell_shapes', form.show_constell_shapes.data)
        form.show_constell_borders.data = session.get('chart_show_constell_borders', form.show_constell_borders.data)
        form.dss_layer.data = session.get('chart_dss_layer', form.dss_layer.data)
        form.show_equatorial_grid.data = session.get('chart_show_equatorial_grid', form.show_equatorial_grid.data)
        form.show_dso_mag.data = session.get('chart_show_dso_mag', form.show_dso_mag.data)
        form.show_star_mag.data = session.get('chart_show_star_mag', form.show_star_mag.data)
        form.mirror_x.data = session.get('chart_mirror_x', form.mirror_x.data)
        form.mirror_y.data = session.get('chart_mirror_y', form.mirror_y.data)
        form.optimize_traffic.data = session.get('optimize_traffic', form.optimize_traffic.data)
    else:
        session['chart_eyepiece_fov'] = form.eyepiece_fov.data
        session['chart_show_telrad'] = form.show_telrad.data
        session['chart_show_picker'] = form.show_picker.data
        session['chart_show_constell_shapes'] = form.show_constell_shapes.data
        session['chart_show_constell_borders'] = form.show_constell_borders.data
        session['chart_show_dso'] = form.show_dso.data
        session['chart_show_solar_system'] = form.show_solar_system.data
        session['chart_dss_layer'] = form.dss_layer.data
        if session.get('theme', '') == 'night' and session.get('chart_dss_layer','') == 'blue':
            session['chart_dss_layer'] = 'colored'
        session['chart_show_equatorial_grid'] = form.show_equatorial_grid.data
        session['chart_mirror_x'] = form.mirror_x.data
        session['chart_mirror_y'] = form.mirror_y.data
        session['chart_show_dso_mag'] = form.show_dso_mag.data
        session['chart_show_star_mag'] = form.show_star_mag.data
        session['optimize_traffic'] = form.optimize_traffic.data

    form.maglim.data = _check_in_mag_interval(form.maglim.data, cur_mag_scale)
    session['pref_maglim' + str(fld_size)] = form.maglim.data

    if request.method == 'POST':
        _actualize_stars_pref_maglims(form.maglim.data, form.radius.data)

    form.dso_maglim.data = _check_in_mag_interval(form.dso_maglim.data, cur_dso_mag_scale)
    session['pref_dso_maglim'  + str(fld_size)] = form.dso_maglim.data

    if request.method == 'POST':
        _actualize_dso_pref_maglims(form.dso_maglim.data, form.radius.data)

    mag_range_values = []
    dso_mag_range_values = []

    for i in range(0, len(FIELD_SIZES)):
        _, ml, dml = _get_fld_size_maglim(i)
        mag_range_values.append(ml)
        dso_mag_range_values.append(dml)

    gui_field_sizes = STR_GUI_FIELD_SIZES

    chart_flags, legend_flags = get_chart_legend_flags(form)

    chart_dso_list_menu = common_chart_dso_list_menu()
    equipment_telescopes, equipment_eyepieces = common_equipment()

    has_date_from_to = hasattr(form, 'date_from') and hasattr(form, 'date_to')
    date_from = form.date_from.data if has_date_from_to else None
    date_to = form.date_to.data if has_date_from_to else None
    back_search_url_b64 = base64.b64encode(request.full_path.encode()).decode('utf-8')
    show_not_found = session.pop('show_not_found', None)
    theme = session.get('theme', '')

    if cancel_selection_url is None:
        cancel_selection_url = url_for('main_chart.chart')

    eyepiece_fov = form.eyepiece_fov.data if form.eyepiece_fov.data else ''

    return ChartControl(chart_fsz=str(fld_size),
                        mag_scale=cur_mag_scale, mag_ranges=MAG_SCALES, mag_range_values=mag_range_values,
                        dso_mag_scale=cur_dso_mag_scale, dso_mag_ranges=DSO_MAG_SCALES, dso_mag_range_values=dso_mag_range_values,
                        theme=theme,
                        gui_field_sizes=gui_field_sizes,
                        chart_mlim=str(form.maglim.data),
                        chart_flags=chart_flags, legend_flags=legend_flags, chart_pdf_flags=(chart_flags + legend_flags),
                        chart_dso_list_menu=chart_dso_list_menu,
                        has_date_from_to=has_date_from_to,
                        date_from=date_from, date_to=date_to,
                        back_search_url_b64=back_search_url_b64,
                        show_not_found=show_not_found,
                        cancel_selection_url=cancel_selection_url,
                        eyepiece_fov=eyepiece_fov,
                        equipment_telescopes=equipment_telescopes,
                        equipment_eyepieces=equipment_eyepieces,
                        )


def common_prepare_date_from_to(form):
    if request.method == 'GET':
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        if date_from and date_to:
            try:
                date_from = datetime.strptime(date_from, '%d-%m-%Y').date()
                date_to = datetime.strptime(date_to, '%d-%m-%Y').date()
                form.date_from.data = date_from
                form.date_to.data = date_to
            except ValueError:
                pass


def _calc_spherical_angle(ra1, dec1, ra2, dec2, ra3, dec3):
    cos_dec1, sin_dec1 = cos(dec1), sin(dec1)
    cos_dec2, sin_dec2 = cos(dec2), sin(dec2)
    cos_dec3, sin_dec3 = cos(dec3), sin(dec3)

    cos_ra1, sin_ra1 = cos(ra1), sin(ra1)
    cos_ra2, sin_ra2 = cos(ra2), sin(ra2)
    cos_ra3, sin_ra3 = cos(ra3), sin(ra3)

    vec1_x = cos_dec1 * cos_ra1 - cos_dec2 * cos_ra2
    vec1_y = cos_dec1 * sin_ra1 - cos_dec2 * sin_ra2
    vec1_z = sin_dec1 - sin_dec2

    vec2_x = cos_dec3 * cos_ra3 - cos_dec2 * cos_ra2
    vec2_y = cos_dec3 * sin_ra3 - cos_dec2 * sin_ra2
    vec2_z = sin_dec3 - sin_dec2

    dot_product = vec1_x * vec2_x + vec1_y * vec2_y + vec1_z * vec2_z

    norm1 = (vec1_x ** 2 + vec1_y ** 2 + vec1_z ** 2) ** 0.5
    norm2 = (vec2_x ** 2 + vec2_y ** 2 + vec2_z ** 2) ** 0.5

    cos_angle = max(min(dot_product / (norm1 * norm2), 1.0), -1.0)
    angle = acos(cos_angle)

    return angle


def _interpolate_adaptive_segm(ra1, dec1, t1, lbl1, ra2, dec2, t2, lbl2, ra3, dec3, t3, lbl3, ts, earth, body, threshold_rad, level):
    angle = _calc_spherical_angle(ra1, dec1, ra2, dec2, ra3, dec3)

    if level < 7 and abs(angle-pi) > threshold_rad:
        result = []
        t_c1 = t1 + (t2 - t1) / 2
        ra_c1, dec_c1, _ = earth.at(t_c1).observe(body).radec()
        ra_c1, dec_c1 = ra_c1.radians, dec_c1.radians
        result.extend(_interpolate_adaptive_segm(ra1, dec1, t1, lbl1, ra_c1, dec_c1, t_c1, None, ra2, dec2, t2, lbl2, ts, earth, body, threshold_rad, level+1))
        result.append((ra2, dec2, lbl2))
        if level > 0:
            t_c2 = t2 + (t3 - t2) / 2
            ra_c2, dec_c2, _ = earth.at(t_c2).observe(body).radec()
            ra_c2, dec_c2 = ra_c2.radians, dec_c2.radians
            result.extend(_interpolate_adaptive_segm(ra2, dec2, t2, lbl2, ra_c2, dec_c2, t_c2, None, ra3, dec3, t3, lbl3, ts, earth, body, threshold_rad, level+1))
    else:
        result = [(ra2, dec2, lbl2)]
    return result


def _interpolate_adaptive(trajectory, trajectory_time, ts, earth, body):
    result = [trajectory[0]]

    threshold_rad = 5.0 * pi / 180.0

    for i in range(1, len(trajectory) - 1):
        ra1, dec1, lbl1 = trajectory[i - 1]
        ra2, dec2, lbl2 = trajectory[i]
        ra3, dec3, lbl3 = trajectory[i + 1]
        t1 = trajectory_time[i - 1]
        t2 = trajectory_time[i]
        t3 = trajectory_time[i + 1]

        result.extend(_interpolate_adaptive_segm(ra1, dec1, t1, lbl1, ra2, dec2, t2, lbl2, ra3, dec3, t3, lbl3, ts, earth, body, threshold_rad, 0))

    result.append(trajectory[-1])

    return result


def get_trajectory_b64(d1, d2, ts, earth, body):
    if d1 < d2:
        time_delta = d2 - d1
        if time_delta.days > 365:
            d2 = d1 + timedelta(days=365)
        dt, hr_step = get_trajectory_time_delta(d1, d2)
        trajectory = []
        hr_count = 0
        prev_date = None

        trajectory_time = []

        while d1 <= d2:
            t = ts.utc(d1.year, d1.month, d1.day, d1.hour)
            ra, dec, _ = earth.at(t).observe(body).radec()

            if d1 == d2 or prev_date is None or prev_date.month != d1.month:
                fmt = '%d.%-m.' if (hr_count % 24) == 0 else '%H:00'
            else:
                fmt = '%d' if (hr_count % 24) == 0 else '%H:00'

            trajectory.append((ra.radians, dec.radians, d1.strftime(fmt)))
            trajectory_time.append(t)

            prev_date = d1
            d1 += dt
            hr_count += hr_step

        interpolated_trajectory = _interpolate_adaptive(trajectory, trajectory_time, ts, earth, body)

        trajectory_json = json.dumps(interpolated_trajectory)
        trajectory_b64 = base64.b64encode(trajectory_json.encode('utf-8'))

    else:
        trajectory_b64 = None

    return trajectory_b64


def _actualize_stars_pref_maglims(cur_maglim, magscale_index):
    mag_interval = MAG_SCALES[magscale_index]
    cur_index = cur_maglim - mag_interval[0]
    max_index = mag_interval[1] - mag_interval[0]

    for i in range(len(MAG_SCALES)):
        if i == len(MAG_SCALES)-1:
            # max field level can be just actualized only manually
            continue
        if i == magscale_index:
            continue
        mag_interval = MAG_SCALES[i]
        pref_mag = mag_interval[0] + int(cur_index * (mag_interval[1]-mag_interval[0]) / max_index)
        session['pref_maglim' + str(FIELD_SIZES[i])] = pref_mag


def _actualize_dso_pref_maglims(cur_maglim, magscale_index):
    for i in range(magscale_index+1, len(DSO_MAG_SCALES)):
        dso_maglim = session.get('pref_dso_maglim' + str(FIELD_SIZES[i]))
        if dso_maglim is not None and dso_maglim > cur_maglim:
            session['pref_dso_maglim' + str(FIELD_SIZES[i])] = cur_maglim

    for i in range(0, magscale_index):
        dso_maglim = session.get('pref_dso_maglim' + str(FIELD_SIZES[i]))
        if dso_maglim is not None and dso_maglim < cur_maglim:
            session['pref_dso_maglim' + str(FIELD_SIZES[i])] = cur_maglim


def _get_fld_size_maglim(fld_size_index):
    fld_size = FIELD_SIZES[fld_size_index]

    mag_scale = MAG_SCALES[fld_size_index]
    dso_mag_scale = DSO_MAG_SCALES[fld_size_index]

    maglim = session.get('pref_maglim' + str(fld_size))
    if maglim is None:
        maglim = (mag_scale[0] + mag_scale[1]) // 2

    dso_maglim = session.get('pref_dso_maglim' + str(fld_size))
    if dso_maglim is None:
        if fld_size_index == len(MAG_SCALES) - 1:
            dso_maglim = dso_mag_scale[0] + 1  # use the second lowest mag to decrease number of DSO in the largest field
        else:
            dso_maglim = (dso_mag_scale[0] + dso_mag_scale[1]) // 2
        for i in range(fld_size_index+1, len(DSO_MAG_SCALES)):
            prev_dso_maglim = session.get('pref_dso_maglim' + str(FIELD_SIZES[i]))
            if prev_dso_maglim is not None and prev_dso_maglim > dso_maglim:
                dso_maglim = prev_dso_maglim
        for i in range(fld_size_index):
            next_dso_maglim = session.get('pref_dso_maglim' + str(FIELD_SIZES[i]))
            if next_dso_maglim is not None and next_dso_maglim < dso_maglim:
                dso_maglim = next_dso_maglim

    return fld_size, maglim, dso_maglim


def get_fld_size_mags_from_request():
    gui_fld_size = to_float(request.args.get('fsz'), 23.0)

    for i in range(len(FIELD_SIZES)-1, -1, -1):
        if gui_fld_size >= FIELD_SIZES[i]:
            fld_size_index = i
            break
    else:
        fld_size_index = 0

    fld_size, maglim, dso_maglim = _get_fld_size_maglim(fld_size_index)

    return gui_fld_size, maglim, dso_maglim


def _check_in_mag_interval(mag, mag_interval):
    if mag is None:
        return mag_interval[0]
    if mag_interval[0] > mag:
        return mag_interval[0]
    if mag_interval[1] < mag:
        return mag_interval[1]
    return mag


def _create_chart(png_fobj, visible_objects, obj_ra, obj_dec, ra, dec, fld_size, width, height, star_maglim, dso_maglim,
                  show_legend=True, dso_names=None, flags='', highlights_dso_list=None, observed_dso_ids=None,
                  highlights_pos_list=None, trajectory=None, hl_constellation=None, img_formats='png'):
    """Create chart in czsky process."""
    global free_mem_counter
    tm = time()

    used_catalogs = _load_used_catalogs()

    config = fchart3.EngineConfiguration()
    _setup_skymap_graphics(config, fld_size, width, DEFAULT_SCREEN_FONT_SIZE)

    config.show_dso_legend = False
    config.show_orientation_legend = False

    config.show_flamsteed = (fld_size <= 30)

    if width and width <= MOBILE_WIDTH:
        config.show_flamsteed = False

    config.show_constellation_shapes = FlagValue.CONSTELL_SHAPES.value in flags
    config.show_constellation_borders = FlagValue.CONSTELL_BORDERS.value in flags
    config.show_deepsky = FlagValue.SHOW_DEEPSKY.value in flags
    config.show_nebula_outlines = config.show_deepsky
    config.show_equatorial_grid = FlagValue.SHOW_EQUATORIAL_GRID.value in flags
    config.show_dso_mag = FlagValue.SHOW_DSO_MAG.value in flags
    config.show_star_mag = FlagValue.SHOW_STAR_MAG.value in flags
    config.show_picker = False  # do not show picker, only activate it
    if FlagValue.SHOW_PICKER.value in flags:
        config.picker_radius = PICKER_RADIUS
    else:
        config.picker_radius = -1

    if show_legend:
        config.show_mag_scale_legend = True
        config.show_map_scale_legend = True
        config.show_field_border = True

    if dso_maglim is None:
        dso_maglim = -10

    high_quality = request.args.get('hqual', '')
    avif = request.args.get('avif', '')

    jpg_low_quality = int(current_app.config.get('CHART_JPEG_LOW_QUALITY'))
    jpg_high_quality = int(current_app.config.get('CHART_JPEG_HIGH_QUALITY'))
    jpg_quality = jpg_high_quality if high_quality == '1' else jpg_low_quality

    avif_speed = int(current_app.config.get('CHART_AVIF_SPEED'))
    avif_low_quality = int(current_app.config.get('CHART_AVIF_LOW_QUALITY'))
    avif_high_quality = int(current_app.config.get('CHART_AVIF_HIGH_QUALITY'))
    avif_quality = avif_high_quality if high_quality == '1' else avif_low_quality
    avif_width_threshold = int(current_app.config.get('CHART_AVIF_THRESHOLD_WIDTH'))

    optimize_traffic = session.get('optimize_traffic', 'false')

    if avif_width_threshold >= width and (('avif' in img_formats and avif == '1') or optimize_traffic == 'true'):
        img_format = 'avif'
    elif 'jpg' in img_formats:
        img_format = 'jpg'
    else:
        img_format = 'png'

    show_dss = FlagValue.DSS_COLORED.value in flags or FlagValue.DSS_BLUE.value in flags

    if show_dss and img_format == 'jpg':
        img_format = 'png'

    projection = fchart3.ProjectionType.ORTHOGRAPHIC if show_dss else fchart3.ProjectionType.STEREOGRAPHIC

    artist = fchart3.CairoDrawing(png_fobj, width if width else 220, height if height else 220, format=img_format,
                                  pixels=True if width else False, jpg_quality=jpg_quality,
                                  avif_quality=avif_quality, avif_speed=avif_speed)
    # artist = fchart3.SkiaDrawing(png_fobj, width if width else 220, height if height else 220, format=img_format,
    #                               pixels=True if width else False, jpg_quality=jpg_quality)
    engine = fchart3.SkymapEngine(artist, language=fchart3.LABELi18N, lm_stars=star_maglim, lm_deepsky=dso_maglim)
    engine.set_configuration(config)

    mirror_x = FlagValue.MIRROR_X.value in flags
    mirror_y = FlagValue.MIRROR_Y.value in flags

    engine.set_field(ra, dec, fld_size*pi/180.0/2.0, mirror_x, mirror_y, projection)

    if not highlights_pos_list and obj_ra is not None and obj_dec is not None:
        highlights = _create_highlights(obj_ra, obj_dec, config.highlight_linewidth*1.3)
    elif highlights_pos_list:
        highlights = _create_highlights_from_pos_list(highlights_pos_list, config.highlight_color, config.highlight_linewidth)
    else:
        highlights = None

    showing_dsos = set()
    if dso_names:
        for dso_name in dso_names:
            dso = _find_dso_by_name(dso_name)
            if dso:
                showing_dsos.add(dso)

    for dso_name in FORCE_SHOWING_DSOS:
        dso = _find_dso_by_name(dso_name)
        if dso:
            showing_dsos.add(dso)

    dso_highlights = _create_dso_highlights(highlights_dso_list, observed_dso_ids) if highlights_dso_list else None

    transparent = False
    if show_dss:
        config.show_simple_milky_way = False
        config.show_enhanced_milky_way = False
        config.show_star_circles = False
        transparent = True

    sl_bodies = _get_solsys_bodies() if FlagValue.SHOW_SOLAR_SYSTEM.value in flags else None

    engine.make_map(used_catalogs,
                    solsys_bodies=sl_bodies,
                    jd=None, # jd=skyfield_ts.now().tdb,
                    showing_dsos=showing_dsos,
                    dso_highlights=dso_highlights,
                    highlights=highlights,
                    dso_hide_filter=_get_dso_hide_filter(),
                    trajectory=trajectory,
                    hl_constellation=hl_constellation,
                    visible_objects=visible_objects,
                    use_optimized_mw=(high_quality != '1'),
                    transparent=transparent)

    free_mem_counter += 1
    if free_mem_counter > NO_FREE_MEM_CYCLES:
        free_mem_counter = 0
        used_catalogs.free_mem()

    print("Map created within : {} ms".format(str(time()-tm)), flush=True)

    return img_format


def _create_chart_pdf(pdf_fobj, visible_objects, obj_ra, obj_dec, ra, dec, fld_size, star_maglim, dso_maglim,
                      landscape=True, show_legend=True, dso_names=None, flags='', highlights_dso_list=None,
                      observed_dso_ids=None, highlights_pos_list=None, trajectory=None, eyepiece_fov=None):
    """Create chart PDF in czsky process."""
    global free_mem_counter
    tm = time()

    if flags is None:
        flags = ''

    used_catalogs = _load_used_catalogs()

    config = fchart3.EngineConfiguration()
    _setup_skymap_graphics(config, fld_size, None, DEFAULT_PDF_FONT_SIZE, force_light_mode=True, is_pdf=True)

    config.show_dso_legend = False
    config.show_orientation_legend = True
    config.show_equatorial_grid = True

    config.show_flamsteed = (fld_size <= 20)

    config.show_constellation_shapes = FlagValue.CONSTELL_SHAPES.value in flags
    config.show_constellation_borders = FlagValue.CONSTELL_BORDERS.value in flags
    config.show_deepsky = FlagValue.SHOW_DEEPSKY.value in flags
    config.show_equatorial_grid = FlagValue.SHOW_EQUATORIAL_GRID.value in flags
    config.fov_telrad = FlagValue.FOV_TELRAD.value in flags
    config.show_simple_milky_way = False
    config.show_enhanced_milky_way = False
    config.show_dso_mag = FlagValue.SHOW_DSO_MAG.value in flags
    config.show_star_mag = FlagValue.SHOW_STAR_MAG.value in flags
    config.eyepiece_fov = eyepiece_fov
    config.star_mag_shift = 1.5  # increase radius of star by 1.5 magnitude

    if show_legend:
        config.show_mag_scale_legend = True
        config.show_map_scale_legend = True
        config.show_field_border = True

    if dso_maglim is None:
        dso_maglim = -10

    if landscape:
        artist = fchart3.CairoDrawing(pdf_fobj, 267, 180, format='pdf', landscape=landscape)
    else:
        artist = fchart3.CairoDrawing(pdf_fobj, 180, 267, format='pdf', landscape=landscape)
    engine = fchart3.SkymapEngine(artist, language=fchart3.LABELi18N, lm_stars=star_maglim, lm_deepsky=dso_maglim)
    engine.set_configuration(config)

    mirror_x = FlagValue.MIRROR_X.value in flags
    mirror_y = FlagValue.MIRROR_Y.value in flags

    engine.set_field(ra, dec, fld_size*pi/180.0/2.0, mirror_x, mirror_y, fchart3.ProjectionType.STEREOGRAPHIC)

    if obj_ra is not None and obj_dec is not None:
        highlights = _create_highlights(obj_ra, obj_dec, config.highlight_linewidth*1.3, True)
    elif highlights_pos_list:
        highlights = _create_highlights_from_pos_list(highlights_pos_list, config.highlight_color, config.highlight_linewidth)
    else:
        highlights = None

    showing_dsos = set()
    if dso_names:
        for dso_name in dso_names:
            dso = _find_dso_by_name(dso_name)
            if dso:
                showing_dsos.add(dso)

    dso_highlights = _create_dso_highlights(highlights_dso_list, observed_dso_ids, True) if highlights_dso_list else None

    dso_hide_filter = _get_dso_hide_filter()

    sl_bodies = _get_solsys_bodies() if FlagValue.SHOW_SOLAR_SYSTEM.value in flags else None

    engine.make_map(used_catalogs,
                    solsys_bodies = sl_bodies,
                    showing_dsos=showing_dsos,
                    dso_highlights=dso_highlights,
                    highlights=highlights,
                    dso_hide_filter=dso_hide_filter,
                    trajectory=trajectory,
                    visible_objects=visible_objects)

    print("PDF map created within : {} ms".format(str(time()-tm)), flush=True)


def _create_chart_legend(png_fobj, ra, dec, width, height, fld_size, star_maglim, dso_maglim, eyepiece_fov, flags='', img_format='png'):
    global free_mem_counter
    # tm = time()

    used_catalogs = _load_used_catalogs()

    config = fchart3.EngineConfiguration()
    _setup_skymap_graphics(config, fld_size, width, config.font_size)

    config.show_dso_legend = False
    config.show_orientation_legend = False

    config.legend_only = True
    config.show_mag_scale_legend = True
    config.show_map_scale_legend = True
    config.show_field_border = False
    config.show_equatorial_grid = True
    config.show_picker = FlagValue.SHOW_PICKER.value in flags
    config.picker_radius = PICKER_RADIUS

    config.fov_telrad = FlagValue.FOV_TELRAD.value in flags

    config.eyepiece_fov = eyepiece_fov
    config.star_mag_shift = 1.0  # increase radius of star by 1 magnitude

    config.show_flamsteed = (fld_size <= 20)

    if dso_maglim is None:
        dso_maglim = -10

    artist = fchart3.CairoDrawing(png_fobj, width if width else 220, height if height else 220, format=img_format, pixels=True if width else False)
    engine = fchart3.SkymapEngine(artist, language=fchart3.LABELi18N, lm_stars=star_maglim, lm_deepsky=dso_maglim)
    engine.set_configuration(config)

    projection = fchart3.ProjectionType.ORTHOGRAPHIC if ('S' in flags) else fchart3.ProjectionType.STEREOGRAPHIC

    mirror_x = FlagValue.MIRROR_X.value in flags
    mirror_y = FlagValue.MIRROR_Y.value in flags

    engine.set_field(ra, dec, fld_size*pi/180.0/2.0, mirror_x, mirror_y, projection)

    engine.make_map(used_catalogs, transparent=True)
    free_mem_counter += 1
    if free_mem_counter > NO_FREE_MEM_CYCLES:
        free_mem_counter = 0
        used_catalogs.free_mem()
    # app.logger.info("Map created within : %s ms", str(time()-tm))


def _create_highlights(obj_ra, obj_dec, line_width, force_light_mode=False):
    if force_light_mode or session.get('theme', '') == 'light':
        color = (0.0, 0.5, 0.0)
    elif session.get('theme', '') == 'night':
        color = (0.5, 0.2, 0.0)
    else:
        color = (0.0, 0.5, 0.0)

    hl = fchart3.HighlightDefinition('cross', line_width, color, [[obj_ra, obj_dec, '', '']])
    return [hl]


def _create_dso_highlights(highlights_dso_list, observed_dso_ids, force_light_mode=False):
    full_highlighted_dsos = set()
    dashed_highlighted_dsos = set()

    for hl_dso in highlights_dso_list:
        dso = _find_dso_by_name(hl_dso.name)
        if dso:
            if observed_dso_ids and hl_dso.id in observed_dso_ids:
                dashed_highlighted_dsos.add(dso)
            else:
                full_highlighted_dsos.add(dso)

    if force_light_mode or session.get('theme', '') == 'light':
        color = (0.1, 0.2, 0.4)
        line_width = 0.3
    elif session.get('theme', '') == 'night':
        color = (0.4, 0.2, 0.1)
        line_width = 0.3
    else:
        color = (0.15, 0.3, 0.6)
        line_width = 0.3

    # def __init__(self, dsos, line_width, color, dash):
    hl1 = fchart3.DsoHighlightDefinition(full_highlighted_dsos, line_width, color, None)
    hl2 = fchart3.DsoHighlightDefinition(dashed_highlighted_dsos, line_width+0.1, color, (0.6, 1.2))
    return [hl1, hl2]


def _create_highlights_from_pos_list(highlights_pos_list, color, line_width):
    highlight_def_items = []
    for hlpos in highlights_pos_list:
        highlight_def_items.append((hlpos[0], hlpos[1], hlpos[2], hlpos[3],))
    hl = fchart3.HighlightDefinition('circle', line_width, color, highlight_def_items)
    return [hl]


def _find_dso_by_name(dso_name):
    if dso_name not in dso_name_cache:
        dso, cat, name = used_catalogs.lookup_dso(dso_name)
        dso_name_cache[dso_name] = dso
    else:
        dso = dso_name_cache[dso_name]
    return dso


def get_chart_legend_flags(form):
    chart_flags = ''
    legend_flags = ''

    if form.show_telrad.data == 'true':
        legend_flags += FlagValue.FOV_TELRAD.value

    if form.show_picker.data == 'true':
        legend_flags += FlagValue.SHOW_PICKER.value
        chart_flags += FlagValue.SHOW_PICKER.value

    if form.show_constell_shapes.data == 'true':
        chart_flags += FlagValue.CONSTELL_SHAPES.value

    if form.show_constell_borders.data == 'true':
        chart_flags += FlagValue.CONSTELL_BORDERS.value

    if form.show_dso.data == 'true':
        chart_flags += FlagValue.SHOW_DEEPSKY.value

    if form.show_solar_system.data == 'true':
        chart_flags += FlagValue.SHOW_SOLAR_SYSTEM.value

    if form.show_equatorial_grid.data == 'true':
        chart_flags += FlagValue.SHOW_EQUATORIAL_GRID.value

    if form.dss_layer.data == 'colored':
        chart_flags += FlagValue.DSS_COLORED.value

    if form.dss_layer.data == 'blue':
        chart_flags += FlagValue.DSS_BLUE.value

    if form.show_dso_mag.data == 'true':
        chart_flags += FlagValue.SHOW_DSO_MAG.value

    if form.show_star_mag.data == 'true':
        chart_flags += FlagValue.SHOW_STAR_MAG.value

    if form.mirror_x.data == 'true':
        legend_flags += FlagValue.MIRROR_X.value
        chart_flags += FlagValue.MIRROR_X.value

    if form.mirror_y.data == 'true':
        legend_flags += FlagValue.MIRROR_Y.value
        chart_flags += FlagValue.MIRROR_Y.value

    return chart_flags, legend_flags


class FChartDsoListMenu:
    def __init__(self, dso_lists, is_wish_list, session_plans, observing_sessions):
        self.dso_lists = dso_lists
        self.is_wish_list = is_wish_list
        self.session_plans = session_plans
        self.observing_sessions = observing_sessions


def common_chart_dso_list_menu():
    dso_lists = DsoList.query.all()
    if not current_user.is_anonymous:
        is_wish_list = True
        session_plans = SessionPlan.query.filter_by(user_id=current_user.id).all()
        observing_sessions = ObservingSession.query.filter_by(user_id=current_user.id).all()
    else:
        is_wish_list = False
        session_plans = None
        observing_sessions = None

    return FChartDsoListMenu(dso_lists, is_wish_list, session_plans, observing_sessions)


def common_equipment():
    if not current_user.is_anonymous:
        telescopes = Telescope.query.filter_by(user_id=current_user.id, is_deleted=False, is_active=True, fixed_magnification=None).all()
        eyepieces = Eyepiece.query.filter_by(user_id=current_user.id, is_deleted=False, is_active=True).all()
        if telescopes and eyepieces:
            return telescopes, eyepieces
    return None, None


def get_trajectory_time_delta(d1, d2):
    delta = d2 - d1
    if delta.days > 120:
        return timedelta(days=30), 0
    if delta.days > 30:
        return timedelta(days=7), 0
    if delta.days > 4:
        return timedelta(days=1), 0
    if delta.days > 2:
        return timedelta(hours=12), 12
    if delta.days > 1:
        return timedelta(hours=6), 6
    return timedelta(hours=3), 3


def common_set_initial_ra_dec(form):
    day_zero = datetime(2021, 3, 21, 0, 0, 0).timetuple().tm_yday
    day_now = datetime.now().timetuple().tm_yday
    ra = 2.0 * np.pi * (day_now - day_zero) / 365 + np.pi
    if ra > 2 * np.pi:
        ra -= 2 * np.pi
    dec = 0.0
    if form.ra.data is None:
        form.ra.data = ra
    if form.dec.data is None:
        form.dec.data = dec


def _get_chart_font_face():
    global chart_font_face
    global chart_font_face_initialized

    if not chart_font_face_initialized:
        chart_font_face_initialized = True
        if current_app.config.get('CHART_FONT'):
            chart_font_face = create_cairo_font_face_for_file(current_app.config.get('CHART_FONT'), 0)

    return chart_font_face


def _get_pdf_font_face():
    global pdf_font_face
    global pdf_font_face_initialized

    if not pdf_font_face_initialized:
        pdf_font_face_initialized = True
        if current_app.config.get('PDF_FONT'):
            pdf_font_face = create_cairo_font_face_for_file(current_app.config.get('PDF_FONT'), 0)

    return pdf_font_face


ft_initialized = False


def create_cairo_font_face_for_file(filename, faceindex=0, loadoptions=0):
    "given the name of a font file, and optional faceindex to pass to FT_New_Face" \
    " and loadoptions to pass to cairo_ft_font_face_create_for_ft_face, creates" \
    " a cairo.FontFace object that may be used to render text with that font."
    global ft_initialized
    global _freetype_so
    global _cairo_so
    global _ft_lib
    global _ft_destroy_key
    global _surface

    CAIRO_STATUS_SUCCESS = 0
    FT_Err_Ok = 0

    if not ft_initialized:
        # find shared objects
        _freetype_so = ct.CDLL("libfreetype.so.6")
        _cairo_so = ct.CDLL("libcairo.so.2")
        _cairo_so.cairo_ft_font_face_create_for_ft_face.restype = ct.c_void_p
        _cairo_so.cairo_ft_font_face_create_for_ft_face.argtypes = [ ct.c_void_p, ct.c_int ]
        _cairo_so.cairo_font_face_get_user_data.restype = ct.c_void_p
        _cairo_so.cairo_font_face_get_user_data.argtypes = (ct.c_void_p, ct.c_void_p)
        _cairo_so.cairo_font_face_set_user_data.argtypes = (ct.c_void_p, ct.c_void_p, ct.c_void_p, ct.c_void_p)
        _cairo_so.cairo_set_font_face.argtypes = [ ct.c_void_p, ct.c_void_p ]
        _cairo_so.cairo_font_face_status.argtypes = [ ct.c_void_p ]
        _cairo_so.cairo_font_face_destroy.argtypes = (ct.c_void_p,)
        _cairo_so.cairo_status.argtypes = [ ct.c_void_p ]
        # initialize freetype
        _ft_lib = ct.c_void_p()
        status = _freetype_so.FT_Init_FreeType(ct.byref(_ft_lib))
        if status != FT_Err_Ok :
            raise RuntimeError("Error %d initializing FreeType library." % status)

        class PycairoContext(ct.Structure):
            _fields_ = \
                [
                    ("PyObject_HEAD", ct.c_byte * object.__basicsize__),
                    ("ctx", ct.c_void_p),
                    ("base", ct.c_void_p),
                ]

        _surface = cairo.ImageSurface(cairo.FORMAT_A8, 0, 0)
        _ft_destroy_key = ct.c_int() # dummy address
        _initialized = True

    ft_face = ct.c_void_p()
    cr_face = None
    try:
        # load FreeType face
        status = _freetype_so.FT_New_Face(_ft_lib, filename.encode("utf-8"), faceindex, ct.byref(ft_face))
        if status != FT_Err_Ok :
            raise RuntimeError("Error %d creating FreeType font face for %s" % (status, filename))

        # create Cairo font face for freetype face
        cr_face = _cairo_so.cairo_ft_font_face_create_for_ft_face(ft_face, loadoptions)
        status = _cairo_so.cairo_font_face_status(cr_face)
        if status != CAIRO_STATUS_SUCCESS:
            raise RuntimeError("Error %d creating cairo font face for %s" % (status, filename))
        # Problem: Cairo doesn't know to call FT_Done_Face when its font_face object is
        # destroyed, so we have to do that for it, by attaching a cleanup callback to
        # the font_face. This only needs to be done once for each font face, while
        # cairo_ft_font_face_create_for_ft_face will return the same font_face if called
        # twice with the same FT Face.
        # The following check for whether the cleanup has been attached or not is
        # actually unnecessary in our situation, because each call to FT_New_Face
        # will return a new FT Face, but we include it here to show how to handle the
        # general case.
        if _cairo_so.cairo_font_face_get_user_data(cr_face, ct.byref(_ft_destroy_key)) == None:
            status = _cairo_so.cairo_font_face_set_user_data \
                    (
                    cr_face,
                    ct.byref(_ft_destroy_key),
                    ft_face,
                    _freetype_so.FT_Done_Face
                )
            if status != CAIRO_STATUS_SUCCESS:
                raise RuntimeError("Error %d doing user_data dance for %s" % (status, filename))
            ft_face = None # Cairo has stolen my reference

        # set Cairo font face into Cairo context
        cairo_ctx = cairo.Context(_surface)
        cairo_t = PycairoContext.from_address(id(cairo_ctx)).ctx
        _cairo_so.cairo_set_font_face(cairo_t, cr_face)
        status = _cairo_so.cairo_font_face_status(cairo_t)
        if status != CAIRO_STATUS_SUCCESS :
            raise RuntimeError("Error %d creating cairo font face for %s" % (status, filename))

    finally :
        _cairo_so.cairo_font_face_destroy(cr_face)
        _freetype_so.FT_Done_Face(ft_face)

    # get back Cairo font face as a Python object
    face = cairo_ctx.get_font_face()
    return face

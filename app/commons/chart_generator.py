import base64
import os
from datetime import timedelta
from datetime import datetime
from io import BytesIO
from math import pi, sqrt
from time import time
import numpy as np
import ctypes as ct
import cairo

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
    Lens,
    ObservingSession,
    ObservationTargetType,
    SessionPlan,
    Telescope,
)

from .utils import to_float, to_boolean

MOBILE_WIDTH = 768

used_catalogs = None
dso_name_cache = None
dso_hide_filter = None

MAX_IMG_WIDTH = 3000
MAX_IMG_HEIGHT = 3000

A4_WIDTH = 800

FIELD_SIZES = (0.25, 0.5, 1, 2, 5, 10, 20, 40, 100)

GUI_FIELD_SIZES = []

for i in range(0, len(FIELD_SIZES)-1):
    GUI_FIELD_SIZES.append(FIELD_SIZES[i])
    GUI_FIELD_SIZES.append((FIELD_SIZES[i] + FIELD_SIZES[i+1]) / 2)

GUI_FIELD_SIZES.append(FIELD_SIZES[-1])

STR_GUI_FIELD_SIZES = ','.join(str(x) for x in GUI_FIELD_SIZES)

MAG_SCALES = [(14, 16), (13, 16), (12, 16), (11, 15), (10, 13), (8, 11), (6, 9), (6, 8), (5, 7)]
DSO_MAG_SCALES = [(10, 18), (10, 18), (10, 18), (10, 18), (10, 18), (7, 15), (7, 13), (7, 11), (6, 10)]

free_mem_counter = 0
NO_FREE_MEM_CYCLES = 500

FORCE_SHOWING_DSOS = ['NGC 1909', 'IC443']

ADD_SHOW_CATALOGS = ['Berk', 'King']

PICKER_RADIUS = 4.0

DEFAULT_SCREEN_FONT_SIZE = 3.3
DEFAULT_PDF_FONT_SIZE = 3.0

chart_font_face = None
chart_font_face_initialized = False

pdf_font_face = None
pdf_font_face_initialized = False


class ChartControl:
    def __init__(self, chart_fsz=None, mag_scale=None, mag_ranges=None, mag_range_values=None,
                 dso_mag_scale=None, dso_mag_ranges=None, dso_mag_range_values=None,
                 theme=None, gui_field_sizes=None, gui_field_index=None,
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
        self.gui_field_index = gui_field_index
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
    global used_catalogs
    if used_catalogs is None:
        data_dir = os.path.join(fchart3.get_catalogs_dir())
        usno_nomad_file = os.path.join(os.getcwd(), 'data/USNO-NOMAD-1e8.dat')
        extra_data_dir = os.path.join(os.getcwd(), 'data/')
        used_catalogs = fchart3.UsedCatalogs(data_dir,
                                             extra_data_dir,
                                             usno_nomad_file=usno_nomad_file,
                                             limiting_magnitude_deepsky=100.0,
                                             force_asterisms=False,
                                             force_unknown=False,
                                             show_catalogs=ADD_SHOW_CATALOGS,
                                             use_pgc_catalog=True)
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


def _setup_dark_theme(config, width):
    if width and width <= MOBILE_WIDTH:
        config.background_color = (0.01, 0.01, 0.01)
    else:
        config.background_color = (0.005, 0.005, 0.02)
    config.constellation_lines_color = (0.18, 0.27, 0.3)
    config.constellation_border_color = (0.3, 0.27, 0.07)
    config.constellation_hl_border_color = (0.6, 0.5, 0.14)
    config.draw_color = (1.0, 1.0, 1.0)
    config.label_color = (0.7, 0.7, 0.7)
    config.dso_color = (0.6, 0.6, 0.6)
    config.nebula_color = (0.2, 0.6, 0.2)
    config.nebula_linewidth = 0.25
    config.galaxy_color = (0.6, 0.2, 0.2)
    config.star_cluster_color = (0.6, 0.6, 0.0)
    config.galaxy_cluster_color = (0.6, 0.6, 0.6)
    if width and width <= MOBILE_WIDTH:
        config.grid_color = (0.18, 0.27, 0.3)
        config.constellation_linewidth = 0.2
    else:
        config.grid_color = (0.12, 0.18, 0.20)
        config.constellation_linewidth = 0.2
    config.constellation_border_linewidth = 0.15
    config.grid_linewidth = 0.1
    config.star_colors = True
    config.dso_dynamic_brightness = True
    config.dso_highlight_color = (0.1, 0.2, 0.4)
    config.dso_highlight_linewidth = 0.3
    config.milky_way_color = (0.05, 0.07, 0.1)
    config.light_mode = False
    config.picker_color = (0.5, 0.5, 0.0)


def _setup_night_theme(config, width):
    config.background_color = (0.01, 0.01, 0.01)
    config.constellation_lines_color = (0.37, 0.12, 0.0)
    if width and width <= MOBILE_WIDTH:
        config.constellation_linewidth = 0.2
    else:
        config.constellation_linewidth = 0.2
    config.constellation_border_color = (0.4, 0.19, 0.05)
    config.constellation_hl_border_color = (0.6, 0.26, 0.06)
    config.draw_color = (1.0, 0.5, 0.5)
    config.label_color = (0.7, 0.3, 0.3)
    config.dso_color = (0.6, 0.15, 0.0)
    config.nebula_color = (0.6, 0.15, 0.0)
    config.nebula_linewidth = 0.25
    config.galaxy_color = (0.6, 0.15, 0.0)
    config.star_cluster_color = (0.6, 0.15, 0.0)
    config.galaxy_cluster_color = (0.6, 0.15, 0.0)
    config.grid_color = (0.2, 0.06, 0.06)
    config.constellation_border_linewidth = 0.15
    config.grid_linewidth = 0.1
    config.star_colors = False
    config.dso_dynamic_brightness = True
    config.dso_highlight_color = (0.4, 0.2, 0.1)
    config.dso_highlight_linewidth = 0.3
    config.milky_way_color = (0.1, 0.02, 0.02)
    config.light_mode = False
    config.picker_color = (0.5, 0.1, 0.0)
    config.eyepiece_color = (0.5, 0.0, 0.0)


def _setup_light_theme(config, width):
    fac = 0.8
    config.constellation_lines_color = (0.5 * fac, 0.7 * fac, 0.8 * fac)
    if width and width <= MOBILE_WIDTH:
        config.constellation_linewidth = 0.2
    else:
        config.constellation_linewidth = 0.2
    config.constellation_hl_border_color = (0.4, 0.4, 0.4)
    config.constellation_border_color = (0.4, 0.35, 0.05)
    config.draw_color = (0.0, 0.0, 0.0)
    config.label_color = (0.2, 0.2, 0.2)
    config.dso_color = (0.3, 0.3, 0.3)
    config.nebula_color = (0.0, 0.3, 0.0)
    config.nebula_linewidth = 0.25
    config.galaxy_color = (0.3, 0.0, 0.0)
    config.star_cluster_color = (0.3, 0.3, 0.0)
    config.galaxy_cluster_color = (0.3, 0.3, 0.3)
    config.grid_color = (0.7, 0.7, 0.7)
    config.constellation_border_linewidth = 0.15
    config.grid_linewidth = 0.1
    config.dso_dynamic_brightness = False
    config.dso_highlight_color = (0.1, 0.2, 0.4)
    config.dso_highlight_linewidth = 0.3
    config.milky_way_color = (0.836, 0.945, 0.992)
    config.light_mode = True
    config.picker_color = (0.2, 0.2, 0.0)


def _setup_skymap_graphics(config, fld_size, width, font_size, force_light_mode=False, is_pdf=False):
    config.constellation_linewidth = 0.3
    config.open_cluster_linewidth = 0.3
    config.galaxy_cluster_linewidth = 0.3
    config.constellation_border_linewidth = 0.15
    config.grid_linewidth = 0.1
    config.dso_linewidth = 0.4
    config.legend_linewidth = 0.2
    config.no_margin = True
    config.bayer_label_font_fac = 1.2
    config.flamsteed_label_font_fac = 0.9
    config.outlined_dso_label_font_fac = 1.1
    if is_pdf:
        font = _get_pdf_font_face()
    else:
        font = _get_chart_font_face()
    if font is None:
        font = 'sans'
    config.font = font
    config.font_size = font_size
    config.legend_font_scale = 1.4

    if force_light_mode or session.get('theme', '') == 'light':
        _setup_light_theme(config, width)
    elif session.get('theme', '') == 'night':
        _setup_night_theme(config, width)
    else:
        _setup_dark_theme(config, width)

    if fld_size >= 60 or (fld_size >= 40 and width and width <= MOBILE_WIDTH):
        config.constellation_linespace = 1.5
        config.show_star_labels = False
    else:
        config.constellation_linespace = 2.0

    if fld_size <= 10:
        config.show_milky_way = False  # hide MW if field < 10deg
    elif config.show_milky_way:
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
            config.show_milky_way = False


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
                flt_trajectory.append(trajectory[i])
            i += m

        flt_trajectory.append(trajectory[-1])
        return flt_trajectory


def common_chart_pos_img(obj_ra, obj_dec, ra, dec, dso_names=None, visible_objects=None, highlights_dso_list=None,
                         highlights_pos_list=None, trajectory=None, hl_constellation=None):
    gui_fld_size, maglim, dso_maglim = _get_fld_size_mags_from_request()

    width = request.args.get('width', type=int)
    height = request.args.get('height', type=int)

    if width > MAX_IMG_WIDTH:
        width = MAX_IMG_WIDTH
    if height > MAX_IMG_HEIGHT:
        height = MAX_IMG_HEIGHT

    trajectory = _fld_filter_trajectory(trajectory, gui_fld_size, width)

    flags = request.args.get('flags')

    img_bytes = BytesIO()
    _create_chart(img_bytes, visible_objects, obj_ra, obj_dec, float(ra), float(dec), gui_fld_size, width, height,
                  maglim, dso_maglim, show_legend=False, dso_names=dso_names, flags=flags, highlights_dso_list=highlights_dso_list,
                  highlights_pos_list=highlights_pos_list, trajectory=trajectory, hl_constellation=hl_constellation)
    img_bytes.seek(0)
    return img_bytes


def common_chart_legend_img(obj_ra, obj_dec, ra, dec):
    gui_fld_size, maglim, dso_maglim = _get_fld_size_mags_from_request()

    width = request.args.get('width', type=int)
    height = request.args.get('height', type=int)

    if width > MAX_IMG_WIDTH:
        width = MAX_IMG_WIDTH
    if height > MAX_IMG_HEIGHT:
        height = MAX_IMG_HEIGHT

    flags = request.args.get('flags')

    eyepiece_fov = to_float(request.args.get('epfov'), None)

    img_bytes = BytesIO()
    _create_chart_legend(img_bytes, float(ra), float(dec), width, height, gui_fld_size, maglim, dso_maglim, eyepiece_fov,  flags=flags)
    img_bytes.seek(0)
    return img_bytes


def common_chart_pdf_img(obj_ra, obj_dec, ra, dec, dso_names=None, highlights_dso_list=None, trajectory=None, highlights_pos_list=None):
    gui_fld_size, maglim, dso_maglim = _get_fld_size_mags_from_request()

    trajectory = _fld_filter_trajectory(trajectory, gui_fld_size, A4_WIDTH)

    flags = request.args.get('flags')

    landscape = request.args.get('landscape', 'true') == 'true'

    eyepiece_fov = to_float(request.args.get('epfov'), None)

    img_bytes = BytesIO()
    _create_chart_pdf(img_bytes, obj_ra, obj_dec, float(ra), float(dec), gui_fld_size, maglim, dso_maglim,
                      landscape=landscape, dso_names=dso_names, flags=flags, highlights_dso_list=highlights_dso_list,
                      highlights_pos_list=highlights_pos_list, trajectory=trajectory, eyepiece_fov=eyepiece_fov)
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
                form.radius.data = i+1
                break
        else:
            form.radius.data = len(FIELD_SIZES)
        return True
    return False


def common_prepare_chart_data(form, cancel_selection_url=None):
    fld_size = FIELD_SIZES[form.radius.data-1]

    cur_mag_scale = MAG_SCALES[form.radius.data - 1]
    cur_dso_mag_scale = DSO_MAG_SCALES[form.radius.data - 1]

    if request.method == 'GET':
        _, pref_maglim, pref_dso_maglim = _get_fld_size_maglim(form.radius.data-1)
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
        form.show_telrad.data = session.get('chart_show_telrad', form.show_telrad.data)
        form.show_picker.data = session.get('chart_show_picker', form.show_picker.data)
        form.show_constell_shapes.data = session.get('chart_show_constell_shapes', form.show_constell_shapes.data)
        form.show_constell_borders.data = session.get('chart_show_constell_borders', form.show_constell_borders.data)
        form.show_dso.data = session.get('chart_show_dso', form.show_dso.data)
        form.show_equatorial_grid.data = session.get('chart_show_equatorial_grid', form.show_equatorial_grid.data)
        form.mirror_x.data = session.get('chart_mirror_x', form.mirror_x.data)
        form.mirror_y.data = session.get('chart_mirror_y', form.mirror_y.data)
    else:
        session['chart_eyepiece_fov'] = form.eyepiece_fov.data
        session['chart_show_telrad'] = form.show_telrad.data
        session['chart_show_picker'] = form.show_picker.data
        session['chart_show_constell_shapes'] = form.show_constell_shapes.data
        session['chart_show_constell_borders'] = form.show_constell_borders.data
        session['chart_show_dso'] = form.show_dso.data
        session['chart_show_equatorial_grid'] = form.show_equatorial_grid.data
        session['chart_mirror_x'] = form.mirror_x.data
        session['chart_mirror_y'] = form.mirror_y.data

    form.maglim.data = _check_in_mag_interval(form.maglim.data, cur_mag_scale)
    session['pref_maglim' + str(fld_size)] = form.maglim.data

    if request.method == 'POST':
        _actualize_stars_pref_maglims(form.maglim.data, form.radius.data - 1)

    form.dso_maglim.data = _check_in_mag_interval(form.dso_maglim.data, cur_dso_mag_scale)
    session['pref_dso_maglim'  + str(fld_size)] = form.dso_maglim.data

    if request.method == 'POST':
        _actualize_dso_pref_maglims(form.dso_maglim.data, form.radius.data - 1)

    mag_range_values = []
    dso_mag_range_values = []

    for i in range(0, len(FIELD_SIZES)):
        _, ml, dml = _get_fld_size_maglim(i)
        mag_range_values.append(ml)
        dso_mag_range_values.append(dml)

    gui_field_sizes = STR_GUI_FIELD_SIZES
    gui_field_index = (form.radius.data-1)*2

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
                        gui_field_sizes=gui_field_sizes, gui_field_index=gui_field_index,
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
        maglim = (mag_scale[0] + mag_scale[1] + 1) // 2

    dso_maglim = session.get('pref_dso_maglim' + str(fld_size))
    if dso_maglim is None:
        if fld_size_index == len(MAG_SCALES) - 1:
            dso_maglim = dso_mag_scale[0] + 1  # use second lowest mag to decrease number of DSO in largest field
        else:
            dso_maglim = (dso_mag_scale[0] + dso_mag_scale[1] + 1) // 2
        for i in range(fld_size_index+1, len(DSO_MAG_SCALES)):
            prev_dso_maglim = session.get('pref_dso_maglim' + str(FIELD_SIZES[i]))
            if prev_dso_maglim is not None and prev_dso_maglim > dso_maglim:
                dso_maglim = prev_dso_maglim
        for i in range(fld_size_index):
            next_dso_maglim = session.get('pref_dso_maglim' + str(FIELD_SIZES[i]))
            if next_dso_maglim is not None and next_dso_maglim < dso_maglim:
                dso_maglim = next_dso_maglim

    return fld_size, maglim, dso_maglim


def _get_fld_size_mags_from_request():
    gui_fld_size = to_float(request.args.get('fsz'), 20.0)

    for i in range(len(FIELD_SIZES)-1, -1, -1):
        if gui_fld_size >= FIELD_SIZES[i]:
            fld_size_index = i
            break
    else:
        fld_size_index = 0

    fld_size, maglim, dso_maglim = _get_fld_size_maglim(fld_size_index)

    if gui_fld_size > fld_size and (fld_size_index + 1) < len(FIELD_SIZES):
        next_fld_size, next_maglim, next_dso_maglim = _get_fld_size_maglim(fld_size_index+1)
        maglim = (maglim + next_maglim) / 2
        dso_maglim = (dso_maglim + next_dso_maglim) / 2

    return gui_fld_size, maglim, dso_maglim


def _check_in_mag_interval(mag, mag_interval):
    if mag_interval[0] > mag:
        return mag_interval[0]
    if mag_interval[1] < mag:
        return mag_interval[1]
    return mag


def _create_chart(png_fobj, visible_objects, obj_ra, obj_dec, ra, dec, fld_size, width, height, star_maglim, dso_maglim,
                  show_legend=True, dso_names=None, flags='', highlights_dso_list=None, highlights_pos_list=None, trajectory=None,
                  hl_constellation=None):
    """Create chart in czsky process."""
    global free_mem_counter
    tm = time()

    used_catalogs = _load_used_catalogs()

    config = fchart3.EngineConfiguration()
    _setup_skymap_graphics(config, fld_size, width, DEFAULT_SCREEN_FONT_SIZE)

    config.show_dso_legend = False
    config.show_orientation_legend = False
    config.mirror_x = 'X' in flags
    config.mirror_y = 'Y' in flags
    config.show_equatorial_grid = True

    config.show_flamsteed = (fld_size <= 30)

    config.show_constellation_shapes = 'C' in flags
    config.show_constellation_borders = 'B' in flags
    config.show_deepsky = 'D' in flags
    config.show_equatorial_grid = 'E' in flags
    config.show_picker = False  # do not show picker, only activate it
    if 'P' in flags:
        config.picker_radius = PICKER_RADIUS

    if show_legend:
        config.show_mag_scale_legend = True
        config.show_map_scale_legend = True
        config.show_field_border = True

    if dso_maglim is None:
        dso_maglim = -10

    artist = fchart3.CairoDrawing(png_fobj, width if width else 220, height if height else 220, format='png',
                                  pixels=True if width else False)
    engine = fchart3.SkymapEngine(artist, fchart3.EN, lm_stars=star_maglim, lm_deepsky=dso_maglim)
    engine.set_configuration(config)

    engine.set_field(ra, dec, fld_size*pi/180.0/2.0)

    if obj_ra is not None and obj_dec is not None:
        highlights = _create_highlights(obj_ra, obj_dec, config.dso_highlight_linewidth*1.3)
    elif highlights_pos_list:
        highlights = _create_highlights_from_pos_list(highlights_pos_list, config.dso_highlight_color, config.dso_highlight_linewidth)
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

    len1 = len(showing_dsos)

    if highlights_dso_list:
        for hl_dso in highlights_dso_list:
            dso = _find_dso_by_name(hl_dso.name)
            if dso:
                showing_dsos.add(dso)

    hl_showing_dsos = len(showing_dsos) - len1 > 0

    engine.make_map(used_catalogs,
                    showing_dsos=showing_dsos,
                    hl_showing_dsos=hl_showing_dsos,
                    highlights=highlights,
                    dso_hide_filter=_get_dso_hide_filter(),
                    trajectory=trajectory,
                    hl_constellation=hl_constellation,
                    visible_objects=visible_objects)

    free_mem_counter += 1
    if free_mem_counter > NO_FREE_MEM_CYCLES:
        free_mem_counter = 0
        used_catalogs.free_mem()

    print("Map created within : {} ms".format(str(time()-tm)), flush=True)


def _create_chart_pdf(pdf_fobj, obj_ra, obj_dec, ra, dec, fld_size, star_maglim, dso_maglim,
                      landscape=True, show_legend=True, dso_names=None, flags='', highlights_dso_list=None,
                      highlights_pos_list=None, trajectory=None, eyepiece_fov=None):
    """Create chart PDF in czsky process."""
    global free_mem_counter
    tm = time()

    used_catalogs = _load_used_catalogs()

    config = fchart3.EngineConfiguration()
    _setup_skymap_graphics(config, fld_size, None, DEFAULT_PDF_FONT_SIZE, force_light_mode=True, is_pdf=True)

    config.show_dso_legend = False
    config.show_orientation_legend = True
    config.mirror_x = 'X' in flags
    config.mirror_y = 'Y' in flags
    config.show_equatorial_grid = True

    config.show_flamsteed = (fld_size <= 20)

    config.show_constellation_shapes = 'C' in flags
    config.show_constellation_borders = 'B' in flags
    config.show_deepsky = 'D' in flags
    config.show_equatorial_grid = 'E' in flags
    config.fov_telrad = 'T' in flags
    config.show_milky_way = False
    config.eyepiece_fov = eyepiece_fov
    config.star_mag_shift = 0.7  # increase radius of star by 0.5 magnitude

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
    engine = fchart3.SkymapEngine(artist, fchart3.EN, lm_stars=star_maglim, lm_deepsky=dso_maglim)
    engine.set_configuration(config)

    engine.set_field(ra, dec, fld_size*pi/180.0/2.0)

    if obj_ra is not None and obj_dec is not None:
        highlights = _create_highlights(obj_ra, obj_dec, config.dso_highlight_linewidth*1.3, True)
    elif highlights_pos_list:
        highlights = _create_highlights_from_pos_list(highlights_pos_list, config.dso_highlight_color, config.dso_highlight_linewidth)
    else:
        highlights = None

    showing_dsos = set()
    if dso_names:
        for dso_name in dso_names:
            dso = _find_dso_by_name(dso_name)
            if dso:
                showing_dsos.add(dso)

    len1 = len(showing_dsos)

    if highlights_dso_list:
        for hl_dso in highlights_dso_list:
            dso = _find_dso_by_name(hl_dso.name)
            if dso:
                showing_dsos.add(dso)

    hl_showing_dsos = len(showing_dsos) - len1 > 0

    dso_hide_filter = _get_dso_hide_filter()

    engine.make_map(used_catalogs, showing_dsos=showing_dsos, hl_showing_dsos=hl_showing_dsos, highlights=highlights,
                    dso_hide_filter=dso_hide_filter, trajectory=trajectory)

    print("PDF map created within : {} ms".format(str(time()-tm)), flush=True)


def _create_chart_legend(png_fobj, ra, dec, width, height, fld_size, star_maglim, dso_maglim, eyepiece_fov, flags=''):
    global free_mem_counter
    # tm = time()

    used_catalogs = _load_used_catalogs()

    config = fchart3.EngineConfiguration()
    _setup_skymap_graphics(config, fld_size, width, DEFAULT_SCREEN_FONT_SIZE)

    config.show_dso_legend = False
    config.show_orientation_legend = False
    config.mirror_x = 'X' in flags
    config.mirror_y = 'Y' in flags

    config.legend_only = True
    config.show_mag_scale_legend = True
    config.show_map_scale_legend = True
    config.show_field_border = True
    config.show_equatorial_grid = True
    config.show_picker = 'P' in flags
    config.picker_radius = PICKER_RADIUS

    config.fov_telrad = 'T' in flags

    config.eyepiece_fov = eyepiece_fov
    config.star_mag_shift = 1.0  # increase radius of star by 1 magnitude

    config.show_flamsteed = (fld_size <= 20)

    if dso_maglim is None:
        dso_maglim = -10

    artist = fchart3.CairoDrawing(png_fobj, width if width else 220, height if height else 220, format='png', pixels=True if width else False)
    engine = fchart3.SkymapEngine(artist, fchart3.EN, lm_stars=star_maglim, lm_deepsky=dso_maglim)
    engine.set_configuration(config)

    engine.set_field(ra, dec, fld_size*pi/180.0/2.0)

    engine.make_map(used_catalogs)
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

    hl = fchart3.HighlightDefinition('cross', line_width, color, [[obj_ra, obj_dec, '']])
    return [hl]


def _create_highlights_from_pos_list(highlights_pos_list, color, line_width):
    highlight_def_items = []
    for pos in highlights_pos_list:
        highlight_def_items.append([pos[0], pos[1], pos[2]])
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
        legend_flags += 'T'

    if form.show_picker.data == 'true':
        legend_flags += 'P'
        chart_flags += 'P'

    if form.show_constell_shapes.data == 'true':
        chart_flags += 'C'

    if form.show_constell_borders.data == 'true':
        chart_flags += 'B'

    if form.show_dso.data == 'true':
        chart_flags += 'D'

    if form.show_equatorial_grid.data == 'true':
        chart_flags += 'E'

    if form.mirror_x.data == 'true':
        legend_flags += 'X'
        chart_flags += 'X'

    if form.mirror_y.data == 'true':
        legend_flags += 'Y'
        chart_flags += 'Y'

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

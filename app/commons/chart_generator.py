import subprocess
import os
import sys
from math import pi
from time import time
from io import BytesIO

from flask import (
    request,
    session,
)

import fchart3

from flask import app

used_catalogs = None

MAX_IMG_WIDTH = 3000
MAX_IMG_HEIGHT = 3000

FIELD_SIZES = (1, 2, 5, 10, 20, 40, 100)

GUI_FIELD_SIZES = []

for i in range(0, len(FIELD_SIZES)-1):
    GUI_FIELD_SIZES.append(FIELD_SIZES[i])
    GUI_FIELD_SIZES.append((FIELD_SIZES[i] + FIELD_SIZES[i+1]) / 2)

GUI_FIELD_SIZES.append(FIELD_SIZES[-1])

STR_GUI_FIELD_SIZES = ','.join(str(x) for x in GUI_FIELD_SIZES)

# DEFAULT_MAG = [15, 12, 11, (8, 11), (6, 9), (6, 8), 6, 6, 5]
MAG_SCALES = [(12, 16), (11, 15), (10, 13), (8, 11), (6, 9), (6, 8), (5, 7)]
DSO_MAG_SCALES = [(10, 18), (10, 18), (10, 18), (7, 15), (7, 13), (6, 11), (5, 9)]


from .utils import to_float, to_boolean

free_mem_counter = 0
NO_FREE_MEM_CYCLES = 500

def _load_used_catalogs():
    global used_catalogs
    if used_catalogs is None:
        data_dir = os.path.join(fchart3.get_catalogs_dir())
        usno_nomad_file = os.path.join(os.getcwd(), 'data/USNO-NOMAD-1e8.dat')
        used_catalogs = fchart3.UsedCatalogs(data_dir, usno_nomad_file,
                                             limiting_magnitude_deepsky = 100.0,
                                             force_asterisms = False,
                                             force_unknown = False,
                                             show_catalogs = [])
    return used_catalogs

def _setup_skymap_graphics(config, fld_size, width, night_mode):
        config.constellation_linewidth = 0.5
        config.constellation_linewidth = 0.3
        config.open_cluster_linewidth = 0.3
        config.grid_linewidth = 0.15
        config.dso_linewidth = 0.4
        config.legend_linewidth = 0.2
        config.no_margin = True
        config.font = "Roboto"
        config.font_size = 2.8

        if fld_size >= 40 and width and width <= 768:
            config.show_star_labels = False

        if night_mode:
            config.background_color = (0.01, 0.01, 0.05)
            config.constellation_lines_color = (0.18, 0.27, 0.3)
            config.constellation_border_color = (0.3, 0.27, 0.07)
            config.draw_color = (1.0, 1.0, 1.0)
            config.label_color = (0.7, 0.7, 0.7)
            config.dso_color = (0.6, 0.6, 0.6)
            config.nebula_color = (0.2, 0.6, 0.2)
            config.galaxy_color = (0.6, 0.2, 0.2)
            config.star_cluster_color = (0.6, 0.6, 0.0)
            if width and width <= 768:
                config.grid_color = (0.18, 0.27, 0.3)
            else:
                config.grid_color = (0.12, 0.18, 0.20)
            config.star_colors = True
            config.dso_symbol_brightness = True
        else:
            config.constellation_lines_color = (0.5, 0.7, 0.8)
            config.constellation_border_color = (0.8, 0.7, 0.1)
            config.draw_color = (0.0, 0.0, 0.0)
            config.label_color = (0.2, 0.2, 0.2)
            config.dso_color = (0.3, 0.3, 0.3)
            config.nebula_color = (0.0, 0.3, 0.0)
            config.galaxy_color = (0.3, 0.0, 0.0)
            config.star_cluster_color = (0.3, 0.3, 0.0)
            config.grid_color = (0.7, 0.7, 0.7)
            config.dso_symbol_brightness = False


def common_chart_pos_img(obj_ra, obj_dec, ra, dec, dso_names=None, visible_objects=None):

    gui_fld_size, maglim, dso_maglim = _get_fld_size_mags_from_request()

    width = request.args.get('width', type=int)
    height = request.args.get('height', type=int)

    if width > MAX_IMG_WIDTH:
        width = MAX_IMG_WIDTH
    if height > MAX_IMG_HEIGHT:
        height = MAX_IMG_HEIGHT

    night_mode = to_boolean(request.args.get('nm'), True)
    mirror_x = to_boolean(request.args.get('mx'), False)
    mirror_y = to_boolean(request.args.get('my'), False)
    flags = request.args.get('flags')

    img_bytes = BytesIO()
    create_chart(img_bytes, visible_objects, obj_ra, obj_dec, float(ra), float(dec), gui_fld_size, width, height, maglim, dso_maglim, night_mode, mirror_x, mirror_y, show_legend=False, dso_names=dso_names, flags=flags)
    img_bytes.seek(0)
    return img_bytes

def common_chart_pdf_img(obj_ra, obj_dec, ra, dec, dso_names=None):
    gui_fld_size, maglim, dso_maglim = _get_fld_size_mags_from_request()

    mirror_x = to_boolean(request.args.get('mx'), False)
    mirror_y = to_boolean(request.args.get('my'), False)
    flags = request.args.get('flags')

    img_bytes = BytesIO()
    create_chart_pdf(img_bytes, obj_ra, obj_dec, float(ra), float(dec), gui_fld_size, maglim, dso_maglim, mirror_x, mirror_y, dso_names=dso_names, flags=flags)
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

    night_mode = to_boolean(request.args.get('nm'), True)
    mirror_x = to_boolean(request.args.get('mx'), False)
    mirror_y = to_boolean(request.args.get('my'), False)
    flags = request.args.get('flags')

    img_bytes = BytesIO()
    create_chart_legend(img_bytes, float(ra), float(dec), width, height, gui_fld_size, maglim, dso_maglim, night_mode, mirror_x, mirror_y, flags=flags)
    img_bytes.seek(0)
    return img_bytes


def common_prepare_chart_data(form):
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


    form.maglim.data = _check_in_mag_interval(form.maglim.data, cur_mag_scale)
    session['pref_maglim'  + str(fld_size)] = form.maglim.data

    form.dso_maglim.data = _check_in_mag_interval(form.dso_maglim.data, cur_dso_mag_scale)
    session['pref_dso_maglim'  + str(fld_size)] = form.dso_maglim.data

    mag_range_values = []
    dso_mag_range_values = []

    for i in range(0, len(FIELD_SIZES)):
        _, ml, dml = _get_fld_size_maglim(i)
        mag_range_values.append(ml)
        dso_mag_range_values.append(dml)

    return (fld_size, cur_mag_scale, cur_dso_mag_scale, mag_range_values, dso_mag_range_values)


def _get_fld_size_maglim(fld_size_index):
    fld_size = FIELD_SIZES[fld_size_index]

    mag_scale = MAG_SCALES[fld_size_index]
    dso_mag_scale = DSO_MAG_SCALES[fld_size_index]

    maglim = session.get('pref_maglim' + str(fld_size))
    if maglim is None:
        maglim = (mag_scale[0] + mag_scale[1] + 1) // 2

    dso_maglim = session.get('pref_dso_maglim' + str(fld_size))
    if dso_maglim is None:
        dso_maglim = (dso_mag_scale[0] + dso_mag_scale[1] + 1) // 2

    return (fld_size, maglim, dso_maglim)


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

    return (gui_fld_size, maglim, dso_maglim)


def _check_in_mag_interval(mag, mag_interval):
    if mag_interval[0] > mag:
        return mag_interval[0]
    if mag_interval[1] < mag:
        return mag_interval[1]
    return mag


def create_chart(png_fobj, visible_objects, obj_ra, obj_dec, ra, dec, fld_size, width, height, star_maglim, dso_maglim, night_mode, mirror_x=False, mirror_y=False, show_legend=True, dso_names=None, flags=''):
    """Create chart in czsky process."""
    global free_mem_counter
    tm = time()

    used_catalogs = _load_used_catalogs()

    config = fchart3.EngineConfiguration()
    _setup_skymap_graphics(config, fld_size, width, night_mode)

    config.show_dso_legend = False
    config.show_orientation_legend = False
    config.mirror_x = mirror_x
    config.mirror_y = mirror_y
    config.show_equatorial_grid = True

    config.show_flamsteed = (fld_size <= 20)

    config.show_constellation_shapes = 'C' in flags
    config.show_constellation_borders = 'B' in flags
    config.show_deepsky = 'D' in flags
    config.show_equatorial_grid = 'E' in flags

    if show_legend:
        config.show_mag_scale_legend = True
        config.show_map_scale_legend = True
        config.show_field_border = True

    if dso_maglim is None:
        dso_maglim = -10

    artist = fchart3.CairoDrawing(png_fobj, width if width else 220, height if height else 220, format='png', pixels=True if width else False)
    engine = fchart3.SkymapEngine(artist, fchart3.EN, lm_stars = star_maglim, lm_deepsky=dso_maglim)
    engine.set_configuration(config)

    engine.set_field(ra, dec, fld_size*pi/180.0/2.0)

    showing_dsos = None
    if dso_names:
        showing_dsos = []
        for dso_name in dso_names:
            dso, cat, name = used_catalogs.lookup_dso(dso_name)
            if dso:
                showing_dsos.append(dso)

    highlights = None
    if not obj_ra is None and not obj_dec is None:
        highlights = []
        highlights.append([obj_ra, obj_dec])

    engine.make_map(used_catalogs, showing_dsos=showing_dsos, highlights=highlights, visible_objects=visible_objects)
    free_mem_counter += 1
    if free_mem_counter > NO_FREE_MEM_CYCLES:
        free_mem_counter = 0
        used_catalogs.free_mem()
    print("Map created within : {} ms".format(str(time()-tm)), flush=True)


def create_chart_pdf(pdf_fobj, obj_ra, obj_dec, ra, dec, fld_size, star_maglim, dso_maglim, mirror_x=False, mirror_y=False, show_legend=True, dso_names=None, flags=''):
    """Create chart PDF in czsky process."""
    global free_mem_counter
    tm = time()

    used_catalogs = _load_used_catalogs()

    config = fchart3.EngineConfiguration()
    _setup_skymap_graphics(config, fld_size, None, False)

    config.show_dso_legend = False
    config.show_orientation_legend = True
    config.mirror_x = mirror_x
    config.mirror_y = mirror_y
    config.show_equatorial_grid = True

    config.show_flamsteed = (fld_size <= 20)

    config.show_constellation_shapes = 'C' in flags
    config.show_constellation_borders = 'B' in flags
    config.show_deepsky = 'D' in flags
    config.show_equatorial_grid = 'E' in flags

    if show_legend:
        config.show_mag_scale_legend = True
        config.show_map_scale_legend = True
        config.show_field_border = True

    if dso_maglim is None:
        dso_maglim = -10

    artist = fchart3.CairoDrawing(pdf_fobj, 180, 220, format='pdf')
    engine = fchart3.SkymapEngine(artist, fchart3.EN, lm_stars = star_maglim, lm_deepsky=dso_maglim)
    engine.set_configuration(config)

    engine.set_field(ra, dec, fld_size*pi/180.0/2.0)

    showing_dsos = None
    if dso_names:
        showing_dsos = []
        for dso_name in dso_names:
            dso, cat, name = used_catalogs.lookup_dso(dso_name)
            if dso:
                showing_dsos.append(dso)

    highlights = None
    if not obj_ra is None and not obj_dec is None:
        highlights = []
        highlights.append([obj_ra, obj_dec])

    engine.make_map(used_catalogs, showing_dsos=showing_dsos, highlights=highlights)

    print("PDF map created within : {} ms".format(str(time()-tm)), flush=True)



def create_chart_legend(png_fobj, ra, dec, width, height, fld_size, star_maglim, dso_maglim, night_mode, mirror_x=False, mirror_y=False, flags=''):
    global free_mem_counter
    tm = time()

    used_catalogs = _load_used_catalogs()

    config = fchart3.EngineConfiguration()
    _setup_skymap_graphics(config, fld_size, width, night_mode)

    config.show_dso_legend = False
    config.show_orientation_legend = False
    config.mirror_x = mirror_x
    config.mirror_y = mirror_y

    config.legend_only = True
    config.show_mag_scale_legend = True
    config.show_map_scale_legend = True
    config.show_field_border = True
    config.show_equatorial_grid = True

    config.fov_telrad = 'T' in flags

    config.show_flamsteed = (fld_size <= 20)

    if dso_maglim is None:
        dso_maglim = -10

    artist = fchart3.CairoDrawing(png_fobj, width if width else 220, height if height else 220, format='png', pixels=True if width else False)
    engine = fchart3.SkymapEngine(artist, fchart3.EN, lm_stars = star_maglim, lm_deepsky=dso_maglim)
    engine.set_configuration(config)

    engine.set_field(ra, dec, fld_size*pi/180.0/2.0)

    engine.make_map(used_catalogs)
    free_mem_counter += 1
    if free_mem_counter > NO_FREE_MEM_CYCLES:
        free_mem_counter = 0
        used_catalogs.free_mem()
    # app.logger.info("Map created within : %s ms", str(time()-tm))


def get_chart_legend_flags(form):
    chart_flags = ''
    legend_flags = ''

    if form.show_telrad.data == 'true':
        legend_flags += 'T'

    if form.show_constell_shapes.data == 'true':
        chart_flags += 'C'

    if form.show_constell_borders.data == 'true':
        chart_flags += 'B'

    if form.show_dso.data == 'true':
        chart_flags += 'D'

    if form.show_equatorial_grid.data == 'true':
        chart_flags += 'E'

    return (chart_flags, legend_flags)

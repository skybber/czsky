import subprocess
import os
import sys
from math import pi
from time import time

import fchart3

from flask import app

used_catalogs = None

MAX_IMG_WIDTH = 3000
MAX_IMG_HEIGHT = 3000

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

def _setup_skymap_graphics(config, night_mode):
        config.constellation_linewidth = 0.5
        config.constellation_linewidth = 0.3
        config.open_cluster_linewidth = 0.3
        config.dso_linewidth = 0.4
        config.legend_linewidth = 0.2
        config.no_margin = True
        if night_mode:
            config.background_color = (0.01, 0.01, 0.05)
            config.constellation_lines_color = (0.18, 0.27, 0.3)
            config.constellation_border_color = (0.2, 0.18, 0.05)
            config.draw_color = (1.0, 1.0, 1.0)
            config.label_color = (0.7, 0.7, 0.7)
            config.dso_color = (0.6, 0.6, 0.6)
            config.nebula_color = (0.2, 0.6, 0.2)
            config.galaxy_color = (0.6, 0.2, 0.2)
            config.star_cluster_color = (0.6, 0.6, 0.0)
        else:
            config.constellation_lines_color = (0.5, 0.7, 0.8)
            config.constellation_border_color = (0.8, 0.7, 0.1)
            config.draw_color = (0.0, 0.0, 0.0)
            config.label_color = (0.2, 0.2, 0.2)
            config.dso_color = (0.3, 0.3, 0.3)
            config.nebula_color = (0.0, 0.3, 0.0)
            config.galaxy_color = (0.3, 0.0, 0.0)
            config.star_cluster_color = (0.3, 0.3, 0.0)
            

def create_chart(png_fobj, ra, dec, fld_size, width, height, star_maglim, dso_maglim, night_mode, mirror_x=False, mirror_y=False, show_legend=True, dso_names=None):
    """Create chart in czsky process."""
    tm = time()

    used_catalogs = _load_used_catalogs()

    config = fchart3.EngineConfiguration()
    _setup_skymap_graphics(config, night_mode)
    
    config.show_dso_legend = False
    config.mirror_x = mirror_x
    config.mirror_y = mirror_y
    config.show_flamsteed = (fld_size <= 20)

    if show_legend:
        config.show_mag_scale_legend = True
        config.show_map_scale_legend = True
        config.show_orientation_legend = True
        config.show_field_border = True

    artist = fchart3.CairoDrawing(width if width else 220, height if height else 220, png_fobj=png_fobj, pixels=True if width else False)
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

    engine.make_map(used_catalogs, showing_dsos=showing_dsos)
    used_catalogs.free_mem()
    # app.logger.info("Map created within : %s ms", str(time()-tm))
    
def create_chart_legend(png_fobj, ra, dec, width, height, fld_size, star_maglim, dso_maglim, night_mode, mirror_x=False, mirror_y=False):
    tm = time()

    used_catalogs = _load_used_catalogs()

    config = fchart3.EngineConfiguration()
    _setup_skymap_graphics(config, night_mode)
    
    config.show_dso_legend = False
    config.mirror_x = mirror_x
    config.mirror_y = mirror_y

    config.legend_only = True
    config.show_mag_scale_legend = True
    config.show_map_scale_legend = True
    config.show_orientation_legend = True
    config.show_field_border = True
    config.show_flamsteed = (fld_size <= 20)

    artist = fchart3.CairoDrawing(width if width else 220, height if height else 220, png_fobj=png_fobj, pixels=True if width else False)
    engine = fchart3.SkymapEngine(artist, fchart3.EN, lm_stars = star_maglim, lm_deepsky=dso_maglim)
    engine.set_configuration(config)

    engine.set_field(ra, dec, fld_size*pi/180.0/2.0)

    engine.make_map(used_catalogs)
    used_catalogs.free_mem()
    # app.logger.info("Map created within : %s ms", str(time()-tm))

def create_common_chart_in_pipeline(ra, dec, caption, full_file_name, fld_size, star_maglim, dso_maglim, night_mode, mirror_x, mirror_y):
    """Create chart in czsky process."""
    tm = time()

    used_catalogs = _load_used_catalogs()

    config = fchart3.EngineConfiguration()
    _setup_skymap_graphics(config, night_mode)
    
    config.show_dso_legend = False
    config.mirror_x = mirror_x
    config.mirror_y = mirror_y
    
    config.show_mag_scale_legend = True
    config.show_map_scale_legend = True
    config.show_orientation_legend = True
    config.show_field_border = True

    config.show_flamsteed = (fld_size <= 20)

    artist = fchart3.CairoDrawing(220, 220, filename=full_file_name)
    engine = fchart3.SkymapEngine(artist, fchart3.EN, lm_stars = star_maglim, lm_deepsky=dso_maglim)
    engine.set_configuration(config)

    engine.set_field(ra, dec, fld_size*pi/180.0/2.0)

    # engine.set_active_constellation(dso.constellation)
    extra_positions = []
    extra_positions.append([ra,dec,'',None])
    
    engine.make_map(used_catalogs, extra_positions=extra_positions)
    used_catalogs.free_mem()
    # app.logger.info("Map created within : %s ms", str(time()-tm))
    
def create_trajectory_chart_in_pipeline(ra, dec, trajectory, caption, full_file_name, fld_size, star_maglim, dso_maglim, night_mode, mirror_x, mirror_y):
    """Create chart in czsky process."""
    tm = time()

    used_catalogs = _load_used_catalogs()

    config = fchart3.EngineConfiguration()
    _setup_skymap_graphics(config, night_mode)
    
    config.show_dso_legend = False
    config.mirror_x = mirror_x
    config.mirror_y = mirror_y
    config.show_flamsteed = (fld_size <= 20)

    artist = fchart3.CairoDrawing(220, 220, filename=full_file_name)
    engine = fchart3.SkymapEngine(artist, fchart3.EN, lm_stars = star_maglim, lm_deepsky=dso_maglim)
    engine.set_configuration(config)

    engine.set_field(ra, dec, fld_size*pi/180.0/2.0)

    engine.make_map(used_catalogs, trajectory=trajectory)
    used_catalogs.free_mem()
    # app.logger.info("Map created within : %s ms", str(time()-tm))
    

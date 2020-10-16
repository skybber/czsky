import subprocess
import os
import sys
from math import pi
from time import time

import fchart3

from flask import app

used_catalogs = None

def _load_used_catalogs():
    global used_catalogs
    if used_catalogs is None:
        data_dir = os.path.join(fchart3.get_catalogs_dir())
        usno_nomad_file = os.path.join(os.getcwd(), 'data/USNO-NOMAD-1e8.dat')
        used_catalogs = fchart3.UsedCatalogs(data_dir, usno_nomad_file,
                                             limiting_magnitude_deepsky = 100.0,
                                             force_messier = True,
                                             force_asterisms = False,
                                             force_unknown = False,
                                             show_catalogs = [])
    return used_catalogs

def create_dso_chart(png_fobj, dso_name, fld_size, star_maglim, dso_maglim, night_mode, mirror_x, mirror_y):
    """Create chart in czsky process."""
    tm = time()
    
    used_catalogs = _load_used_catalogs()

    dso, cat, name = used_catalogs.lookup_dso(dso_name)

    if dso:
        config = fchart3.EngineConfiguration()
        config.show_dso_legend = False
        config.invert_colors = False
        config.mirror_x = mirror_x
        config.mirror_y = mirror_y
        config.constellation_linewidth = 0.5
        config.star_border_linewidth = 0.06
        config.open_cluster_linewidth = 0.3
        config.dso_linewidth = 0.2
        config.legend_linewidth = 0.2
        config.night_mode = night_mode
        config.show_flamsteed = (fld_size <= 20)

        artist = fchart3.CairoDrawing(220, 220, png_fobj=png_fobj)
        engine = fchart3.SkymapEngine(artist, fchart3.EN, lm_stars = star_maglim, lm_deepsky=dso_maglim)
        engine.set_configuration(config)

        engine.set_field(dso.ra, dso.dec, fld_size*pi/180.0/2.0)
        if dso.master_object:
            dso = dso.master_object

        engine.set_active_constellation(dso.constellation)
        engine.make_map(used_catalogs,extra_positions=[], showing_dso=dso)
        used_catalogs.free_mem()
        # app.logger.info("Map created within : %s ms", str(time()-tm))
    else:
        pass
        #app.logger.error("DSO %s not found!", dso_name)
        
def create_chart(png_fobj, ra, dec, fld_size, star_maglim, dso_maglim, night_mode, mirror_x=False, mirror_y=False):
    """Create chart in czsky process."""
    tm = time()

    used_catalogs = _load_used_catalogs()

    config = fchart3.EngineConfiguration()
    config.show_dso_legend = False
    config.invert_colors = False
    config.mirror_x = mirror_x
    config.mirror_y = mirror_y
    config.constellation_linewidth = 0.5
    config.star_border_linewidth = 0.06
    config.open_cluster_linewidth = 0.3
    config.dso_linewidth = 0.2
    config.legend_linewidth = 0.2
    config.night_mode = night_mode
    config.show_flamsteed = (fld_size <= 20)
    
    artist = fchart3.CairoDrawing(220, 220, png_fobj=png_fobj)
    engine = fchart3.SkymapEngine(artist, fchart3.EN, lm_stars = star_maglim, lm_deepsky=dso_maglim)
    engine.set_configuration(config)

    engine.set_field(ra, dec, fld_size*pi/180.0/2.0)

    engine.make_map(used_catalogs)
    used_catalogs.free_mem()
    # app.logger.info("Map created within : %s ms", str(time()-tm))
    
def create_chart_legend(png_fobj, ra, dec, fld_size, star_maglim, dso_maglim, night_mode, mirror_x=False, mirror_y=False):
    tm = time()

    used_catalogs = _load_used_catalogs()

    config = fchart3.EngineConfiguration()
    config.show_dso_legend = False
    config.invert_colors = False
    config.mirror_x = mirror_x
    config.mirror_y = mirror_y
    config.constellation_linewidth = 0.5
    config.star_border_linewidth = 0.06
    config.open_cluster_linewidth = 0.3
    config.dso_linewidth = 0.2
    config.legend_linewidth = 0.2
    config.night_mode = night_mode
    config.legend_only = True
    config.show_mag_scale_legend = True
    config.show_map_scale_legend = True
    config.show_orientation_legend = True
    config.show_field_border = True
    config.show_flamsteed = (fld_size <= 20)

    artist = fchart3.CairoDrawing(220, 220, png_fobj=png_fobj)
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
    config.show_dso_legend = False
    config.invert_colors = False
    config.mirror_x = mirror_x
    config.mirror_y = mirror_y
    config.constellation_linewidth = 0.5
    config.star_border_linewidth = 0.06
    config.open_cluster_linewidth = 0.3
    config.dso_linewidth = 0.2
    config.legend_linewidth = 0.2
    config.night_mode = night_mode
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
    config.show_dso_legend = False
    config.invert_colors = False
    config.mirror_x = mirror_x
    config.mirror_y = mirror_y
    config.constellation_linewidth = 0.5
    config.star_border_linewidth = 0.06
    config.open_cluster_linewidth = 0.3
    config.dso_linewidth = 0.2
    config.legend_linewidth = 0.2
    config.night_mode = night_mode
    config.show_flamsteed = (fld_size <= 20)

    artist = fchart3.CairoDrawing(220, 220, filename=full_file_name)
    engine = fchart3.SkymapEngine(artist, fchart3.EN, lm_stars = star_maglim, lm_deepsky=dso_maglim)
    engine.set_configuration(config)

    engine.set_field(ra, dec, fld_size*pi/180.0/2.0)

    engine.make_map(used_catalogs, trajectory=trajectory)
    used_catalogs.free_mem()
    # app.logger.info("Map created within : %s ms", str(time()-tm))
    

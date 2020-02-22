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
        used_catalogs = fchart3.UsedCatalogs(data_dir, usno_nomad_file, 100.0, True, False, False)
    return used_catalogs

def create_chart_by_extprocess(dso_name, full_file_name, fld_size, star_maglim, dso_maglim, night_mode, mirror_x, mirror_y):
    """Create chart in extra process."""
    prog_params = ['fchart3',
                   '-size', str(fld_size),
                   '-width', '220',
                   '-f', full_file_name,
                   '-capt', '',
                   '-limdso', str(dso_maglim),
                   '-limstar', str(star_maglim),
                   '-lstar', '0.06',
                   '-locl', '0.15',
                   '-ldso', '0.1',
                   '-llegend', '0.3',
                   '-usno-nomad', os.path.join(os.getcwd(), 'data/USNO-NOMAD-1e8.dat'),
                   '-fmessier',
                   ]
    if night_mode:
        prog_params.append('-nm')
    if mirror_x:
        prog_params.append('-mx')
    if mirror_y:
        prog_params.append('-my')
    prog_params.append(dso_name)
    p = subprocess.Popen(prog_params)
    p.wait()

def create_chart_in_pipeline(dso_name, full_file_name, fld_size, star_maglim, dso_maglim, night_mode, mirror_x, mirror_y):
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

        artist = fchart3.CairoDrawing(full_file_name, 220, 220)
        engine = fchart3.SkymapEngine(artist, fchart3.EN, lm_stars = star_maglim, lm_deepsky=dso_maglim)
        engine.set_configuration(config)

        engine.set_field(dso.ra, dso.dec, fld_size*pi/180.0/2.0)
        if dso.master_object:
            dso = dso.master_object
        used_catalogs.deepskycatalog.add_dso(dso)
        used_catalogs.deepskycatalog.add_showing_dso(dso)

        engine.set_active_constellation(dso.constellation)
        engine.make_map(used_catalogs)
        used_catalogs.free_mem()
        # app.logger.info("Map created within : %s ms", str(time()-tm))
    else:
        pass
        #app.logger.error("DSO %s not found!", dso_name)


def create_star_chart_in_pipeline(ra, dec, full_file_name, fld_size, star_maglim, dso_maglim, night_mode):
    """Create chart in czsky process."""
    tm = time()

    used_catalogs = _load_used_catalogs()

    config = fchart3.EngineConfiguration()
    config.show_dso_legend = False
    config.invert_colors = False
    config.mirror_x = False
    config.mirror_y = False
    config.constellation_linewidth = 0.5
    config.star_border_linewidth = 0.06
    config.open_cluster_linewidth = 0.3
    config.dso_linewidth = 0.2
    config.legend_linewidth = 0.2
    config.night_mode = night_mode

    artist = fchart3.CairoDrawing(full_file_name, 220, 220)
    engine = fchart3.SkymapEngine(artist, fchart3.EN, lm_stars = star_maglim, lm_deepsky=dso_maglim)
    engine.set_configuration(config)

    engine.set_field(ra, dec, fld_size*pi/180.0/2.0)

    engine.make_map(used_catalogs)
    used_catalogs.free_mem()
    # app.logger.info("Map created within : %s ms", str(time()-tm))

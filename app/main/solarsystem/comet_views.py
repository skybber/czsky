import os
import numpy as np
import math
import threading

from datetime import datetime, timedelta

from flask import (
    abort,
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func
from skyfield.api import load
from skyfield.data import mpc
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN

from app import db

from app.models import User, SHOWN_APERTURE_DESCRIPTIONS
from app.commons.pagination import Pagination
from app.commons.search_utils import process_paginated_session_search

from .comet_forms import (
    SearchCometForm,
    CometFindChartForm,
)

from app.main.views import ITEMS_PER_PAGE
from app.commons.chart_generator import create_common_chart_in_pipeline
from app.commons.img_dir_resolver import resolve_img_path_dir, parse_inline_link

main_comet = Blueprint('main_comet', __name__)

ALADIN_ANG_SIZES = (5/60, 10/60, 15/60, 30/60, 1, 2, 5, 10)

all_comets_expiration = datetime.now() + timedelta(days=1)
all_comets = None
creation_running = False


def _load_comet_brightness(all_comets, fname):
    with open(fname, 'r') as f:
        lines = f.readlines()
    for line in lines:
        print(line, flush=True)
        comet_id, str_mag = line.split(' ')
        try:
            all_comets.loc[all_comets['comet_id'] == comet_id, 'mag'] = float(str_mag) 
        except Exception:
            pass
          

def _create_comet_brighness_file(all_comets, fname):
    global creation_running
    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    sun, earth = eph['sun'], eph['earth']
    mags = []
    t = ts.now()
    with open(fname, 'w') as f:
        for index, row in all_comets.iterrows(): 
            m = 22.0 
            try:
                comet = sun + mpc.comet_orbit(row, ts, GM_SUN)
                dist_earth = earth.at(t).observe(comet).distance().au
                dist_sun = sun.at(t).observe(comet).distance().au
                if (dist_earth<10.0):
                    m = row['magnitude_H'] + 5.0*np.log10(dist_earth) + 2.5*row['magnitude_G']*np.log10(dist_sun)
                    print('Comet: {} de={} ds={} m={} g={}'.format(row['designation'], dist_earth, dist_sun, m, row['magnitude_G']), flush=True)
            except Exception:
                pass
            f.write(row['comet_id'] + ' ' + str(m) + '\n')
            mags.append(m)

    all_comets['mag'] = mags
    creation_running = False

def _get_all_comets():
    global all_comets
    global all_comets_expiration
    global creation_running
    now = datetime.now()
    if all_comets is None or now > all_comets_expiration:
        all_comets_expiration = now + timedelta(days=1)
        with load.open(mpc.COMET_URL, reload=False) as f:
            all_comets = mpc.load_comets_dataframe_slow(f)
            all_comets['comet_id'] = np.where(all_comets['designation_packed'].isnull(), all_comets['designation'], all_comets['designation_packed'])    
            all_comets['comet_id'] = all_comets['comet_id'].str.replace('/','')
            all_comets['comet_id'] = all_comets['comet_id'].str.replace(' ', '')

        fname = os.path.join(current_app.config.get('USER_DATA_DIR'), 'comets_brightness.txt')
        
        if (not os.path.isfile(fname) or datetime.fromtimestamp(os.path.getctime(fname)) < all_comets_expiration) and not creation_running:
            all_comets.loc[:,'mag'] = 22.0
            creation_running = True
            thread = threading.Thread(target=_create_comet_brighness_file, args=(all_comets, fname,))
            thread.start()
        else:
            _load_comet_brightness(all_comets, fname)
            
    return all_comets

@main_comet.route('/comets', methods=['GET', 'POST'])
def comets():
    """View comets."""
    search_form = SearchCometForm()

    page, search_expr = process_paginated_session_search('comet_search_page', [
        ('comet_search', search_form.q),
    ])

    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page
    comets = _get_all_comets()
    
    comets = comets[comets['mag'] < 17.0].sort_values(by=['mag'])

    if search_expr:
        search_expr = search_expr.replace('"','')
        comets = comets.query('designation.str.contains("{}")'.format(search_expr))
    
    if len(comets) > 0:
        comets_for_render = comets.iloc[offset : offset + per_page]
    else:
        comets_for_render = comets 

    pagination = Pagination(page=page, total=len(comets), search=False, record_name='comets', css_framework='semantic', not_passed_args='back')
    return render_template('main/solarsystem/comets.html', comets=comets_for_render, pagination=pagination, search_form=search_form)

def _find_comet(comet_id):
    all_comets = _get_all_comets()
    c = all_comets.loc[all_comets['comet_id'] == comet_id]
    return c.iloc[0] if len(c)>0 else None

@main_comet.route('/comet/<string:comet_id>', methods=['GET', 'POST'])
@main_comet.route('/comet/<string:comet_id>/info', methods=['GET', 'POST'])
def comet_info(comet_id):
    """View a comet info."""
    comet = _find_comet(comet_id)
    if comet is None:
        abort(404)

    form  = CometFindChartForm()
    from_observation_id = request.args.get('from_observation_id')

    preview_url_dir = '/static/webassets-external/preview/'
    preview_dir = 'app' + preview_url_dir

    field_sizes = (1, 3, 8, 20)
    fld_size = field_sizes[form.radius.data-1]

    prev_fld_size = session.get('comet_prev_fld')
    session['prev_fld'] = fld_size

    night_mode = not session.get('themlight', False)

    mag_scales = [(12, 16), (10, 13), (8, 11), (6, 9)]
    cur_mag_scale = mag_scales[form.radius.data - 1]

    if prev_fld_size != fld_size:
        pref_maglim = session.get('comet_pref_maglim' + str(fld_size))
        if pref_maglim is None:
            pref_maglim = (cur_mag_scale[0] + cur_mag_scale[1] + 1) // 2
        form.maglim.data = pref_maglim

    form.maglim.data = _check_in_mag_interval(form.maglim.data, cur_mag_scale)
    session['comet_pref_maglim'  + str(fld_size)] = form.maglim.data

    invert_part = '_i' if night_mode else ''
    mirror_x_part = '_mx' if form.mirror_x.data else ''
    mirror_y_part = '_my' if form.mirror_y.data else ''
    
    comet_file_name = str(comet_id) \
        + '_r' + str(fld_size) \
        + '_m' + str(form.maglim.data) \
        + invert_part + mirror_x_part + mirror_y_part + '.png'
        
    full_file_name = os.path.join(preview_dir, comet_file_name)
    
    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    sun, earth = eph['sun'], eph['earth']

    c = sun + mpc.comet_orbit(comet, ts, GM_SUN)

    t = ts.now()
    ra, dec, distance = earth.at(t).observe(c).radec()

    if os.path.isfile(full_file_name) and datetime.fromtimestamp(os.path.getctime(full_file_name)) + timedelta(hours=1) < datetime.now():
        os.remove(full_file_name)
        
    if not os.path.exists(full_file_name):
        create_common_chart_in_pipeline(ra.radians, dec.radians, comet['designation'], full_file_name, fld_size, form.maglim.data, 10, 
                                        night_mode, form.mirror_x.data, form.mirror_y.data)

    fchart_url = preview_url_dir + comet_file_name

    disable_dec_mag = 'disabled' if form.maglim.data <= cur_mag_scale[0] else ''
    disable_inc_mag = 'disabled' if form.maglim.data >= cur_mag_scale[1] else ''

    return render_template('main/solarsystem/comet_info.html', form=form, type='info', comet=comet, fchart_url=fchart_url,
                           from_observation_id=from_observation_id, mag_scale=cur_mag_scale, disable_dec_mag=disable_dec_mag, 
                           disable_inc_mag=disable_inc_mag,
                           )

@main_comet.route('/comet/<string:comet_id>')
@main_comet.route('/comet/<string:comet_id>/catalogue_data')
def comet_catalogue_data(comet_id):
    """View a comet catalog info."""
    comet = _find_comet(comet_id)
    if not comet:
        abort(404)
    from_observation_id = request.args.get('from_observation_id')
    return render_template('main/solarsystem/comet_info.html', type='catalogue_data', user_descr=user_descr, from_observation_id=from_observation_id)

def _check_in_mag_interval(mag, mag_interval):
    if mag_interval[0] > mag:
        return mag_interval[0]
    if mag_interval[1] < mag:
        return mag_interval[1]
    return mag
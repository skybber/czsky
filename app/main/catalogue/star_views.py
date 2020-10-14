from datetime import datetime
import os

from io import BytesIO

from flask import (
    abort,
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from app import db

from app.models import User, Permission, Star, UserStarDescription
from app.commons.pagination import Pagination
from app.commons.chart_generator import create_star_chart
from app.commons.utils import to_float, to_boolean

main_star = Blueprint('main_star', __name__)

from .star_forms import (
    StarEditForm,
    StarFindChartForm,
)

@main_star.route('/star/<int:star_id>')
@main_star.route('/star/<int:star_id>/info')
def star_info(star_id):
    """View a star info."""
    user_descr = UserStarDescription.query.filter_by(id=star_id, lang_code='cs').first()
    if user_descr is None:
        abort(404)
        
    editable=current_user.is_editor()
    return render_template('main/catalogue/star_info.html', type='info', user_descr=user_descr, editable=editable)

@main_star.route('/star/<int:star_id>')
@main_star.route('/star/<int:star_id>/catalogue_data')
def star_catalogue_data(star_id):
    """View a deepsky object info."""
    user_descr = UserStarDescription.query.filter_by(id=star_id, lang_code='cs').first()
    if user_descr is None:
        abort(404)
        
    return render_template('main/catalogue/star_info.html', type='catalogue_data', user_descr=user_descr)

@main_star.route('/star/<int:star_id>/fchart', methods=['GET', 'POST'])
def star_fchart(star_id):
    """View a star  findchart."""
    user_descr = UserStarDescription.query.filter_by(id=star_id, lang_code='cs').first()
    if user_descr is None:
        abort(404)

    star = user_descr.star
    if not star:
        abort(404)

    form  = StarFindChartForm()

    field_sizes = (1, 3, 8, 20)
    fld_size = field_sizes[form.radius.data-1]

    prev_fld_size = session.get('star_prev_fld')
    session['prev_fld'] = fld_size

    night_mode = not session.get('themlight', False)

    mag_scales = [(12, 16), (10, 13), (8, 11), (6, 9)]
    cur_mag_scale = mag_scales[form.radius.data - 1]

    if prev_fld_size != fld_size:
        pref_maglim = session.get('star_pref_maglim' + str(fld_size))
        if pref_maglim is None:
            pref_maglim = (cur_mag_scale[0] + cur_mag_scale[1] + 1) // 2
        form.maglim.data = pref_maglim

    form.maglim.data = _check_in_mag_interval(form.maglim.data, cur_mag_scale)
    session['star_pref_maglim'  + str(fld_size)] = form.maglim.data

    disable_dec_mag = 'disabled' if form.maglim.data <= cur_mag_scale[0] else ''
    disable_inc_mag = 'disabled' if form.maglim.data >= cur_mag_scale[1] else ''

    fchart_url = url_for('main_star.star_fchartimg', star_id=star_id,
                         ra=str(star.ra),
                         dec=str(star.dec),
                         fsz=str(fld_size),
                         mlim=str(form.maglim.data),
                         nm='1' if night_mode else '0'
                         )

    return render_template('main/catalogue/star_info.html', form=form, type='fchart', user_descr=user_descr, fchart_url=fchart_url,
                           mag_scale=cur_mag_scale, disable_dec_mag=disable_dec_mag, disable_inc_mag=disable_inc_mag,
                           )

@main_star.route('/star/<string:star_id>/fchartimg', methods=['GET'])
def star_fchartimg(star_id):
    star = Star.query.filter_by(id=star_id).first()
    if star is None:
        abort(404)
    fld_size = to_float(request.args.get('fsz'), 20.0)
    ra = to_float(request.args.get('ra'), None)
    dec = to_float(request.args.get('dec'), None)
    if ra is None or dec is None:
        abort(404)
    maglim = to_float(request.args.get('mlim'), 8.0)
    night_mode = to_boolean(request.args.get('nm'), True) 
    
    img_bytes = BytesIO()
    create_star_chart(img_bytes, ra, dec, fld_size, maglim, 10, night_mode)
    img_bytes.seek(0)
    return send_file(img_bytes, mimetype='image/png')

def _check_in_mag_interval(mag, mag_interval):
    if mag_interval[0] > mag:
        return mag_interval[0]
    if mag_interval[1] < mag:
        return mag_interval[1]
    return mag

@main_star.route('/star/<int:star_id>/edit', methods=['GET', 'POST'])
@login_required
def star_edit(star_id):
    """Update user star description object."""
    if not current_user.is_editor():
        abort(403)
    user_descr = UserStarDescription.query.filter_by(id=star_id).first()
    goback = False
    if user_descr is None:
        abort(404)
    form = StarEditForm()
    if request.method == 'GET':
        form.common_name.data = user_descr.common_name
        form.text.data = user_descr.text
    elif form.validate_on_submit():
        user_descr.common_name = form.common_name.data
        user_descr.text = form.text.data
        user_descr.update_by = current_user.id
        user_descr.update_date = datetime.now()
        db.session.add(user_descr)
        db.session.commit()
        flash('Star description successfully updated', 'form-success')
        if form.goback.data == 'true':
            goback = True

    if goback:
        back = request.args.get('back')
        back_id = request.args.get('back_id')
        return redirect(url_for('main_constellation.constellation_info', constellation_id=back_id, _anchor='star' + str(star_id)))
    
    return render_template('main/catalogue/star_edit.html', form=form, user_descr=user_descr)

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
from app.commons.chart_generator import create_chart, create_chart_legend, MAX_IMG_WIDTH, MAX_IMG_HEIGHT
from app.commons.utils import to_float, to_boolean

main_star = Blueprint('main_star', __name__)

from .star_forms import (
    StarEditForm,
    StarFindChartForm,
)

FIELD_SIZES = (1, 2, 5, 10, 20, 40, 60, 80)

GUI_FIELD_SIZES = []

for i in range(0, len(FIELD_SIZES)-1):
    GUI_FIELD_SIZES.append(FIELD_SIZES[i])
    GUI_FIELD_SIZES.append((FIELD_SIZES[i] + FIELD_SIZES[i+1]) / 2)

GUI_FIELD_SIZES.append(FIELD_SIZES[-1])

# DEFAULT_MAG = [15, 12, 11, (8, 11), (6, 9), (6, 8), 6, 6, 5]
MAG_SCALES = [(12, 16), (11, 15), (10, 13), (8, 11), (6, 9), (6, 8), (5, 7), (5, 7)]


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

    fld_size = FIELD_SIZES[form.radius.data-1]
    prev_fld_size = session.get('star_prev_fld')
    session['star_prev_fld'] = fld_size

    night_mode = not session.get('themlight', False)

    cur_mag_scale = MAG_SCALES[form.radius.data - 1]

    if prev_fld_size != fld_size or request.method == 'GET':
        _, pref_maglim = _get_fld_size_maglim(form.radius.data-1)
        form.maglim.data = pref_maglim

    mag_range_values = []

    for i in range(0, len(FIELD_SIZES)):
        _, ml = _get_fld_size_maglim(i)
        mag_range_values.append(ml)

    form.maglim.data = _check_in_mag_interval(form.maglim.data, cur_mag_scale)
    session['star_pref_maglim'  + str(fld_size)] = form.maglim.data

    disable_dec_mag = 'disabled' if form.maglim.data <= cur_mag_scale[0] else ''
    disable_inc_mag = 'disabled' if form.maglim.data >= cur_mag_scale[1] else ''

    gui_field_sizes = ','.join(str(x) for x in GUI_FIELD_SIZES)

    if form.ra.data is None:
        form.ra.data = star.ra
    if form.dec.data is None:
        form.dec.data = star.dec

    return render_template('main/catalogue/star_info.html', form=form, type='fchart', user_descr=user_descr,
                           mag_scale=cur_mag_scale, disable_dec_mag=disable_dec_mag, disable_inc_mag=disable_inc_mag,
                           gui_field_sizes=gui_field_sizes, gui_field_index = (form.radius.data-1)*2,
                           chart_fsz=str(fld_size), chart_mlim=str(form.maglim.data), chart_nm=('1' if night_mode else '0'),
                           mag_ranges=MAG_SCALES, mag_range_values=mag_range_values,
                           )


@main_star.route('/star/<string:star_id>/fchart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def star_fchart_pos_img(star_id, ra, dec):
    star = Star.query.filter_by(id=star_id).first()
    if star is None:
        abort(404)

    gui_fld_size, maglim = _get_fld_size_mags_from_request()

    width = request.args.get('width', type=int)
    height = request.args.get('height', type=int)

    if width > MAX_IMG_WIDTH:
        width = MAX_IMG_WIDTH
    if height > MAX_IMG_HEIGHT:
        height = MAX_IMG_HEIGHT

    night_mode = to_boolean(request.args.get('nm'), True)

    img_bytes = BytesIO()
    create_chart(img_bytes, star.ra, star.dec, float(ra), float(dec), gui_fld_size, width, height, maglim, None, night_mode, show_legend=False)
    img_bytes.seek(0)
    return send_file(img_bytes, mimetype='image/png')


@main_star.route('/star/<string:star_id>/fchart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def star_fchart_legend_img(star_id, ra, dec):
    star = Star.query.filter_by(id=star_id).first()
    if star is None:
        abort(404)

    gui_fld_size, maglim = _get_fld_size_mags_from_request()

    width = request.args.get('width', type=int)
    height = request.args.get('height', type=int)

    if width > MAX_IMG_WIDTH:
        width = MAX_IMG_WIDTH
    if height > MAX_IMG_HEIGHT:
        height = MAX_IMG_HEIGHT

    night_mode = to_boolean(request.args.get('nm'), True)

    img_bytes = BytesIO()
    create_chart_legend(img_bytes, float(ra), float(dec), width, height, gui_fld_size, maglim, None, night_mode)
    img_bytes.seek(0)
    return send_file(img_bytes, mimetype='image/png')


def _get_fld_size_maglim(fld_size_index):
    fld_size = FIELD_SIZES[fld_size_index]

    mag_scale = MAG_SCALES[fld_size_index]

    maglim = session.get('star_pref_maglim' + str(fld_size))
    if maglim is None:
        maglim = (mag_scale[0] + mag_scale[1] + 1) // 2

    return (fld_size, maglim)


def _get_fld_size_mags_from_request():
    gui_fld_size = to_float(request.args.get('fsz'), 20.0)

    for i in range(len(FIELD_SIZES)-1, -1, -1):
        if gui_fld_size >= FIELD_SIZES[i]:
            fld_size_index = i
            break
    else:
        fld_size_index = 0

    fld_size, maglim = _get_fld_size_maglim(fld_size_index)

    if gui_fld_size > fld_size and (fld_size_index + 1) < len(FIELD_SIZES):
        next_fld_size, next_maglim = _get_fld_size_maglim(fld_size_index+1)
        maglim = (maglim + next_maglim) / 2

    return (gui_fld_size, maglim)

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

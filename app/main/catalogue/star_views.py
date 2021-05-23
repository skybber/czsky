from datetime import datetime
import os
import base64

from io import BytesIO

from flask import (
    abort,
    Blueprint,
    flash,
    jsonify,
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
from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_chart_pdf_img,
    common_prepare_chart_data,
    common_ra_dec_fsz_from_request,
)

from app.commons.utils import get_lang_and_editor_user_from_request

main_star = Blueprint('main_star', __name__)

from .star_forms import (
    StarEditForm,
)

from app.main.chart.chart_forms import ChartForm

@main_star.route('/star/<int:star_id>')
@main_star.route('/star/<int:star_id>/info')
def star_info(star_id):
    """View a star info."""
    star = Star.query.filter_by(id=star_id).first()
    if star is None:
        abort(404)

    return render_template('main/catalogue/star_info.html', type='info', star=star, user_descr=None, editable=False)

@main_star.route('/star/<int:star_descr_id>/descr-info')
def star_descr_info(star_descr_id):
    """View a star description info."""
    lang, editor_user = get_lang_and_editor_user_from_request()
    user_descr = UserStarDescription.query.filter_by(id=star_descr_id, user_id=editor_user.id, lang_code=lang).first()
    if user_descr is None:
        abort(404)

    editable=current_user.is_editor()
    return render_template('main/catalogue/star_info.html', type='info', user_descr=user_descr, editable=editable)

@main_star.route('/star/<int:star_id>/catalogue-data')
def star_catalogue_data(star_id):
    """View a star catalogue data."""
    star = Star.query.filter_by(id=star_id).first()
    if star is None:
        abort(404)

    return render_template('main/catalogue/star_info.html', type='catalogue_data', star=star,  user_descr=None)

@main_star.route('/star/<int:star_descr_id>/descr-catalogue-data')
def star_descr_catalogue_data(star_descr_id):
    """View a star catalogue data."""
    lang, editor_user = get_lang_and_editor_user_from_request()
    user_descr = UserStarDescription.query.filter_by(id=star_descr_id, user_id=editor_user.id, lang_code=lang).first()
    if user_descr is None:
        abort(404)

    return render_template('main/catalogue/star_info.html', type='catalogue_data', user_descr=user_descr)

@main_star.route('/star/<int:star_id>/chart', methods=['GET', 'POST'])
def star_chart(star_id):
    """View a star findchart."""
    star = Star.query.filter_by(id=star_id).first()
    if not star:
        abort(404)

    form  = ChartForm()

    if not common_ra_dec_fsz_from_request(form):
        if form.ra.data is None or form.dec.data is None:
            form.ra.data = star.ra
            form.dec.data = star.dec

    chart_control = common_prepare_chart_data(form)

    return render_template('main/catalogue/star_info.html', fchart_form=form, type='chart', star=star, user_descr=None, chart_control=chart_control, )


@main_star.route('/star/<int:star_descr_id>/descr-chart', methods=['GET', 'POST'])
def star_descr_chart(star_descr_id):
    """View a star findchart."""
    lang, editor_user = get_lang_and_editor_user_from_request()
    user_descr = UserStarDescription.query.filter_by(id=star_descr_id, user_id=editor_user.id, lang_code=lang).first()
    if user_descr is None:
        abort(404)

    star = user_descr.star
    if not star:
        abort(404)

    form  = ChartForm()

    if not common_ra_dec_fsz_from_request(form):
        if form.ra.data is None or form.dec.data is None:
            form.ra.data = star.ra
            form.dec.data = star.dec

    chart_control = common_prepare_chart_data(form)

    return render_template('main/catalogue/star_info.html', fchart_form=form, type='chart', user_descr=user_descr, chart_control=chart_control, )

@main_star.route('/star/<string:star_id>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def star_chart_pos_img(star_id, ra, dec):
    star = Star.query.filter_by(id=star_id).first()
    if star is None:
        abort(404)

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes = common_chart_pos_img(star.ra, star.dec, ra, dec, visible_objects=visible_objects)
    if visible_objects is not None:
        img = base64.b64encode(img_bytes.read()).decode()
        return jsonify(img=img, img_map=visible_objects)
    else:
        return send_file(img_bytes, mimetype='image/png')


@main_star.route('/star/<string:star_id>/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def star_chart_legend_img(star_id, ra, dec):
    star = Star.query.filter_by(id=star_id).first()
    if star is None:
        abort(404)

    img_bytes = common_chart_legend_img(star.ra, star.dec, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')


@main_star.route('/star/<string:star_id>/chart-pdf/<string:ra>/<string:dec>', methods=['GET'])
def star_chart_pdf(star_id, ra, dec):
    star = Star.query.filter_by(id=star_id).first()
    if star is None:
        abort(404)

    img_bytes = common_chart_pdf_img(star.ra, star.dec, ra, dec)

    return send_file(img_bytes, mimetype='application/pdf')

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

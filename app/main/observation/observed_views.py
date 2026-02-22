import os
import csv
from datetime import datetime
from io import StringIO, BytesIO
import base64
from typing import Optional

from werkzeug.utils import secure_filename

from sqlalchemy.orm import joinedload, load_only

from flask import (
    abort,
    Blueprint,
    current_app,
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
from flask_babel import gettext

from app import db, csrf

from .observed_forms import (
    AddToObservedListForm,
    SearchObservedForm,
)

from app.models import ObservedList, ObservedListItem, DeepskyObject, DoubleStar
from app.commons.search_utils import process_paginated_session_search, get_items_per_page, ITEMS_PER_PAGE
from app.commons.pagination import Pagination, get_page_parameter, get_page_args
from app.commons.chart_generator import (
    common_chart_pos_img,
    common_prepare_chart_data,
    common_ra_dec_dt_fsz_from_request,
)
from app.commons.chart_scene import (
    build_scene_v1,
    build_cross_highlight,
    SceneHighlight, normalized_theme_name,
)
from app.commons.dso_utils import (
    CHART_DOUBLE_STAR_PREFIX,
    CHART_COMET_PREFIX,
    CHART_MINOR_PLANET_PREFIX,
)

from app.commons.search_sky_object_utils import (
    search_dso,
    search_comet_exact,
    search_double_star,
    search_minor_planet_exact,
)


from app.commons.prevnext_utils import find_by_url_obj_id_in_list, get_default_chart_iframe_url
from app.commons.highlights_list_utils import common_highlights_from_observed_list_items

from app.main.chart.chart_forms import ChartForm

main_observed = Blueprint('main_observed', __name__)

@main_observed.route('/observed-list', methods=['GET'])
@main_observed.route('/observed-list/info', methods=['GET', 'POST'])
@login_required
def observed_list_info():
    """View observed list."""
    add_form = AddToObservedListForm()
    search_form = SearchObservedForm()

    ret, page, _ = process_paginated_session_search('observed_search_page', None, [
        ('observed_search', search_form.q),
        ('items_per_page', search_form.items_per_page)
    ])

    per_page = get_items_per_page(search_form.items_per_page)

    if not ret:
        return redirect(url_for('main_observed.observed_list_info'))

    observed_list = ObservedList.create_get_observed_list_by_user_id(current_user.id)
    observed_list_items = observed_list.observed_list_items

    page_offset = (page - 1) * per_page

    if page_offset < len(observed_list_items):
        page_items = observed_list_items[page_offset:page_offset + per_page]
    else:
        page_items = []

    pagination = Pagination(page=page, per_page=per_page, total=len(observed_list.observed_list_items), search=False, record_name='observed',
                            css_framework='semantic', not_passed_args='back')

    return render_template('main/observation/observed_list.html', observed_list=observed_list, type='info', add_form=add_form,
                           search_form=search_form, observed_list_items=enumerate(page_items), page_offset=page_offset, pagination=pagination)


@main_observed.route('/observed-list-item-add', methods=['POST'])
@login_required
def observed_list_item_add():
    """Add item to observed list."""
    form = AddToObservedListForm()
    object_name = form.object_name.data.strip()
    if request.method == 'POST' and form.validate_on_submit():
        observed_list = ObservedList.create_get_observed_list_by_user_id(current_user.id)
        deepsky_object = search_dso(object_name)
        new_item = None
        not_found = False
        if deepsky_object:
            dso_id = deepsky_object.master_id if deepsky_object.master_id is not None else deepsky_object.id
            if not observed_list.find_list_item_by_dso_id(dso_id):
                new_item = observed_list.create_new_deepsky_object_item(dso_id)
        else:
            double_star = search_double_star(object_name)
            if double_star:
                if not observed_list.find_list_item_by_double_star_id(double_star.id):
                    new_item = observed_list.create_new_double_star_item(double_star.id)
            else:
                comet = search_comet_exact(object_name)
                if comet:
                    if not observed_list.find_list_item_by_comet_id(comet.id):
                        new_item = observed_list.create_new_comet_item(comet.id)
                else:
                    minor_planet = search_minor_planet_exact(object_name)
                    if minor_planet:
                        if not observed_list.find_list_item_by_minor_planet_id(minor_planet.id):
                            new_item = observed_list.create_new_minor_planet_item(minor_planet.id)
                    else:
                        not_found = True
        if new_item is not None:
            db.session.add(new_item)
            db.session.commit()
            flash(gettext('Object was added to observed list.'), 'form-success')
        elif not not_found:
            flash(gettext('Object is already on observed list.'), 'form-info')
        else:
            flash(gettext('Object not found.'), 'form-warning')

    return redirect(url_for('main_observed.observed_list_info'))


@main_observed.route('/observed-list-item/<int:item_id>/delete')
@login_required
def observed_list_item_delete(item_id):
    """Remove item to observed list."""
    observed_list_item = ObservedListItem.query.filter_by(id=item_id).first()
    if observed_list_item is None:
        abort(404)
    if observed_list_item.observed_list.user_id != current_user.id:
        abort(404)
    db.session.delete(observed_list_item)
    db.session.commit()
    flash(gettext('Observed list item was deleted'), 'form-success')
    return redirect(url_for('main_observed.observed_list_info'))


@main_observed.route('/observed-list-delete', methods=['GET'])
@login_required
def observed_list_delete():
    """delete observed list."""
    add_form = AddToObservedListForm()
    observed_list = ObservedList.create_get_observed_list_by_user_id(current_user.id)
    ObservedListItem.query.filter_by(observed_list_id=observed_list.id).delete()
    db.session.commit()
    flash(gettext('Observed list deleted'), 'form-success')
    return redirect(url_for('main_observed.observed_list_info'))


@main_observed.route('/observed-list-upload', methods=['POST'])
@login_required
def observed_list_upload():
    if 'file' not in request.files:
        flash(gettext('No file part'), 'form-error')
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        flash(gettext('No selected file'))
        return redirect(request.url)
    if file:
        filename = secure_filename(file.filename)
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        with open(path) as csvfile:
            reader = csv.DictReader(csvfile, delimiter=';', fieldnames=['DSO_NAME'])
            observed_list = ObservedList.create_get_observed_list_by_user_id(current_user.id)
            existing_ids = set(item.dso_id for item in observed_list.observed_list_items)
            for row in reader:
                dso_name = row['DSO_NAME']
                if dso_name == 'none':
                    continue
                object_name = dso_name.replace(' ', '')
                dso = DeepskyObject.query.filter_by(name=object_name).first()
                if dso and dso.id not in existing_ids:
                    new_item = ObservedListItem(
                        observed_list_id=observed_list.id,
                        dso_id=dso.id,
                        create_date=datetime.now(),
                        update_date=datetime.now(),
                        )
                    db.session.add(new_item)
                    existing_ids.add(dso.id)
        db.session.commit()
        os.remove(path)
        flash(gettext('Observed list updated.'), 'form-success')

    return redirect(url_for('main_observed.observed_list_info'))


@main_observed.route('/observed-list-download', methods=['POST'])
@login_required
def observed_list_download():
    buf = StringIO()
    observed_list = ObservedList.create_get_observed_list_by_user_id(current_user.id)
    for observed_item in observed_list.observed_list_items:
        if observed_item.dso_id is not None:
            buf.write(observed_item.deepsky_object.name + '\n')
    mem = BytesIO()
    mem.write(buf.getvalue().encode('utf-8'))
    mem.seek(0)
    return send_file(mem, as_attachment=True,
                     download_name='observed-' + current_user.user_name + '.csv',
                     mimetype='text/csv')


@main_observed.route('/observed-list/chart', methods=['GET', 'POST'])
@login_required
@csrf.exempt
def observed_list_chart():
    observed_list = ObservedList.create_get_observed_list_by_user_id(current_user.id)
    if observed_list is None:
        abort(404)

    form = ChartForm()

    observed_list_item = find_by_url_obj_id_in_list(request.args.get('obj_id'), observed_list.observed_list_items)

    if not observed_list_item:
        observed_list_item = observed_list.observed_list_items[0] if observed_list.observed_list_items else None

    common_ra_dec_dt_fsz_from_request(form,
                                   observed_list_item.get_ra() if observed_list_item else 0,
                                   observed_list_item.get_dec() if observed_list_item else 0)

    chart_control = common_prepare_chart_data(form)
    default_chart_iframe_url = get_default_chart_iframe_url(observed_list_item, back='observed_list')

    return render_template('main/observation/observed_list.html', fchart_form=form, type='chart', observed_list=observed_list, chart_control=chart_control,
                           default_chart_iframe_url=default_chart_iframe_url,)


@main_observed.route('/observed-list/chart-pos-img', methods=['GET'])
@login_required
def observed_list_chart_pos_img():
    observed_list_items = _get_observed_list_items(current_user.id)
    highlights_dso_list, highlights_pos_list = common_highlights_from_observed_list_items(observed_list_items)
    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes, img_format = common_chart_pos_img(None, None, visible_objects=visible_objects,
                                                 highlights_dso_list=highlights_dso_list, highlights_pos_list=highlights_pos_list,
                                                 highlights_style='cross', highlights_size=0.75,
                                                 dso_highlights_style='cross', dso_highlights_size=0.75)
    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


def build_obs_highlight_cross(
        highlight_id: str,
        label: str,
        ra: float,
        dec: float,
        theme_name: Optional[str],
        size: float = 1.0,
) -> SceneHighlight:
    theme = normalized_theme_name(theme_name)
    if theme == "light":
        hl_color = [0.1, 0.2, 0.4]
    elif theme == "night":
        hl_color = [0.4, 0.2, 0.1]
    else:
        hl_color = [0.15, 0.3, 0.6]
    return {
        "shape": "cross",
        "id": highlight_id,
        "label": label,
        "ra": float(ra),
        "dec": float(dec),
        "size": float(size),
        "line_width": 0.3,
        "color": hl_color,
    }

@main_observed.route('/observed-list/chart/scene-v1', methods=['GET'])
@login_required
def observed_list_chart_scene_v1():
    observed_list = ObservedList.create_get_observed_list_by_user_id(current_user.id)
    if observed_list is None:
        abort(404)

    observed_list_item = find_by_url_obj_id_in_list(request.args.get('obj_id'), observed_list.observed_list_items)
    if not observed_list_item:
        observed_list_item = observed_list.observed_list_items[0] if observed_list.observed_list_items else None

    highlights_dso_list, highlights_pos_list = common_highlights_from_observed_list_items(observed_list.observed_list_items)

    scene = build_scene_v1()
    scene_meta = scene.setdefault('meta', {})
    scene_objects = scene.setdefault('objects', {})
    highlights = scene_objects.setdefault('highlights', [])
    cur_theme = session.get('theme')

    if observed_list_item:
        if observed_list_item.dso_id is not None and observed_list_item.deepsky_object is not None:
            dso = observed_list_item.deepsky_object
            highlights.append(
                build_obs_highlight_cross(highlight_id=str(dso.name).replace(' ', ''), label=dso.denormalized_name(), ra=dso.ra, dec=dso.dec, theme_name=cur_theme,)
            )
        elif observed_list_item.double_star_id is not None and observed_list_item.double_star is not None:
            double_star = observed_list_item.double_star
            highlights.append(
                build_obs_highlight_cross(highlight_id=CHART_DOUBLE_STAR_PREFIX + str(double_star.id), label=double_star.get_catalog_name(), ra=double_star.ra_first, dec=double_star.dec_first, theme_name=cur_theme,)
            )
        elif observed_list_item.comet_id is not None and observed_list_item.comet is not None:
            comet = observed_list_item.comet
            highlights.append(
                build_obs_highlight_cross(highlight_id=CHART_COMET_PREFIX + str(comet.id), label=comet.designation, ra=comet.cur_ra, dec=comet.cur_dec, theme_name=cur_theme,)
            )
        elif observed_list_item.minor_planet_id is not None and observed_list_item.minor_planet is not None:
            minor_planet = observed_list_item.minor_planet
            highlights.append(
                build_obs_highlight_cross(highlight_id=CHART_MINOR_PLANET_PREFIX + str(minor_planet.id), label=minor_planet.designation, ra=minor_planet.cur_ra, dec=minor_planet.cur_dec, theme_name=cur_theme,)
            )

    if highlights_dso_list:
        for hl_dso in highlights_dso_list:
            if hl_dso is None:
                continue
            highlights.append(
                build_obs_highlight_cross(highlight_id=str(hl_dso.name).replace(' ', ''), label=hl_dso.denormalized_name(), ra=hl_dso.ra, dec=hl_dso.dec, theme_name=cur_theme, size=0.75,)
            )

    if highlights_pos_list:
        for hl_pos in highlights_pos_list:
            if hl_pos is None or len(hl_pos) < 4:
                continue
            hl_ra, hl_dec, hl_id, hl_label = hl_pos[0], hl_pos[1], hl_pos[2], hl_pos[3]
            if hl_ra is None or hl_dec is None:
                continue
            highlights.append(
                build_obs_highlight_cross(highlight_id=str(hl_id), label=str(hl_label or hl_id), ra=hl_ra, dec=hl_dec, theme_name=cur_theme, size=0.75,)
            )

    scene_meta['object_context'] = {
        'kind': 'observed_list',
        'id': str(observed_list.id),
    }
    return jsonify(scene)


def _get_observed_list_items(user_id):
    observed_list = ObservedList.query.options(load_only(ObservedList.id)).filter_by(user_id=user_id).first()
    if observed_list:
        ret = db.session.query(ObservedListItem).options(
                load_only(ObservedListItem.id, ObservedListItem.observed_list_id, ObservedListItem.dso_id, ObservedListItem.double_star_id),
                joinedload(ObservedListItem.deepsky_object).load_only(DeepskyObject.id, DeepskyObject.name),
                joinedload(ObservedListItem.double_star).load_only(
                    DoubleStar.id, DoubleStar.ra_first, DoubleStar.dec_first, DoubleStar.common_cat_id, DoubleStar.wds_number
                ),
                ) \
                .filter(ObservedListItem.observed_list_id == observed_list.id) \
                .all()
        return ret
    return []

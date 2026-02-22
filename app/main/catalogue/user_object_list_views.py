from datetime import datetime
import base64

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
from flask_babel import gettext

from app import db, csrf
from app.commons.highlights_list_utils import common_highlights_from_user_object_list

from app.main.catalogue.user_object_list_forms import (
    UserObjectListNewForm,
    UserObjectListEditForm,
    UserObjectListItemsEditForm,
)

from app.models import (
    UserObjectListItemType,
    User,
    UserObjectList,
    UserObjectListItem,
)

from app.commons.search_utils import ITEMS_PER_PAGE
from app.commons.pagination import Pagination, get_page_parameter

from app.commons.chart_generator import (
    common_chart_pos_img,
    common_prepare_chart_data,
    common_ra_dec_dt_fsz_from_request,
    common_chart_pdf_img,
)
from app.commons.chart_scene import (
    build_scene_v1,
    build_cross_highlight,
    build_circle_highlight,
    ensure_scene_dso_item,
)
from app.commons.dso_utils import CHART_DOUBLE_STAR_PREFIX

from app.main.chart.chart_forms import ChartForm
from app.commons.prevnext_utils import get_default_chart_iframe_url, parse_prefix_obj_id

main_user_object_list = Blueprint('main_user_object_list', __name__)


@main_user_object_list.route('/user-object-lists', methods=['GET', 'POST'])
@login_required
def user_object_lists():
    """View user object lists."""
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    user_object_lists = UserObjectList.query.filter_by(user_id=current_user.id).order_by(UserObjectList.create_date.desc())
    search = False

    uol_for_render = user_object_lists.limit(per_page).offset(offset).all()

    pagination = Pagination(page=page, per_page=per_page, total=user_object_lists.count(), search=search, record_name='user_object_list', css_framework='semantic')
    return render_template('main/catalogue/user_object_lists.html', user_object_lists=uol_for_render, pagination=pagination, user=None)


@main_user_object_list.route('/user-user-object-lists/<int:user_id>', methods=['GET', 'POST'])
def user_user_object_lists(user_id):
    """View user object lists of given user."""
    user = User.query.filter_by(id=user_id).first()
    if user is None:
        abort(404)
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    user_object_lists = UserObjectList.query.filter_by(user_id=user_id, is_public=True) \
        .order_by(UserObjectList.date_from.desc())
    search = False

    obs_sessions_for_render = user_object_lists.limit(per_page).offset(offset).all()

    pagination = Pagination(page=page, per_page=per_page, total=user_object_lists.count(), search=search, record_name='observations', css_framework='semantic')
    return render_template('main/catalogue/user_object_lists.html', user_object_lists=obs_sessions_for_render, pagination=pagination, user=user)


def _check_user_object_list(user_object_list, allow_public=False):
    if user_object_list is None:
        abort(404)
    if current_user.is_anonymous:
        if user_object_list.is_public:
            return False
        abort(404)
    elif user_object_list.user_id != current_user.id:
        if allow_public and user_object_list.is_public:
            return False
        abort(404)

    return True


@main_user_object_list.route('/user-object-list/<int:user_object_list_id>', methods=['GET'])
@main_user_object_list.route('/user-object-list/<int:user_object_list_id>/info', methods=['GET'])
def user_object_list_info(user_object_list_id):
    """View a user object list."""
    user_object_list = UserObjectList.query.filter_by(id=user_object_list_id).first()
    is_mine_user_object_list = _check_user_object_list(user_object_list, allow_public=True)

    return render_template('main/catalogue/user_object_list_info.html', user_object_list=user_object_list, type='info',
                           is_mine_user_object_list=is_mine_user_object_list)


@main_user_object_list.route('/new-user-object-list', methods=['GET', 'POST'])
@login_required
def new_user_object_list():
    """Create new user_object_list"""
    form = UserObjectListNewForm()
    if form.validate_on_submit():
        new_list = UserObjectList(
            user_id=current_user.id,
            title=form.title.data,
            text=form.text.data,
            is_public=form.is_public.data,
            create_date=datetime.now(),
            update_date=datetime.now()
        )
        db.session.add(new_list)
        db.session.commit()
        flash(gettext('User object list successfully created'), 'form-success')
        return redirect(url_for('main_user_object_list.user_object_list_info', user_object_list_id=new_list.id))

    return render_template(
        'main/catalogue/user_object_list_edit.html',
        form=form,
        is_new=True,
        user_object_list=None
    )


@main_user_object_list.route('/user-object-list/<int:user_object_list_id>/edit', methods=['GET', 'POST'])
@login_required
def user_object_list_edit(user_object_list_id):
    """Update user_object_list"""
    user_object_list = UserObjectList.query.get_or_404(user_object_list_id)
    _check_user_object_list(user_object_list)

    form = UserObjectListEditForm()

    if request.method == 'GET':
        form.title.data = user_object_list.title
        form.text.data = user_object_list.text
        form.is_public.data = user_object_list.is_public
    else:
        if form.validate_on_submit():
            user_object_list.title = form.title.data
            user_object_list.text = form.text.data
            user_object_list.is_public = form.is_public.data
            user_object_list.update_date = datetime.now()
            db.session.commit()

            flash(gettext('User object list successfully updated'), 'form-success')
            if form.goback.data == 'true':
                return redirect(url_for('main_user_object_list.user_object_list_info', user_object_list_id=user_object_list.id))
            return redirect(url_for('main_user_object_list.user_object_list_edit', user_object_list_id=user_object_list.id))

    return render_template(
        'main/catalogue/user_object_list_edit.html',
        form=form,
        is_new=False,
        user_object_list=user_object_list
    )


@main_user_object_list.route('/user-object-list/<int:user_object_list_id>/delete', methods=['GET', 'POST'])
@login_required
def user_object_list_delete(user_object_list_id):
    """Request deletion of a user_object_list."""
    user_object_list = UserObjectList.query.get_or_404(user_object_list_id)
    _check_user_object_list(user_object_list)
    db.session.delete(user_object_list)
    db.session.commit()
    flash(gettext('User object list was deleted'), 'form-success')
    return redirect(url_for('main_user_object_list.user_object_lists'))


@main_user_object_list.route('/user-object-list/<int:user_object_list_id>/items-edit', methods=['GET', 'POST'])
@login_required
def user_object_list_items_edit(user_object_list_id):
    """Update user_object_list items"""
    user_object_list = UserObjectList.query.filter_by(id=user_object_list_id).first()
    _check_user_object_list(user_object_list)

    form = UserObjectListItemsEditForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            for list_item in user_object_list.list_items:
                list_item.deepsky_objects = []
                db.session.delete(list_item)
            user_object_list.list_items.clear()
            for item_form in form.items[1:]:
                if ':' in item_form.comp_notes.data:
                    targets, notes = item_form.comp_notes.data.split(':', 1)
                else:
                    targets, notes = item_form.comp_notes.data.strip(), ''

                list_item = UserObjectListItem(
                    user_object_list_id=user_object_list.id,
                    user_id=current_user.id,
                    text=text,
                    create_date=datetime.now(),
                    update_date=datetime.now(),
                )
                user_object_list.observations.append(list_item)

                set_observation_targets(list_item, targets)

            db.session.add(user_object_list)
            db.session.commit()

            if form.goback.data == 'true':
                return redirect(url_for('main_user_object_list.user_object_list_info', user_object_list_id=user_object_list.id))
            return redirect(url_for('main_user_object_list.user_object_list_items_edit', user_object_list_id=user_object_list.id))
    else:
        for oi in user_object_list.observations:
            oif = form.items.append_entry()
            if oi.item_type == UserObjectListItemType.DBL_STAR:
                targets_comp = oi.double_star.get_common_norm_name()
            elif oi.item_type == UserObjectListItemType.COMET:
                targets_comp = oi.comet.designation
            elif oi.item_type == UserObjectListItemType.M_PLANET:
                targets_comp = oi.minor_planet.designation
            else:
                targets_comp = ','.join([dso.name for dso in oi.deepsky_objects])
            targets_comp += ':'
            oif.comp_notes.data = targets_comp + oi.notes
            oif.date_from.data = oi.date_from
            oif.telescope.data = oi.telescope_id if oi.telescope_id is not None else -1
            oif.eyepiece.data = oi.eyepiece_id if oi.eyepiece_id is not None else -1
            oif.filter.data = oi.filter_id if oi.filter_id is not None else -1

    return render_template('main/observation/user_object_list_items_edit.html', form=form, user_object_list=user_object_list)


@main_user_object_list.route('/user-object-list/<int:user_object_list_id>/chart', methods=['GET', 'POST'])
@csrf.exempt
def user_object_list_chart(user_object_list_id):
    user_object_list = UserObjectList.query.filter_by(id=user_object_list_id).first()
    is_mine_user_object_list = _check_user_object_list(user_object_list, allow_public=True)

    form = ChartForm()

    prefix, obj_id = parse_prefix_obj_id(request.args.get('obj_id'))

    user_object_list_item = None

    for oitem in user_object_list.list_items:
        if oitem.item_type == UserObjectListItemType.DSO:
            for oitem_dso in oitem.deepsky_objects:
                if obj_id is None or oitem_dso.id == obj_id:
                    user_object_list_item = oitem
                    break
        elif oitem.item_type == UserObjectListItemType.DBL_STAR:
            if obj_id is None or oitem.double_star_id == obj_id:
                user_object_list_item = oitem
        if user_object_list_item is not None:
            break

    common_ra_dec_dt_fsz_from_request(form,
                                      user_object_list_item.get_ra() if user_object_list_item else None,
                                      user_object_list_item.get_dec() if user_object_list_item else None)

    chart_control = common_prepare_chart_data(form)
    default_chart_iframe_url = get_default_chart_iframe_url(user_object_list_item, back='observation', back_id=user_object_list.id)

    return render_template('main/catalogue/user_object_list_info.html', fchart_form=form, type='chart',
                           user_object_list=user_object_list, chart_control=chart_control,
                           default_chart_iframe_url=default_chart_iframe_url, is_mine_user_object_list=is_mine_user_object_list,
                           back='observation', back_id=user_object_list.id)


@main_user_object_list.route('/user-object-list/<int:user_object_list_id>/chart-pos-img', methods=['GET'])
def user_object_list_chart_pos_img(user_object_list_id):
    user_object_list = UserObjectList.query.filter_by(id=user_object_list_id).first()
    is_mine_user_object_list = _check_user_object_list(user_object_list, allow_public=True)

    highlights_dso_list, highlights_pos_list = common_highlights_from_user_object_list(user_object_list)

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes, img_format = common_chart_pos_img(None, None, visible_objects=visible_objects,
                                                 highlights_dso_list=highlights_dso_list, highlights_pos_list=highlights_pos_list)
    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


@main_user_object_list.route('/user-object-list/<int:user_object_list_id>/chart/scene-v1', methods=['GET'])
def user_object_list_chart_scene_v1(user_object_list_id):
    user_object_list = UserObjectList.query.filter_by(id=user_object_list_id).first()
    _check_user_object_list(user_object_list, allow_public=True)

    prefix, obj_id = parse_prefix_obj_id(request.args.get('obj_id'))
    selected_dso = None
    selected_ds = None
    selected_hl_id = None
    selected_label = None
    selected_ra = None
    selected_dec = None

    for oitem in user_object_list.list_items:
        if oitem.item_type == UserObjectListItemType.DSO:
            for dso in oitem.deepsky_objects:
                if obj_id is None or dso.id == obj_id:
                    selected_dso = dso
                    break
        elif oitem.item_type == UserObjectListItemType.DBL_STAR:
            if obj_id is None or oitem.double_star_id == obj_id:
                selected_ds = oitem.double_star
        if selected_dso is not None or selected_ds is not None:
            break

    highlights_dso_list, highlights_pos_list = common_highlights_from_user_object_list(user_object_list)
    scene = build_scene_v1()
    scene_meta = scene.setdefault('meta', {})
    scene_objects = scene.setdefault('objects', {})
    highlights = scene_objects.setdefault('highlights', [])
    cur_theme = session.get('theme')

    if selected_dso is not None:
        ensure_scene_dso_item(scene, selected_dso)
        selected_hl_id = str(selected_dso.name).replace(' ', '')
        selected_label = selected_dso.denormalized_name()
        selected_ra = selected_dso.ra
        selected_dec = selected_dso.dec
    elif selected_ds is not None:
        selected_hl_id = CHART_DOUBLE_STAR_PREFIX + str(selected_ds.id)
        selected_label = selected_ds.get_catalog_name()
        selected_ra = selected_ds.ra_first
        selected_dec = selected_ds.dec_first

    if selected_hl_id and selected_ra is not None and selected_dec is not None:
        highlights.append(
            build_cross_highlight(highlight_id=selected_hl_id, label=selected_label or selected_hl_id, ra=selected_ra, dec=selected_dec, theme_name=cur_theme,)
        )

    if highlights_dso_list:
        for hl_dso in highlights_dso_list:
            if hl_dso is None:
                continue
            ensure_scene_dso_item(scene, hl_dso)
            highlights.append(
                build_circle_highlight(highlight_id=str(hl_dso.name).replace(' ', ''), label=hl_dso.denormalized_name(), ra=hl_dso.ra, dec=hl_dso.dec, dashed=False, theme_name=cur_theme,)
            )

    if highlights_pos_list:
        for hl_pos in highlights_pos_list:
            if hl_pos is None or len(hl_pos) < 4:
                continue
            hl_ra, hl_dec, hl_id, hl_label = hl_pos[0], hl_pos[1], hl_pos[2], hl_pos[3]
            if hl_ra is None or hl_dec is None:
                continue
            highlights.append(
                build_circle_highlight(highlight_id=str(hl_id), label=str(hl_label or hl_id), ra=hl_ra, dec=hl_dec, dashed=False, theme_name=cur_theme,)
            )

    scene_meta['object_context'] = {
        'kind': 'user_object_list',
        'id': str(user_object_list.id),
        'list_title': user_object_list.title,
        'selected_prefix': prefix,
    }
    return jsonify(scene)


@main_user_object_list.route('/user-object-list/<int:user_object_list_id>/chart-pdf', methods=['GET'])
def user_object_list_chart_pdf(user_object_list_id):
    user_object_list = UserObjectList.query.filter_by(id=user_object_list_id).first()
    _check_user_object_list(user_object_list, allow_public=True)

    highlights_dso_list, highlights_pos_list = common_highlights_from_user_object_list(user_object_list)

    img_bytes = common_chart_pdf_img(None, None, highlights_dso_list=highlights_dso_list, highlights_pos_list=highlights_pos_list)

    return send_file(img_bytes, mimetype='application/pdf')

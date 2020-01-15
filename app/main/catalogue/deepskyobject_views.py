import os
import subprocess

from datetime import datetime

from flask import (
    abort,
    Blueprint,
    current_app,
    flash,
    render_template,
    request,
    session,
)
from flask_login import current_user, login_required

from app import db

from app.models import User, Catalogue, DeepskyObject, Permission, UserDsoDescription
from app.commons.pagination import Pagination
from app.commons.dso_utils import normalize_dso_name
from app.commons.search_utils import process_paginated_session_search

from .deepskyobject_forms import (
    DeepskyObjectFindChartForm,
    DeepskyObjectEditForm,
    SearchDsoForm,
)

from app.main.views import ITEMS_PER_PAGE

main_deepskyobject = Blueprint('main_deepskyobject', __name__)

@main_deepskyobject.route('/deepskyobjects', methods=['GET', 'POST'])
def deepskyobjects():
    """View deepsky objects."""
    search_form = SearchDsoForm()

    page, search_expr, dso_type, catalogue = process_paginated_session_search('dso_search_page', [
        ('dso_search', search_form.q),
        ('dso_type', search_form.dso_type),
        ('dso_catal', search_form.catalogue),
    ])

    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    deepskyobjects = DeepskyObject.query
    if search_expr:
        deepskyobjects = deepskyobjects.filter(DeepskyObject.name.like('%' + normalize_dso_name(search_expr) + '%'))

    if dso_type and dso_type != 'All':
        deepskyobjects = deepskyobjects.filter(DeepskyObject.type==dso_type)

    if catalogue and catalogue != 'All':
        cat_id = Catalogue.get_catalogue_id_by_cat_code(catalogue)
        if cat_id:
            deepskyobjects = deepskyobjects.filter_by(catalogue_id=cat_id)

    deepskyobjects_for_render = deepskyobjects.limit(per_page).offset(offset)

    pagination = Pagination(page=page, total=deepskyobjects.count(), search=False, record_name='deepskyobjects', css_framework='semantic', not_passed_args='back')
    return render_template('main/catalogue/deepskyobjects.html', deepskyobjects=deepskyobjects_for_render, pagination=pagination, search_form=search_form)


@main_deepskyobject.route('/deepskyobject/<int:dso_id>')
@main_deepskyobject.route('/deepskyobject/<int:dso_id>/info')
def deepskyobject_info(dso_id):
    """View a deepsky object info."""
    dso = DeepskyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)
    from_constellation_id = request.args.get('from_constellation_id')
    from_observation_id = request.args.get('from_observation_id')
    user_editor = User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME')).first()
    user_descr = None
    if user_editor:
        user_descr = UserDsoDescription.query.filter_by(dso_id=dso.id, user_id=user_editor.id) \
                        .filter(UserDsoDescription.lang_code.in_(('cs', 'sk'))) \
                        .first()
    prev_dso, next_dso = dso.get_prev_next_dso()
    editable=current_user.is_editor()
    return render_template('main/catalogue/deepskyobject_info.html', type='info', dso=dso, user_descr=user_descr,
                           from_constellation_id=from_constellation_id, from_observation_id=from_observation_id,
                           prev_dso=prev_dso, next_dso=next_dso, editable=editable)

@main_deepskyobject.route('/deepskyobject/<int:dso_id>/catalogue_data')
def deepskyobject_catalogue_data(dso_id):
    """View a deepsky object info."""
    dso = DeepskyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)
    from_constellation_id = request.args.get('from_constellation_id')
    from_observation_id = request.args.get('from_observation_id')
    prev_dso, next_dso = dso.get_prev_next_dso()
    return render_template('main/catalogue/deepskyobject_info.html', type='catalogue_data', dso=dso,
                           from_constellation_id=from_constellation_id, from_observation_id=from_observation_id,
                           prev_dso=prev_dso, next_dso=next_dso)

@main_deepskyobject.route('/deepskyobject/<int:dso_id>/findchart', methods=['GET', 'POST'])
def deepskyobject_findchart(dso_id):
    """View a deepsky object findchart."""
    dso = DeepskyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)
    form  = DeepskyObjectFindChartForm()
    from_constellation_id = request.args.get('from_constellation_id')
    from_observation_id = request.args.get('from_observation_id')
    prev_dso, next_dso = dso.get_prev_next_dso()
    preview_url_dir = '/static/webassets-external/preview/'
    preview_dir = 'app' + preview_url_dir

    dso_dname = dso.denormalized_name().replace(' ','')

    field_sizes = (1, 5, 15)
    fld_size = field_sizes[form.radius.data-1]

    night_mode = not session.get('themlight', False)

    invert_part = '_i' if night_mode else ''
    mirror_x_part = '_mx' if form.mirror_x.data else ''
    mirror_y_part = '_my' if form.mirror_y.data else ''
    dso_file_name = dso_dname + '_' + 'r' + str(fld_size) + '_m' + str(form.maglim.data) + invert_part + mirror_x_part + mirror_y_part + '.png'

    full_file_name = preview_dir + os.sep + dso_file_name

    mag_scales = [(12, 15), (9, 12), (6, 9)]
    cur_mag_scale = mag_scales[form.radius.data - 1]
    if cur_mag_scale[0] > form.maglim.data:
        form.maglim.data = cur_mag_scale[0]
    elif cur_mag_scale[1] < form.maglim.data:
        form.maglim.data = cur_mag_scale[1]

    if not os.path.exists(full_file_name):
        # a4_width = '180'

        prog_params = ['fchart3',
                       '-size', str(fld_size),
                       '-width', '220',
                       '-f', full_file_name,
                       '-capt', '',
                       '-limdso', '13.0',
                       '-limstar', str(form.maglim.data),
                       '-lstar', '0.06',
                       '-locl', '0.15',
                       '-ldso', '0.1',
                       '-llegend', '0.3',
                       '-usno-nomad', os.path.join(os.getcwd(), 'data/USNO-NOMAD-1e8.dat'),
                       ]
        if night_mode:
            prog_params.append('-nm')
        if form.mirror_x.data:
            prog_params.append('-mx')
        if form.mirror_y.data:
            prog_params.append('-my')
        prog_params.append(dso_dname)
        p = subprocess.Popen(prog_params)
        p.wait()
    fchart_url = preview_url_dir + dso_file_name
    return render_template('main/catalogue/deepskyobject_info.html', form=form, type='fchart', dso=dso, fchart_url=fchart_url,
                           from_constellation_id=from_constellation_id, from_observation_id=from_observation_id,
                           prev_dso=prev_dso, next_dso=next_dso, mag_min=cur_mag_scale[0], mag_max=cur_mag_scale[1])

@main_deepskyobject.route('/deepskyobject/<int:dso_id>/edit', methods=['GET', 'POST'])
@login_required
def deepskyobject_edit(dso_id):
    """Update deepsky object."""
    dso = DeepskyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)
    if not current_user.is_editor():
        abort(403)

    user_editor = User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME')).first()
    user_descr = None
    form = DeepskyObjectEditForm()
    if user_editor:
        user_descr = UserDsoDescription.query.filter_by(dso_id=dso.id, user_id=user_editor.id) \
                        .filter(UserDsoDescription.lang_code.in_(('cs', 'sk'))) \
                        .first()
        if not user_descr:
            user_descr = UserDsoDescription(
                dso_id = dso_id,
                user_id = user_editor.id,
                rating = 5,
                lang_code = 'cs',
                common_name = '',
                text = '',
                cons_order = 1,
                create_by = current_user.id,
                create_date = datetime.now(),
                )
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
            flash('Deepsky object successfully updated', 'form-success')

    from_constellation_id = request.args.get('from_constellation_id')
    from_observation_id = request.args.get('from_observation_id')

    return render_template('main/catalogue/deepskyobject_edit.html', form=form, dso=dso, user_descr=user_descr,
                           from_constellation_id=from_constellation_id, from_observation_id=from_observation_id,
                           )

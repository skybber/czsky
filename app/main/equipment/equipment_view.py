from datetime import datetime

from flask import (
    abort,
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from flask_babel import gettext
from sqlalchemy import or_, and_

from app import db

from app.models import Telescope, Eyepiece, Filter, Lens

from .equipment_forms import (
    TelescopeNewForm,
    TelescopeEditForm,
    EyepieceNewForm,
    EyepieceEditForm,
    FilterNewForm,
    FilterEditForm,
    LensNewForm,
    LensEditForm,
)

from app.commons.countries import countries

main_equipment = Blueprint('main_equipment', __name__)


def _is_telescope_editable(telescope):
    return telescope.user_id == current_user.id


def _is_eyepiece_editable(eyepiece):
    return eyepiece.user_id == current_user.id


def _is_filter_editable(filter):
    return filter.user_id == current_user.id


def _is_lens_editable(lens):
    return lens.user_id == current_user.id


@main_equipment.route('/equipment-menu', methods=['GET'])
@login_required
def equipment_menu():
    telescopes_count = Telescope.query.filter_by(user_id=current_user.id, is_deleted=False).count()
    eyepieces_count = Eyepiece.query.filter_by(user_id=current_user.id, is_deleted=False).count()
    filters_count = Filter.query.filter_by(user_id=current_user.id, is_deleted=False).count()
    lenses_count = Lens.query.filter_by(user_id=current_user.id, is_deleted=False).count()

    return render_template('main/equipment/equipment_menu.html', telescopes_count=telescopes_count, eyepieces_count=eyepieces_count,
                           filters_count=filters_count, lenses_count=lenses_count)


@main_equipment.route('/telescopes', methods=['GET', 'POST'])
@login_required
def telescopes():
    telescopes = Telescope.query.filter_by(user_id=current_user.id, is_deleted=False).all()
    return render_template('main/equipment/telescopes.html', telescopes=telescopes)


@main_equipment.route('/telescope/<int:telescope_id>', methods=['GET'])
@main_equipment.route('/telescope/<int:telescope_id>/info', methods=['GET'])
@login_required
def telescope_info(telescope_id):
    """View a telescope info."""
    telescope = Telescope.query.filter_by(id=telescope_id, is_deleted=False).first()
    if telescope is None:
        abort(404)
    if telescope.user_id != current_user.id:
        abort(404)
    return render_template('main/equipment/telescope_info.html', telescope=telescope, editable=_is_telescope_editable(telescope))


@main_equipment.route('/new-telescope', methods=['GET', 'POST'])
@login_required
def new_telescope():
    """New telescope"""
    form = TelescopeNewForm()
    if request.method == 'POST' and form.validate_on_submit():
        telescope = Telescope(
            name=form.name.data,
            vendor=form.vendor.data,
            model=form.model.data,
            descr=form.descr.data,
            aperture_mm=form.aperture_mm.data,
            focal_length_mm=form.focal_length_mm.data,
            fixed_magnification=form.fixed_magnification.data,
            telescope_type=form.telescope_type.data,
            is_default=form.is_default.data,
            is_active=True,
            is_deleted=False,
            user_id=current_user.id,
            create_by=current_user.id,
            update_by=current_user.id,
            create_date=datetime.now(),
            update_date=datetime.now()
        )
        db.session.add(telescope)
        db.session.commit()
        flash(gettext('Telescope successfully created'), 'form-success')
        return redirect(url_for('main_equipment.telescope_edit', telescope_id=telescope.id))
    return render_template('main/equipment/telescope_edit.html', form=form, is_new=True)


@main_equipment.route('/telescope/<int:telescope_id>/edit', methods=['GET', 'POST'])
@login_required
def telescope_edit(telescope_id):
    """Update telescope"""
    telescope = Telescope.query.filter_by(id=telescope_id, is_deleted=False).first()
    if telescope is None:
        abort(404)
    if not _is_telescope_editable(telescope):
        abort(404)
    form = TelescopeEditForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            telescope.name = form.name.data
            telescope.vendor = form.vendor.data
            telescope.model = form.model.data
            telescope.descr = form.descr.data
            telescope.aperture_mm = form.aperture_mm.data
            telescope.focal_length_mm = form.focal_length_mm.data
            telescope.fixed_magnification = form.fixed_magnification.data
            telescope.telescope_type = form.telescope_type.data
            telescope.is_default = form.is_default.data
            telescope.is_active = form.is_active.data
            telescope.is_deleted = False
            telescope.update_by = current_user.id
            telescope.update_date = datetime.now()
            db.session.add(telescope)
            db.session.commit()
            flash(gettext('Telescope successfully updated'), 'form-success')
            return redirect(url_for('main_equipment.telescope_edit', telescope_id=telescope.id))
    else:
        form.name.data = telescope.name
        form.vendor.data = telescope.vendor
        form.model.data = telescope.model
        form.descr.data = telescope.descr
        form.aperture_mm.data = telescope.aperture_mm
        form.focal_length_mm.data = telescope.focal_length_mm
        form.fixed_magnification.data = telescope.fixed_magnification
        form.telescope_type.data = telescope.telescope_type
        form.is_default.data = telescope.is_default
        form.is_active.data = telescope.is_active

    return render_template('main/equipment/telescope_edit.html', form=form, telescope=telescope, is_new=False)


@main_equipment.route('/telescope/<int:telescope_id>/delete')
@login_required
def telescope_delete(telescope_id):
    """Request deletion of telescope."""
    telescope = Telescope.query.filter_by(id=telescope_id, is_deleted=False).first()
    if telescope is None:
        abort(404)
    if not _is_telescope_editable(telescope):
        abort(404)
    telescope.is_deleted = True
    db.session.add(telescope)
    db.session.commit()
    flash(gettext('Telescope was deleted'), 'form-success')
    return redirect(url_for('main_equipment.telescopes'))


@main_equipment.route('/eyepieces', methods=['GET', 'POST'])
@login_required
def eyepieces():
    eyepieces = Eyepiece.query.filter_by(user_id=current_user.id, is_deleted=False).all()
    return render_template('main/equipment/eyepieces.html', eyepieces=eyepieces)


@main_equipment.route('/eyepiece/<int:eyepiece_id>', methods=['GET'])
@main_equipment.route('/eyepiece/<int:eyepiece_id>/info', methods=['GET'])
@login_required
def eyepiece_info(eyepiece_id):
    """View a eyepiece info."""
    eyepiece = Eyepiece.query.filter_by(id=eyepiece_id, is_deleted=False).first()
    if eyepiece is None:
        abort(404)
    if eyepiece.user_id != current_user.id:
        abort(404)
    return render_template('main/equipment/eyepiece_info.html', eyepiece=eyepiece, editable=_is_eyepiece_editable(eyepiece))


@main_equipment.route('/new-eyepiece', methods=['GET', 'POST'])
@login_required
def new_eyepiece():
    """New eyepiece"""
    form = EyepieceNewForm()
    if request.method == 'POST' and form.validate_on_submit():
        eyepiece = Eyepiece(
            name=form.name.data,
            vendor=form.vendor.data,
            model=form.model.data,
            descr=form.descr.data,
            focal_length_mm=form.focal_length_mm.data,
            fov_deg=form.fov_deg.data,
            diameter_inch=form.diameter_inch.data,
            is_active=True,
            is_deleted=False,
            user_id=current_user.id,
            create_by=current_user.id,
            update_by=current_user.id,
            create_date=datetime.now(),
            update_date=datetime.now()
        )
        db.session.add(eyepiece)
        db.session.commit()
        flash(gettext('Eyepiece successfully created'), 'form-success')
        return redirect(url_for('main_equipment.eyepiece_edit', eyepiece_id=eyepiece.id))
    return render_template('main/equipment/eyepiece_edit.html', form=form, is_new=True)


@main_equipment.route('/eyepiece/<int:eyepiece_id>/edit', methods=['GET', 'POST'])
@login_required
def eyepiece_edit(eyepiece_id):
    """Update eyepiece"""
    eyepiece = Eyepiece.query.filter_by(id=eyepiece_id, is_deleted=False).first()
    if eyepiece is None:
        abort(404)
    if not _is_eyepiece_editable(eyepiece):
        abort(404)
    form = EyepieceEditForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            eyepiece.name = form.name.data
            eyepiece.vendor = form.vendor.data
            eyepiece.model = form.model.data
            eyepiece.descr = form.descr.data
            eyepiece.focal_length_mm = form.focal_length_mm.data
            eyepiece.fov_deg = form.fov_deg.data
            eyepiece.diameter_inch = form.diameter_inch.data
            eyepiece.is_active = form.is_active.data
            eyepiece.is_deleted = False
            eyepiece.update_by = current_user.id
            eyepiece.update_date = datetime.now()
            db.session.add(eyepiece)
            db.session.commit()
            flash(gettext('Eyepiece successfully updated'), 'form-success')
            return redirect(url_for('main_equipment.eyepiece_edit', eyepiece_id=eyepiece.id))
    else:
        form.name.data = eyepiece.name
        form.vendor.data = eyepiece.vendor
        form.model.data = eyepiece.model
        form.descr.data = eyepiece.descr
        form.focal_length_mm.data = eyepiece.focal_length_mm
        form.fov_deg.data = eyepiece.fov_deg
        form.diameter_inch.data = eyepiece.diameter_inch
        form.is_active.data = eyepiece.is_active

    return render_template('main/equipment/eyepiece_edit.html', form=form, eyepiece=eyepiece, is_new=False)


@main_equipment.route('/eyepiece/<int:eyepiece_id>/delete')
@login_required
def eyepiece_delete(eyepiece_id):
    """Request deletion of eyepiece."""
    eyepiece = Eyepiece.query.filter_by(id=eyepiece_id, is_deleted=False).first()
    if eyepiece is None:
        abort(404)
    if not _is_eyepiece_editable(eyepiece):
        abort(404)
    eyepiece.is_deleted = True
    db.session.add(eyepiece)
    db.session.commit()
    flash(gettext('Eyepiece was deleted'), 'form-success')
    return redirect(url_for('main_equipment.eyepieces'))


@main_equipment.route('/filters', methods=['GET', 'POST'])
@login_required
def filters():
    filters = Filter.query.filter_by(user_id=current_user.id, is_deleted=False).all()
    return render_template('main/equipment/filters.html', filters=filters)


@main_equipment.route('/filter/<int:filter_id>', methods=['GET'])
@main_equipment.route('/filter/<int:filter_id>/info', methods=['GET'])
@login_required
def filter_info(filter_id):
    """View a filter info."""
    filter = Filter.query.filter_by(id=filter_id, is_deleted=False).first()
    if filter is None:
        abort(404)
    if filter.user_id != current_user.id:
        abort(404)
    return render_template('main/equipment/filter_info.html', filter=filter, editable=_is_filter_editable(filter))


@main_equipment.route('/new-filter', methods=['GET', 'POST'])
@login_required
def new_filter():
    """New filter"""
    form = FilterNewForm()
    if request.method == 'POST' and form.validate_on_submit():
        filter = Filter(
            name=form.name.data,
            vendor=form.vendor.data,
            model=form.model.data,
            descr=form.descr.data,
            filter_type=form.filter_type.data,
            diameter_inch=form.diameter_inch.data,
            is_active=True,
            is_deleted=False,
            user_id=current_user.id,
            create_by=current_user.id,
            update_by=current_user.id,
            create_date=datetime.now(),
            update_date=datetime.now()
        )
        db.session.add(filter)
        db.session.commit()
        flash(gettext('Filter successfully created'), 'form-success')
        return redirect(url_for('main_equipment.filter_edit', filter_id=filter.id))
    return render_template('main/equipment/filter_edit.html', form=form, is_new=True)


@main_equipment.route('/filter/<int:filter_id>/edit', methods=['GET', 'POST'])
@login_required
def filter_edit(filter_id):
    """Update filter"""
    filter = Filter.query.filter_by(id=filter_id, is_deleted=False).first()
    if filter is None:
        abort(404)
    if not _is_filter_editable(filter):
        abort(404)
    form = FilterEditForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            filter.name = form.name.data
            filter.vendor = form.vendor.data
            filter.model = form.model.data
            filter.descr = form.descr.data
            filter.filter_type = form.filter_type.data
            filter.diameter_inch = form.diameter_inch.data
            filter.is_active = form.is_active.data
            filter.is_deleted = False
            filter.update_by = current_user.id
            filter.update_date = datetime.now()
            db.session.add(filter)
            db.session.commit()
            flash(gettext('Filter successfully updated'), 'form-success')
            return redirect(url_for('main_equipment.filter_edit', filter_id=filter.id))
    else:
        form.name.data = filter.name
        form.vendor.data = filter.vendor
        form.model.data = filter.model
        form.descr.data = filter.descr
        form.filter_type.data = filter.filter_type
        form.diameter_inch.data = filter.diameter_inch
        form.is_active.data = filter.is_active

    return render_template('main/equipment/filter_edit.html', form=form, filter=filter, is_new=False)


@main_equipment.route('/filter/<int:filter_id>/delete')
@login_required
def filter_delete(filter_id):
    """Request deletion of filter."""
    filter = Filter.query.filter_by(id=filter_id, is_deleted=False).first()
    if filter is None:
        abort(404)
    if not _is_filter_editable(filter):
        abort(404)
    filter.is_deleted = True
    db.session.add(filter)
    db.session.commit()
    flash(gettext('Filter was deleted'), 'form-success')
    return redirect(url_for('main_equipment.filters'))


@main_equipment.route('/lenses', methods=['GET', 'POST'])
@login_required
def lenses():
    lenses = Lens.query.filter_by(user_id=current_user.id, is_deleted=False).all()
    return render_template('main/equipment/lenses.html', lenses=lenses)


@main_equipment.route('/lens/<int:lens_id>', methods=['GET'])
@main_equipment.route('/lens/<int:lens_id>/info', methods=['GET'])
@login_required
def lens_info(lens_id):
    """View a lens info."""
    lens = Lens.query.filter_by(id=lens_id, is_deleted=False).first()
    if lens is None:
        abort(404)
    if lens.user_id != current_user.id:
        abort(404)
    return render_template('main/equipment/lens_info.html', lens=lens, editable=_is_lens_editable(lens))


@main_equipment.route('/new-lens', methods=['GET', 'POST'])
@login_required
def new_lens():
    """New lens"""
    form = LensNewForm()
    if request.method == 'POST' and form.validate_on_submit():
        lens = Lens(
            name=form.name.data,
            vendor=form.vendor.data,
            model=form.model.data,
            descr=form.descr.data,
            lens_type=form.lens_type.data,
            magnification=form.magnification.data,
            diameter_inch=form.diameter_inch.data,
            is_active=True,
            is_deleted=False,
            user_id=current_user.id,
            create_by=current_user.id,
            update_by=current_user.id,
            create_date=datetime.now(),
            update_date=datetime.now()
        )
        db.session.add(lens)
        db.session.commit()
        flash(gettext('Lens successfully created'), 'form-success')
        return redirect(url_for('main_equipment.lens_edit', lens_id=lens.id))
    return render_template('main/equipment/lens_edit.html', form=form, is_new=True)


@main_equipment.route('/lens/<int:lens_id>/edit', methods=['GET', 'POST'])
@login_required
def lens_edit(lens_id):
    """Update lens"""
    lens = Lens.query.filter_by(id=lens_id, is_deleted=False).first()
    if lens is None:
        abort(404)
    if not _is_lens_editable(lens):
        abort(404)
    form = LensEditForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            lens.name = form.name.data
            lens.vendor = form.vendor.data
            lens.model = form.model.data
            lens.descr = form.descr.data
            lens.lens_type = form.lens_type.data
            lens.magnification = form.magnification.data
            lens.diameter_inch = form.diameter_inch.data
            lens.is_active = form.is_active.data
            lens.is_deleted = False
            lens.update_by = current_user.id
            lens.update_date = datetime.now()
            db.session.add(lens)
            db.session.commit()
            flash(gettext('Lens successfully updated'), 'form-success')
            return redirect(url_for('main_equipment.lens_edit', lens_id=lens.id))
    else:
        form.name.data = lens.name
        form.vendor.data = lens.vendor
        form.model.data = lens.model
        form.descr.data = lens.descr
        form.lens_type.data = lens.lens_type
        form.magnification.data = lens.magnification
        form.diameter_inch.data = lens.diameter_inch
        form.is_active.data = lens.is_active

    return render_template('main/equipment/lens_edit.html', form=form, lens=lens, is_new=False)


@main_equipment.route('/lens/<int:lens_id>/delete')
@login_required
def lens_delete(lens_id):
    """Request deletion of lens."""
    lens = Lens.query.filter_by(id=lens_id, is_deleted=False).first()
    if lens is None:
        abort(404)
    if not _is_lens_editable(lens):
        abort(404)
    lens.is_deleted = True
    db.session.add(lens)
    db.session.commit()
    flash(gettext('Lens was deleted'), 'form-success')
    return redirect(url_for('main_equipment.lenses'))


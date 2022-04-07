import math
from datetime import datetime
from sqlalchemy import and_, or_, not_

from flask_babel import lazy_gettext

from app import db

from app.commons.coordinates import parse_latlon
from app.commons.dso_utils import normalize_dso_name_ext, denormalize_dso_name
from flask_login import current_user

from app.models import (
    Location,
    ObservingSession,
    Observation,
    DeepskyObject,
    User,
    Telescope,
    Eyepiece,
    Lens,
    Filter,
    TelescopeType,
    FilterType,
    Seeing,
)

from app.commons.openastronomylog import parse, filterKind, OalfixedMagnificationOpticsType, OalscopeType, angleUnit


def import_observations(user, import_user, import_history_rec_id, file):
    log_warn = []
    log_error = []

    oal_observations = parse(file, silence=True)

    # Locations
    oal_sites = oal_observations.get_sites()
    found_locations = {}
    add_hoc_locations = {}
    if oal_sites and oal_sites.get_site():
        for oal_site in oal_sites.get_site():
            location = None
            if oal_site.get_name():
                location = Location.query.filter_by(name=oal_site.get_name()).first()
            if location is None:
                add_hoc_locations[oal_site.name] = (oal_site.get_latitude(), oal_site.get_longitude())
                log_warn.append(lazy_gettext('OAL Location "{}" not found').format(oal_site.get_name()))
            else:
                found_locations[oal_site.get_id()] = location

    # Scopes
    found_telescopes = {}
    oal_scopes = oal_observations.get_scopes()
    if oal_scopes:
        for oal_scope in oal_scopes.get_scope():
            model = oal_scope.get_model()
            telescope_type = _get_telescope_type_from_oal_scope_type(oal_scope.get_type())
            vendor = oal_scope.get_vendor()
            aperture_mm = oal_scope.get_aperture()

            focal_length_mm = None
            fixed_magnification = None
            if isinstance(oal_scope, OalscopeType):
                focal_length_mm = oal_scope.get_focalLength()
            if isinstance(oal_scope, OalfixedMagnificationOpticsType):
                fixed_magnification = oal_scope.get_magnification()

            telescope_query = Telescope.query.filter_by(user_id=current_user.id)
            if model:
                telescope_query = telescope_query.filter_by(model=model)
            if telescope_type:
                telescope_query = telescope_query.filter_by(telescope_type=telescope_type)
            if vendor:
                telescope_query = telescope_query.filter_by(vendor=vendor)
            if aperture_mm:
                telescope_query = telescope_query.filter_by(aperture_mm=aperture_mm)
            if focal_length_mm:
                telescope_query = telescope_query.filter_by(focal_length_mm=focal_length_mm)
            if fixed_magnification:
                telescope_query = telescope_query.filter_by(fixed_magnification=fixed_magnification)
            telescope = telescope_query.first()
            if not telescope:
                telescope = Telescope(
                    name=oal_scope.get_id(),
                    vendor=vendor,
                    model=model,
                    descr='',
                    aperture_mm=aperture_mm,
                    focal_length_mm=focal_length_mm,
                    fixed_magnification=fixed_magnification,
                    telescope_type=telescope_type,
                    is_default=False,
                    is_active=True,
                    is_deleted=False,
                    user_id=current_user.id,
                    create_by=current_user.id,
                    update_by=current_user.id,
                    create_date=datetime.now(),
                    update_date=datetime.now()
                )
                db.session.add(telescope)
            found_telescopes[oal_scope.get_id()] = telescope

    # Eyepieces
    found_eyepieces = {}
    oal_eyepieces = oal_observations.get_eyepieces()
    if oal_eyepieces:
        for oal_eyepiece in oal_eyepieces.get_eyepiece():
            model = oal_eyepiece.get_model()
            vendor = oal_eyepiece.get_vendor()
            focal_length_mm = oal_eyepiece.get_focalLength()
            fov_deg = _get_angle_from_oal_angle(oal_eyepiece.get_apparentFOV())

            eyepiece_query = Eyepiece.query.filter_by(user_id=current_user.id)
            if model:
                eyepiece_query = eyepiece_query.filter_by(model=model)
            if vendor:
                eyepiece_query = eyepiece_query.filter_by(vendor=vendor)
            if focal_length_mm:
                eyepiece_query = eyepiece_query.filter_by(focal_length_mm=focal_length_mm)
            if fov_deg:
                eyepiece_query = eyepiece_query.filter_by(fov_deg=fov_deg)
            eyepiece = eyepiece_query.first()
            if not eyepiece:
                eyepiece = Eyepiece(
                    name=oal_eyepiece.get_id(),
                    vendor=vendor,
                    model=model,
                    descr='',
                    focal_length_mm=focal_length_mm,
                    fov_deg=fov_deg,
                    diameter_inch=None,
                    is_active=True,
                    is_deleted=False,
                    user_id=current_user.id,
                    create_by=current_user.id,
                    update_by=current_user.id,
                    create_date=datetime.now(),
                    update_date=datetime.now()
                )
                db.session.add(eyepiece)
            found_eyepieces[oal_eyepiece.get_id()] = eyepiece

    # Filters
    found_filters = {}
    oal_filters = oal_observations.get_filters()
    if oal_filters:
        for oal_filter in oal_filters.get_filter():
            model = oal_filter.get_model()
            vendor = oal_filter.get_vendor()
            filter_type = _get_filter_type_from_oal_filter_kind(oal_filter.get_type())

            filter_query = Filter.query.filter_by(user_id=current_user.id)
            if model:
                filter_query = filter_query.filter_by(model=model)
            if vendor:
                filter_query = filter_query.filter_by(vendor=vendor)
            if filter_type:
                filter_query = filter_query.filter_by(filter_type=filter_type)

            filter = filter_query.first()
            if not filter:
                filter = Filter(
                    name=oal_filter.get_id(),
                    vendor=vendor,
                    model=model,
                    descr='',
                    filter_type=filter_type,
                    diameter_inch=None,
                    is_active=True,
                    is_deleted=False,
                    user_id=current_user.id,
                    create_by=current_user.id,
                    update_by=current_user.id,
                    create_date=datetime.now(),
                    update_date=datetime.now()
                )
                db.session.add(filter)
            found_filters[oal_filter.get_id()] = filter

    # Lenses
    found_lenses = {}
    oal_lenses = oal_observations.get_lenses()
    if oal_lenses:
        for oal_lens in oal_lenses.get_lens():
            model = oal_lens.get_model()
            vendor = oal_lens.get_vendor()
            factor = oal_lens.get_factor()

            lens_query = Lens.query.filter_by(user_id=current_user.id)
            if model:
                lens_query = lens_query.filter_by(model=model)
            if vendor:
                lens_query = lens_query.filter_by(vendor=vendor)
            if factor:
                lens_query = lens_query.filter_by(magnification=factor)

            lens = lens_query.first()
            if not lens:
                lens = Lens(
                    name=oal_lens.get_id(),
                    vendor=vendor,
                    model=model,
                    descr='',
                    lens_type=None,
                    magnification=factor,
                    diameter_inch=None,
                    is_active=True,
                    is_deleted=False,
                    user_id=current_user.id,
                    create_by=current_user.id,
                    update_by=current_user.id,
                    create_date=datetime.now(),
                    update_date=datetime.now()
                )
                db.session.add(lens)
            found_lenses[oal_lens.get_id()] = lens

    # Observations
    oal_sessions = oal_observations.get_sessions()
    found_observing_sessions = {}
    new_observing_sessions = {}
    if oal_sessions and oal_sessions.get_session():
        for oal_session in oal_sessions.get_session():
            begin = oal_session.get_begin()
            end = oal_session.get_end()
            if begin and not end:
                end = begin
            if end and not begin:
                begin = end

            observing_session = ObservingSession.query.filter(ObservingSession.user_id == user.id) \
                .filter(and_(ObservingSession.date_to >= begin, ObservingSession.date_from <= end)) \
                .first()
            if observing_session and observing_session.update_date != observing_session.create_date:
                found_observing_sessions[oal_session.get_id()] = observing_session
            else:
                location = found_locations.get(oal_session.get_site())
                location_position = add_hoc_locations.get(oal_session.get_site())
                if location:
                    title = location.name + ' ' + begin.strftime('%d.%m.%Y')
                elif begin:
                    title = begin.strftime('%d.%m.%Y')
                else:
                    title = oal_session.get_id()

                now = datetime.now()
                if not observing_session:
                    observing_session = ObservingSession(
                        user_id=user.id,
                        title=title,
                        date_from=begin,
                        date_to=end,
                        location_id=location.id if location else None,
                        location_position=location_position,
                        sqm=None,
                        faintest_star=None,
                        seeing=None,
                        transparency=None,
                        rating=None,
                        weather=oal_session.get_weather(),
                        equipment=oal_session.get_equipment(),
                        notes=oal_session.get_comments(),
                        import_history_rec_id=import_history_rec_id,
                        create_by=import_user.id,
                        update_by=import_user.id,
                        create_date=now,
                        update_date=now
                    )
                    new_observing_sessions[oal_session.get_id()] = observing_session
                else:
                    observing_session.title = title
                    observing_session.date_from = begin
                    observing_session.date_to = end
                    observing_session.location_id = location.id if location else None
                    observing_session.location_position = location_position
                    observing_session.weather = oal_session.get_weather()
                    observing_session.equipment = oal_session.get_equipment()
                    observing_session.notes = oal_session.get_comments()
                    observing_session.import_history_rec_id = import_history_rec_id
                    observing_session.update_by = import_user.id
                    observing_session.create_date = now
                    observing_session.update_date = now
                    found_observing_sessions[oal_session.get_id()] = observing_session

                db.session.add(observing_session)

    # Targets
    oal_targets = oal_observations.get_targets()
    found_dsos = {}
    not_found_dsos = set()
    if oal_targets and oal_targets.get_target():
        for target in oal_targets.get_target():
            normalized_name = normalize_dso_name_ext(denormalize_dso_name(target.get_name()))
            dso = DeepskyObject.query.filter_by(name=normalized_name).first()
            if dso:
                found_dsos[target.get_id()] = dso
            else:
                not_found_dsos.add(target.get_id())
                log_error.append(lazy_gettext('DSO "{}" not found').format(target.get_name()))

    oal_observations = oal_observations.get_observation()

    for oal_observation in oal_observations:
        observing_session = found_observing_sessions.get(oal_observation.get_session())
        is_session_new = False
        if not observing_session:
            observing_session = new_observing_sessions.get(oal_observation.get_session())
            is_session_new = True

        observed_dso = found_dsos.get(oal_observation.get_target())
        if not observed_dso:
            if oal_observation.get_target() not in not_found_dsos:
                log_error.append(lazy_gettext('OAL Target "{}" not found.').format(oal_observation.get_target()))
            continue

        observation = None
        if not is_session_new:
            for obs in observing_session.observations:
                if obs.deepsky_objects:
                    for dso in obs.deepsky_objects:
                        if dso.name == observed_dso.name:
                            observation = obs
                            break
                    if observation:
                        break

        if observation and observation.create_date != observation.update_date:
            log_warn.append(lazy_gettext('OAL Observation "{}" for session "{}" already exists and was modified by user.').format(oal_observation.get_id(), oal_observation.get_session()))
        else:
            notes = ''
            if oal_observation.get_result():
                notes = oal_observation.get_result()[0].get_description()

            location = found_locations.get(oal_observation.get_site())
            location_position = add_hoc_locations.get(oal_observation.get_site())

            if observing_session:
                if location and observing_session.location_id == location.id:
                    location = None
                if location_position and observing_session.location_position == location_position:
                    location_position = None

            telescope = found_telescopes.get(oal_observation.get_scope()) if oal_observation.get_scope() else None
            eyepiece = found_eyepieces.get(oal_observation.get_eyepiece()) if oal_observation.get_eyepiece() else None
            filter = found_filters.get(oal_observation.get_filter()) if oal_observation.get_filter() else None

            oal_lens = oal_observation.get_lens()
            lens = found_lenses.get(oal_observation.get_lens()) if oal_observation.get_lens() else None

            now = datetime.now()
            if not observation:
                observation = Observation(
                    user_id=current_user.id,
                    observing_session_id=observing_session.id if observing_session else None,
                    location_id=location.id if location else None,
                    location_position=location_position,
                    date_from=oal_observation.get_begin(),
                    date_to=oal_observation.get_end(),
                    sqm=_get_sqm_from_oal_surface_brightness(oal_observation.get_sky_quality()),
                    faintest_star=oal_observation.get_faintestStar(),
                    seeing=_get_seeing_from_oal_seeing(oal_observation.get_seeing()),
                    telescope_id=telescope.id if telescope else None,
                    eyepiece_id=eyepiece.id if eyepiece else None,
                    filter_id=filter.id if filter else None,
                    lens_id=lens.id if lens else None,
                    notes=notes,
                    import_history_rec_id=import_history_rec_id,
                    create_by=current_user.id,
                    update_by=current_user.id,
                    create_date=now,
                    update_date=now,
                )
                db.session.add(observation)
                observation.deepsky_objects.append(observed_dso)
                if observing_session:
                    observing_session.observations.append(observation)
            else:
                observation.observing_session_id = observing_session.id if observing_session else None
                observation.location_id = location.id if location else None
                observation.location_position = location_position
                observation.date_from = oal_observation.get_begin()
                observation.date_to = oal_observation.get_end()
                observation.sqm = _get_sqm_from_oal_surface_brightness(oal_observation.get_sky_quality())
                observation.faintest_star = oal_observation.get_faintestStar()
                observation.seeing = _get_seeing_from_oal_seeing(oal_observation.get_seeing())
                observation.telescope_id = telescope.id if telescope else None
                observation.eyepiece_id = eyepiece.id if eyepiece else None
                observation.filter_id = filter.id if filter else None
                observation.lens_id = lens.id if lens else None
                observation.notes = notes
                observation.import_history_rec_id = import_history_rec_id
                observation.update_by = current_user.id
                observation.create_date = now  # set create date to update date to easy detect user modifications
                observation.update_date = now
                db.session.add(observation)

            if is_session_new and observing_session:
                if not observing_session.sqm and oal_observation.get_sky_quality():
                    observing_session.sqm = _get_sqm_from_oal_surface_brightness(oal_observation.get_sky_quality())
                if not observing_session.faintest_star and oal_observation.get_faintestStar():
                    observing_session.faintest_star = oal_observation.get_faintestStar()
                if not observing_session.seeing and oal_observation.get_seeing():
                    observing_session.seeing = _get_seeing_from_oal_seeing(oal_observation.get_seeing())

    db.session.commit()

    return log_warn, log_error


def _get_seeing_from_oal_seeing(seeing):
    if seeing == 5:
        return Seeing.VERYBAD
    if seeing == 4:
        return Seeing.BAD
    if seeing == 3:
        return Seeing.AVERAGE
    if seeing == 2:
        return Seeing.GOOD
    if seeing == 1:
        return Seeing.EXCELLENT
    return None


def _get_sqm_from_oal_surface_brightness(surf_brightness):
    if surf_brightness:
        return surf_brightness.get_valueOf_()
    return None


def _get_telescope_type_from_oal_scope_type(scope_type):
    if scope_type == 'A':
        return TelescopeType.NAKED_EYE
    if scope_type == 'C':
        return TelescopeType.CASSEGRAIN
    if scope_type == 'B':
        return TelescopeType.BINOCULAR
    if scope_type == 'S':
        return TelescopeType.SCHMIDT_CASSEGRAIN
    if scope_type == 'N':
        return TelescopeType.NEWTON
    if scope_type == 'K':
        return TelescopeType.KUTTER
    if scope_type == 'R':
        return TelescopeType.REFRACTOR
    if scope_type == 'M':
        return TelescopeType.MAKSUTOV
    return TelescopeType.OTHER


def _get_filter_type_from_oal_filter_kind(filter_kind):
    if filter_kind == filterKind.BROADBAND:
        return FilterType.BROAD_BAND
    if filter_kind == filterKind.NARROWBAND:
        return FilterType.NARROW_BAND
    if filter_kind == filterKind.OIII:
        return FilterType.OIII
    if filter_kind == filterKind.HBETA:
        return FilterType.HBETA
    if filter_kind == filterKind.HALPHA:
        return FilterType.HALPHA
    if filter_kind == filterKind.COLOR:
        return FilterType.COLOR
    if filter_kind == filterKind.NEUTRAL:
        return FilterType.NEUTRAL
    if filter_kind == filterKind.CORRECTIVE:
        return FilterType.CORRECTIVE
    if filter_kind == filterKind.SOLAR:
        return FilterType.SOLAR
    if filter_kind == filterKind.OTHER:
        return FilterType.OTHER
    return None


def _get_angle_from_oal_angle(oal_angle):
    if oal_angle:
        value = float(oal_angle.get_valueOf_())
        unit = oal_angle.get_unit()
        if unit == angleUnit.ARCSEC:
            return value / (60.0 * 60.0)
        if unit == angleUnit.ARCMIN:
            return value / 60.0
        if unit == angleUnit.RAD:
            return 180.0 * value / math.pi
        return value
    return None

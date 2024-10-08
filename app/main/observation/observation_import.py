import re
import math
from datetime import datetime
from sqlalchemy import and_, or_, not_

from flask_babel import lazy_gettext

from app import db

from flask_login import current_user

from app.models import (
    Location,
    ObservingSession,
    ObservationTargetType,
    Observation,
    DeepskyObject,
    DoubleStar,
    User,
    Telescope,
    Eyepiece,
    Lens,
    Filter,
    TelescopeType,
    FilterType,
    Seeing,
    dso_observation_association_table,
)

from app.commons.openastronomylog import (
    OaldeepSkyDS,
    OaldeepSkyGC,
    OaldeepSkyOC,
    OaldeepSkyGN,
    OaldeepSkyDN,
    OaldeepSkyPN,
    OaldeepSkyAS,
    OaldeepSkyQS,
    OaldeepSkyCG,
    OalobservationTargetType,
    OaldeepSkyMS,
)

from app.commons.openastronomylog import parse, filterKind, OalfixedMagnificationOpticsType, OalscopeType, angleUnit
from app.commons.dso_utils import normalize_dso_name_ext, denormalize_dso_name, normalize_double_star_name
from app.commons.search_sky_object_utils import search_double_star_strict, search_double_star


def import_observations(user_id, import_user_id, import_history_rec_id, file, imp_observing_session=None):
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
                lat = _get_angle_from_oal_angle(oal_site.get_latitude())
                lon = _get_angle_from_oal_angle(oal_site.get_longitude())
                location = Location(
                    name=oal_site.get_name(),
                    longitude=lon,
                    latitude=lat,
                    country_code=None,
                    descr=None,
                    bortle=None,
                    rating=None,
                    is_public=True,
                    is_for_observation=True,
                    time_zone=None,
                    iau_code=None,
                    import_history_rec_id=import_history_rec_id,
                    user_id=user_id,
                    create_by=import_user_id,
                    update_by=import_user_id,
                    create_date=datetime.now(),
                    update_date=datetime.now()
                )
                db.session.add(location)
                found_locations[oal_site.get_id()] = location
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

            telescope_query = Telescope.query.filter_by(user_id=user_id)
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
                    import_history_rec_id=import_history_rec_id,
                    user_id=user_id,
                    create_by=import_user_id,
                    update_by=import_user_id,
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

            eyepiece_query = Eyepiece.query.filter_by(user_id=user_id)
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
                    import_history_rec_id=import_history_rec_id,
                    user_id=user_id,
                    create_by=import_user_id,
                    update_by=import_user_id,
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

            filter_query = Filter.query.filter_by(user_id=user_id)
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
                    import_history_rec_id=import_history_rec_id,
                    user_id=user_id,
                    create_by=import_user_id,
                    update_by=import_user_id,
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

            lens_query = Lens.query.filter_by(user_id=user_id)
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
                    import_history_rec_id=import_history_rec_id,
                    user_id=user_id,
                    create_by=import_user_id,
                    update_by=import_user_id,
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
        for i, oal_session in enumerate(oal_sessions.get_session()):
            if imp_observing_session and i>0:
                break

            begin = oal_session.get_begin()
            end = oal_session.get_end()
            if begin and not end:
                end = begin
            if end and not begin:
                begin = end

            if imp_observing_session:
                found_observing_sessions[oal_session.get_id()] = imp_observing_session
            else:
                observing_session = ObservingSession.query.filter(ObservingSession.user_id == user_id) \
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
                            user_id=user_id,
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
                            create_by=import_user_id,
                            update_by=import_user_id,
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
                        observing_session.update_by = import_user_id
                        observing_session.create_date = now
                        observing_session.update_date = now
                        found_observing_sessions[oal_session.get_id()] = observing_session

                    db.session.add(observing_session)

    # Targets
    oal_targets = oal_observations.get_targets()
    found_dsos = {}
    found_double_stars = {}
    not_found_targets = set()
    if oal_targets and oal_targets.get_target():
        for target in oal_targets.get_target():
            if isinstance(target, (OaldeepSkyDS, OaldeepSkyMS)):
                double_star = search_double_star(target.get_name())
                if double_star:
                    found_double_stars[target.get_id()] = double_star
                else:
                    not_found_targets.add(target.get_id())
                    log_error.append(lazy_gettext('Double star "{}" not found').format(target.get_name()))
            else:
                normalized_name = normalize_dso_name_ext(denormalize_dso_name(target.get_name()))
                m = re.search(r'^(NGC|IC)\d+([A-Z]|-[1-9])$', normalized_name)
                if m:
                    normalized_name = normalized_name[:m.start(2)].strip()
                dso = DeepskyObject.query.filter_by(name=normalized_name).first()
                if dso:
                    found_dsos[target.get_id()] = dso
                else:
                    not_found_targets.add(target.get_id())
                    log_error.append(lazy_gettext('DSO "{}" not found').format(target.get_name()))

    oal_observations = oal_observations.get_observation()

    addhoc_observing_sessions = {}

    obs_count = 0

    for i, oal_observation in enumerate(oal_observations):
        location = found_locations.get(oal_observation.get_site())
        location_position = add_hoc_locations.get(oal_observation.get_site())

        observing_session = found_observing_sessions.get(oal_observation.get_session())

        if not observing_session and imp_observing_session:
            continue

        is_session_new = False
        if not observing_session:
            observing_session = new_observing_sessions.get(oal_observation.get_session())
            is_session_new = True

        if not observing_session:
            if oal_observation.get_begin():
                observing_session = addhoc_observing_sessions.get(oal_observation.get_begin().date())
                if not observing_session:
                    observing_session = ObservingSession.query.filter(ObservingSession.user_id == user_id) \
                        .filter(ObservingSession.date_from == oal_observation.get_begin())  \
                        .first()
                    if not observing_session:
                        now = datetime.now()
                        observing_session = ObservingSession(
                            user_id=user_id,
                            title=str(oal_observation.get_begin().date()),
                            date_from=oal_observation.get_begin(),
                            date_to=oal_observation.get_end(),
                            location_id=location.id if location else None,
                            location_position=location_position,
                            sqm=_get_sqm_from_oal_surface_brightness(oal_observation.get_sky_quality()),
                            faintest_star=oal_observation.get_faintestStar(),
                            seeing=_get_seeing_from_oal_seeing(oal_observation.get_seeing()),
                            transparency=None,
                            rating=None,
                            weather=None,
                            equipment=None,
                            notes=None,
                            import_history_rec_id=import_history_rec_id,
                            create_by=import_user_id,
                            update_by=import_user_id,
                            create_date=now,
                            update_date=now
                        )
                        db.session.add(observing_session)
                    addhoc_observing_sessions[oal_observation.get_begin().date()] = observing_session
                is_session_new = True

        observed_double_star = found_double_stars.get(oal_observation.get_target())
        observed_dso = found_dsos.get(oal_observation.get_target())

        if not observed_dso and not observed_double_star:
            if oal_observation.get_target() not in not_found_targets:
                log_error.append(lazy_gettext('OAL Target "{}" not found.').format(oal_observation.get_target()))
            continue

        observation = None
        if not is_session_new:
            for obs in observing_session.observations:
                if obs.target_type == ObservationTargetType.DBL_STAR:
                    if observed_double_star and observed_double_star.id == obs.double_star_id:
                        observation = obs
                elif obs.target_type == ObservationTargetType.DSO:
                    if observed_dso:
                        for dso in obs.deepsky_objects:
                            if dso.id == observed_dso.id:
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

            # find out existing observation by date and observed object
            if not observation:
                if observed_double_star:
                    observation = Observation.query.filter_by(user_id=user_id) \
                                                   .filter(Observation.double_star_id == observed_double_star.id) \
                                                   .filter(Observation.date_from == oal_observation.get_begin())
                if observed_dso:
                    observation = Observation.query.filter_by(user_id=user_id) \
                        .join(dso_observation_association_table, isouter=True) \
                        .join(DeepskyObject, isouter=True) \
                        .filter(Observation.date_from == oal_observation.get_begin()) \
                        .filter((Observation.target_type == ObservationTargetType.DSO) &
                                (dso_observation_association_table.c.observation_id == Observation.id) &
                                (dso_observation_association_table.c.dso_id == DeepskyObject.id) &
                                (DeepskyObject.id == observed_dso.id))
                if observation:
                    observation = observation.first()

            now = datetime.now()
            if not observation:
                observation = Observation(
                    user_id=user_id,
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
                    create_by=import_user_id,
                    update_by=import_user_id,
                    create_date=now,
                    update_date=now,
                )
                if observed_double_star:
                    observation.double_star_id = observed_double_star.id
                    observation.target_type = ObservationTargetType.DBL_STAR
                db.session.add(observation)
                if observed_dso:
                    observation.deepsky_objects.append(observed_dso)
                    observation.target_type = ObservationTargetType.DSO
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
                observation.update_by = import_user_id
                observation.create_date = now  # set create date to update date to easy detect user modifications
                observation.update_date = now
                db.session.add(observation)

            obs_count += 1

            if obs_count % 500 == 0:
                print('Committing {} of {}'.format(obs_count, len(oal_observations)), flush=True)
                db.session.commit()

            if is_session_new and observing_session:
                if not observing_session.sqm and oal_observation.get_sky_quality():
                    observing_session.sqm = _get_sqm_from_oal_surface_brightness(oal_observation.get_sky_quality())
                if not observing_session.faintest_star and oal_observation.get_faintestStar():
                    observing_session.faintest_star = oal_observation.get_faintestStar()
                if not observing_session.seeing and oal_observation.get_seeing():
                    observing_session.seeing = _get_seeing_from_oal_seeing(oal_observation.get_seeing())

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()

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


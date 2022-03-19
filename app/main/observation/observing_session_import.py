from datetime import datetime
from sqlalchemy import and_, or_

from flask_babel import lazy_gettext

from app import db

from app.commons.coordinates import parse_latlon
from app.commons.dso_utils import normalize_dso_name_ext

from app.models import Location, ObservingSession, Observation, DeepskyObject, User
from app.models import Telescope, Eyepiece, Lens, Filter, TelescopeType, FilterType, Seeing
from app.commons.openastronomylog import parse


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
                                                .filter(or_(and_(ObservingSession.date_from >= begin, ObservingSession.date_from <= end),
                                                            and_(ObservingSession.date_to >= begin, ObservingSession.date_from <= end))).first()
            if observing_session:
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
                    create_date=datetime.now(),
                    update_date=datetime.now()
                )
                new_observing_sessions[oal_session.get_id()] = observing_session
                db.session.add(observing_session)

    # Targets
    oal_targets = oal_observations.get_targets()
    found_dsos = {}
    if oal_targets and oal_targets.get_target():
        for target in oal_targets.get_target():
            normalized_name = normalize_dso_name_ext(target.get_name())
            dso = DeepskyObject.query.filter_by(name=normalized_name).first()
            if dso:
                found_dsos[target.get_id()] = dso
            else:
                log_error.append(lazy_gettext('DSO "{}" not found').format(target.get_name()))

# #-------------------------
#     # Scopes
#     oal_scopes = OalscopesType()
#     telescopes = Telescope.query.filter_by(user_id=user.id, is_deleted=False).all()
#     for telescope in telescopes:
#         oal_scope = OalscopeType(id='opt_{}'.format(telescope.id), model=telescope.model,
#                                  type=_get_oal_telescope_type(telescope.telescope_type), vendor=telescope.vendor, aperture=telescope.aperture_mm,
#                                  lightGrasp=telescope.light_grasp, orientation=None, focalLength=telescope.focal_length_mm)
#         oal_scopes.add_scope(oal_scope)
#
#     # Eyepieces
#     oal_eyepieces = OaleyepiecesType()
#     eyepieces = Eyepiece.query.filter_by(user_id=user.id, is_deleted=False).all()
#     for eyepiece in eyepieces:
#         oal_eyepiece = OaleyepieceType(id='ep_{}'.format(eyepiece.id), model=eyepiece.model, vendor=eyepiece.vendor, focalLength=eyepiece.focal_length_mm,
#                                        apparentFOV=_get_oal_non_neg_angle(angleUnit.DEG, eyepiece.fov_deg))
#         oal_eyepieces.add_eyepiece(oal_eyepiece)
#
#     # Lenses
#     oal_lenses = OallensesType()
#     lenses = Lens.query.filter_by(user_id=user.id, is_deleted=False).all()
#     for lens in lenses:
#         oal_lens = OallensType('le_{}'.format(lens.id), model=lens.model, vendor=lens.vendor, factor=lens.magnification)
#         oal_lenses.add_lens(oal_lens)
#
#     # Filters
#     oal_filters = OalfiltersType()
#     filters = Filter.query.filter_by(user_id=user.id, is_deleted=False).all()
#     for filter in filters:
#         oal_filter = OalfilterType('flt_{}'.format(filter.id), model=filter.model, vendor=filter.vendor,
#                                    type=_get_oal_filter_type(filter.filter_type), color=None,
#                                    wratten=None, schott=None)
#         oal_filters.add_filter(oal_filter)

    oal_observations = oal_observations.get_observation()

    for oal_observation in oal_observations:
        observing_session = found_observing_sessions.get(oal_observation.get_session())
        is_session_new = False
        if not observing_session:
            observing_session = new_observing_sessions.get(oal_observation.get_session())
            is_session_new = True

        if not observing_session:
            log_error.append(lazy_gettext('OAL Session "{}" not found.').format(oal_observation.get_id()))
            continue

        observed_dso = found_dsos.get(oal_observation.get_target())
        if not observed_dso:
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

        if observation:
            log_warn.append(lazy_gettext('OAL Observation "{}" for session "{}" already exists').format(oal_observation.get_id(), oal_observation.get_session()))
        else:
            notes = ''
            if oal_observation.get_result():
                notes = oal_observation.get_result()[0].get_description()
            observation = Observation(
                observing_session_id=observing_session.id,
                date_from=oal_observation.get_begin(),
                date_to=oal_observation.get_end(),
                notes=notes,
                import_history_rec_id=import_history_rec_id,
            )
            observation.deepsky_objects.append(observed_dso)
            if is_session_new:
                if not observing_session.sqm and oal_observation.get_sky_quality():
                    observing_session.sqm = oal_observation.get_sky_quality().get_valueOf_()
                if not observing_session.faintest_star and oal_observation.get_faintestStar():
                    observing_session.faintest_star = oal_observation.get_faintestStar()
                if not observing_session.seeing and oal_observation.get_seeing():
                    observing_session.seeing = _get_seeing_from_oal_seeing(oal_observation.get_seeing())

            observing_session.observations.append(observation)

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

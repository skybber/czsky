from datetime import datetime
from sqlalchemy import and_, or_

from flask_babel import lazy_gettext

from app.commons.coordinates import parse_latlon
from app.commons import normalize_dso_name

from app.models import Location, Observation, DeepskyObject, User
from app.models import Telescope, Eyepiece, Lens, Filter, TelescopeType, FilterType, Seeing

from app.commons.openastronomylog import angleUnit, OalangleType, OalnonNegativeAngleType, OalequPosType, OalsurfaceBrightnessType
from app.commons.openastronomylog import OalobserverType, OalobserversType
from app.commons.openastronomylog import OalsiteType, OalsitesType
from app.commons.openastronomylog import Oalobservations, OalobservationType
from app.commons.openastronomylog import OalsessionsType, OalsessionType
from app.commons.openastronomylog import OaltargetsType, OalobservationTargetType
from app.commons.openastronomylog import OalscopesType, OalscopeType
from app.commons.openastronomylog import OaleyepieceType, OaleyepiecesType
from app.commons.openastronomylog import OallensesType, OallensType
from app.commons.openastronomylog import OalfiltersType, OalfilterType
from app.commons.openastronomylog import OalfindingsType


def import_observations(user, import_user, oal_observations):
    log_error = []

    # Locations
    oal_sites = oal_observations.get_sites()
    found_locations = {}
    add_hoc_locations = {}
    for oal_site in oal_sites:
        location = None
        if oal_site.get_name():
            location = Location.query.find_by(name=oal_site.get_name()).first()
        if location is None:
            add_hoc_locations[oal_site.name] = (oal_site.get_latitude(), oal_site.get_longitude())
        else:
            found_locations[oal_site.get_id()] = location

    # Observations
    oal_sessions = oal_observations.get_sessions()
    found_observations = {}
    new_observations = {}
    for oal_session in oal_sessions:
        begin = oal_session.get_begin()
        end = oal_session.get_end()
        if begin and not end:
            end = begin
        if end and not begin:
            begin = end

        observation = Observation.query.filter(user_id=user.id)\
                                       .filter(or_(and_(Observation.date_from >= begin, Observation.date_from <= end),
                                                   and_(Observation.date_to >= begin, Observation.date_from <= end))).first()
        if observation:
            found_observations[oal_session.get_id()] = observation
        else:
            location = found_locations.get(oal_session.get_site())
            location_position = add_hoc_locations.get(oal_session.get_site())
            observation = Observation(
                user_id=user.id,
                title=oal_session.id(),
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
                create_by=import_user.id,
                update_by=import_user.id,
                create_date=datetime.now(),
                update_date=datetime.now()
            )
            new_observations[oal_session.get_id()] = observation

    # Targets
    oal_targets = oal_observations.get_targets()
    found_dsos = {}
    for target in oal_targets:
        normalized_name = normalize_dso_name(target.get_name())
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

    oal_observations = oal_observations.get_targets()
    oal_observation_ar = []

    for observation in observations:
        for obs_item in observation.observation_items:
            for dso in obs_item.deepsky_objects:
                obs_result = OalfindingsType(lang=user.lang_code, description=obs_item.notes)
                oal_sky_quality = OalsurfaceBrightnessType(unit='mags-per-squarearcsec', valueOf_=observation.sqm) if observation.sqm else None
                oal_obs = OalobservationType(id='obs_{}'.format(obs_item.id), observer='usr_{}'.format(user.id), site='site_{}'.format(observation.location_id),
                                             session='se_{}'.format(observation.id), target='_{}'.format(dso.id), begin=obs_item.date_time, end=None,
                                             faintestStar=observation.faintest_star, sky_quality=oal_sky_quality, seeing=_get_oal_seeing(observation.seeing),
                                             scope='opt_'.format(obs_item.telescope_id) if obs_item.telescope_id else None,
                                             accessories=obs_item.accessories,
                                             eyepiece='ep_'.format(obs_item.eyepiece_id) if obs_item.eyepiece_id else None,
                                             lenses='le_'.format(obs_item.lens_id) if obs_item.lens_id else None,
                                             filter='flt_'.format(obs_item.filter_id) if obs_item.filter_id else None,
                                             magnification=obs_item.magnification,
                                             imager=None, result=[obs_result], image=None
                                             )
                oal_observation_ar.append(oal_obs)

    oal_observations = Oalobservations(observers=oal_observers, sites=oal_sites, sessions=oal_sessions, targets=oal_targets,
                                       scopes=oal_scopes, eyepieces=oal_eyepieces, lenses=oal_lenses, filters=oal_filters,
                                       images=None, observation=oal_observation_ar)

    return oal_observations


def _get_oal_angle(unit, angle):
    return OalangleType(unit=unit, valueOf_=angle)


def _get_oal_non_neg_angle(unit, angle):
    return OalnonNegativeAngleType(unit=unit, valueOf_=angle)


def _get_oal_equ_pos(ra, dec):
    return OalequPosType(ra=_get_oal_non_neg_angle(angleUnit.RAD, ra), dec=_get_oal_angle(angleUnit.RAD, dec))


def _get_oal_telescope_type(telescope_type):
    if telescope_type == TelescopeType.BINOCULAR:
        return 'B'
    if telescope_type == TelescopeType.NEWTON:
        return 'N'
    if telescope_type == TelescopeType.REFRACTOR:
        return 'R'
    if telescope_type == TelescopeType.CASSEGRAIN:
        return 'C'
    if telescope_type == TelescopeType.SCHMIDT_CASSEGRAIN:
        return 'S'
    if telescope_type == TelescopeType.MAKSUTOV:
        return 'M'
    if telescope_type == TelescopeType.KUTTER:
        return 'K'
    if telescope_type == TelescopeType.OTHER:
        return None
    return None


def _get_oal_filter_type(filter_type):
    if filter_type == FilterType.UHC:
        return 'narrow band'
    if filter_type == FilterType.OIII:
        return 'O-III'
    if filter_type == FilterType.CLS:
        return 'broad band'
    if filter_type == FilterType.HBETA:
        return 'H-beta'
    if filter_type == FilterType.HALPHA:
        return 'H-alpha'
    if filter_type == FilterType.COLOR:
        return 'color'
    if filter_type == FilterType.NEUTRAL:
        return 'neutral'
    if filter_type == FilterType.CORRECTIVE:
        return 'corrective'
    if filter_type == FilterType.SOLAR:
        return 'solar'
    if filter_type == FilterType.BROAD_BAND:
        return 'broad band'
    if filter_type == FilterType.NARROW_BAND:
        return 'narrow band'
    if filter_type == FilterType.OTHER:
        return 'other'
    return None


def _get_oal_seeing(seeing):
    if seeing == Seeing.TERRIBLE:
        return 5
    if seeing == Seeing.VERYBAD:
        return 5
    if seeing == Seeing.BAD:
        return 4
    if seeing == Seeing.AVERAGE:
        return 3
    if seeing == Seeing.GOOD:
        return 2
    if seeing == Seeing.EXCELLENT:
        return 1
    return None

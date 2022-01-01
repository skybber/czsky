from app.commons.coordinates import parse_lonlat

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


def create_oal_observations(user, observations):
    # Observers
    oal_observer = OalobserverType(id='usr_{}'.format(user.id),
                                   name=user.get_first_name(),
                                   surname=user.get_last_name(),
                                   contact=[user.email],
                                   )
    oal_observers = OalobserversType(observer=[oal_observer])

    # Sites
    oal_sites = OalsitesType()
    for observation in observations:
        location = observation.location
        if location:
            oal_site = OalsiteType(id='site_{}'.format(location.id), name=location.name,
                                   longitude=_get_oal_angle(angleUnit.DEG, location.longitude), latitude=_get_oal_angle(angleUnit.DEG, location.latitude),
                                   elevation=(location.elevation if location.elevation and location.elevation != 0 else None),
                                   timezone=location.timezone, code=location.iau_code)
        else:
            lon, lat = parse_lonlat(observation.location_position)
            oal_site = OalsiteType(id='site_adhoc_{}'.format(observation.id), name=None,
                                   longitude=_get_oal_angle(angleUnit.DEG, lon), latitude=_get_oal_angle(angleUnit.DEG, lat),
                                   elevation=None, timezone=None, code=None)
        oal_sites.add_site(oal_site)

    # Sessions
    oal_sessions = OalsessionsType()
    for observation in observations:
        if observation.location:
            site_ref = 'site_{}'.format(observation.location.id)
        else:
            site_ref = 'site_adhoc_{}'.format(observation.id)
        oal_session = OalsessionType(id='se_{}'.format(observation.id), lang=user.lang_code,
                                     begin=observation.date_from, end=observation.date_to, site=site_ref,
                                     coObserver=None, weather=observation.weather, equipment=observation.equipment,
                                     comments=observation.notes, image=None
                                     )
        oal_sessions.add_session(oal_session)

    # Targets
    oal_targets = OaltargetsType()
    for observation in observations:
        for obs_item in observation.observation_items:
            for dso in obs_item.deepsky_objects:
                oal_obs_target = OalobservationTargetType(id='_{}'.format(dso.id), datasource='CzSky', observer=None,
                                                          name=dso.name, alias=None, position=_get_oal_equ_pos(dso.ra, dso.dec),
                                                          constellation=dso.get_constellation_iau_code(),
                                                          notes=None, extensiontype_=None)
                oal_targets.add_target(oal_obs_target)

    # Scopes
    oal_scopes = OalscopesType()
    telescopes = Telescope.query.filter_by(user_id=user.id, is_deleted=False).all()
    for telescope in telescopes:
        oal_scope = OalscopeType(id='opt_{}'.format(telescope.id), model=telescope.model,
                                 type=_get_oal_telescope_type(telescope.telescope_type), vendor=telescope.vendor, aperture=telescope.aperture_mm,
                                 lightGrasp=telescope.light_grasp, orientation=None, focalLength=telescope.focal_length_mm)
        oal_scopes.add_scope(oal_scope)

    # Eyepieces
    oal_eyepieces = OaleyepiecesType()
    eyepieces = Eyepiece.query.filter_by(user_id=user.id, is_deleted=False).all()
    for eyepiece in eyepieces:
        oal_eyepiece = OaleyepieceType(id='ep_{}'.format(eyepiece.id), model=eyepiece.model, vendor=eyepiece.vendor, focalLength=eyepiece.focal_length_mm,
                                       apparentFOV=_get_oal_non_neg_angle(angleUnit.DEG, eyepiece.fov_deg))
        oal_eyepieces.add_eyepiece(oal_eyepiece)

    # Lenses
    oal_lenses = OallensesType()
    lenses = Lens.query.filter_by(user_id=user.id, is_deleted=False).all()
    for lens in lenses:
        oal_lens = OallensType('le_{}'.format(lens.id), model=lens.model, vendor=lens.vendor, factor=lens.magnification)
        oal_lenses.add_lens(oal_lens)

    # Filters
    oal_filters = OalfiltersType()
    filters = Filter.query.filter_by(user_id=user.id, is_deleted=False).all()
    for filter in filters:
        oal_filter = OalfilterType('flt_{}'.format(filter.id), model=filter.model, vendor=filter.vendor,
                                   type=_get_oal_filter_type(filter.filter_type), color=None,
                                   wratten=None, schott=None)
        oal_filters.add_filter(oal_filter)

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
    
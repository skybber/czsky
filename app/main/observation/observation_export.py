from app.commons.coordinates import parse_latlon

from app.commons.oal_export_utils import get_oal_angle, get_oal_non_neg_angle, create_observation_target

from app.models import Telescope, Eyepiece, Lens, Filter, TelescopeType, FilterType, Seeing

from app.commons.openastronomylog import (
    angleUnit,
    OalangleType,
    OalnonNegativeAngleType,
    OalequPosType,
    OalsurfaceBrightnessType,
    OalobserverType,
    OalobserversType,
    OalsiteType,
    OalsitesType,
    Oalobservations,
    OalobservationType,
    OalsessionsType,
    OalsessionType,
    OaltargetsType,
    OalobservationTargetType,
    OalscopesType,
    OalscopeType,
    OalfixedMagnificationOpticsType,
    OaleyepieceType,
    OaleyepiecesType,
    OallensesType,
    OallensType,
    OalfiltersType,
    OalfilterType,
    OalfindingsType
)

def create_oal_observations(user, observing_sessions):
    # Observers
    oal_observer = OalobserverType(id='usr_{}'.format(user.id),
                                   name=user.get_first_name(),
                                   surname=user.get_last_name(),
                                   contact=[user.email],
                                   )
    oal_observers = OalobserversType(observer=[oal_observer])

    # Sites
    oal_sites = OalsitesType()
    proc_locations = set()
    for observing_session in observing_sessions:
        location = observing_session.location
        if location:
            if location.id in proc_locations:
                continue
            proc_locations.add(location.id)
            oal_site = OalsiteType(id='site_{}'.format(location.id), name=location.name,
                                   longitude=get_oal_angle(angleUnit.DEG, location.longitude), latitude=get_oal_angle(angleUnit.DEG, location.latitude),
                                   elevation=(location.elevation if location.elevation and location.elevation != 0 else None),
                                   timezone=location.time_zone, code=location.iau_code)
        else:
            lat, lon = parse_latlon(observing_session.location_position)
            oal_site = OalsiteType(id='site_adhoc_{}'.format(observing_session.id), name=None,
                                   longitude=get_oal_angle(angleUnit.DEG, lon), latitude=get_oal_angle(angleUnit.DEG, lat),
                                   elevation=None, timezone=None, code=None)
        oal_sites.add_site(oal_site)

    # Sessions
    oal_sessions = OalsessionsType()
    for observing_session in observing_sessions:
        if observing_session.location:
            site_ref = 'site_{}'.format(observing_session.location.id)
        else:
            site_ref = 'site_adhoc_{}'.format(observing_session.id)
        oal_session = OalsessionType(id='se_{}'.format(observing_session.id), lang=user.lang_code,
                                     begin=observing_session.date_from, end=observing_session.date_to, site=site_ref,
                                     coObserver=None, weather=observing_session.weather, equipment=observing_session.equipment,
                                     comments=observing_session.notes, image=None
                                     )
        oal_sessions.add_session(oal_session)

    # Targets
    oal_targets = OaltargetsType()
    proc_targets = set()
    for observing_session in observing_sessions:
        for observation in observing_session.observations:
            for dso in observation.deepsky_objects:
                if dso.id in proc_targets:
                    continue
                proc_targets.add(dso.id)
                oal_obs_target = create_observation_target(dso)
                oal_targets.add_target(oal_obs_target)

    # Scopes
    oal_scopes = OalscopesType()
    telescopes = Telescope.query.filter_by(user_id=user.id, is_deleted=False).all()
    for telescope in telescopes:
        if telescope.fixed_magnification is None:
            oal_scope = OalscopeType(id='opt_{}'.format(telescope.id), model=telescope.model,
                                     type_=_get_oal_telescope_type(telescope.telescope_type), vendor=telescope.vendor, aperture=telescope.aperture_mm,
                                     lightGrasp=telescope.light_grasp, orientation=None, focalLength=telescope.focal_length_mm,
                                     extensiontype_="scopeType")
        else:
            oal_scope = OalfixedMagnificationOpticsType(id='opt_{}'.format(telescope.id), model=telescope.model,
                                                        type_=_get_oal_telescope_type(telescope.telescope_type), vendor=telescope.vendor, aperture=telescope.aperture_mm,
                                                        lightGrasp=telescope.light_grasp, orientation=None, magnification=telescope.fixed_magnification,
                                                        trueField=None, extensiontype_="scopeType")
        oal_scopes.add_scope(oal_scope)

    # Eyepieces
    oal_eyepieces = OaleyepiecesType()
    eyepieces = Eyepiece.query.filter_by(user_id=user.id, is_deleted=False).all()
    for eyepiece in eyepieces:
        oal_eyepiece = OaleyepieceType(id='ep_{}'.format(eyepiece.id), model=eyepiece.model, vendor=eyepiece.vendor, focalLength=eyepiece.focal_length_mm,
                                       apparentFOV=get_oal_non_neg_angle(angleUnit.DEG, eyepiece.fov_deg))
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
                                   type_=_get_oal_filter_type(filter.filter_type), color=None,
                                   wratten=None, schott=None)
        oal_filters.add_filter(oal_filter)

    oal_observation_ar = []

    for observing_session in observing_sessions:
        for observation in observing_session.observations:
            for dso in observation.deepsky_objects:
                obs_result = OalfindingsType(lang=user.lang_code, description=observation.notes)
                oal_sky_quality = OalsurfaceBrightnessType(unit='mags-per-squarearcsec', valueOf_=observing_session.sqm) if observing_session.sqm else None
                oal_obs = OalobservationType(id='obs_{}'.format(observation.id), observer='usr_{}'.format(user.id), site='site_{}'.format(observing_session.location_id),
                                             session='se_{}'.format(observing_session.id), target='_{}'.format(dso.id), begin=observation.date_from, end=observation.date_to,
                                             faintestStar=observing_session.faintest_star, sky_quality=oal_sky_quality, seeing=_get_oal_seeing(observing_session.seeing),
                                             scope='opt_'.format(observation.telescope_id) if observation.telescope_id else None,
                                             accessories=observation.accessories,
                                             eyepiece='ep_'.format(observation.eyepiece_id) if observation.eyepiece_id else None,
                                             lenses='le_'.format(observation.lens_id) if observation.lens_id else None,
                                             filter='flt_'.format(observation.filter_id) if observation.filter_id else None,
                                             magnification=observation.magnification,
                                             imager=None, result=[obs_result], image=None
                                             )
                oal_observation_ar.append(oal_obs)

    oal_observations = Oalobservations(observers=oal_observers, sites=oal_sites, sessions=oal_sessions, targets=oal_targets,
                                       scopes=oal_scopes, eyepieces=oal_eyepieces, lenses=oal_lenses, filters=oal_filters,
                                       images=None, observation=oal_observation_ar)

    return oal_observations


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
    
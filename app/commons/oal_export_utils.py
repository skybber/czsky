from app.commons.openastronomylog import angleUnit, OalnonNegativeAngleType, OalequPosType, OalangleType, OalsurfaceBrightnessType
from app.commons.openastronomylog import OalobservationTargetType
from app.commons.openastronomylog import (
    OaldeepSkyGC,
    OaldeepSkyOC,
    OaldeepSkyGN,
    OaldeepSkyDN,
    OaldeepSkyPN,
    OaldeepSkyAS,
    OaldeepSkyQS,
    OaldeepSkyCG,
)

DS_CZSKY = 'CzSky'

def get_oal_angle(unit, angle):
    return OalangleType(unit=unit, valueOf_=angle)


def get_oal_equ_pos(ra, dec):
    return OalequPosType(ra=get_oal_non_neg_angle(angleUnit.RAD, ra), dec=get_oal_angle(angleUnit.RAD, dec))


def get_oal_non_neg_angle(unit, angle):
    return OalnonNegativeAngleType(unit=unit, valueOf_=angle) if angle is not None else None


def get_oal_surface_brighttness(unit, brightness):
    return OalsurfaceBrightnessType(unit=unit, valueOf_=brightness) if brightness is not None else None


def create_double_star_observation_target(double_star):
    dso_position = get_oal_equ_pos(double_star.ra_first, double_star.dec_first)
    dso_constell = double_star.get_constellation_iau_code()
    oal_obs_target = OaldeepSkyGN(id=id, datasource=DS_CZSKY, observer=None,
                                  name=double_star.common_cat_id, alias=None, position=dso_position,
                                  constellation=dso_constell, notes=None,
                                  smallDiameter=None, largeDiameter=None,
                                  visMag=double_star.mag_first, surfBr=None, nebulaType=None,
                                  pa=double_star.pos_angle
                                  )
    return oal_obs_target


def create_dso_observation_target(dso):
    id = '_{}'.format(dso.name)
    dso_position = get_oal_equ_pos(dso.ra, dso.dec)
    dso_constell = dso.get_constellation_iau_code()
    smallDiameter = get_oal_non_neg_angle('arcsec', dso.minor_axis)
    largeDiameter = get_oal_non_neg_angle('arcsec', dso.major_axis)
    surface_brightness = get_oal_surface_brighttness('mags-per-squarearcsec', dso.surface_bright)

    if dso.type == 'BN':
        oal_obs_target = OaldeepSkyGN(id=id, datasource=DS_CZSKY, observer=None,
                                      name=dso.name, alias=None, position=dso_position,
                                      constellation=dso_constell, notes=None,
                                      smallDiameter=smallDiameter, largeDiameter=largeDiameter,
                                      visMag=dso.mag, surfBr=surface_brightness, nebulaType=dso.subtype,
                                      pa=dso.position_angle
                                      )
    elif dso.type == 'DN':
        oal_obs_target = OaldeepSkyDN(id=id, datasource=DS_CZSKY, observer=None,
                                      name=dso.name, alias=None, position=dso_position,
                                      constellation=dso_constell, notes=None,
                                      smallDiameter=smallDiameter, largeDiameter=largeDiameter,
                                      visMag=dso.mag, surfBr=surface_brightness, nebulaType=dso.subtype,
                                      pa=dso.position_angle, opacity=None
                                      )
    elif dso.type == 'GC':
        oal_obs_target = OaldeepSkyGC(id=id, datasource=DS_CZSKY, observer=None,
                                      name=dso.name, alias=None, position=dso_position,
                                      constellation=dso_constell, notes=None,
                                      smallDiameter=smallDiameter, largeDiameter=largeDiameter,
                                      visMag=dso.mag, surfBr=surface_brightness, magStars=None,
                                      )
    elif dso.type == 'OC':
        oal_obs_target = OaldeepSkyOC(id=id, datasource=DS_CZSKY, observer=None,
                                      name=dso.name, alias=None, position=dso_position,
                                      constellation=dso_constell, notes=None,
                                      smallDiameter=smallDiameter, largeDiameter=largeDiameter,
                                      visMag=dso.mag, surfBr=surface_brightness,
                                      stars=None, brightestStar=None
                                      )
    elif dso.type == 'PN' or dso.type == 'pA*':
        oal_obs_target = OaldeepSkyPN(id=id, datasource=DS_CZSKY, observer=None,
                                      name=dso.name, alias=None, position=dso_position,
                                      constellation=dso_constell, notes=None,
                                      smallDiameter=smallDiameter, largeDiameter=largeDiameter,
                                      visMag=dso.mag, surfBr=surface_brightness, magStar=dso.c_star_b_mag
                                      )
    elif dso.type == 'GX':
        oal_obs_target = OaldeepSkyGC(id=id, datasource=DS_CZSKY, observer=None,
                                      name=dso.name, alias=None, position=dso_position,
                                      constellation=dso_constell, notes=None,
                                      smallDiameter=smallDiameter, largeDiameter=largeDiameter,
                                      visMag=dso.mag, surfBr=surface_brightness, hubbleType=dso.subtype,
                                      pa=dso.position_angle, opacity=None
                                      )
    elif dso.type == 'AST':
        oal_obs_target = OaldeepSkyAS(id=id, datasource=DS_CZSKY, observer=None,
                                      name=dso.name, alias=None, position=dso_position,
                                      constellation=dso_constell, notes=None,
                                      smallDiameter=smallDiameter, largeDiameter=largeDiameter,
                                      visMag=dso.mag, surfBr=surface_brightness,
                                      pa=dso.position_angle
                                      )
    elif dso.type == 'GALCL':
        oal_obs_target = OaldeepSkyCG(id=id, datasource=DS_CZSKY, observer=None,
                                      name=dso.name, alias=None, position=dso_position,
                                      constellation=dso_constell, notes=None,
                                      smallDiameter=smallDiameter, largeDiameter=largeDiameter,
                                      visMag=dso.mag, surfBr=surface_brightness,
                                      mag10=None
                                      )
    elif dso.type == 'QSO':
        oal_obs_target = OaldeepSkyQS(id=id, datasource=DS_CZSKY, observer=None,
                                      name=dso.name, alias=None, position=dso_position,
                                      constellation=dso_constell, notes=None,
                                      smallDiameter=smallDiameter, largeDiameter=largeDiameter,
                                      visMag=dso.mag, surfBr=surface_brightness
                                      )
    else:
        oal_obs_target = OalobservationTargetType(id=id, datasource=DS_CZSKY, observer=None,
                                                  name=dso.name, alias=None, position=dso_position,
                                                  constellation=dso.get_constellation_iau_code(),
                                                  notes=None, extensiontype_=None)
    return oal_obs_target

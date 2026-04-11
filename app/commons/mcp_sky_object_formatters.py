from __future__ import annotations

from typing import Any

from app.commons.comet_utils import fetch_recent_cobs_observations
from app.commons.dso_description_utils import get_dso_descriptions_with_master_fallback
from app.commons.dso_utils import denormalize_dso_name
from app.models import Constellation, DeepskyObject


def _drop_none(value):
    if isinstance(value, dict):
        return {
            key: cleaned
            for key, raw in value.items()
            if (cleaned := _drop_none(raw)) is not None
        }
    if isinstance(value, list):
        cleaned_list = [_drop_none(item) for item in value]
        return [item for item in cleaned_list if item is not None]
    return value


def _coordinates(ra=None, dec=None, ra_str=None, dec_str=None):
    if ra is None and dec is None and not ra_str and not dec_str:
        return None
    return _drop_none(
        {
            "ra": ra,
            "dec": dec,
            "ra_str": ra_str,
            "dec_str": dec_str,
        }
    )


def _constellation_summary(code=None, name=None):
    result = {}
    if code:
        result["constellation"] = code
    if name:
        result["constellation_name"] = name
    return result


def _dso_aliases(dso):
    aliases = []
    if dso.master_id:
        master = DeepskyObject.query.filter_by(id=dso.master_id).first()
        if master:
            aliases.append(denormalize_dso_name(master.name))
    child_dsos = DeepskyObject.query.filter_by(master_id=dso.id).all()
    aliases.extend(denormalize_dso_name(child.name) for child in child_dsos)

    deduped = []
    seen = set()
    for alias in aliases:
        if alias and alias not in seen and alias != denormalize_dso_name(dso.name):
            deduped.append(alias)
            seen.add(alias)
    return deduped


def _format_constellation(query: str, resolved: dict[str, Any]) -> dict[str, Any]:
    constellation = resolved["object"]
    return _drop_none(
        {
            "query": query,
            "matched_by": resolved["matched_by"],
            "object_type": "constellation",
            "title": constellation.name,
            "identifier": constellation.iau_code,
            "summary": _drop_none(
                {
                    "classification": "constellation",
                    **_constellation_summary(constellation.iau_code, constellation.name),
                    "season": constellation.season,
                }
            ),
            "details": _drop_none(
                {
                    "description": constellation.descr,
                    "image": constellation.image,
                    "label_ra": constellation.label_ra,
                    "label_dec": constellation.label_dec,
                }
            ),
        }
    )


def _format_dso(query: str, resolved: dict[str, Any]) -> dict[str, Any]:
    dso = resolved["object"]
    constellation = Constellation.get_constellation_by_id(dso.constellation_id) if dso.constellation_id else None
    user_descr, apert_descriptions, _ = get_dso_descriptions_with_master_fallback(dso)
    return _drop_none(
        {
            "query": query,
            "matched_by": resolved["matched_by"],
            "object_type": "dso",
            "title": dso.denormalized_name(),
            "subtitle": dso.common_name,
            "identifier": dso.name,
            "aliases": _dso_aliases(dso),
            "coordinates": _coordinates(dso.ra, dso.dec, dso.ra_str(), dso.dec_str()),
            "summary": _drop_none(
                {
                    "classification": dso.type,
                    **_constellation_summary(dso.get_constellation_iau_code(), constellation.name if constellation else None),
                    "magnitude": dso.mag,
                    "size": _drop_none(
                        {
                            "major_axis": dso.major_axis,
                            "minor_axis": dso.minor_axis,
                        }
                    ),
                }
            ),
            "details": _drop_none(
                {
                    "subtype": dso.subtype,
                    "surface_brightness": dso.surface_bright,
                    "position_angle": dso.position_angle,
                    "axis_ratio": dso.axis_ratio,
                    "distance": dso.distance,
                    "catalogue_id": dso.catalogue_id,
                    "description": dso.descr,
                    "editor_description": user_descr.text if user_descr and user_descr.text else None,
                    "aperture_descriptions": [
                        {
                            "aperture_class": aperture_class,
                            "text": text,
                        }
                        for aperture_class, text in apert_descriptions
                    ],
                    "import_source": dso.import_source,
                }
            ),
        }
    )


def _split_double_star_aliases(double_star):
    aliases = []
    if double_star.other_designation:
        aliases.extend(
            part.strip()
            for part in double_star.other_designation.split(";")
            if part.strip()
        )
    return aliases


def _format_double_star(query: str, resolved: dict[str, Any]) -> dict[str, Any]:
    double_star = resolved["object"]
    constellation = Constellation.get_constellation_by_id(double_star.constellation_id) if double_star.constellation_id else None
    return _drop_none(
        {
            "query": query,
            "matched_by": resolved["matched_by"],
            "object_type": "double_star",
            "title": double_star.get_catalog_name(),
            "subtitle": double_star.get_common_name(),
            "identifier": double_star.common_cat_id or double_star.wds_number,
            "aliases": _split_double_star_aliases(double_star),
            "coordinates": _coordinates(
                double_star.ra_first,
                double_star.dec_first,
                double_star.ra_first_str(),
                double_star.dec_first_str(),
            ),
            "summary": _drop_none(
                {
                    "classification": "double_star",
                    **_constellation_summary(double_star.get_constellation_iau_code(), constellation.name if constellation else None),
                    "separation": double_star.separation,
                }
            ),
            "details": _drop_none(
                {
                    "wds_number": double_star.wds_number,
                    "components": double_star.components,
                    "position_angle": double_star.pos_angle,
                    "separation": double_star.separation,
                    "mag_first": double_star.mag_first,
                    "mag_second": double_star.mag_second,
                    "delta_mag": double_star.delta_mag,
                    "spectral_type": double_star.spectral_type,
                }
            ),
        }
    )


def _format_star(query: str, resolved: dict[str, Any]) -> dict[str, Any]:
    star = resolved["object"]
    constellation = star.constellation
    return _drop_none(
        {
            "query": query,
            "matched_by": resolved["matched_by"],
            "object_type": "star",
            "title": star.get_name(),
            "identifier": star.get_name(),
            "coordinates": _coordinates(star.ra, star.dec, star.ra_str(), star.dec_str()),
            "summary": _drop_none(
                {
                    "classification": "star",
                    **_constellation_summary(star.get_constellation_iau_code(), constellation.name if constellation else None),
                    "magnitude": star.mag,
                }
            ),
            "details": _drop_none(
                {
                    "common_name": star.common_name,
                    "bayer": star.bayer,
                    "flamsteed": star.flamsteed,
                    "var_id": star.var_id,
                    "hr": star.hr,
                    "hd": star.hd,
                    "sao": star.sao,
                    "spectral_type": star.sp_type,
                    "mag_max": star.mag_max,
                    "mag_min": star.mag_min,
                    "bv": star.bv,
                }
            ),
        }
    )


def _format_earth_moon(query: str, resolved: dict[str, Any]) -> dict[str, Any]:
    moon = resolved["object"]
    return {
        "query": query,
        "matched_by": resolved["matched_by"],
        "object_type": "earth_moon",
        "title": moon["title"],
        "identifier": moon["identifier"],
        "summary": {
            "classification": "planetary_moon",
            "planet": "Earth",
        },
        "details": {
            "iau_name": "Moon",
        },
    }


def _format_planet(query: str, resolved: dict[str, Any]) -> dict[str, Any]:
    planet = resolved["object"]
    return _drop_none(
        {
            "query": query,
            "matched_by": resolved["matched_by"],
            "object_type": "planet",
            "title": planet.get_localized_name(),
            "identifier": planet.iau_code,
            "summary": {
                "classification": "planet",
            },
            "details": _drop_none(
                {
                    "iau_code": planet.iau_code,
                    "int_designation": planet.int_designation,
                }
            ),
        }
    )


def _format_planet_moon(query: str, resolved: dict[str, Any]) -> dict[str, Any]:
    planet_moon = resolved["object"]
    return _drop_none(
        {
            "query": query,
            "matched_by": resolved["matched_by"],
            "object_type": "planet_moon",
            "title": planet_moon.name,
            "subtitle": planet_moon.planet.get_localized_name() if planet_moon.planet else None,
            "identifier": planet_moon.name,
            "summary": {
                "classification": "planet_moon",
            },
            "details": _drop_none(
                {
                    "iau_number": planet_moon.iau_number,
                    "planet": planet_moon.planet.get_localized_name() if planet_moon.planet else None,
                    "planet_iau_code": planet_moon.planet.iau_code if planet_moon.planet else None,
                }
            ),
        }
    )


def _format_comet(query: str, resolved: dict[str, Any]) -> dict[str, Any]:
    comet = resolved["object"]
    constellation = comet.cur_constell()
    recent_cobs_observations = fetch_recent_cobs_observations(comet.id, limit=5)
    return _drop_none(
        {
            "query": query,
            "matched_by": resolved["matched_by"],
            "object_type": "comet",
            "title": comet.designation,
            "identifier": comet.comet_id,
            "coordinates": _coordinates(comet.cur_ra, comet.cur_dec, comet.cur_ra_str(), comet.cur_dec_str()),
            "summary": _drop_none(
                {
                    "classification": "comet",
                    **_constellation_summary(comet.cur_constellation_iau_code(), constellation.name if constellation else None),
                    "magnitude": comet.displayed_mag(),
                }
            ),
            "details": _drop_none(
                {
                    "orbit_type": comet.orbit_type,
                    "perihelion_distance_au": comet.perihelion_distance_au,
                    "eccentricity": comet.eccentricity,
                    "inclination_degrees": comet.inclination_degrees,
                    "is_disintegrated": comet.is_disintegrated,
                    "recent_cobs_observations": recent_cobs_observations,
                }
            ),
        }
    )


def _format_minor_planet(query: str, resolved: dict[str, Any]) -> dict[str, Any]:
    minor_planet = resolved["object"]
    constellation = minor_planet.cur_constell()
    return _drop_none(
        {
            "query": query,
            "matched_by": resolved["matched_by"],
            "object_type": "minor_planet",
            "title": minor_planet.designation,
            "identifier": minor_planet.int_designation,
            "coordinates": _coordinates(
                minor_planet.cur_ra,
                minor_planet.cur_dec,
                minor_planet.cur_ra_str(),
                minor_planet.cur_dec_str(),
            ),
            "summary": _drop_none(
                {
                    "classification": "minor_planet",
                    **_constellation_summary(minor_planet.cur_constellation_iau_code(), constellation.name if constellation else None),
                    "magnitude": minor_planet.displayed_mag(),
                }
            ),
            "details": _drop_none(
                {
                    "magnitude_H": minor_planet.magnitude_H,
                    "magnitude_G": minor_planet.magnitude_G,
                    "semimajor_axis_au": minor_planet.semimajor_axis_au,
                    "eccentricity": minor_planet.eccentricity,
                    "inclination_degrees": minor_planet.inclination_degrees,
                }
            ),
        }
    )


_FORMATTERS = {
    "constellation": _format_constellation,
    "dso": _format_dso,
    "double_star": _format_double_star,
    "star": _format_star,
    "earth_moon": _format_earth_moon,
    "planet": _format_planet,
    "planet_moon": _format_planet_moon,
    "comet": _format_comet,
    "minor_planet": _format_minor_planet,
}


def format_resolved_object(query: str, resolved: dict[str, Any]) -> dict[str, Any]:
    formatter = _FORMATTERS[resolved["object_type"]]
    return formatter(query, resolved)

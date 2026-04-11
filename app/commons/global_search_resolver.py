from __future__ import annotations

from typing import Any

from flask import has_request_context
from sqlalchemy import func

from app.commons.search_sky_object_utils import (
    _search_by_bayer_flamsteed,
    _search_star_from_catalog,
    search_comet,
    search_constellation,
    search_double_star,
    search_dso,
    search_earth_moon,
    search_minor_planet,
    search_planet,
    search_planet_moon,
    search_star,
)
from app.models import Star


def _search_star_safe(query: str):
    if has_request_context():
        return search_star(query)

    star = _search_by_bayer_flamsteed(query)
    if not star:
        star = _search_star_from_catalog(query)
    if not star:
        star = Star.query.filter(Star.var_id.ilike(query)).first()
    if not star:
        star = Star.query.filter(func.lower(Star.common_name) == query.lower()).first()
    return star, None


def resolve_global_object(query: str) -> dict[str, Any] | None:
    query = (query or "").strip()
    if not query:
        return None

    constellation = search_constellation(query)
    if constellation:
        return {
            "matched_by": "constellation",
            "object_type": "constellation",
            "object": constellation,
        }

    dso = search_dso(query)
    if dso:
        return {
            "matched_by": "dso",
            "object_type": "dso",
            "object": dso,
        }

    double_star = search_double_star(query)
    if double_star:
        return {
            "matched_by": "double_star",
            "object_type": "double_star",
            "object": double_star,
        }

    star, usd = _search_star_safe(query)
    if star:
        return {
            "matched_by": "star",
            "object_type": "star",
            "object": star,
            "user_description": usd,
        }

    if search_earth_moon(query):
        return {
            "matched_by": "earth_moon",
            "object_type": "earth_moon",
            "object": {"identifier": "moon", "title": "Moon"},
        }

    planet = search_planet(query)
    if planet:
        return {
            "matched_by": "planet",
            "object_type": "planet",
            "object": planet,
        }

    planet_moon = search_planet_moon(query)
    if planet_moon:
        return {
            "matched_by": "planet_moon",
            "object_type": "planet_moon",
            "object": planet_moon,
        }

    comet = search_comet(query)
    if comet:
        return {
            "matched_by": "comet",
            "object_type": "comet",
            "object": comet,
        }

    minor_planet = search_minor_planet(query)
    if minor_planet:
        return {
            "matched_by": "minor_planet",
            "object_type": "minor_planet",
            "object": minor_planet,
        }

    return None

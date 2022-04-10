import urllib.parse

from .dso_utils import normalize_dso_name, denormalize_dso_name, normalize_double_star_name
from .greek import GREEK_TO_LAT, SHORT_LAT_TO_GREEK, LONG_LAT_TO_GREEK, LONG_LAT_CZ_TO_GREEK, SHORT_LAT_TO_GREEK_EXT
from .utils import get_lang_and_editor_user_from_request

from app.models import (
    Constellation,
    DeepskyObject,
    DoubleStar,
    Star,
    UserStarDescription,
)

from app.main.solarsystem.comet_views import get_all_comets

from sqlalchemy import func


def search_constellation(query):
    constellation = Constellation.query.filter(func.lower(Constellation.iau_code) == func.lower(query)).first()
    if not constellation:
        constellation = Constellation.query.filter(Constellation.name.like('%' + query + '%')).first()
    return constellation


def search_dso(query):
    if query.isdigit():
        query = 'NGC' + query
    else:
        query = urllib.parse.unquote(query)

    normalized_name = normalize_dso_name(denormalize_dso_name(query))
    dso = DeepskyObject.query.filter_by(name=normalized_name).first()
    return dso


def search_star(query):
    star = _search_by_bayer_flamsteed(query)
    if not star:
        star = _search_star_from_catalog(query)
    if not star:
        # try to search by var ID
        star = Star.query.filter(Star.var_id.ilike(query)).first()
    usd = None
    if not star:
        # try to search by common star name
        star = Star.query.filter_by(common_name=query.lower().capitalize()).first()
        if star:
            lang, editor_user = get_lang_and_editor_user_from_request(for_constell_descr=True)
            usd = UserStarDescription.query.filter_by(star_id=star.id, user_id=editor_user.id, lang_code=lang).first()

    return star, usd


def _search_by_bayer_flamsteed(query):
    star = None
    if query[:1] in GREEK_TO_LAT and len(query) > 1:
        bayer = query[:1]
        constell = _get_constell(query[1:])
        if constell:
            star = Star.query.filter_by(bayer=bayer, constellation_id=constell.id).first()
    else:
        words = query.split()
        if len(words) in [2, 3]:
            constell_index = 1 if len(words) == 2 else 2
            constell = _get_constell(words[constell_index])
            if constell:
                star_name = words[0].lower()
                bayer = None
                if star_name in GREEK_TO_LAT:
                    bayer = star_name
                elif star_name in SHORT_LAT_TO_GREEK:
                    bayer = SHORT_LAT_TO_GREEK[star_name]
                elif star_name in LONG_LAT_TO_GREEK:
                    bayer = LONG_LAT_TO_GREEK[star_name]
                elif star_name in LONG_LAT_CZ_TO_GREEK:
                    bayer = LONG_LAT_CZ_TO_GREEK[star_name]
                if bayer:
                    if len(words) == 3:
                        if words[1].isdigit():
                            full_name = GREEK_TO_LAT[bayer] + ' ' + words[1]
                            if full_name in SHORT_LAT_TO_GREEK_EXT:
                                star = Star.query.filter_by(bayer=SHORT_LAT_TO_GREEK_EXT[full_name], constellation_id=constell.id).first()
                    else:
                        star = Star.query.filter_by(bayer=bayer, constellation_id=constell.id).first()
                elif len(words) == 2 and star_name.isdigit():

                    star = Star.query.filter_by(flamsteed=int(star_name), constellation_id=constell.id).first()
        elif len(words) == 1 and query[0].isdigit():
            i = 1
            while i < len(query) and query[i].isdigit():
                i+=1
            if i < len(query):
                constell = _get_constell(query[i:])
                if constell:
                    star = Star.query.filter_by(flamsteed=int(query[:i]), constellation_id=constell.id).first()
    return star


def _search_star_from_catalog(query):
    star = None
    for i, letter in enumerate(query, 0):
        if letter.isdigit():
            break
    if i > 0 and i < len(query)-1:
        cat = query[:i].strip()
        sid = query[i:].strip()
        if cat and sid.isdigit():
            cat = cat.upper()
            if cat == 'HR':
                star = Star.query.filter_by(hr=int(sid)).first()
            if not not star and cat == 'HD':
                star = Star.query.filter_by(hd=int(sid)).first()
            if not star and cat == 'SAO':
                star = Star.query.filter_by(sao=int(sid)).first()
    return star


def search_double_star(query):
    double_star = None
    if query[0].isdigit():
        double_star = DoubleStar.query.filter_by(wds_number=query).first()
    if not double_star:
        double_star = DoubleStar.query.filter_by(common_cat_id=normalize_double_star_name(query)).first()
    if not double_star:
        words = query.split()
        if words and len(words) in (2, 3):
            star_name = words[0].lower()
            bayer = None
            if star_name in GREEK_TO_LAT:
                bayer = star_name
            elif star_name in SHORT_LAT_TO_GREEK:
                bayer = SHORT_LAT_TO_GREEK[star_name]
            elif star_name in LONG_LAT_TO_GREEK:
                bayer = LONG_LAT_TO_GREEK[star_name]
            elif star_name in LONG_LAT_CZ_TO_GREEK:
                bayer = LONG_LAT_CZ_TO_GREEK[star_name]
            if bayer:
                query = GREEK_TO_LAT[bayer] + ' ' + ' '.join(words[1:])

        double_star = DoubleStar.query.filter(DoubleStar.norm_other_designation.like('%;' + query.title() + ';%')).first()

    return double_star


def search_double_star_strict(query):
    double_star = None
    if not double_star:
        double_star = DoubleStar.query.filter_by(common_cat_id=normalize_double_star_name(query)).first()
    if query[0].isdigit():
        double_star = DoubleStar.query.filter_by(wds_number=query).first()

    return double_star


def search_comet(query):
    if len(query) > 5:
        search_expr = query.replace('"', '')
        all_comets = get_all_comets()
        comets = all_comets.query('designation.str.contains("{}")'.format(search_expr))
        if len(comets) >= 1:
            return comets.iloc[0]


def _get_constell(costell_code):
    constell_iau_code = costell_code.strip().upper()
    if constell_iau_code:
        constell = Constellation.get_iau_dict().get(constell_iau_code)
        return constell
    return None


def parse_observation_targets(targets):
    not_found = []
    dsos = []
    double_star = None
    target_names = targets.split(',')
    for target_name in target_names:
        dso_name = normalize_dso_name(target_name)
        dso = DeepskyObject.query.filter_by(name=dso_name).first()
        if dso:
            dsos.append(dso)
            continue
        double_star_name = normalize_double_star_name(target_name)
        double_star = DoubleStar.query.filter_by(common_cat_id=double_star_name).first()
        if double_star:
            break
        double_star = DoubleStar.query.filter(DoubleStar.norm_other_designation.ilike('%;' + target_name + ';%')).first()
        if double_star:
            break
        not_found.append(target_name)

    return dsos, double_star, not_found

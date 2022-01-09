import sys
import re

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.star import Star, UserStarDescription
from app.models.constellation import Constellation

from app.commons.dso_utils import normalize_dso_name
from app.main.catalogue.constellation_views import constellations

STAR_MAP = {
    "α":"alp",
    "β":"bet",
    "γ":"gam",
    "δ":"del",
    "ε":"eps",
    "ζ":"zet",
    "η":"eta",
    "θ":"the",
    "ι":"iot",
    "κ":"kap",
    "λ":"lam",
    "μ":"mu",
    "ν":"nu",
    "ξ":"xi",
    "ο":"omi",
    "π":"pi",
    "ρ":"rho",
    "σ":"sig",
    "ς":"sig",
    "τ":"tau",
    "υ":"ups",
    "φ":"phi",
    "χ":"chi",
    "ψ":"psi",
    "ω":"ome"
};

map_names = {
    'ζ a 80 UMa': 'ζ UMa',
    'α1 Cap': 'α Cap',
    'ο2 Eri':'ο Eri',
    '16/17 Dra':'16 Dra',
    '36/37 Her':'36 Her',
    '17 a 18 Sex' : '17 Sex',
    'γ1 a γ2 Nor' : 'γ Nor',
    'Sirrah' : 'α And',
    'π1 UMi': '18 UMi'
}

def _find_constellation(name, constellations):
    if name == 'Adromedae':
        name = 'And'
    elif name == 'Leonis':
        name = 'Leo'

    if len(name) == 3:
        for constell in constellations:
            if constell.iau_code.upper() == name.upper():
                return constell
        print('Constellation not found {}.'.format(name))
    else:
        if name.endswith('inis'):
            name = name[:-4]
        if name.endswith('orum'):
            name = name[:-4]
        elif name.endswith('is'):
            name = name[:-3]
        elif  name.endswith('ri'):
            name = name[:-2]
        elif  name.endswith('i'):
            name = name[:-1]
        elif  name.endswith('ae'):
            name = name[:-2]
        for constell in constellations:
            if constell.name.capitalize().startswith(name):
                return constell
    return None



def _find_max_star(stars):
    min_star = None
    for star in stars:
        if min_star is None:
            min_star = star
        elif star.mag<min_star.mag:
            min_star = star
    return min_star


def _find_star_by_digit(stars, num):
    result = []
    for star in stars:
        if star.bayer_flamsteed.startswith(num):
            after = star.bayer_flamsteed[len(num):len(num)+1]
            if not after.isdigit():
                result.append(star)
    return result

def _resolve_star(star_name, constellations):
    star = None
    constell = None
    if star_name in map_names:
        star_name = map_names[star_name]
    elif 'Canum Venaticorum' in star_name:
        star_name = star_name.replace('Canum Venaticorum', 'CVn')
    comps = star_name.split()
    if len(comps) == 2:
        id_in_constell = None
        if comps[0][0] in STAR_MAP:
            id_in_constell = STAR_MAP[comps[0][0]].capitalize()
        elif comps[0].isdigit():
            id_in_constell = comps[0]
        if id_in_constell:
            constell = _find_constellation(comps[1], constellations)
            if constell is None:
                print('Unknown constellation {}'.format(comps[1]))
            else:
                sql_search = '%' + id_in_constell +'%' + constell.iau_code + '%'
                stars = Star.query.filter(Star.bayer_flamsteed.like(sql_search)).all()
                if len(stars) == 0:
                    print('Not found in DB search: ({})  {}'.format(star_name, sql_search))
                elif len(stars) > 1:
                    if comps[0].isdigit():
                        stars = _find_star_by_digit(stars, comps[0])
                    star = _find_max_star(stars)
                    if not star:
                        print('Unresolved multiple: {}'.format(star_name))
                else:
                    star = stars[0]
        else:
            print('Unresolved: {}'.format(star_name))
    else:
        print('Unexpected num of elements {}'.format(star_name))

    return star, constell


def link_star_descriptions_by_bayer_flamsteed_star():
    constellations = []

    print('Linking star descriptions by bayer/flamsteed...')

    for co in Constellation.query.all():
        constellations.append(co)

    try:
        star_descriptions = UserStarDescription.query.all()
        for star_descr in star_descriptions:
            m = re.search(r'\((.*)', star_descr.common_name)
            star = None
            constell = None
            if m:
                star_name = m.group(1)
                if star_name.endswith(')'):
                    star_name = star_name[:-1]
                star, constell = _resolve_star(star_name, constellations)
            else:
                star, constell = _resolve_star(star_descr.common_name, constellations)
            if star:
                star_descr.star_id = star.id
                star.constellation_id = constell.id
                db.session.add(star_descr)
                db.session.add(star)
        db.session.commit()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()

    print('DONE.')


def link_star_descriptions_by_var_id():

    print('Linking star descriptions by var_id ...')

    try:
        star_descriptions = UserStarDescription.query.filter_by(star_id=None).all()
        for star_descr in star_descriptions:
            star = Star.query.filter_by(var_id=star_descr.common_name).first()
            if star:
                print('Updating {}'.format(star.var_id))
                star_descr.star_id = star.id
                db.session.add(star_descr)
        db.session.commit()
    except IntegrityError as err:
        print('\nIntegrity error {}'.format(err))
        db.session.rollback()

    print('DONE.')

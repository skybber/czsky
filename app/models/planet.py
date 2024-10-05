from .. import db

from flask_babel import gettext
from skyfield.api import load

BODY_KEY_DICT = {
    'mercury': 'MERCURY',
    'venus': 'VENUS',
    'mars': 'MARS',
    'jupiter': 'JUPITER_BARYCENTER',
    'saturn': 'SATURN_BARYCENTER',
    'uranus': 'URANUS_BARYCENTER',
    'neptune': 'NEPTUNE_BARYCENTER',
    'pluto': 'PLUTO_BARYCENTER'
}

ALL_LOCALE_NAMES = [
    ['mercury', ['merkur']],
    ['venus', ['venuse','venuše']],
    ['mars', ['mars']],
    ['jupiter', ['jupiter']],
    ['saturn', ['saturn']],
    ['uranus', ['uran']],
    ['neptune', ['neptun']],
    ['pluto', ['pluto']],
]


class Planet(db.Model):
    __tablename__ = 'planets'
    id = db.Column(db.Integer, primary_key=True)
    int_designation = db.Column(db.Integer, index=True)
    iau_code = db.Column(db.String(20))

    _all = None
    _iau_dict = None
    _id_dict = None

    def get_localized_name(self):
        return gettext(self.iau_code).capitalize()

    @classmethod
    def get_all(cls):
        if Planet._all is None:
            all_pl = []
            eph = load('de421.bsp')
            for pl in Planet.query.all():
                db.session.expunge(pl)
                pl.eph = eph[BODY_KEY_DICT[pl.iau_code.lower()]]
                all_pl.append(pl)
            Planet._all = all_pl

        return Planet._all

    @classmethod
    def get_by_iau_code(cls, iau_code):
        if not Planet._iau_dict:
            Planet._iau_dict = {}
            for pl in Planet.get_all():
                Planet._iau_dict[pl.iau_code.upper()] = pl
        return Planet._iau_dict.get(iau_code.upper())

    @classmethod
    def get_by_locale_name(cls, planet_name):
        planet_name = planet_name.lower()
        for iau_code, locale_names in ALL_LOCALE_NAMES:
            if iau_code == planet_name:
                return Planet.get_by_iau_code(iau_code)
            for locale_name in locale_names:
                if locale_name == planet_name:
                    return Planet.get_by_iau_code(iau_code)
        return None

    @classmethod
    def get_planet_by_id(cls, planet_id):
        if not Planet._id_dict:
            Planet._id_dict = {}
            for pl in Planet.get_all():
                Planet._id_dict[pl.id] = pl
        return Planet._id_dict.get(planet_id)

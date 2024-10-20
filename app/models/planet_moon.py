from sqlalchemy.orm import joinedload
from .. import db


class PlanetMoon(db.Model):
    __tablename__ = 'planet_moons'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), index=True)
    iau_number = db.Column(db.Integer)
    planet_id = db.Column(db.Integer, db.ForeignKey('planets.id'))
    planet = db.relationship("Planet")

    _all = None
    _name_dict = None
    _id_dict = None

    @classmethod
    def get_all(cls):
        if PlanetMoon._all is None:
            all_pl = []
            for plm in PlanetMoon.query.options(joinedload(PlanetMoon.planet)).all():
                db.session.expunge(plm)
                all_pl.append(plm)
            PlanetMoon._all = all_pl

        return PlanetMoon._all

    @classmethod
    def get_by_name(cls, name):
        if not PlanetMoon._name_dict:
            PlanetMoon._name_dict = {}
            for plm in PlanetMoon.query.options(joinedload(PlanetMoon.planet)).all():
                db.session.expunge(plm)
                PlanetMoon._name_dict[plm.name.upper()] = plm
        return PlanetMoon._name_dict.get(name.upper())

    @classmethod
    def get_by_id(cls, id):
        if not PlanetMoon._id_dict:
            PlanetMoon._id_dict = {}
            for plm in PlanetMoon.query.options(joinedload(PlanetMoon.planet)).all():
                db.session.expunge(plm)
                PlanetMoon._id_dict[plm.id] = plm
        return PlanetMoon._id_dict.get(id)

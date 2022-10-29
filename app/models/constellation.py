import numpy as np
from datetime import datetime

from skyfield.api import load_constellation_map, position_from_radec

from .. import db


class Constellation(db.Model):
    __tablename__ = 'constellations'
    id = db.Column(db.Integer, primary_key=True)
    iau_code = db.Column(db.String(3), unique=True, index=True)
    name = db.Column(db.String(64), unique=True, index=True)
    season = db.Column(db.String(32))
    descr = db.Column(db.Text)
    image = db.Column(db.String(256))
    label_ra = db.Column(db.Float)
    label_dec = db.Column(db.Float)
    deepsky_objects = db.relationship('DeepskyObject', backref='constellation', lazy=True)

    _all = None
    _iau_dict = None
    _id_dict = None

    @classmethod
    def get_all(cls):
        if not Constellation._all:
            Constellation._all = []
            for co in Constellation.query.all():
                db.session.expunge(co)
                Constellation._all.append(co)
        return Constellation._all

    @classmethod
    def get_iau_dict(cls):
        if not Constellation._iau_dict:
            Constellation._iau_dict = {}
            for co in Constellation.get_all():
                Constellation._iau_dict[co.iau_code.upper()] = co
        return Constellation._iau_dict

    @classmethod
    def get_constellation_by_iau_code(cls, iau_code):
        return Constellation.get_iau_dict().get(iau_code.upper())

    @classmethod
    def get_id_dict(cls):
        if not Constellation._id_dict:
            Constellation._id_dict = {}
            for co in Constellation.get_all():
                Constellation._id_dict[co.id] = co
        return Constellation._id_dict

    @classmethod
    def get_constellation_by_id(cls, constellation_id):
        return Constellation.get_id_dict().get(constellation_id)

    @classmethod
    def get_season_constell_ids(cls, season):
        if season and season != 'All':
            constell_ids = set()
            for constell_id in db.session.query(Constellation.id).filter(Constellation.season == season):
                constell_ids.add(constell_id[0])
            return constell_ids
        return None

    @classmethod
    def get_constellation_by_position(cls, ra, dec):
        constellation_at = load_constellation_map()
        const_code = constellation_at(position_from_radec(ra / np.pi * 12.0, dec / np.pi * 180.0))
        return Constellation.get_constellation_by_iau_code(const_code)


class UserConsDescription(db.Model):
    __tablename__ = 'user_cons_descriptions'
    id = db.Column(db.Integer, primary_key=True)
    constellation_id = db.Column(db.Integer, db.ForeignKey('constellations.id'), nullable=False)
    constellation = db.relationship("Constellation")
    common_name = db.Column(db.String(256))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    lang_code = db.Column(db.String(2))
    text = db.Column(db.Text)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

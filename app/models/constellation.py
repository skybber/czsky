from datetime import datetime
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
                Constellation._iau_dict[co.iau_code] = co
        return Constellation._iau_dict

    @classmethod
    def get_id_dict(cls):
        if not Constellation._id_dict:
            Constellation._id_dict = {}
            for co in Constellation.get_all():
                Constellation._id_dict[co.id] = co
        return Constellation._id_dict


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

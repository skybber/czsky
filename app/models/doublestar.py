from datetime import datetime

from .. import db


class DoubleStar(db.Model):
    __tablename__ = 'double_stars'
    id = db.Column(db.Integer, primary_key=True)
    wds_number = db.Column(db.String(10), index=True)
    common_cat_id = db.Column(db.String(20), index=True)
    components = db.Column(db.String(12))
    other_designation = db.Column(db.Text)
    pos_angle = db.Column(db.Integer)
    separation = db.Column(db.Float)
    mag_first = db.Column(db.Float)
    mag_second = db.Column(db.Float)
    spectral_type = db.Column(db.String(20))
    constellation_id = db.Column(db.Integer, db.ForeignKey('constellations.id'))
    constellation = db.relationship("Constellation")
    ra_first = db.Column(db.Float)
    dec_first = db.Column(db.Float)

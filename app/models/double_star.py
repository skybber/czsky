from datetime import datetime
from .. import db

from app.commons.coordinates import ra_to_str_short, dec_to_str_short, ra_to_str, dec_to_str
from .constellation import Constellation


class DoubleStar(db.Model):
    __tablename__ = 'double_stars'
    id = db.Column(db.Integer, primary_key=True)
    star_id = db.Column(db.Integer, db.ForeignKey('stars.id'))
    star = db.relationship("Star")
    wds_number = db.Column(db.String(10), index=True)
    common_cat_id = db.Column(db.String(20), index=True)
    components = db.Column(db.String(12))
    other_designation = db.Column(db.Text)
    norm_other_designation = db.Column(db.Text)
    pos_angle = db.Column(db.Integer)
    separation = db.Column(db.Float)
    mag_first = db.Column(db.Float)
    mag_second = db.Column(db.Float)
    delta_mag = db.Column(db.Float)
    spectral_type = db.Column(db.String(20))
    constellation_id = db.Column(db.Integer, db.ForeignKey('constellations.id'))
    constellation = db.relationship("Constellation")
    ra_first = db.Column(db.Float)
    dec_first = db.Column(db.Float)

    def get_common_name(self):
        if self.other_designation:
            return self.other_designation
        if self.common_cat_id:
            return self.common_cat_id
        return self.wds_number

    def get_common_norm_name(self):
        if self.norm_other_designation:
            for name in self.norm_other_designation.split(';'):
                if name:
                    return name
        return self.common_cat_id

    def ra_first_str_short(self):
        return ra_to_str_short(self.ra_first)

    def dec_first_str_short(self):
        return dec_to_str_short(self.dec_first)

    def ra_second_str_short(self):
        return ra_to_str_short(self.ra_second)

    def dec_second_str_short(self):
        return dec_to_str_short(self.dec_second)

    def ra_first_str(self):
        return ra_to_str(self.ra_first)

    def dec_first_str(self):
        return dec_to_str(self.dec_first)

    def get_constellation_iau_code(self):
        if self.constellation_id:
            return Constellation.get_constellation_by_id(self.constellation_id).iau_code
        return ''


class UserDoubleStarDescription(db.Model):
    __tablename__ = 'user_double_star_descriptions'
    id = db.Column(db.Integer, primary_key=True)
    double_star_id = db.Column(db.Integer, db.ForeignKey('double_stars.id'), nullable=False, index=True)
    double_star = db.relationship("DoubleStar")
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer)
    lang_code = db.Column(db.String(2))
    common_name = db.Column(db.String(256))
    text = db.Column(db.Text)
    references = db.Column(db.Text)
    cons_order = db.Column(db.Integer) # TODO: remove
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

    def rating_to_int(self, m):
        return int(round(self.rating * m / 10)) if self.rating else m//2

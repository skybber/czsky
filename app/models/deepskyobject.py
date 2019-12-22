from datetime import datetime

from .. import db
from skyfield.units import Angle
from .catalogue import Catalogue

from app.commons.dso_utils import normalize_dso_name, denormalize_dso_name
browsing_catalogues = ('M', 'Abell', 'VIC')

class DeepskyObject(db.Model):
    __tablename__ = 'deepsky_objects'
    id = db.Column(db.Integer, primary_key=True)
    master_id = db.Column(db.Integer, db.ForeignKey('deepsky_objects.id'))
    name = db.Column(db.String(32), index=True)
    type = db.Column(db.String(8))
    ra = db.Column(db.Float, index=True)
    dec = db.Column(db.Float, index=True)
    constellation_id = db.Column(db.Integer, db.ForeignKey('constellations.id'))
    catalogue_id = db.Column(db.Integer, db.ForeignKey('catalogues.id'))
    major_axis = db.Column(db.Float)
    minor_axis = db.Column(db.Float)
    positon_angle = db.Column(db.Float)
    b_mag = db.Column(db.Float)
    v_mag = db.Column(db.Float)
    j_mag = db.Column(db.Float)
    h_mag = db.Column(db.Float)
    k_mag = db.Column(db.Float)
    surface_bright = db.Column(db.Float)
    hubble_type = db.Column(db.String(16))
    c_star_u_mag = db.Column(db.Float)
    c_star_b_mag = db.Column(db.Float)
    c_star_v_mag = db.Column(db.Float)
    identifiers = db.Column(db.Text)
    common_name = db.Column(db.String(256))
    descr = db.Column(db.Text)

    _browsing_catalogue_map = None

    def denormalized_name(self):
        return denormalize_dso_name(self.name)

    def ra_str(self):
        if self.ra:
            return '%02d:%02d:%04.1f' % Angle(radians=self.ra).hms(warn=False)
        return 'nan'

    def dec_str(self):
        if self.ra:
            sgn, d, m, s = Angle(radians=self.dec).signed_dms(warn=False)
            sign = '-' if sgn < 0.0 else '+'
            return '%s%02d:%02d:%04.1f' % (sign, d, m, s)
        return 'nan'

    def ra_str_short(self):
        if self.ra:
            return '%02d:%02d:%02d' % Angle(radians=self.ra).hms(warn=False)
        return 'nan'

    def dec_str_short(self):
        if self.ra:
            sgn, d, m, s = Angle(radians=self.dec).signed_dms(warn=False)
            sign = '-' if sgn < 0.0 else '+'
            return '%s%02d:%02d:%02d' % (sign, d, m, s)
        return 'nan'

    def get_prev_next_dso(self):
        prev_dso = None
        next_dso = None
        catalogue = DeepskyObject.get_browsing_catalogue_map().get(self.catalogue_id)
        if catalogue:
            dso_id = int(self.name[len(catalogue.code):])
            if dso_id > 0:
                prev_name = normalize_dso_name(catalogue.code + str(dso_id - 1))
                prev_dso = DeepskyObject.query.filter_by(name=prev_name).first()
            next_name = normalize_dso_name(catalogue.code + str(dso_id + 1))
            next_dso = DeepskyObject.query.filter_by(name=next_name).first()
        return prev_dso, next_dso

    def get_constellation_iau_code(self):
        if self.constellation:
            return self.constellation.iau_code
        return ''

    @classmethod
    def get_browsing_catalogue_map(cls):
        if not DeepskyObject._browsing_catalogue_map:
            DeepskyObject._browsing_catalogue_map = {}
            for ccode in browsing_catalogues:
                catalogue = Catalogue.get_catalogue_by_code(ccode)
                DeepskyObject._browsing_catalogue_map[catalogue.id] = catalogue
        return DeepskyObject._browsing_catalogue_map

class UserDsoDescription(db.Model):
    __tablename__ = 'user_dso_descriptions'
    id = db.Column(db.Integer, primary_key=True)
    dso_id = db.Column(db.Integer, db.ForeignKey('deepsky_objects.id'), nullable=False)
    deepSkyObject = db.relationship("DeepskyObject")
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer)
    lang_code = db.Column(db.String(2))
    common_name = db.Column(db.String(256))
    text = db.Column(db.Text)
    cons_order = db.Column(db.Integer) # description order in constellation
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

    def rating_to_int(self, m):
        return int(round(self.rating * m / 10))

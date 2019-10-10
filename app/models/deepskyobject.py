import re
from .constellation import Constellation
from .catalogue import Catalogue
from .. import db

class DeepSkyObject(db.Model):
    __tablename__ = 'deep_sky_objects'
    id = db.Column(db.Integer, primary_key=True)
    master_id = db.Column(db.Integer, db.ForeignKey('deep_sky_objects.id'))
    name = db.Column(db.String(32), index=True)
    type = db.Column(db.String(8))
    ra = db.Column(db.String(32))
    dec = db.Column(db.String(32))
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

    def denormalized_name(self):
        zero_index = self.name.find('0')	
        norm = None
        if zero_index < 0 or self.name[zero_index-1].isdigit():
            norm = self.name
        else:
            last_zero_index = zero_index
            while self.name[last_zero_index+1] == '0':
                last_zero_index += 1
            norm = self.name[:zero_index] + self.name[last_zero_index+1:]
        if norm.startswith('SH-1'):
            return norm
        m = re.search("\d", norm)
        return norm[:m.start()] + ' ' + norm[m.start():] if m else norm

class UserDsoDescription(db.Model):
    __tablename__ = 'user_dso_descriptions'
    id = db.Column(db.Integer, primary_key=True)
    dso_id = db.Column(db.Integer, db.ForeignKey('deep_sky_objects.id'), nullable=False)
    deepSkyObject = db.relationship("DeepSkyObject")
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer)
    lang_code = db.Column(db.String(2))
    common_name = db.Column(db.String(256))
    text = db.Column(db.Text)
    cons_order = db.Column(db.Integer) # description order in constellation

    def rating_to_int(self, m):
        return int(round(self.rating * m / 10))


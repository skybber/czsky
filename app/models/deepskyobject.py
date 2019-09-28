from .constellation import Constellation
from .catalogue import Catalogue
from .. import db

class DeepSkyObject(db.Model):
    __tablename__ = 'deep_sky_objects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), index=True)
    type = db.Column(db.String(8))
    ra = db.Column(db.String(32))
    dec = db.Column(db.String(32))
    constellation_id = db.Column(db.Integer, db.ForeignKey('constellations.id'))
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


class DsoCatalogueLink(db.Model):
    __tablename__ = 'dso_catalogue_links'
    catalogue_id = db.Column(db.Integer, db.ForeignKey('catalogues.id'), primary_key=True, nullable=False)
    dso_id = db.Column(db.Integer, db.ForeignKey('deep_sky_objects.id'), primary_key=True, nullable=False)
    name = db.Column(db.String(64))

class UserDsoDescription(db.Model):
    __tablename__ = 'user_dso_description'
    id = db.Column(db.Integer, primary_key=True)
    dso_id = db.Column(db.Integer, db.ForeignKey('deep_sky_objects.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer)
    text = db.Column(db.Text)
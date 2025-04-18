import re
from datetime import datetime

from .. import db
from .catalogue import Catalogue

from app.commons.dso_utils import normalize_dso_name, denormalize_dso_name, normalize_dso_name_for_img, destructuralize_dso_name, main_component_dso_name, dso_name_to_simbad_id
from app.commons.coordinates import ra_to_str_short, dec_to_str_short, ra_to_str, dec_to_str

from .constellation import Constellation

BROWSING_CATALOGS = ('M', 'Abell', 'Sh2', 'VIC', 'NGC', 'HCG', 'Pal')

ALL_APERTURE_DESCRIPTIONS = ('Naked-eye', '<100', '100/150', '200/250', '300/350', '400/500', '600/800', '900/1200', '110/660')

SHOWN_APERTURE_DESCRIPTIONS = ('Naked-eye', '<100', '100/150', '200/250', '300/350', '400/500', '600/800', '900/1200')

IMPORT_SOURCE_HNSKY = 1
IMPORT_SOURCE_PGC = 2
IMPORT_SOURCE_COLLINDER = 3
IMPORT_SOURCE_HNSKY_SUPPLEMENT = 4

IMPORT_SOURCE_SIMBAD = 1000


class DeepskyObject(db.Model):
    __tablename__ = 'deepsky_objects'
    id = db.Column(db.Integer, primary_key=True)
    master_id = db.Column(db.Integer, db.ForeignKey('deepsky_objects.id'))
    master_dso = db.relationship("DeepskyObject", remote_side=[id], lazy=True)
    name = db.Column(db.String(32), index=True)
    type = db.Column(db.String(8))
    subtype = db.Column(db.String(16))
    ra = db.Column(db.Float, index=True)
    dec = db.Column(db.Float, index=True)
    constellation_id = db.Column(db.Integer, db.ForeignKey('constellations.id'))
    catalogue_id = db.Column(db.Integer, db.ForeignKey('catalogues.id'))
    major_axis = db.Column(db.Float)
    minor_axis = db.Column(db.Float)
    axis_ratio = db.Column(db.Float)
    position_angle = db.Column(db.Float)
    mag = db.Column(db.Float)
    surface_bright = db.Column(db.Float)
    c_star_b_mag = db.Column(db.Float)
    c_star_v_mag = db.Column(db.Float)
    distance = db.Column(db.Float)
    common_name = db.Column(db.String(256))
    descr = db.Column(db.Text)
    import_source = db.Column(db.Integer)

    _browsing_catalogue_map = None

    def denormalized_name(self):
        return denormalize_dso_name(self.name)

    def normalized_name_for_img(self):
        return normalize_dso_name_for_img(self.name)

    def simbad_id(self):
        return dso_name_to_simbad_id(self.name)

    def catalog_number(self):
        return destructuralize_dso_name(self.name)[1]

    def ra_str(self):
        return ra_to_str(self.ra)

    def dec_str(self):
        return dec_to_str(self.dec)

    def ra_str_short(self):
        return ra_to_str_short(self.ra)

    def dec_str_short(self):
        return dec_to_str_short(self.dec)

    def get_prev_next_dso(self):
        prev_dso = None
        next_dso = None
        catalogue = DeepskyObject.get_browsing_catalogue_map().get(self.catalogue_id)
        if catalogue:
            main_component_name = main_component_dso_name(self.name)
            in_cat_name = main_component_name[catalogue.prefix_len():]
            dso_id = int(re.findall('\\d+', in_cat_name)[0])
            prev_dso = self._get_by_catcode_and_id(catalogue.get_prefix(), dso_id-1)
            if not prev_dso:
                prev_dso = self._get_by_catcode_and_id(catalogue.get_prefix(), dso_id-2)
            next_dso = self._get_by_catcode_and_id(catalogue.get_prefix(), dso_id+1)
            if not next_dso:
                next_dso = self._get_by_catcode_and_id(catalogue.get_prefix(), dso_id+2)
        return prev_dso, next_dso

    def _get_by_catcode_and_id(self, cat_prefix, dso_id):
        if dso_id <= 0:
            return None
        dso_name = normalize_dso_name(cat_prefix + str(dso_id))
        return DeepskyObject.query.filter_by(name=dso_name).first()

    def get_constellation_iau_code(self):
        if self.constellation_id:
            return Constellation.get_constellation_by_id(self.constellation_id).iau_code
        return ''

    @classmethod
    def get_browsing_catalogue_map(cls):
        if not DeepskyObject._browsing_catalogue_map:
            DeepskyObject._browsing_catalogue_map = {}
            for ccode in BROWSING_CATALOGS:
                catalogue = Catalogue.get_catalogue_by_code(ccode)
                DeepskyObject._browsing_catalogue_map[catalogue.id] = catalogue
        return DeepskyObject._browsing_catalogue_map


class UserDsoDescription(db.Model):
    __tablename__ = 'user_dso_descriptions'
    id = db.Column(db.Integer, primary_key=True)
    dso_id = db.Column(db.Integer, db.ForeignKey('deepsky_objects.id'), nullable=False, index=True)
    deepsky_object = db.relationship("DeepskyObject")
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


class UserDsoApertureDescription(db.Model):
    __tablename__ = 'user_dso_aperture_descriptions'
    id = db.Column(db.Integer, primary_key=True)
    dso_id = db.Column(db.Integer, db.ForeignKey('deepsky_objects.id'), nullable=False, index=True)
    deepsky_object = db.relationship("DeepskyObject")
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer)
    lang_code = db.Column(db.String(2))
    aperture_class = db.Column(db.String(32))
    text = db.Column(db.Text)
    is_public = db.Column(db.Boolean, default=False)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

    def rating_to_int(self, m):
        return int(round(self.rating * m / 10))

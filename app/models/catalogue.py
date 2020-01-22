from .. import db


class Catalogue(db.Model):
    __tablename__ = 'catalogues'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True)
    name = db.Column(db.String(128))
    descr = db.Column(db.Text)

    _catalog_code_map = None
    _catalog_id_map = None

    @classmethod
    def _load_catalogue_maps(cls):
        Catalogue._catalog_code_map = {}
        Catalogue._catalog_id_map = {}
        for c in Catalogue.query.all():
            db.session.expunge(c)
            Catalogue._catalog_code_map[c.code] = c
            Catalogue._catalog_id_map[c.id] = c

    def prefix_len(self):
        if self.code == 'SH2':
            return len(self.code) + 1 # prefix is 'Sh2-'
        return len(self.code)

    def get_prefix(self):
        if self.code == 'SH2':
            return self.code + '-'
        return self.code


    @classmethod
    def get_catalogue_by_code(cls, code):
        if not Catalogue._catalog_id_map:
            Catalogue._load_catalogue_maps()
        return Catalogue._catalog_code_map.get(code, None)

    @classmethod
    def get_catalogue_by_id(cls, id):
        if not Catalogue._catalog_id_map:
            Catalogue._load_catalogue_maps()
        return Catalogue._catalog_code_map.get(id, None)

    @classmethod
    def get_catalogue_id_by_cat_code(cls, code):
        c = Catalogue.get_catalogue_by_code(code)
        return c.id if c else None

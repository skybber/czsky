from .. import db

class Catalogue(db.Model):
    __tablename__ = 'catalogues'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True)
    name = db.Column(db.String(128))
    descr = db.Column(db.Text)

    _catalog_id_map = None

    @classmethod
    def get_catalogue_id(cls, code):
        if code is None:
            return None
        if not Catalogue._catalog_id_map:
            Catalogue._catalog_id_map = {}
            for c in Catalogue.query.all():
                Catalogue._catalog_id_map[c.code] = c.id
        return Catalogue._catalog_id_map.get(code, None)

from .. import db

class Catalogue(db.Model):
    __tablename__ = 'catalogues'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True)
    name = db.Column(db.String(128))
    descr = db.Column(db.Text)

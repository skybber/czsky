from .. import db

class Constellation(db.Model):
    __tablename__ = 'constellations'
    id = db.Column(db.Integer, primary_key=True)
    iau_code = db.Column(db.String(3), unique=True)
    name = db.Column(db.String(64), unique=True)
    descr = db.Column(db.Text)
    image = db.Column(db.String(256))
    deep_sky_objects = db.relationship('DeepSkyObject', backref='constellation', lazy=True)

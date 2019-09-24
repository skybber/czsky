from .. import db

class Location(db.Model):
    __tablename__ = 'locations'
    id = db.Column(db.Integer, primary_key=True)
    longitude = db.Column(db.Float, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    descr = db.Column(db.Text)
    bortle = db.Column(db.Float)
    # sql_readings = db.relationship('SqlReading', backref='location', lazy=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    is_public = db.Column(db.Boolean)

from . import Constellation
from . import Catalogue
from .. import db

class UserDsoDescription(db.Model):
    __tablename__ = 'user_dso_description'
    id = db.Column(db.Integer, primary_key=True)
    dso_id = db.Column(db.Integer, db.ForeignKey('deep_sky_objects.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer)
    notes = db.Column(db.Text)

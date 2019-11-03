from datetime import datetime

from .. import db

class UserStarDescription(db.Model):
    __tablename__ = 'user_star_descriptions'
    id = db.Column(db.Integer, primary_key=True)
    constellation_id = db.Column(db.Integer, db.ForeignKey('constellations.id'), nullable=False)
    constellation = db.relationship("Constellation")
    common_name = db.Column(db.String(256), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    lang_code = db.Column(db.String(2))
    text = db.Column(db.Text)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

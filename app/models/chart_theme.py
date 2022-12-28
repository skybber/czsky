from datetime import datetime

from .. import db


class ChartTheme(db.Model):
    __tablename__ = 'chart_themes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), index=True)
    definition = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

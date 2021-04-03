from datetime import datetime

from .. import db

class News(db.Model):
    __tablename__ = 'news'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128), nullable=False, index=True)
    ra = db.Column(db.Float, index=True)
    dec = db.Column(db.Float, index=True)
    dso_id = db.Column(db.Integer, db.ForeignKey('deepsky_objects.id'), nullable=True)
    deepskyObject = db.relationship("DeepskyObject")
    title_row = db.Column(db.Text)
    text = db.Column(db.Text)
    rating = db.Column(db.Integer)
    is_released = db.Column(db.Boolean)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

    def rating_to_int(self, m):
        return int(round(self.rating * m / 10))

from datetime import datetime

from .. import db


class News(db.Model):
    __tablename__ = 'news'
    id = db.Column(db.Integer, primary_key=True)
    lang_code = db.Column(db.String(6), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    ra = db.Column(db.Float)
    dec = db.Column(db.Float)
    title_row = db.Column(db.Text)
    text = db.Column(db.Text)
    rating = db.Column(db.Integer)
    is_released = db.Column(db.Boolean, index=True)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

    def rating_to_int(self, m):
        return int(round(self.rating * m / 10))

    def has_position(self):
        return (self.ra is not None) and (self.dec is not None)
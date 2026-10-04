from datetime import datetime

from .. import db


class ChartDrawing(db.Model):
    """Named set of user drawings (polylines, polygons, points) shown on the chart.

    ``definition`` holds the JSON format produced by the chart drawing tool,
    see app/commons/chart_drawings.py.
    """
    __tablename__ = 'chart_drawings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    description = db.Column(db.Text)
    definition = db.Column(db.Text, nullable=False)
    item_count = db.Column(db.Integer, nullable=False, default=0)
    center_ra = db.Column(db.Float)
    center_dec = db.Column(db.Float)
    fld_size = db.Column(db.Float)
    is_public = db.Column(db.Boolean, nullable=False, default=False)
    create_date = db.Column(db.DateTime, default=datetime.now)
    update_date = db.Column(db.DateTime, default=datetime.now)

    user = db.relationship('User')

    def is_readable_by(self, user):
        return self.is_public or self.is_owned_by(user)

    def is_owned_by(self, user):
        return user is not None and user.is_authenticated and user.id == self.user_id

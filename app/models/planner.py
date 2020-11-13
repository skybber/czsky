from datetime import datetime

from .. import db

from .skylist import SkyListItem

class SessionPlan(db.Model):
    __tablename__ = 'session_plans'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(256), index=True, nullable=False)
    notes = db.Column(db.Text)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    location = db.relationship("Location")
    for_date = db.Column(db.DateTime, default=datetime.now())
    sky_list_id = db.Column(db.Integer, db.ForeignKey('sky_lists.id'), nullable=False)
    sky_list = db.relationship("SkyList")
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

    def append_deepsky_object(self, dso_id, user_id):
        if not self.sky_list.find_dso_in_skylist(dso_id):
            new_item = self.create_new_sky_list_item(self.sky_list_id, dso_id, user_id)
            db.session.add(new_item)
            db.session.commit()
            return True
        return False

    def create_new_sky_list_item(self, sky_list_id, dso_id, user_id):
        max = db.session.query(db.func.max(SkyListItem.order)).filter_by(sky_list_id=sky_list_id).scalar()
        if not max:
            max = 0
        new_item = SkyListItem(
            sky_list_id = sky_list_id,
            dso_id = dso_id,
            order = max + 1,
            notes = '',
            create_by = user_id,
            update_by = user_id,
            create_date = datetime.now(),
            update_date = datetime.now(),
            )
        return new_item

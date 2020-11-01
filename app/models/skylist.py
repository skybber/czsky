from datetime import datetime

from .. import db

DEFAULT_ORDER = 100000

class SkyList(db.Model):
    __tablename__ = 'sky_lists'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(256), index=True)
    notes = db.Column(db.Text)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())
    sky_list_items = db.relationship('SkyListItem', backref='sky_list', lazy=True)

    def find_dso_in_skylist(self, dso_id):
        for item in self.sky_list_items:
            if item.deepskyObject and item.deepskyObject.id == dso_id:
                return item
        return None

    def get_prev_next_item(self, dso_id):
        sorted_list = sorted(self.sky_list_items, key=lambda x: x.order if x.order != DEFAULT_ORDER else x.id)
        for i, item in enumerate(sorted_list):
            if item.dso_id == dso_id:
                prev_item = sorted_list[i-1] if i > 0 else None
                next_item = sorted_list[i+1] if i < len(sorted_list) - 1 else None
                return prev_item, next_item
        return None, None

class SkyListItem(db.Model):
    __tablename__ = 'sky_list_items'
    id = db.Column(db.Integer, primary_key=True)
    sky_list_id = db.Column(db.Integer, db.ForeignKey('sky_lists.id'), nullable=False)
    dso_id = db.Column(db.Integer, db.ForeignKey('deepsky_objects.id'))
    deepskyObject = db.relationship("DeepskyObject")
    order = db.Column(db.Integer, default=DEFAULT_ORDER)
    notes = db.Column(db.Text)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

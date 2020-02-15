from datetime import datetime

from .. import db

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

    def find_dso_in_skylist(self, dso_name):
        for item in self.sky_list_items:
            if item.deepskyObject and item.deepskyObject.name == dso_name:
                return item
        return None

class SkyListItem(db.Model):
    __tablename__ = 'sky_list_items'
    id = db.Column(db.Integer, primary_key=True)
    sky_list_id = db.Column(db.Integer, db.ForeignKey('sky_lists.id'), nullable=False)
    dso_id = db.Column(db.Integer, db.ForeignKey('deepsky_objects.id'))
    deepskyObject = db.relationship("DeepskyObject")
    order = db.Column(db.Integer, default=100000)
    notes = db.Column(db.Text)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

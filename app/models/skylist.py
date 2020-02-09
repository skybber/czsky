from .. import db

class SkyList(db.Model):
    __tablename__ = 'sky_list'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(256), index=True)
    text = db.Column(db.Text)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

class SkyListItem(db.Model):
    __tablename__ = 'sky_list_item'
    id = db.Column(db.Integer, primary_key=True)
    sky_list_id = db.Column(db.Integer, db.ForeignKey('sky_list.id'), nullable=False)
    sky_list = db.relationship("SkyList")
    dso_id = db.Column(db.Integer, db.ForeignKey('deepsky_objects.id'))
    deepSkyObject = db.relationship("DeepskyObject")
    order = db.Column(db.Integer, default=100000)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

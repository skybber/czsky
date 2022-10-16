from datetime import datetime
from sqlalchemy import Index

from .. import db


class DsoList(db.Model):
    __tablename__ = 'dso_lists'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), index=True)
    long_name = db.Column(db.String(256), index=True)
    show_common_name = db.Column(db.Boolean, default=True)
    show_descr_name = db.Column(db.Boolean, default=False)
    show_dso_type = db.Column(db.Boolean, default=False)
    show_angular_size = db.Column(db.Boolean, default=True)
    show_minor_axis = db.Column(db.Boolean, default=True)
    show_distance = db.Column(db.Boolean, default=False)
    hidden = db.Column(db.Boolean, default=False)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())
    dso_list_items = db.relationship('DsoListItem', backref='dso_list', lazy=True, cascade="delete, delete-orphan")
    dso_list_descriptions = db.relationship('DsoListDescription', backref='dso_list', lazy=True, cascade="delete, delete-orphan")

    def get_descr_by_lang_code(self, lang_code):
        for descr in self.dso_list_descriptions:
            if descr.lang_code == lang_code:
                return descr
        return None


class DsoListDescription(db.Model):
    __tablename__ = 'dso_list_descriptions'
    id = db.Column(db.Integer, primary_key=True)
    dso_list_id = db.Column(db.Integer, db.ForeignKey('dso_lists.id'), nullable=False)
    long_name = db.Column(db.String(256), index=True)
    short_descr = db.Column(db.String(256))
    lang_code = db.Column(db.String(2), nullable=False)
    text = db.Column(db.Text)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())


class DsoListItem(db.Model):
    __tablename__ = 'dso_list_items'
    id = db.Column(db.Integer, primary_key=True)
    dso_list_id = db.Column(db.Integer, db.ForeignKey('dso_lists.id'), nullable=False, index=True)
    dso_id = db.Column(db.Integer, db.ForeignKey('deepsky_objects.id'), nullable=False)
    item_id = db.Column(db.Integer, nullable=False)
    deepsky_object = db.relationship("DeepskyObject")
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())


Index('dso_list_item_index', DsoListItem.dso_list_id, DsoListItem.item_id)
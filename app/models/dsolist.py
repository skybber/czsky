from datetime import datetime
from sqlalchemy import Index

from .. import db

class DsoList(db.Model):
    __tablename__ = 'dso_lists'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), index=True)
    show_descr_name = db.Column(db.Boolean, default=False)
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

    def get_prev_next_item(self, dso_id):
        sorted_list = sorted(self.dso_list_items, key=lambda x: x.item_id)
        for i, item in enumerate(sorted_list):
            if item.dso_id == dso_id:
                prev_item = sorted_list[i-1] if i > 0 else None
                next_item = sorted_list[i+1] if i < len(sorted_list) - 1 else None
                return prev_item, next_item
        return None, None

class DsoListDescription(db.Model):
    __tablename__ = 'dso_list_descriptions'
    id = db.Column(db.Integer, primary_key=True)
    dso_list_id = db.Column(db.Integer, db.ForeignKey('dso_lists.id'), nullable=False)
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
    dso_list_id = db.Column(db.Integer, db.ForeignKey('dso_lists.id'), nullable=False)
    dso_id = db.Column(db.Integer, db.ForeignKey('deepsky_objects.id'), nullable=False)
    item_id = db.Column(db.Integer, nullable=False)
    deepskyObject = db.relationship("DeepskyObject")
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())

Index('dso_list_item_index', DsoListItem.dso_list_id, DsoListItem.item_id)
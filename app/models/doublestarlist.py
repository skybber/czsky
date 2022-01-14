from datetime import datetime
from sqlalchemy import Index

from .. import db


class DoubleStarList(db.Model):
    __tablename__ = 'double_star_lists'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), index=True)
    long_name = db.Column(db.String(256), index=True)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())
    double_star_list_items = db.relationship('DoubleStarListItem', backref='double_star_list', lazy=True, cascade="delete, delete-orphan")
    double_star_list_descriptions = db.relationship('DoubleStarListDescription', backref='double_star_list', lazy=True, cascade="delete, delete-orphan")

    def get_descr_by_lang_code(self, lang_code):
        for descr in self.double_star_list_descriptions:
            if descr.lang_code == lang_code:
                return descr
        return None

    def get_prev_next_item(self, star_id, constell_ids):
        sorted_list = sorted(self.double_star_list_items, key=lambda x: x.item_id)
        for i, item in enumerate(sorted_list):
            if item.star_id == star_id:
                for prev_item in reversed(sorted_list[0:i]):
                    if constell_ids is None or prev_item.star.constellation_id in constell_ids:
                        break
                else:
                    prev_item = None
                for next_item in sorted_list[i+1:]:
                    if constell_ids is None or next_item.star.constellation_id in constell_ids:
                        break
                else:
                    next_item = None
                return prev_item, next_item
        return None, None


class DoubleStarListDescription(db.Model):
    __tablename__ = 'double_star_list_descriptions'
    id = db.Column(db.Integer, primary_key=True)
    double_star_list_id = db.Column(db.Integer, db.ForeignKey('double_star_lists.id'), nullable=False)
    long_name = db.Column(db.String(256), index=True)
    short_descr = db.Column(db.String(256))
    lang_code = db.Column(db.String(2), nullable=False)
    text = db.Column(db.Text)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())


class DoubleStarListItem(db.Model):
    __tablename__ = 'double_star_list_items'
    id = db.Column(db.Integer, primary_key=True)
    double_star_list_id = db.Column(db.Integer, db.ForeignKey('double_star_lists.id'), nullable=False)
    star_id = db.Column(db.Integer, db.ForeignKey('stars.id'), nullable=False)
    item_id = db.Column(db.Integer, nullable=False)
    star = db.relationship("Star")
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())


Index('double_star_list_item_index', DoubleStarListItem.double_star_list_id, DoubleStarListItem.item_id)



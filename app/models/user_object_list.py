from enum import Enum
import sqlalchemy
from datetime import datetime
from flask import url_for

from .. import db


class UserObjectList(db.Model):
    __tablename__ = 'user_object_lists'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(256), index=True)
    text = db.Column(db.Text)
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    create_date = db.Column(db.DateTime, default=datetime.now)
    update_date = db.Column(db.DateTime, default=datetime.now)

    list_items = db.relationship('UserObjectListItem', backref='user_object_list', lazy=True)

    def create_new_dso_item(self, dso_id):
        item = UserObjectListItem(
            user_object_list_id=self.id,
            item_type=UserObjectListItemType.DSO,
            dso_id=dso_id,
        )
        return item

    def create_new_star_item(self, star_id):
        item = UserObjectListItem(
            user_object_list_id=self.id,
            item_type=UserObjectListItemType.STAR,
            star_id=star_id,
        )
        return item

    def create_new_double_star_item(self, double_star_id):
        item = UserObjectListItem(
            user_object_list_id=self.id,
            item_type=UserObjectListItemType.DOUBLE_STAR,
            double_star_id=double_star_id,
        )
        return item

    def create_new_comet_item(self, comet_id):
        item = UserObjectListItem(
            user_object_list_id=self.id,
            item_type=UserObjectListItemType.COMET,
            comet_id=comet_id,
        )
        return item

    def create_new_minor_planet_item(self, minor_planet_id):
        item = UserObjectListItem(
            user_object_list_id=self.id,
            item_type=UserObjectListItemType.MINOR_PLANET,
            minor_planet_id=minor_planet_id,
        )
        return item


dso_user_object_list_item_association_table = db.Table('user_object_list_item_dsos', db.Model.metadata,
                                             db.Column('user_object_list_item_id', db.Integer, db.ForeignKey('user_object_list_items.id')),
                                             db.Column('dso_id', db.Integer, db.ForeignKey('deepsky_objects.id')),
                                             db.UniqueConstraint('user_object_list_item_id', 'dso_id', name='unique_user_object_list_item_dso'),
                                             )


class UserObjectListItemType(Enum):
    DSO = 'DSO'
    DBL_STAR = 'DBL_STAR'
    COMET = 'COMET'
    M_PLANET = 'M_PLANET'


class UserObjectListItem(db.Model):
    __tablename__ = 'user_object_list_items'
    id = db.Column(db.Integer, primary_key=True)

    user_object_list_id = db.Column(db.Integer, db.ForeignKey('user_object_lists.id'),
                                    nullable=False, index=True)

    item_type = db.Column(sqlalchemy.Enum(UserObjectListItemType), nullable=False)

    deepsky_objects = db.relationship("DeepskyObject", secondary=dso_user_object_list_item_association_table)
    double_star_id = db.Column(db.Integer, db.ForeignKey('double_stars.id'), nullable=True)
    comet_id = db.Column(db.Integer, db.ForeignKey('comets.id'), nullable=True)
    minor_planet_id = db.Column(db.Integer, db.ForeignKey('minor_planets.id'), nullable=True)

    double_star = db.relationship("DoubleStar")
    comet = db.relationship("Comet")
    minor_planet = db.relationship("MinorPlanet")

    text = db.Column(db.Text, nullable=True)
    order = db.Column(db.Integer)
    create_date = db.Column(db.DateTime, default=datetime.now)
    update_date = db.Column(db.DateTime, default=datetime.now)

    def get_ra(self):
        if self.target_type == UserObjectListItemType.DSO:
            return self.deepsky_objects[0].ra if len(self.deepsky_objects) > 0 else None
        if self.target_type == UserObjectListItemType.DBL_STAR:
            return self.double_star.ra_first
        if self.target_type == UserObjectListItemType.COMET:
            return self.comet.cur_ra
        if self.target_type == UserObjectListItemType.M_PLANET:
            return self.minor_planet.cur_ra
        return None

    def get_dec(self):
        if self.target_type == UserObjectListItemType.DSO:
            return self.deepsky_objects[0].dec if len(self.deepsky_objects) > 0 else None
        if self.target_type == UserObjectListItemType.DBL_STAR:
            return self.double_star.dec_first
        if self.target_type == UserObjectListItemType.COMET:
            return self.comet.cur_dec
        if self.target_type == UserObjectListItemType.M_PLANET:
            return self.minor_planet.cur_dec
        return None

    def get_item_name(self):
        if self.target_type == UserObjectListItemType.DBL_STAR and self.double_star:
            return self.double_star.get_common_norm_name()
        if self.target_type == UserObjectListItemType.COMET and self.comet:
            return self.comet.designation
        if self.target_type == UserObjectListItemType.M_PLANET and self.minor_planet:
            return self.minor_planet.designation
        if self.target_type == UserObjectListItemType.DSO and self.deepsky_objects:
            return ','.join(dso.name for dso in self.deepsky_objects)
        return ''

    def get_target_type(self):
        if self.target_type == UserObjectListItemType.DBL_STAR and self.double_star:
            return 'DBL_STAR'
        if self.target_type == UserObjectListItemType.COMET and self.comet:
            return 'COMET'
        if self.target_type == UserObjectListItemType.M_PLANET and self.minor_planet:
            return 'MINOR_PLANET'
        if self.target_type == UserObjectListItemType.DSO and self.deepsky_objects:
            dso_type = None
            for dso in self.deepsky_objects:
                if dso_type is not None and dso_type != dso.type:
                    dso_type = ''
                    break
                dso_type = dso.type
            return dso_type
        return ''

    def item_to_html(self):
        return self._targets_to_html('user_object_list', self.user_object_list_id)

    def _item_to_html(self, back, back_id):
        if self.item_type == UserObjectListItemType.DBL_STAR and self.double_star:
            return '<a class="sw-link" href="' + url_for('main_double_star.double_star_seltab', double_star_id=self.double_star_id, back=back, back_id=back_id) + '">' + self.double_star.get_common_name() + '</a>'
        if self.item_type == UserObjectListItemType.COMET and self.comet:
            return '<a class="sw-link" href="' + url_for('main_comet.comet_seltab', comet_id=self.comet.comet_id, back=back, back_id=back_id) + '">' + self.comet.designation + '</a>'
        if self.item_type == UserObjectListItemType.M_PLANET and self.minor_planet:
            return '<a href="' + url_for('main_minor_planet.minor_planet_info', minor_planet_id=self.minor_planet.int_designation, back=back, back_id=back_id) + '">' + self.minor_planet.designation + '</a>'
        formatted_dsos = []
        for dso in self.deepsky_objects:
            formatted_dsos.append('<a class="sw-link" href="' + url_for('main_deepskyobject.deepskyobject_seltab', dso_id=dso.name, back=back, back_id=back_id) + '">' + dso.denormalized_name() + '</a>')
        return ','.join(formatted_dsos)

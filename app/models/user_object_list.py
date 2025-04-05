from enum import Enum
import sqlalchemy
from datetime import datetime

from .. import db

from sqlalchemy import or_

from .deepskyobject import DeepskyObject


class TargetType(Enum):
    DSO = 'DSO'
    STAR = 'STAR'
    DOUBLE_STAR = 'DOUBLE_STAR'
    COMET = 'COMET'
    MINOR_PLANET = 'MINOR_PLANET'


class UserObjectList(db.Model):
    __tablename__ = 'user_object_lists'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    create_date = db.Column(db.DateTime, default=datetime.now)
    update_date = db.Column(db.DateTime, default=datetime.now)

    list_items = db.relationship('UserObjectListItem', backref='user_object_list', lazy=True)

    def create_new_dso_item(self, dso_id):
        item = UserObjectListItem(
            user_object_list_id=self.id,
            target_type=TargetType.DSO,
            dso_id=dso_id,
        )
        return item

    def create_new_star_item(self, star_id):
        item = UserObjectListItem(
            user_object_list_id=self.id,
            target_type=TargetType.STAR,
            star_id=star_id,
        )
        return item

    def create_new_double_star_item(self, double_star_id):
        item = UserObjectListItem(
            user_object_list_id=self.id,
            target_type=TargetType.DOUBLE_STAR,
            double_star_id=double_star_id,
        )
        return item

    def create_new_comet_item(self, comet_id):
        item = UserObjectListItem(
            user_object_list_id=self.id,
            target_type=TargetType.COMET,
            comet_id=comet_id,
        )
        return item

    def create_new_minor_planet_item(self, minor_planet_id):
        item = UserObjectListItem(
            user_object_list_id=self.id,
            target_type=TargetType.MINOR_PLANET,
            minor_planet_id=minor_planet_id,
        )
        return item


class UserObjectListItem(db.Model):
    __tablename__ = 'user_object_list_items'
    id = db.Column(db.Integer, primary_key=True)

    user_object_list_id = db.Column(db.Integer, db.ForeignKey('user_object_lists.id'),
                                    nullable=False, index=True)

    target_type = db.Column(sqlalchemy.Enum(TargetType), nullable=False)

    dso_id = db.Column(db.Integer, db.ForeignKey('deepsky_objects.id'), nullable=True)
    star_id = db.Column(db.Integer, db.ForeignKey('stars.id'), nullable=True)
    double_star_id = db.Column(db.Integer, db.ForeignKey('double_stars.id'), nullable=True)
    comet_id = db.Column(db.Integer, db.ForeignKey('comets.id'), nullable=True)
    minor_planet_id = db.Column(db.Integer, db.ForeignKey('minor_planets.id'), nullable=True)

    deepsky_object = db.relationship("DeepSkyObject")
    star = db.relationship("Star")
    double_star = db.relationship("DoubleStar")
    comet = db.relationship("Comet")
    minor_planet = db.relationship("MinorPlanet")

    notes = db.Column(db.Text, nullable=True)
    create_date = db.Column(db.DateTime, default=datetime.now)
    update_date = db.Column(db.DateTime, default=datetime.now)

    def get_ra(self):
        if self.dso_id is not None:
            return self.deepsky_object.ra
        if self.star_id is not None:
            return self.star.ra
        if self.double_star_id is not None:
            return self.double_star.ra_first
        if self.comet_id is not None:
            return self.comet.cur_ra
        if self.minor_planet_id is not None:
            return self.minor_planet.cur_ra
        return None

    def get_dec(self):
        if self.dso_id is not None:
            return self.deepsky_object.dec
        if self.star_id is not None:
            return self.star.dec
        if self.double_star_id is not None:
            return self.double_star.dec_first
        if self.comet_id is not None:
            return self.comet.cur_dec
        if self.minor_planet_id is not None:
            return self.minor_planet.cur_dec
        return None

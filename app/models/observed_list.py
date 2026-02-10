from enum import Enum
import sqlalchemy
from datetime import datetime

from .. import db

from sqlalchemy import or_

from .deepskyobject import DeepskyObject


class ObservedTargetType(Enum):
    DSO = 'DSO'
    DBL_STAR = 'DBL_STAR'
    COMET = 'COMET'
    M_PLANET = 'M_PLANET'


class ObservedList(db.Model):
    __tablename__ = 'observed_lists'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())
    observed_list_items = db.relationship('ObservedListItem', backref='observed_list', lazy=True)

    def create_new_deepsky_object_item(self, dso_id):
        new_item = ObservedListItem(
            observed_list_id=self.id,
            dso_id=dso_id,
            target_type=ObservedTargetType.DSO,
            create_date=datetime.now(),
            update_date=datetime.now(),
            )
        return new_item

    def create_new_double_star_item(self, double_star_id):
        new_item = ObservedListItem(
            observed_list_id=self.id,
            double_star_id=double_star_id,
            target_type=ObservedTargetType.DBL_STAR,
            create_date=datetime.now(),
            update_date=datetime.now(),
        )
        return new_item

    def create_new_comet_item(self, comet_id):
        new_item = ObservedListItem(
            observed_list_id=self.id,
            comet_id=comet_id,
            target_type=ObservedTargetType.COMET,
            create_date=datetime.now(),
            update_date=datetime.now(),
        )
        return new_item

    def create_new_minor_planet_item(self, minor_planet_id):
        new_item = ObservedListItem(
            observed_list_id=self.id,
            minor_planet_id=minor_planet_id,
            target_type=ObservedTargetType.M_PLANET,
            create_date=datetime.now(),
            update_date=datetime.now(),
        )
        return new_item

    def find_list_item_by_dso_id(self, dso_id):
        for item in self.observed_list_items:
            if item.target_type == ObservedTargetType.DSO and item.dso_id == dso_id:
                return item
        return None

    def find_list_item_by_double_star_id(self, double_star_id):
        for item in self.observed_list_items:
            if item.target_type == ObservedTargetType.DBL_STAR and item.double_star_id == double_star_id:
                return item
        return None

    def find_list_item_by_comet_id(self, comet_id):
        for item in self.observed_list_items:
            if item.target_type == ObservedTargetType.COMET and item.comet_id == comet_id:
                return item
        return None

    def find_list_item_by_minor_planet_id(self, minor_planet_id):
        for item in self.observed_list_items:
            if item.target_type == ObservedTargetType.M_PLANET and item.minor_planet_id == minor_planet_id:
                return item
        return None

    @staticmethod
    def create_get_observed_list_by_user_id(user_id):
        observed_list = ObservedList.query.filter_by(user_id=user_id).first()
        if not observed_list:
            observed_list = ObservedList(
                user_id=user_id,
                create_date=datetime.now(),
                update_date=datetime.now(),
                )
            db.session.add(observed_list)
            db.session.commit()
        return observed_list

    @staticmethod
    def get_observed_dsos_by_user_id(user_id):
        observed_list = ObservedList.query.filter_by(user_id=user_id).first()
        if not observed_list:
            return []
        observed_subquery = db.session.query(ObservedListItem.dso_id) \
            .join(ObservedListItem.observed_list) \
            .filter(ObservedList.id == observed_list.id, ObservedList.user_id == user_id, ObservedListItem.dso_id is not None)

        return DeepskyObject.query.filter(or_(DeepskyObject.id.in_(observed_subquery), DeepskyObject.master_id.in_(observed_subquery))).all()


class ObservedListItem(db.Model):
    __tablename__ = 'observed_list_items'
    id = db.Column(db.Integer, primary_key=True)
    observed_list_id = db.Column(db.Integer, db.ForeignKey('observed_lists.id'), nullable=False, index=True)
    target_type = db.Column(sqlalchemy.Enum(ObservedTargetType))
    dso_id = db.Column(db.Integer, db.ForeignKey('deepsky_objects.id'), nullable=True)
    deepsky_object = db.relationship("DeepskyObject")
    double_star_id = db.Column(db.Integer, db.ForeignKey('double_stars.id'), nullable=True)
    double_star = db.relationship("DoubleStar")
    comet_id = db.Column(db.Integer, db.ForeignKey('comets.id'), nullable=True)
    comet = db.relationship("Comet")
    minor_planet_id = db.Column(db.Integer, db.ForeignKey('minor_planets.id'), nullable=True)
    minor_planet = db.relationship("MinorPlanet")
    notes = db.Column(db.Text)
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

    def get_ra(self):
        if self.dso_id is not None:
            return self.deepsky_object.ra
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
        if self.double_star_id is not None:
            return self.double_star.dec_first
        if self.comet_id is not None:
            return self.comet.cur_dec
        if self.minor_planet_id is not None:
            return self.minor_planet.cur_dec
        return None

from datetime import datetime

from .. import db

from sqlalchemy import or_

from .deepskyobject import DeepskyObject


class ObservedList(db.Model):
    __tablename__ = 'observed_lists'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())
    observed_list_items = db.relationship('ObservedListItem', backref='observed_list', lazy=True)

    def create_new_deepsky_object_item(self, dso_id):
        new_item = ObservedListItem(
            observed_list_id=self.id,
            dso_id=dso_id,
            create_date=datetime.now(),
            update_date=datetime.now(),
            )
        return new_item

    def create_new_double_star_item(self, double_star_id):
        new_item = ObservedListItem(
            observed_list_id=self.id,
            double_star_id=double_star_id,
            create_date=datetime.now(),
            update_date=datetime.now(),
        )
        return new_item

    def find_list_item_by_id(self, dso_id):
        for item in self.observed_list_items:
            if item.dso_id == dso_id:
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

        observed_subquery = db.session.query(ObservedListItem.dso_id) \
            .join(ObservedListItem.observed_list) \
            .filter(ObservedList.id == observed_list.id, ObservedList.user_id == user_id, ObservedListItem.dso_id is not None)

        return DeepskyObject.query.filter(or_(DeepskyObject.id.in_(observed_subquery), DeepskyObject.master_id.in_(observed_subquery))).all()


class ObservedListItem(db.Model):
    __tablename__ = 'observed_list_items'
    id = db.Column(db.Integer, primary_key=True)
    observed_list_id = db.Column(db.Integer, db.ForeignKey('observed_lists.id'), nullable=False, index=True)
    dso_id = db.Column(db.Integer, db.ForeignKey('deepsky_objects.id'), nullable=True)
    deepsky_object = db.relationship("DeepskyObject")
    double_star_id = db.Column(db.Integer, db.ForeignKey('double_stars.id'), nullable=True)
    double_star = db.relationship("DoubleStar")
    notes = db.Column(db.Text)
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

    def get_ra(self):
        if self.dso_id is not None:
            return self.deepsky_object.ra
        if self.double_star_id is not None:
            return self.double_star.ra_first
        return None

    def get_dec(self):
        if self.dso_id is not None:
            return self.deepsky_object.dec
        if self.double_star_id is not None:
            return self.double_star.dec_first
        return None

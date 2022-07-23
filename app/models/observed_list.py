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

    def append_deepsky_object(self, dso_id, user_id):
        if not self.find_list_item_by_id(dso_id):
            self.append_new_deepsky_object(dso_id, user_id)
        return False

    def append_new_deepsky_object(self, dso_id, user_id):
        new_item = ObservedListItem(
            observed_list_id=self.id,
            dso_id=dso_id,
            create_date=datetime.now(),
            update_date=datetime.now(),
            )
        db.session.add(new_item)
        db.session.commit()
        return new_item

    def find_list_item_by_id(self, dso_id):
        for item in self.observed_list_items:
            if item.dso_id == dso_id:
                return item
        return None

    def get_prev_next_item(self, dso_id, constell_ids):
        sorted_list = sorted(self.observed_list_items, key=lambda x: x.id)
        for i, item in enumerate(sorted_list):
            if item.dso_id == dso_id:
                for prev_item in reversed(sorted_list[0:i]):
                    if constell_ids is None or prev_item.deepskyObject.constellation_id in constell_ids:
                        break
                else:
                    prev_item = None
                for next_item in sorted_list[i+1:]:
                    if constell_ids is None or next_item.deepskyObject.constellation_id in constell_ids:
                        break
                else:
                    next_item = None
                return prev_item, next_item
        return None, None

    @staticmethod
    def create_get_observed_list_by_user_id(user_id):
        observed_list = ObservedList.query.filter_by(user_id=user_id).first()
        if not observed_list:
            observed_list = ObservedList(
                user_id = user_id,
                create_date = datetime.now(),
                update_date = datetime.now(),
                )
            db.session.add(observed_list)
            db.session.commit()
        return observed_list

    @staticmethod
    def get_observed_dsos_by_user_id(user_id):
        observed_list = ObservedList.query.filter_by(user_id=user_id).first()

        observed_subquery = db.session.query(ObservedListItem.dso_id) \
            .join(ObservedListItem.observed_list) \
            .filter(ObservedList.id == observed_list.id, ObservedList.user_id == user_id)

        return DeepskyObject.query.filter(or_(DeepskyObject.id.in_(observed_subquery), DeepskyObject.master_id.in_(observed_subquery))).all()


class ObservedListItem(db.Model):
    __tablename__ = 'observed_list_items'
    id = db.Column(db.Integer, primary_key=True)
    observed_list_id = db.Column(db.Integer, db.ForeignKey('observed_lists.id'), nullable=False)
    dso_id = db.Column(db.Integer, db.ForeignKey('deepsky_objects.id'), nullable=True)
    deepskyObject = db.relationship("DeepskyObject")
    double_star_id = db.Column(db.Integer, db.ForeignKey('double_stars.id'), nullable=True)
    double_star = db.relationship("DoubleStar")
    notes = db.Column(db.Text)
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

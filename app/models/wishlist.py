from datetime import datetime

from .. import db


class WishList(db.Model):
    __tablename__ = 'wish_lists'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())
    wish_list_items = db.relationship('WishListItem', backref='wish_list', lazy=True)

    def append_deepsky_object(self, dso_id, user_id):
        if not self.find_dso_by_id(dso_id):
            self.append_new_deepsky_object(dso_id, user_id)
        return False

    def append_new_deepsky_object(self, dso_id, user_id):
        max = db.session.query(db.func.max(WishListItem.order)).filter_by(wish_list_id=self.id).scalar()
        if not max:
            max = 0
        new_item = WishListItem(
            wish_list_id=self.id,
            dso_id=dso_id,
            order=max + 1,
            create_date=datetime.now(),
            update_date=datetime.now(),
            )
        db.session.add(new_item)
        db.session.commit()
        return new_item

    def find_dso_by_id(self, dso_id):
        for item in self.wish_list_items:
            if item.deepskyObject and item.deepskyObject.id == dso_id:
                return item
        return None

    def get_prev_next_item(self, dso_id, constell_ids):
        sorted_list = sorted(self.wish_list_items, key=lambda x: x.id)
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
    def create_get_wishlist_by_user_id(user_id):
        wish_list = WishList.query.filter_by(user_id=user_id).first()
        if not wish_list:
            wish_list = WishList(
                user_id = user_id,
                create_date = datetime.now(),
                update_date = datetime.now(),
                )
            db.session.add(wish_list)
            db.session.commit()
        return wish_list


class WishListItem(db.Model):
    __tablename__ = 'wish_list_items'
    id = db.Column(db.Integer, primary_key=True)
    wish_list_id = db.Column(db.Integer, db.ForeignKey('wish_lists.id'), nullable=False)
    dso_id = db.Column(db.Integer, db.ForeignKey('deepsky_objects.id'))
    deepskyObject = db.relationship("DeepskyObject")
    double_star_id = db.Column(db.Integer, db.ForeignKey('double_stars.id'), nullable=True)
    double_star = db.relationship("DoubleStar")
    order = db.Column(db.Integer, default=100000)
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

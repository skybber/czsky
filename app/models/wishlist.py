from datetime import datetime

from .. import db


class WishList(db.Model):
    __tablename__ = 'wish_lists'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())
    wish_list_items = db.relationship('WishListItem', backref='wish_list', lazy=True)

    def _get_max_order(self):
        max = db.session.query(db.func.max(WishListItem.order)).filter_by(wish_list_id=self.id).scalar()
        return max if max else 0

    def create_new_deepsky_object_item(self, dso_id):
        new_item = WishListItem(
            wish_list_id=self.id,
            dso_id=dso_id,
            order=self._get_max_order() + 1,
            create_date=datetime.now(),
            update_date=datetime.now(),
            )
        return new_item

    def create_new_double_star_item(self, double_star_id):
        new_item = WishListItem(
            wish_list_id=self.id,
            double_star_id=double_star_id,
            order=self._get_max_order() + 1,
            create_date=datetime.now(),
            update_date=datetime.now(),
        )
        return new_item

    def find_dso_by_id(self, dso_id):
        for item in self.wish_list_items:
            if item.dso_id == dso_id:
                return item
        return None

    def find_double_star_by_id(self, double_star_id):
        for item in self.wish_list_items:
            if item.double_star_id == double_star_id:
                return item
        return None

    @staticmethod
    def create_get_wishlist_by_user_id(user_id):
        wish_list = WishList.query.filter_by(user_id=user_id).first()
        if not wish_list:
            wish_list = WishList(
                user_id=user_id,
                create_date=datetime.now(),
                update_date=datetime.now(),
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

    def get_ra(self):
        if self.dso_id is not None:
            return self.deepskyObject.ra
        if self.double_star_id is not None:
            return self.double_star.ra_first
        return None

    def get_dec(self):
        if self.dso_id is not None:
            return self.deepskyObject.dec
        if self.double_star_id is not None:
            return self.double_star.dec_first
        return None

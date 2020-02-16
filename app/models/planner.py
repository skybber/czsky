from datetime import datetime

from .. import db

from .skylist import SkyList, SkyListItem

class SessionPlan(db.Model):
    __tablename__ = 'session_plans'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(256), index=True, nullable=False)
    notes = db.Column(db.Text)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    location = db.relationship("Location")
    for_date = db.Column(db.DateTime, default=datetime.now())
    sky_list_id = db.Column(db.Integer, db.ForeignKey('sky_lists.id'), nullable=False)
    sky_list = db.relationship("SkyList")
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

    def append_deepsky_object(self, deepsky_object, user_id):
        if not self.sky_list.find_dso_in_skylist(deepsky_object.id):
            new_item = _create_new_deepsky_object(self.sky_list_id, deepsky_object, user_id)
            db.session.add(new_item)
            db.session.commit()
            return True
        return False

class WishList(db.Model):
    __tablename__ = 'wish_lists'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    sky_list_id = db.Column(db.Integer, db.ForeignKey('sky_lists.id'), nullable=False)
    sky_list = db.relationship("SkyList")
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

    def append_deepsky_object(self, deepsky_object, user_id):
        if not self.sky_list.find_dso_in_skylist(deepsky_object.id):
            new_item = _create_new_deepsky_object(self.sky_list_id, deepsky_object, user_id)
            db.session.add(new_item)
            db.session.commit()
            return True
        return False

    @staticmethod
    def create_get_wishlist_by_user_id(user_id):
        wish_list = WishList.query.filter_by(user_id=user_id).first()
        if not wish_list:
            sky_list = SkyList(
                user_id = user_id,
                name = 'WishList[user.id={}]'.format(user_id),
                notes = '',
                create_by = user_id,
                update_by = user_id,
                create_date = datetime.now(),
                update_date = datetime.now(),
                )

            wish_list = WishList(
                user_id = user_id,
                sky_list = sky_list,
                create_by = user_id,
                update_by = user_id,
                create_date = datetime.now(),
                update_date = datetime.now(),
                )
            db.session.add(wish_list)
            db.session.commit()
        return wish_list

def _create_new_deepsky_object(sky_list_id, deepsky_object, user_id):
    max = db.session.query(db.func.max(SkyListItem.order)).filter_by(sky_list_id=sky_list_id).scalar()
    if not max:
        max = 0
    new_item = SkyListItem(
        sky_list_id = sky_list_id,
        dso_id = deepsky_object.id,
        order = max + 1,
        notes = '',
        create_by = user_id,
        update_by = user_id,
        create_date = datetime.now(),
        update_date = datetime.now(),
        )
    return new_item

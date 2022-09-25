import sqlalchemy
from datetime import datetime

from .. import db

from app.commons.form_utils import FormEnum

DEFAULT_ORDER = 100000


class SessionPlan(db.Model):
    __tablename__ = 'session_plans'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(256), index=True, nullable=False)
    notes = db.Column(db.Text)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    location = db.relationship("Location")
    location_position = db.Column(db.String(256))
    for_date = db.Column(db.DateTime, default=datetime.now())
    is_anonymous = db.Column(db.Boolean, default=False, nullable=False)
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    import_history_rec_id = db.Column(db.Integer, db.ForeignKey('import_history_recs.id'), nullable=True, index=True)
    session_plan_items = db.relationship('SessionPlanItem', backref='session_plan', lazy=True)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

    def find_dso_by_id(self, dso_id):
        for item in self.session_plan_items:
            if item.dso_id == dso_id:
                return item
        return None

    def find_double_star_by_id(self, double_star_id):
        for item in self.session_plan_items:
            if item.double_star_id == double_star_id:
                return item
        return None

    def _get_max_order(self):
        max = db.session.query(db.func.max(SessionPlanItem.order)).filter_by(session_plan_id=self.id).scalar()
        return max if max else 0

    def create_new_deepsky_object_item(self, dso_id):
        new_item = SessionPlanItem(
            session_plan_id=self.id,
            item_type=SessionPlanItemType.DSO,
            dso_id=dso_id,
            order=self._get_max_order() + 1,
            create_date=datetime.now(),
            update_date=datetime.now(),
            )
        return new_item

    def create_new_double_star_item(self, double_star_id):
        new_item = SessionPlanItem(
            session_plan_id=self.id,
            item_type=SessionPlanItemType.DBL_STAR,
            double_star_id=double_star_id,
            order=self._get_max_order() + 1,
            create_date=datetime.now(),
            update_date=datetime.now(),
        )
        return new_item

    @staticmethod
    def create_get_session_plan_by_user_id(user_id):
        session_plan = SessionPlan.query.filter_by(user_id=user_id).first()
        if not session_plan:
            session_plan = SessionPlan(
                user_id = user_id,
                create_date = datetime.now(),
                update_date = datetime.now(),
                )
            db.session.add(session_plan)
            db.session.commit()
        return session_plan


class SessionPlanItemType(FormEnum):
    DSO = 'DSO'
    DBL_STAR = 'DBL_STAR'
    MINOR_PLANET = 'MINOR_PLANET'
    COMET = 'COMET'


class SessionPlanItem(db.Model):
    __tablename__ = 'session_plan_items'
    id = db.Column(db.Integer, primary_key=True)
    session_plan_id = db.Column(db.Integer, db.ForeignKey('session_plans.id'), nullable=False, index=True)
    item_type = db.Column(sqlalchemy.Enum(SessionPlanItemType))
    dso_id = db.Column(db.Integer, db.ForeignKey('deepsky_objects.id'))
    deepskyObject = db.relationship("DeepskyObject")
    double_star_id = db.Column(db.Integer, db.ForeignKey('double_stars.id'))
    double_star = db.relationship("DoubleStar")
    minor_planet_id = db.Column(db.Integer, db.ForeignKey('minor_planets.id'))
    minorPlanet = db.relationship("MinorPlanet")
    comet_id = db.Column(db.Integer, db.ForeignKey('comets.id'))
    comet = db.relationship("Comet")
    order = db.Column(db.Integer, default=DEFAULT_ORDER)
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

    def get_ra_str_short(self):
        if self.dso_id is not None:
            return self.deepskyObject.ra_str_short()
        if self.double_star_id is not None:
            return self.double_star.ra_first_str_short()
        return None

    def get_dec_str_short(self):
        if self.dso_id is not None:
            return self.deepskyObject.dec_str_short()
        if self.double_star_id is not None:
            return self.double_star.dec_first_str_short()
        return None


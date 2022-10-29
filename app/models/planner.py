import sqlalchemy
from datetime import datetime

from .. import db

from app.commons.form_utils import FormEnum
from app.commons.coordinates import ra_to_str_short, dec_to_str_short
from app.commons.solar_system_utils import get_mpc_comet_position, find_mpc_comet, get_mpc_minor_planet_position, find_mpc_minor_planet

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

    def find_dso_item_by_id(self, dso_id):
        for item in self.session_plan_items:
            if item.dso_id == dso_id:
                return item
        return None

    def find_double_star_item_by_id(self, double_star_id):
        for item in self.session_plan_items:
            if item.double_star_id == double_star_id:
                return item
        return None

    def find_comet_item_by_id(self, comet_id):
        for item in self.session_plan_items:
            if item.comet_id == comet_id:
                return item
        return None

    def find_minor_planet_item_by_id(self, minor_planet_id):
        for item in self.session_plan_items:
            if item.minor_planet_id == minor_planet_id:
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

    def create_new_comet_item(self, comet, date_time):
        ra, dec = get_mpc_comet_position(find_mpc_comet(comet.comet_id), date_time)
        new_item = SessionPlanItem(
            session_plan_id=self.id,
            item_type=SessionPlanItemType.COMET,
            comet_id=comet.id,
            ra=ra.radians,
            dec=dec.radians,
            order=self._get_max_order() + 1,
            create_date=datetime.now(),
            update_date=datetime.now(),
        )
        return new_item

    def create_new_minor_planet_item(self, minor_planet, date_time):
        ra, dec = get_mpc_minor_planet_position(find_mpc_minor_planet(minor_planet.int_designation), date_time)
        new_item = SessionPlanItem(
            session_plan_id=self.id,
            item_type=SessionPlanItemType.MINOR_PLANET,
            minor_planet_id=minor_planet.id,
            ra=ra.radians,
            dec=dec.radians,
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
    deepsky_object = db.relationship("DeepskyObject")
    double_star_id = db.Column(db.Integer, db.ForeignKey('double_stars.id'))
    double_star = db.relationship("DoubleStar")
    minor_planet_id = db.Column(db.Integer, db.ForeignKey('minor_planets.id'))
    minor_planet = db.relationship("MinorPlanet")
    comet_id = db.Column(db.Integer, db.ForeignKey('comets.id'))
    comet = db.relationship("Comet")
    ra = db.Column(db.Float, index=True)
    dec = db.Column(db.Float, index=True)
    order = db.Column(db.Integer, default=DEFAULT_ORDER)
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

    def get_ra(self):
        if self.dso_id is not None:
            return self.deepsky_object.ra
        if self.double_star_id is not None:
            return self.double_star.ra_first
        return self.ra

    def get_dec(self):
        if self.dso_id is not None:
            return self.deepsky_object.dec
        if self.double_star_id is not None:
            return self.double_star.dec_first
        return self.dec

    def get_ra_str_short(self):
        return ra_to_str_short(self.get_ra())

    def get_dec_str_short(self):
        return dec_to_str_short(self.get_dec())

    def actualize_ra_dec(self, date_time):
        ra, dec = None, None
        if self.item_type == SessionPlanItemType.COMET:
            ra, dec = get_mpc_comet_position(find_mpc_comet(self.comet.comet_id), date_time)
        elif self.item_type == SessionPlanItemType.MINOR_PLANET:
            ra, dec = get_mpc_minor_planet_position(find_mpc_minor_planet(self.minor_planet.int_designation), date_time)
        if (ra is not None) and (dec is not None):
            ra = ra.radians
            dec = dec.radians
            if (ra != self.ra) or (dec != self.dec):
                self.ra = ra
                self.dec = dec
                return True
        return False


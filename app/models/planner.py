from datetime import datetime

from .. import db

DEFAULT_ORDER = 100000

class SessionPlan(db.Model):
    __tablename__ = 'session_plans'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(256), index=True, nullable=False)
    notes = db.Column(db.Text)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'))
    location = db.relationship("Location")
    for_date = db.Column(db.DateTime, default=datetime.now())
    is_anonymous = db.Column(db.Boolean, default=False)
    session_plan_items = db.relationship('SessionPlanItem', backref='session_plan', lazy=True)
    create_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    update_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())


    def find_dso_by_id(self, dso_id):
        for item in self.session_plan_items:
            if item.deepskyObject and item.deepskyObject.id == dso_id:
                return item
        return None


    def create_new_session_plan_item(self, dso_id, user_id):
        max = db.session.query(db.func.max(SessionPlanItem.order)).filter_by(session_plan_id=self.id).scalar()
        if not max:
            max = 0
        new_item = SessionPlanItem(
            session_plan_id = self.id,
            dso_id = dso_id,
            order = max + 1,
            create_date = datetime.now(),
            update_date = datetime.now(),
            )
        return new_item


    def get_prev_next_item(self, dso_id, constell_ids):
        sorted_list = sorted(self.session_plan_items, key=lambda x: x.id)
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
        return wish_list


class SessionPlanItem(db.Model):
    __tablename__ = 'session_plan_items'
    id = db.Column(db.Integer, primary_key=True)
    session_plan_id = db.Column(db.Integer, db.ForeignKey('session_plans.id'), nullable=False)
    dso_id = db.Column(db.Integer, db.ForeignKey('deepsky_objects.id'))
    deepskyObject = db.relationship("DeepskyObject")
    order = db.Column(db.Integer, default=DEFAULT_ORDER)
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

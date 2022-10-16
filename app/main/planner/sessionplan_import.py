from datetime import datetime
from sqlalchemy import and_, or_

from flask_babel import lazy_gettext

from app import db

from app.commons.coordinates import parse_latlon
from app.commons.dso_utils import normalize_dso_name_ext

from app.models import Location, SessionPlan, SessionPlanItem, DeepskyObject, User
from app.models import Telescope, Eyepiece, Lens, Filter, TelescopeType, FilterType, Seeing, SessionPlanItemType
from app.commons.openastronomylog import parse


def import_session_plan_items(session_plan, file):
    log_warn = []
    log_error = []

    oal_observations = parse(file, silence=True)

    # Locations
    oal_sites = oal_observations.get_sites()
    found_locations = {}
    add_hoc_locations = {}
    if oal_sites and oal_sites.get_site():
        for oal_site in oal_sites.get_site():
            location = None
            if oal_site.get_name():
                location = Location.query.filter_by(name=oal_site.get_name()).first()
            if location is None:
                add_hoc_locations[oal_site.name] = (oal_site.get_latitude(), oal_site.get_longitude())
                log_warn.append(lazy_gettext('OAL Location "{}" not found').format(oal_site.get_name()))
            else:
                found_locations[oal_site.get_id()] = location

    # Targets
    oal_targets = oal_observations.get_targets()
    item_order = 0
    existing_dsos = {}
    for session_plan_item in session_plan.session_plan_items:
        if session_plan_item.deepsky_object:
            existing_dsos[session_plan_item.deepsky_object.id] = session_plan_item.deepsky_object
        if session_plan_item.order >= item_order:
            item_order = session_plan_item.order + 1

    if oal_targets and oal_targets.get_target():
        for target in oal_targets.get_target():
            normalized_name = normalize_dso_name_ext(target.get_name())
            dso = DeepskyObject.query.filter_by(name=normalized_name).first()
            if dso:
                if dso.id not in existing_dsos:
                    existing_dsos[dso.id] = dso
                    session_plan_item = SessionPlanItem(
                        session_plan_id=session_plan.id,
                        item_type=SessionPlanItemType.DSO,
                        dso_id=dso.id,
                        order=item_order,
                        create_date=datetime.now(),
                        update_date=datetime.now(),
                    )
                    db.session.add(session_plan_item)
                    session_plan.session_plan_items.append(session_plan_item)
                    item_order += 1
            else:
                log_error.append(lazy_gettext('DSO "{}" not found').format(target.get_name()))

    return log_warn, log_error


def _get_seeing_from_oal_seeing(seeing):
    if seeing == 5:
        return Seeing.VERYBAD
    if seeing == 4:
        return Seeing.BAD
    if seeing == 3:
        return Seeing.AVERAGE
    if seeing == 2:
        return Seeing.GOOD
    if seeing == 1:
        return Seeing.EXCELLENT
    return None

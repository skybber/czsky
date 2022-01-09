from datetime import datetime
from sqlalchemy import and_, or_

from flask_babel import lazy_gettext

from app import db

from app.commons.coordinates import parse_latlon
from app.commons import normalize_dso_name_ext

from app.models import Location, SessionPlan, SessionPlanItem, DeepskyObject, User
from app.models import Telescope, Eyepiece, Lens, Filter, TelescopeType, FilterType, Seeing
from app.commons.openastronomylog import parse


def import_session_plan(user, import_user, title, for_date, location_id, location_position, import_history_rec_id, file):
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

    session_plan = SessionPlan(
        user_id=user.id,
        title='Imported session plan ' + title,
        for_date=for_date,
        location_id=location_id,
        location_position=location_position,
        is_public=False,
        is_archived=False,
        notes='',
        is_anonymous=False,
        import_history_rec_id=import_history_rec_id,
        create_by=import_user.id,
        update_by=import_user.id,
        create_date=datetime.now(),
        update_date=datetime.now(),
    )

    db.session.add(session_plan)

    # Targets
    oal_targets = oal_observations.get_targets()
    found_dsos = {}
    item_order = 0
    if oal_targets and oal_targets.get_target():
        for target in oal_targets.get_target():
            normalized_name = normalize_dso_name_ext(target.get_name())
            dso = DeepskyObject.query.filter_by(name=normalized_name).first()
            if dso:
                found_dsos[target.get_id()] = dso
                session_plan_item = SessionPlanItem(
                    dso_id=dso.id,
                    order=item_order,
                    create_date=datetime.now(),
                    update_date=datetime.now(),
                )
                session_plan.observations.append(session_plan_item)
                item_order += 1
            else:
                log_error.append(lazy_gettext('DSO "{}" not found').format(target.get_name()))

    db.session.commit()

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

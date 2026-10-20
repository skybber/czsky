import os
from datetime import datetime, timedelta

from flask import Blueprint, current_app, render_template, request
from sqlalchemy import func, nullslast

from app import create_app, scheduler
from app.models import (
    AU_KM,
    DB_UPDATE_NEO_POS_KEY,
    LUNAR_DISTANCE_KM,
    NEO_IMPRECISE_DIST_AU,
    MinorPlanet,
    NeoCloseApproach,
)
from app.commons.dbupdate_utils import ask_dbupdate_permit
from app.commons.minor_planet_utils import update_neo_positions
from app.commons.search_utils import create_table_sort
from app.commons.neo_utils import update_neos

from .neo_forms import SearchNeoForm

main_neo = Blueprint('main_neo', __name__)

# Approaches that passed less than this long ago are still listed.
NEO_RECENT_PAST = timedelta(days=1)

# Computed peak brightness; the rough estimate only for asteroids without an orbit.
NEO_PEAK_MAG = func.coalesce(NeoCloseApproach.peak_mag, NeoCloseApproach.est_peak_mag)

NEO_SORT_DEF = {
    # Unmatched approaches have no minor planet; show and sort them by the CAD designation.
    'name': func.coalesce(MinorPlanet.designation, NeoCloseApproach.designation),
    'date': NeoCloseApproach.approach_time,
    'dist': NeoCloseApproach.dist_au,
    'v_rel': NeoCloseApproach.v_rel_kms,
    # Size by H (MPC, CAD without an orbit): ascending = largest first.
    'size': func.coalesce(MinorPlanet.magnitude_H, NeoCloseApproach.h),
    'peak_mag': NEO_PEAK_MAG,
    'peak_time': NeoCloseApproach.peak_time,
    'cur_mag': MinorPlanet.eval_mag,
}
# Observers care first about what they can see.
NEO_DEFAULT_SORT = 'peak_mag'


def _update_neos():
    app = create_app(os.getenv('FLASK_CONFIG') or 'default', web=False)
    with app.app_context():
        try:
            update_neos()  # claims its own lock
        except Exception:
            current_app.logger.exception('Updating near-Earth asteroids failed.')


def _update_neo_positions():
    app = create_app(os.getenv('FLASK_CONFIG') or 'default', web=False)
    with app.app_context():
        if ask_dbupdate_permit(DB_UPDATE_NEO_POS_KEY, timedelta(minutes=30)):
            try:
                update_neo_positions()
            except Exception:
                current_app.logger.exception('Updating near-Earth asteroid positions failed.')


# Daily at 4:30, away from the other jobs; positions hourly (the daily run updates them too).
job1 = scheduler.add_job(_update_neos, 'cron', hour=4, minute=30, replace_existing=True, jitter=60)
job2 = scheduler.add_job(_update_neo_positions, 'cron', minute=15, replace_existing=True, jitter=60)


@main_neo.route('/near-earth-asteroids', methods=['GET'])
def near_earth_asteroids():
    """Upcoming close approaches of near-Earth asteroids."""
    form = SearchNeoForm(request.args)
    form.validate()
    # Invalid values fall back to defaults instead of reaching the query.
    if form.maglim.errors:
        form.maglim.data = None
    if form.period.data not in {value for value, _ in form.period.choices}:
        form.period.data = '30'
    if form.dist_max_ld.data not in {value for value, _ in form.dist_max_ld.choices}:
        form.dist_max_ld.data = 'all'

    sort_by = request.args.get('sortby') or NEO_DEFAULT_SORT
    if sort_by.lstrip('-') not in NEO_SORT_DEF:
        sort_by = NEO_DEFAULT_SORT

    days = int(form.period.data)
    now = datetime.utcnow()
    query = NeoCloseApproach.query \
        .outerjoin(MinorPlanet, NeoCloseApproach.minor_planet_id == MinorPlanet.id) \
        .filter(
        NeoCloseApproach.approach_time >= now - NEO_RECENT_PAST,
        NeoCloseApproach.approach_time < now + timedelta(days=days),
    )
    if form.dist_max_ld.data != 'all':
        query = query.filter(NeoCloseApproach.dist_au <= float(form.dist_max_ld.data) * LUNAR_DISTANCE_KM / AU_KM)
    if form.maglim.data is not None:
        query = query.filter(NEO_PEAK_MAG <= form.maglim.data)
    if form.pha_only.data:
        query = query.filter(MinorPlanet.is_pha.is_(True))
    # Missing values (no H, unmatched asteroid without current brightness) go last in both directions.
    order_by_field = NEO_SORT_DEF[sort_by.lstrip('-')]
    if sort_by.startswith('-'):
        order_by_field = order_by_field.desc()
    order_by_field = nullslast(order_by_field)
    approaches = query.order_by(order_by_field, NeoCloseApproach.approach_time).all()

    filter_args = {
        'period': form.period.data,
        'dist_max_ld': form.dist_max_ld.data,
        # '' keeps a cleared limit; omitted, the default 16 mag would apply again.
        'maglim': form.maglim.data if form.maglim.data is not None else '',
        'pha_only': 'y' if form.pha_only.data else None,
    }
    return render_template('main/solarsystem/near_earth_asteroids.html', approaches=approaches, form=form,
                           now=now, neo_imprecise_dist_au=NEO_IMPRECISE_DIST_AU, sort_by=sort_by,
                           table_sort=create_table_sort(sort_by, NEO_SORT_DEF.keys()), filter_args=filter_args)

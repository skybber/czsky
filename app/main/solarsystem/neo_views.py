import os
from datetime import datetime, timedelta

from flask import Blueprint, current_app, render_template, request

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
from app.commons.neo_utils import update_neos

from .neo_forms import SearchNeoForm

main_neo = Blueprint('main_neo', __name__)

# Approaches that passed less than this long ago are still listed.
NEO_RECENT_PAST = timedelta(days=1)


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
        form.dist_max_ld.data = ''

    days = int(form.period.data)
    now = datetime.utcnow()
    query = NeoCloseApproach.query.filter(
        NeoCloseApproach.approach_time >= now - NEO_RECENT_PAST,
        NeoCloseApproach.approach_time < now + timedelta(days=days),
    )
    if form.dist_max_ld.data:
        query = query.filter(NeoCloseApproach.dist_au <= float(form.dist_max_ld.data) * LUNAR_DISTANCE_KM / AU_KM)
    if form.maglim.data is not None:
        query = query.filter(NeoCloseApproach.est_peak_mag <= form.maglim.data)
    if form.pha_only.data:
        query = query.join(MinorPlanet, NeoCloseApproach.minor_planet_id == MinorPlanet.id) \
                     .filter(MinorPlanet.is_pha.is_(True))
    approaches = query.order_by(NeoCloseApproach.approach_time).all()

    return render_template('main/solarsystem/near_earth_asteroids.html', approaches=approaches, form=form,
                           now=now, neo_imprecise_dist_au=NEO_IMPRECISE_DIST_AU)

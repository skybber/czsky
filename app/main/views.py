import base64
import urllib.parse

from flask import (
    abort,
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from app.commons.dso_utils import CHART_STAR_PREFIX, CHART_DOUBLE_STAR_PREFIX
from app.commons.utils import get_site_lang_code
from app.commons.coordinates import parse_radec

from app.commons.search_sky_object_utils import (
    search_constellation,
    search_dso,
    search_star,
    search_comet,
    search_double_star,
    search_minor_planet
)

from app.models import (
    Constellation,
    DoubleStar,
    News,
    Star,
    EditableHTML,
)


main = Blueprint('main', __name__)


@main.route('/')
def index():
    lang_code = get_site_lang_code()
    news_list = News.query.filter_by(is_released=True, lang_code=lang_code).order_by(News.id.desc()).limit(3).all()
    return render_template('main/index.html', is_anonymous=current_user.is_anonymous, news_list=news_list)


@main.route('/about')
def about():
    editable_html_obj = EditableHTML.get_editable_html('about')
    return render_template(
        'main/about.html', editable_html_obj=editable_html_obj)


@main.route('/theme_dark')
def theme_dark():
    session['theme'] = 'dark'
    return redirect(request.referrer)


@main.route('/theme_light')
def theme_light():
    session['theme'] = 'light'
    return redirect(request.referrer)


@main.route('/theme_night')
def theme_night():
    session['theme'] = 'night'
    return redirect(request.referrer)


@main.route('/search')
def global_search():
    query = request.args.get('q', None)
    if query is None:
        abort(404)

    query = query.strip()

    if not query:
        abort(404)

    # 0. search by czsky chart ids
    res = _search_chart_ids(query)
    if res:
        return res

    # 1. Search constellation
    constellation = search_constellation(query)
    if constellation:
        if request.args.get('fromchart') is not None:
            return redirect(url_for('main_constellation.constellation_chart', constellation_id=constellation.iau_code,
                                    fullscreen=request.args.get('fullscreen'), splitview=request.args.get('splitview'), embed=request.args.get('embed')))
        return redirect(url_for('main_constellation.constellation_info', constellation_id=constellation.iau_code))

    # 2. Search DSO
    dso = search_dso(query)
    if dso:
        return redirect(url_for('main_deepskyobject.deepskyobject_seltab',
                                dso_id=dso.name,
                                seltab=request.args.get('seltab'),
                                fullscreen=request.args.get('fullscreen'),
                                splitview=request.args.get('splitview'),
                                back=request.args.get('back'),
                                back_id=request.args.get('back_id'),
                                embed=request.args.get('embed')))

    # 3. Search Double Star
    double_star = search_double_star(query)
    if double_star:
        return redirect(url_for('main_double_star.double_star_seltab',
                                double_star_id=double_star.id,
                                seltab=request.args.get('seltab'),
                                fullscreen=request.args.get('fullscreen'),
                                splitview=request.args.get('splitview'),
                                back=request.args.get('back'),
                                back_id=request.args.get('back_id'),
                                embed=request.args.get('embed')))

    # 4. Search Star
    star, usd = search_star(query)
    if star:
        if usd:
            if request.args.get('fromchart') is not None:
                return redirect(url_for('main_star.star_descr_chart', star_descr_id=usd.id,
                                        fullscreen=request.args.get('fullscreen'), splitview=request.args.get('splitview'), embed=request.args.get('embed')))
            else:
                return redirect(url_for('main_star.star_descr_info', star_descr_id=usd.id))
        else:
            return redirect(url_for('main_star.star_chart', star_id=star.id, splitview=request.args.get('splitview'), embed=request.args.get('embed')))

    # 5. Search comet
    comet = search_comet(query)
    if comet is not None:
        return redirect(url_for('main_comet.comet_info', comet_id=comet.comet_id))

    # 7. Search minor planet
    # 5. Search comet
    minor_planet = search_minor_planet(query)
    if minor_planet is not None:
        return redirect(url_for('main_minor_planet.minor_planet_info', minor_planet_id=minor_planet.int_designation))

    # 6. search by radec
    res = _search_by_ra_dec(query)
    if res:
        return res

    back_url_enc = request.args.get('back_url')
    if back_url_enc:
        back_url_b64 = urllib.parse.unquote(back_url_enc)
        back_url = base64.b64decode(back_url_b64).decode('utf-8')
        session['show_not_found'] = True
        if request.args.get('fullscreen'):
            back_url += '&fullscreen=true'
        if request.args.get('splitview'):
            back_url += '&splitview=true'
        return redirect(back_url)

    return redirect(url_for('main.object_not_found'))


def _search_by_ra_dec(query):
    try:
        ra, dec = parse_radec(query)
        if ra is not None and dec is not None:
            return redirect(url_for('main_chart.chart', mra=ra, mdec=dec, embed=request.args.get('embed')))
    except ValueError:
        pass


def _search_chart_ids(query):
    if query.startswith(CHART_STAR_PREFIX):
        try:
            star_id = int(query[len(CHART_STAR_PREFIX):])
            star = Star.query.filter_by(id=star_id).first()
            return redirect(url_for('main_star.star_catalogue_data', star_id=star.id, splitview=request.args.get('splitview'), embed=request.args.get('embed')))
        except (ValueError, TypeError):
            pass
    if query.startswith(CHART_DOUBLE_STAR_PREFIX):
        try:
            double_star_id = int(query[len(CHART_DOUBLE_STAR_PREFIX):])
            double_star = DoubleStar.query.filter_by(id=double_star_id).first()
            return redirect(url_for('main_double_star.double_star_info', double_star_id=double_star.id, embed=request.args.get('embed')))
        except (ValueError, TypeError):
            pass
    return None


def _get_constell(costell_code):
    constell_iau_code = costell_code.strip().upper()
    if constell_iau_code:
        constell = Constellation.get_iau_dict().get(constell_iau_code)
        return constell
    return None

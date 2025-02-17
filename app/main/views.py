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

from app import db

from app.commons.dso_utils import (
    CHART_STAR_PREFIX,
    CHART_DOUBLE_STAR_PREFIX,
    CHART_COMET_PREFIX,
    CHART_MINOR_PLANET_PREFIX,
    dso_name_to_simbad_id,
)
from app.commons.simbad_utils import simbad_query, simbad_obj_to_deepsky, get_otype_from_simbad

from app.commons.utils import get_site_lang_code
from app.commons.coordinates import parse_radec

from app.commons.search_sky_object_utils import (
    search_constellation,
    search_dso,
    search_star,
    search_comet,
    search_double_star,
    search_minor_planet,
    search_planet,
    search_planet_moon,
)

from app.models import (
    ChartTheme,
    Comet,
    Constellation,
    DeepskyObject,
    DoubleStar,
    MinorPlanet,
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
    lang_code = get_site_lang_code()
    return render_template(
        'main/about.html', editable_html_obj=editable_html_obj, lang_code=lang_code)


@main.route('/theme_dark')
def theme_dark():
    session['theme'] = 'dark'
    _clear_custom_theme()
    return redirect(request.referrer)


@main.route('/theme_light')
def theme_light():
    session['theme'] = 'light'
    _clear_custom_theme()
    return redirect(request.referrer)


@main.route('/theme_night')
def theme_night():
    session['theme'] = 'night'
    _clear_custom_theme()
    return redirect(request.referrer)


def _clear_custom_theme():
    if session.get('cur_custom_theme_id'):
        session.pop('cur_custom_theme_name', None)
        session.pop('cur_custom_theme_id', None)


@main.route('/theme_custom/<int:chart_theme_id>/set')
def theme_custom(chart_theme_id):
    chart_theme = ChartTheme.query.filter_by(id=chart_theme_id).first()
    if chart_theme is None:
        abort(404)
    session['theme'] = chart_theme.default_type.value.lower()
    session['cur_custom_theme_name'] = chart_theme.name
    session['cur_custom_theme_id'] = chart_theme.id
    return redirect(request.referrer)


@main.route('/search')
def global_search():
    query = request.args.get('q', None)
    if query is None:
        abort(404)

    query = query.strip()

    if not query:
        abort(404)
    return do_global_search(query, 1)


def do_global_search(query, level):
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
                                embed=request.args.get('embed'),
                                screenWidth=request.args.get('screenWidth')))

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
                                embed=request.args.get('embed'),
                                screenWidth=request.args.get('screenWidth')))

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

    # 5. Search planet
    planet = search_planet(query)
    if planet is not None:
        return redirect(url_for('main_planet.planet_seltab',
                                planet_iau_code=planet.iau_code,
                                seltab=request.args.get('seltab'),
                                fullscreen=request.args.get('fullscreen'),
                                splitview=request.args.get('splitview'),
                                back=request.args.get('back'),
                                back_id=request.args.get('back_id'),
                                embed=request.args.get('embed'),
                                screenWidth=request.args.get('screenWidth')
                                ))

    # 6. Search planet moons
    planet_moon = search_planet_moon(query)
    if planet_moon is not None:
        return redirect(url_for('main_planet_moon.planet_moon_seltab',
                                planet_moon_name=planet_moon.name,
                                seltab=request.args.get('seltab'),
                                fullscreen=request.args.get('fullscreen'),
                                splitview=request.args.get('splitview'),
                                back=request.args.get('back'),
                                back_id=request.args.get('back_id'),
                                embed=request.args.get('embed'),
                                screenWidth=request.args.get('screenWidth')
                                ))

    # 7. Search comet
    comet = search_comet(query)
    if comet is not None:
        return redirect(url_for('main_comet.comet_seltab',
                                comet_id=comet.comet_id,
                                seltab=request.args.get('seltab'),
                                fullscreen=request.args.get('fullscreen'),
                                splitview=request.args.get('splitview'),
                                back=request.args.get('back'),
                                back_id=request.args.get('back_id'),
                                embed=request.args.get('embed'),
                                screenWidth=request.args.get('screenWidth')))

    # 8. Search minor planet
    minor_planet = search_minor_planet(query)
    if minor_planet is not None:
        return redirect(url_for('main_minor_planet.minor_planet_seltab',
                                minor_planet_id=minor_planet.int_designation,
                                seltab=request.args.get('seltab'),
                                fullscreen=request.args.get('fullscreen'),
                                splitview=request.args.get('splitview'),
                                back=request.args.get('back'),
                                back_id=request.args.get('back_id'),
                                embed=request.args.get('embed'),
                                screenWidth=request.args.get('screenWidth')
                                ))

    # 9. search by radec
    res = _search_by_ra_dec(query)
    if res:
        return res

    # 10. Search Simbad
    if level != 2:
        simbad_obj = simbad_query(dso_name_to_simbad_id(query))
        if simbad_obj is not None:
            simbad_obj = simbad_obj[0]
            if simbad_obj['MAIN_ID'] != query and level == 1:
                res = do_global_search(simbad_obj['MAIN_ID'], 2)
            if not res:
                if get_otype_from_simbad(simbad_obj) is not None:
                    dso = DeepskyObject()
                    simbad_obj_to_deepsky(simbad_obj, dso)
                    db.session.add(dso)
                    db.session.commit()
                    res = do_global_search(simbad_obj['MAIN_ID'], 2)
                else:
                    ra_dec_query = '{} {}'.format(simbad_obj['RA'], simbad_obj['DEC'])
                    res = _search_by_ra_dec(ra_dec_query)
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
            return redirect(url_for('main_star.star_catalogue_data',
                                    star_id=star.id,
                                    back=request.args.get('back'),
                                    back_id=request.args.get('back_id'),
                                    splitview=request.args.get('splitview'),
                                    embed=request.args.get('embed')))
        except (ValueError, TypeError):
            pass
    if query.startswith(CHART_DOUBLE_STAR_PREFIX):
        try:
            double_star_id = int(query[len(CHART_DOUBLE_STAR_PREFIX):])
            double_star = DoubleStar.query.filter_by(id=double_star_id).first()
            return redirect(url_for('main_double_star.double_star_seltab',
                                    double_star_id=double_star.id,
                                    back=request.args.get('back'),
                                    back_id=request.args.get('back_id'),
                                    embed=request.args.get('embed')))
        except (ValueError, TypeError):
            pass
    if query.startswith(CHART_COMET_PREFIX):
        try:
            comet_id = int(query[len(CHART_COMET_PREFIX):])
            comet = Comet.query.filter_by(id=comet_id).first()
            return redirect(url_for('main_comet.comet_seltab', comet_id=comet.comet_id, embed=request.args.get('embed')))
        except (ValueError, TypeError):
            pass
    if query.startswith(CHART_MINOR_PLANET_PREFIX):
        try:
            minor_planet_id = int(query[len(CHART_MINOR_PLANET_PREFIX):])
            minor_planet = MinorPlanet.query.filter_by(id=minor_planet_id).first()
            return redirect(url_for('main_minor_planet.minor_planet_seltab', minor_planet_id=minor_planet.int_designation, embed=request.args.get('embed')))
        except (ValueError, TypeError):
            pass
    return None


def _get_constell(costell_code):
    constell_iau_code = costell_code.strip()
    if constell_iau_code:
        constell = Constellation.get_constellation_by_iau_code(constell_iau_code)
        return constell
    return None

import re
import math
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

from app.commons.dso_utils import normalize_dso_name, CZSKY_CHART_STAR_PREFIX
from app.commons.greek import GREEK_TO_LAT, SHORT_LAT_TO_GREEK, LONG_LAT_TO_GREEK, LONG_LAT_CZ_TO_GREEK
from app.commons.utils import get_lang_and_editor_user_from_request, get_site_lang_code
from app.commons.coordinates import parse_radec
from app.models import Constellation, DeepskyObject, News, Star, UserStarDescription, EditableHTML
from app.main.solarsystem.comet_views import get_all_comets

from sqlalchemy import func

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

    # 1. search by radec
    res = _search_by_ra_dec(query)
    if res:
        return res

    # 2. Search constellation
    res = _search_constellation(query)
    if res:
        return res

    # 3. Search DSO
    res = _search_dso(query)
    if res:
        return res

    # 4. Search Star
    res = _search_star(query)
    if res:
        return res

    # 5. Search comet
    res = _search_comet(query)
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


def _search_constellation(query):
    constellation = Constellation.query.filter(func.lower(Constellation.iau_code) == func.lower(query)).first()
    if not constellation:
        constellation = Constellation.query.filter(Constellation.name.like('%' + query + '%')).first()

    if constellation:
        if request.args.get('fromchart') is not None:
            return redirect(url_for('main_constellation.constellation_chart', constellation_id=constellation.iau_code,
                                    fullscreen=request.args.get('fullscreen'), splitview=request.args.get('splitview'), embed=request.args.get('embed')))
        else:
            return redirect(url_for('main_constellation.constellation_info', constellation_id=constellation.iau_code))

    return None


def _search_dso(query):
    if query.isdigit():
        query = 'NGC' + query
    else:
        query = urllib.parse.unquote(query)

    normalized_name = normalize_dso_name(query)
    dso = DeepskyObject.query.filter_by(name=normalized_name).first()
    if dso:
        return redirect(url_for('main_deepskyobject.deepskyobject_seltab',
                                    dso_id=dso.name,
                                    seltab=request.args.get('seltab'),
                                    fullscreen=request.args.get('fullscreen'),
                                    splitview=request.args.get('splitview'),
                                    back=request.args.get('back'),
                                    back_id=request.args.get('back_id'),
                                    embed=request.args.get('embed')))
    return None


def _search_star(query):
    go_catalogue_data = False
    star = None
    if query.startswith(CZSKY_CHART_STAR_PREFIX):
        try:
            star_id = int(query[len(CZSKY_CHART_STAR_PREFIX):])
            star = Star.query.filter_by(id=star_id).first()
            go_catalogue_data = True
        except (ValueError, TypeError):
            pass

    if not star:
        star = _search_by_bayer_flamsteed(query)
    if not star:
        star = _search_star_from_catalog(query)
    if not star:
        # try to search by var ID
        star = Star.query.filter(Star.var_id.ilike(query)).first()
    if not star:
        # try to search by common star name
        star = Star.query.filter_by(common_name=query.lower().capitalize()).first()

    if star:
        lang, editor_user = get_lang_and_editor_user_from_request()
        usd = UserStarDescription.query.filter_by(star_id=star.id, user_id=editor_user.id, lang_code=lang).first()
        if usd:
            if request.args.get('fromchart') is not None:
                return redirect(url_for('main_star.star_descr_chart', star_descr_id=usd.id,
                                    fullscreen=request.args.get('fullscreen'), splitview=request.args.get('splitview'), embed=request.args.get('embed')))
            else:
                return redirect(url_for('main_star.star_descr_info', star_descr_id=usd.id))
        else:
            if go_catalogue_data:
                return redirect(url_for('main_star.star_catalogue_data', star_id=star.id, splitview=request.args.get('splitview'), embed=request.args.get('embed')))
            return redirect(url_for('main_star.star_chart', star_id=star.id, splitview=request.args.get('splitview'), embed=request.args.get('embed')))

    return None


def _search_by_bayer_flamsteed(query):
    star = None
    if query[:1] in GREEK_TO_LAT and len(query) > 1:
        bayer = query[:1]
        constell = _get_constell(query[1:])
        if constell:
            star = Star.query.filter_by(bayer=bayer, constellation_id=constell.id).first()
    else:
        words = query.split()
        if len(words) == 2:
            constell = _get_constell(words[1])
            if constell:
                star_name = words[0].lower()
                bayer = None
                if star_name in GREEK_TO_LAT:
                    bayer = star_name
                elif star_name in SHORT_LAT_TO_GREEK:
                    bayer = SHORT_LAT_TO_GREEK[star_name]
                elif star_name in LONG_LAT_TO_GREEK:
                    bayer = LONG_LAT_TO_GREEK[star_name]
                elif star_name in LONG_LAT_CZ_TO_GREEK:
                    bayer = LONG_LAT_CZ_TO_GREEK[star_name]
                if bayer:
                    star = Star.query.filter_by(bayer=bayer, constellation_id=constell.id).first()
                elif star_name.isdigit():
                    star = Star.query.filter_by(flamsteed=int(star_name), constellation_id=constell.id).first()
        elif len(words) == 1 and query[0].isdigit():
            i = 1
            while i < len(query) and query[i].isdigit():
                i+=1
            if i < len(query):
                constell = _get_constell(query[i:])
                if constell:
                    star = Star.query.filter_by(flamsteed=int(query[:i]), constellation_id=constell.id).first()
    return star


def _search_star_from_catalog(query):
    star = None
    for i, letter in enumerate(query, 0):
        if letter.isdigit():
            break
    if i > 0 and i < len(query)-1:
        cat = query[:i].strip()
        sid = query[i:].strip()
        if cat and sid.isdigit():
            cat = cat.upper()
            if cat == 'HR':
                star = Star.query.filter_by(hr=int(sid)).first()
            if not not star and cat == 'HD':
                star = Star.query.filter_by(hd=int(sid)).first()
            if not star and cat == 'SAO':
                star = Star.query.filter_by(sao=int(sid)).first()
    return star


def _search_comet(query):
    if len(query) > 5:
        search_expr = query.replace('"', '')
        all_comets = get_all_comets()
        comets = all_comets.query('designation.str.contains("{}")'.format(search_expr))
        if len(comets) >= 1:
            return redirect(url_for('main_comet.comet_info', comet_id=comets.iloc[0]['comet_id']))
    return None


def _get_constell(costell_code):
    constell_iau_code = costell_code.strip().lower().capitalize()
    if constell_iau_code:
        constell = Constellation.get_iau_dict().get(constell_iau_code)
        return constell
    return None

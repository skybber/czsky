from datetime import datetime
import base64

from flask import (
    abort,
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_, and_

from app import db

from app.models import News
from app.commons.pagination import Pagination, get_page_parameter, get_page_args
from app.commons.search_utils import process_paginated_session_search, get_items_per_page
from app.commons.coordinates import parse_radec, radec_to_string_short

from .news_forms import (
    NewsNewForm,
    NewsEditForm,
    SearchNewsForm,
)

from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_chart_pdf_img,
    common_prepare_chart_data,
    common_ra_dec_fsz_from_request,
)

from app.main.chart.chart_forms import ChartForm
from app.commons.countries import countries
from app.commons.utils import to_float

main_news = Blueprint('main_news', __name__)


def _is_editable(news):
    return news.user_id == current_user.id or current_user.is_admin() or current_user.is_editor()


@main_news.route('/news-list', methods=['GET', 'POST'])
@login_required
def news_list():
    search_form = SearchNewsForm()

    ret, page = process_paginated_session_search('news_search_page', [
        ('news_search', search_form.q),
    ])

    per_page = get_items_per_page(search_form.items_per_page)

    if not ret:
        return redirect(url_for('main_news.news_list'))

    offset = (page - 1) * per_page

    news = News.query
    if search_form.q.data:
        news = news.filter(News.name.like('%' + search_form.q.data + '%'))
    news_for_render = news.order_by(News.id.desc()).limit(per_page).offset(offset).all()

    pagination = Pagination(page=page, total=news.count(), search=False, record_name='news', css_framework='semantic', not_passed_args='back')

    return render_template('main/news/news_list.html', news=news_for_render, pagination=pagination, search_form=search_form)


@main_news.route('/news/<int:news_id>', methods=['GET'])
@main_news.route('/news/<int:news_id>/info', methods=['GET'])
def news_info(news_id):
    news = News.query.filter_by(id=news_id).first()
    if news is None:
        abort(404)
    if not news.is_released and (current_user.is_anonymous or not current_user.is_editor):
        abort(404)

    editable = current_user.is_editor

    return render_template('main/news/news_info.html', news=news, type='info', editable=editable, )


@main_news.route('/news/<int:news_id>', methods=['GET', 'POST'])
@main_news.route('/news/<int:news_id>/chart', methods=['GET', 'POST'])
def news_chart(news_id):
    """View a comet info."""
    news = News.query.filter_by(id=news_id).first()
    if news is None:
        abort(404)
    if not news.is_released and (current_user.is_anonymous or not current_user.is_editor):
        abort(404)

    form  = ChartForm()

    if not common_ra_dec_fsz_from_request(form):
        if form.ra.data is None or form.dec.data is None:
            form.ra.data = news.ra
            form.dec.data = news.dec

    chart_control = common_prepare_chart_data(form)

    return render_template('main/news/news_info.html', fchart_form=form, type='chart', news=news, user_descr=None, chart_control=chart_control, )


@main_news.route('/news/<int:news_id>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def news_chart_pos_img(news_id, ra, dec):
    news = News.query.filter_by(id=news_id).first()
    if news is None:
        abort(404)
    if not news.is_released and (current_user.is_anonymous or not current_user.is_editor):
        abort(404)

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes = common_chart_pos_img(news.ra, news.dec, ra, dec, visible_objects=visible_objects)

    if visible_objects is not None:
        img = base64.b64encode(img_bytes.read()).decode()
        return jsonify(img=img, img_map=visible_objects)
    else:
        return send_file(img_bytes, mimetype='image/png')


@main_news.route('/news/<int:news_id>/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def news_chart_legend_img(news_id, ra, dec):
    news = News.query.filter_by(id=news_id).first()
    if news is None:
        abort(404)
    if not news.is_released and (current_user.is_anonymous or not current_user.is_editor):
        abort(404)

    img_bytes = common_chart_legend_img(news.ra, news.dec, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')


@main_news.route('/news/<int:news_id>/chart-pdf/<string:ra>/<string:dec>', methods=['GET'])
def news_chart_pdf(news_id, ra, dec):
    news = News.query.filter_by(id=news_id).first()
    if news is None:
        abort(404)
    if not news.is_released and (current_user.is_anonymous or not current_user.is_editor):
        abort(404)

    news_ra = to_float(request.args.get('obj_ra'), None)
    news_dec = to_float(request.args.get('obj_dec'), None)

    img_bytes = common_chart_pdf_img(news_ra, news_dec, ra, dec)

    return send_file(img_bytes, mimetype='application/pdf')


@main_news.route('/new-news', methods=['GET', 'POST'])
@login_required
def new_news():
    if not current_user.is_editor():
        abort(404)
    form = NewsNewForm()
    if request.method == 'POST' and form.validate_on_submit():
        if form.radec.data:
            ra, dec = parse_radec(form.radec.data)
        else:
            ra, dec = (None, None)
        news = News(
            title = form.title.data,
            ra = ra,
            dec = dec,
            title_row = form.title_row.data,
            text = form.text.data,
            rating = form.rating.data,
            is_released = form.is_released.data,
            create_by = current_user.id,
            update_by = current_user.id,
            create_date = datetime.now(),
            update_date = datetime.now()
            )
        db.session.add(news)
        db.session.commit()
        flash('News successfully created', 'form-success')
        return redirect(url_for('main_news.news_edit', news_id=news.id))
    return render_template('main/news/news_edit.html', form=form, is_new=True, countries=countries)


@main_news.route('/news/<int:news_id>/edit', methods=['GET', 'POST'])
@login_required
def news_edit(news_id):
    if not current_user.is_editor():
        abort(404)
    news = News.query.filter_by(id=news_id).first()
    if news is None:
        abort(404)

    form = NewsEditForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            news.title = form.title.data
            if form.radec.data:
                news.ra, news.dec = parse_radec(form.radec.data)
            else:
                news.ra, news.dec = (None, None)
            news.title_row = form.title_row.data
            news.text = form.text.data
            news.rating = form.rating.data
            news.is_released = form.is_released.data
            news.update_by = current_user.id
            news.update_date = datetime.now()
            db.session.add(news)
            db.session.commit()
            flash('News successfully updated', 'form-success')
    else:
        form.title.data = news.title
        form.radec.data = radec_to_string_short(news.ra, news.dec)
        form.title_row.data = news.title_row
        form.text.data = news.text
        form.rating.data = news.rating
        form.is_released.data = news.is_released

    return render_template('main/news/news_edit.html', form=form, news=news, is_new=False, countries=countries)


@main_news.route('/news/<int:news_id>/delete')
@login_required
def news_delete(news_id):
    if not current_user.is_editor():
        abort(404)
    news = News.query.filter_by(id=news_id).first()
    if news is None:
        abort(404)
    db.session.delete(news)
    flash('News was deleted', 'form-success')
    return redirect(url_for('main_news.news_list'))

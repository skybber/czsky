from datetime import datetime

from flask import (
    abort,
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
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

from app.commons.countries import countries

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
    return render_template('main/news/news_info.html', news=news, type='info', editable=editable)


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
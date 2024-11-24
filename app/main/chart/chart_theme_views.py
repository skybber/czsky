from datetime import datetime


from flask import (
    abort,
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from flask_login import current_user, login_required
from flask_babel import gettext

from app import db

from app.models import (
    ChartTheme,
    User,
)

from .chart_theme_forms import (
    ChartThemeEditForm,
    ChartThemeNewForm,
)
from ...commons.chart_theme_definition import MERGED_DARK_THEME_TEMPL, MERGED_LIGHT_THEME_TEMPL, \
    MERGED_NIGHT_THEME_TEMPL

main_chart_theme = Blueprint('main_chart_theme', __name__)


@main_chart_theme.route('/chart-themes', methods=['GET', 'POST'])
@login_required
def chart_themes():
    chart_themes = ChartTheme.query.filter_by(user_id=current_user.id).all()
    return render_template('main/chart/chart_themes.html', chart_themes=chart_themes)


@main_chart_theme.route('/chart-theme/<int:chart_theme_id>/edit', methods=['GET', 'POST'])
@login_required
def chart_theme_edit(chart_theme_id):
    """Edit chart theme."""
    chart_theme = ChartTheme.query.filter_by(id=chart_theme_id).first()
    if chart_theme is None:
        abort(404)

    form = ChartThemeEditForm()
    if request.method == 'GET':
        form.name.data = chart_theme.name
        form.default_type.data = chart_theme.default_type
        form.is_active.data = chart_theme.is_active
        form.definition.data = chart_theme.definition
        form.dark_definition.data = MERGED_DARK_THEME_TEMPL
        form.light_definition.data = MERGED_LIGHT_THEME_TEMPL
        form.night_definition.data = MERGED_NIGHT_THEME_TEMPL
    elif form.validate_on_submit():
        chart_theme.name = form.name.data
        chart_theme.default_type = form.default_type.data
        chart_theme.is_active = form.is_active.data
        chart_theme.definition = form.definition.data
        chart_theme.update_date = datetime.now()
        db.session.add(chart_theme)
        db.session.commit()
        flash(gettext('Constellation successfully updated'), 'form-success')

        if session.get('cur_custom_theme_id') == str(chart_theme.id):
            session.pop('cur_custom_theme_name', None)
            session.pop('cur_custom_theme_id', None)
            session['theme'] = chart_theme.default_type.value.lower()

    return render_template('main/chart/chart_theme_edit.html', form=form, chart_theme=chart_theme)


@main_chart_theme.route('/new-news', methods=['GET', 'POST'])
@login_required
def new_chart_theme():
    chart_themes = ChartTheme.query.filter_by(user_id=current_user.id).all()
    if len(chart_themes) >= 5:
        return redirect(url_for('main_chart_theme.chart_themes'))

    form = ChartThemeNewForm()
    if request.method == 'POST' and form.validate_on_submit():
        chart_theme = ChartTheme(
            name=form.name.data,
            default_type=form.default_type.data,
            definition=form.definition.data,
            is_active=form.is_active.data,
            is_public=False,
            order=len(chart_themes) + 1,
            user_id=current_user.id,
            create_date=datetime.now(),
            update_date=datetime.now()
        )
        db.session.add(chart_theme)
        db.session.commit()
        flash('Chart theme successfully created', 'form-success')
        return redirect(url_for('main_chart_theme.chart_theme_edit', chart_theme_id=chart_theme.id))
    else:
        form.definition.data = MERGED_DARK_THEME_TEMPL
        form.dark_definition.data = MERGED_DARK_THEME_TEMPL
        form.light_definition.data = MERGED_LIGHT_THEME_TEMPL
        form.night_definition.data = MERGED_NIGHT_THEME_TEMPL
    return render_template('main/chart/chart_theme_edit.html', form=form, is_new=True)

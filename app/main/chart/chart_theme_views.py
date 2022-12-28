from datetime import datetime

from flask import (
    abort,
    Blueprint,
    flash,
    render_template,
    request,
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
)

from app.commons.utils import get_lang_and_editor_user_from_request

main_chart_theme = Blueprint('main_chart_theme', __name__)


@main_chart_theme.route('/chart-theme/<int:chart_theme_id>/edit', methods=['GET', 'POST'])
@login_required
def chart_theme_edit(chart_theme_id):
    """Edit chart theme."""
    if not current_user.is_editor():
        abort(403)
    chart_theme = ChartTheme.query.filter_by(id=chart_theme_id).first()
    if chart_theme is None:
        abort(404)

    lang, editor_user = get_lang_and_editor_user_from_request(for_constell_descr=True)
    form = ChartThemeEditForm()
    if editor_user:
        if request.method == 'GET':
            form.name.data = chart_theme.name
            form.definition.data = chart_theme.definition
        elif form.validate_on_submit():
            chart_theme.name = form.name.data
            chart_theme.definition = chart_theme.definition.data
            chart_theme.update_by = current_user.id
            chart_theme.update_date = datetime.now()
            db.session.add(chart_theme)
            db.session.commit()
            flash(gettext('Constellation successfully updated'), 'form-success')

    author = _create_author_entry(chart_theme.update_by, chart_theme.update_date)

    return render_template('main/chart/chart_theme.html', form=form, chart_theme=chart_theme, author=author)


def _create_author_entry(update_by, update_date):
    if update_by is None:
        return '', ''
    user_name = User.query.filter_by(id=update_by).first().user_name
    return user_name, update_date.strftime("%Y-%m-%d %H:%M")

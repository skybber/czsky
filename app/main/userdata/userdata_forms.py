from flask_wtf import FlaskForm
from wtforms.fields import (
    TextAreaField,
)
from wtforms.validators import (
    InputRequired
)


class GitSaveForm(FlaskForm):
    commit_message = TextAreaField('Commit message', validators=[InputRequired(),], render_kw={'rows':2})

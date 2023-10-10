from flask_login import current_user

from app.models import (
    Eyepiece,
    Filter,
    Telescope,
)

def assign_equipment_choices(form, has_filter=True):
    telescopes = Telescope.query.filter_by(user_id=current_user.id, is_active=True, is_deleted=False).all()
    eyepieces = Eyepiece.query.filter_by(user_id=current_user.id, is_active=True, is_deleted=False).all()
    if has_filter:
        filters = Filter.query.filter_by(user_id=current_user.id, is_active=True, is_deleted=False).all()
    form.telescope.choices = [(-1, "---")] + [(t.id, t.name) for t in telescopes]
    form.eyepiece.choices = [(-1, "---")] + [(e.id, e.name) for e in eyepieces]
    if has_filter:
        form.filter.choices = [(-1, "---")] + [(f.id, f.name) for f in filters]


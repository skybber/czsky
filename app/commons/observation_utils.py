from app.models import DeepskyObject
from app.commons.dso_utils import normalize_dso_name
from flask import url_for


def deepsky_objects_to_html(observation_id, dsos):
    formatted_dsos = []
    for dso in dsos:
        formatted_dsos.append('<a href="' + url_for('main_deepskyobject.deepskyobject_info', dso_id=dso.name, back='observation', back_id=observation_id) + '">' + dso.denormalized_name() + '</a>')
    return ','.join(formatted_dsos)


def astro_text_to_html(observation_id, text):
    return text

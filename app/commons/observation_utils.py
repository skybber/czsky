from app.models import DeepskyObject
from app.commons.dso_utils import normalize_dso_name
from flask import url_for

def deepsky_objects_to_html(observation_id, dsos):
    formatted_dsos = []
    for dso_name in dsos.split(','):
        dso_name = normalize_dso_name(dso_name)
        dso = DeepskyObject.query.filter_by(name=dso_name).first()
        if dso:
            formatted_dsos.append('<a href="' +
                                  url_for('main_deepskyobject.deepskyobject_info', dso_id=dso.name, from_observation_id=observation_id) +
                                  '">' + dso.denormalized_name() + '</a>')
        else:
            formatted_dsos.append(dso)
    return ','.join(formatted_dsos)


def astro_text_to_html(observation_id, text):
    return text
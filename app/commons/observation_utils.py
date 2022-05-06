from flask import url_for


def deepsky_objects_to_html(observing_session_id, dsos):
    formatted_dsos = []
    for dso in dsos:
        formatted_dsos.append('<a href="' + url_for('main_deepskyobject.deepskyobject_info', dso_id=dso.name, back='observation', back_id=observing_session_id) + '">' + dso.denormalized_name() + '</a>')
    return ','.join(formatted_dsos)


def astro_text_to_html(observing_session_id, text):
    return text

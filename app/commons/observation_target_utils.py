from app.commons.dso_utils import normalize_dso_name
from app.commons.search_sky_object_utils import normalize_double_star_name, search_dso, search_double_star

from app.models import (
    DeepskyObject,
    DoubleStar,
    ObservationTargetType,
)


def parse_observation_targets(targets):
    not_found = []
    dsos = []
    double_star = search_double_star(targets, number_search=False)
    if not double_star:
        target_names = targets.split(',')
        for target_name in target_names:
            dso = search_dso(target_name)
            if dso:
                dsos.append(dso)
                continue
            not_found.append(target_name)

    return dsos, double_star, not_found


def set_observation_targets(observation, targets):
    observation.deepsky_objects = []
    observation.double_star_id = None
    dsos, double_star, not_found = parse_observation_targets(targets)
    if double_star:
        observation.double_star_id = double_star.id
        observation.target_type = ObservationTargetType.DBL_STAR
    elif dsos:
        for dso in dsos:
            observation.deepsky_objects.append(dso)
        observation.target_type = ObservationTargetType.DSO




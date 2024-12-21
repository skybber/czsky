from app.commons.oal_export_utils import (
    create_double_star_observation_target,
    create_dso_observation_target
)

from app.commons.openastronomylog import OalobserverType, OalobserversType
from app.commons.openastronomylog import Oalobservations
from app.commons.openastronomylog import OaltargetsType


def create_oal_observations_from_wishlist(user, wish_list):
    oal_observer = OalobserverType(id='usr_{}'.format(user.id),
                                   name=user.get_first_name(),
                                   surname=user.get_last_name(),
                                   contact=[user.email],
                                   )
    oal_observers = OalobserversType(observer=[oal_observer])

    oal_targets = OaltargetsType()
    for item in wish_list.wish_list_items:
        oal_obs_target = None
        if item.dso_id is not None:
            oal_obs_target = create_dso_observation_target(item.deepsky_object)
        elif item.double_star_id is not None:
            oal_obs_target = create_double_star_observation_target(item.double_star)
        if oal_obs_target:
            oal_targets.add_target(oal_obs_target)

    oal_observations = Oalobservations(observers=oal_observers, sites=None, sessions=None, targets=oal_targets,
                                       scopes=None, eyepieces=None, lenses=None, filters=None,
                                       images=None, observation=None)

    return oal_observations

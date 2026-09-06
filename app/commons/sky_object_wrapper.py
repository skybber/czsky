from flask import request, url_for

from app.models import Comet, DeepskyObject, DoubleStar, Star


OBJ_ID_DSO_PREFIX = 'dso'
OBJ_ID_DOUBLE_STAR_PREFIX = 'dbl'
OBJ_ID_STAR_PREFIX = 'star'


class SkyObjectWrapper:
    def __init__(self, sky_obj, label, tab):
        self._sky_obj = sky_obj
        self._label = label
        self._tab = tab

    def url(self):
        embed = request.args.get('embed')
        season = request.args.get('season')
        back = request.args.get('back')
        back_id = request.args.get('back_id')

        if isinstance(self._sky_obj, DeepskyObject):
            return url_for(
                'main_deepskyobject.deepskyobject_seltab',
                dso_id=self._sky_obj.name,
                seltab=self._tab,
                back=back,
                back_id=back_id,
                season=season,
                embed=embed,
            )
        if isinstance(self._sky_obj, Star):
            return url_for(
                'main_star.star_chart',
                star_id=self._sky_obj.id,
                back=back,
                back_id=back_id,
                season=season,
                embed=embed,
            )
        if isinstance(self._sky_obj, DoubleStar):
            return url_for(
                'main_double_star.double_star_seltab',
                double_star_id=self._sky_obj.id,
                seltab=self._tab,
                back=back,
                back_id=back_id,
                season=season,
                embed=embed,
            )
        if isinstance(self._sky_obj, Comet):
            return url_for(
                'main_comet.comet_seltab',
                comet_id=self._sky_obj.comet_id,
                back=back,
                back_id=back_id,
                embed=embed,
            )
        return ''

    def top_url(self):
        season = request.args.get('season')
        back = request.args.get('back')
        back_id = request.args.get('back_id')

        if isinstance(self._sky_obj, DeepskyObject):
            obj_id = OBJ_ID_DSO_PREFIX + str(self._sky_obj.id)
        elif isinstance(self._sky_obj, DoubleStar):
            obj_id = OBJ_ID_DOUBLE_STAR_PREFIX + str(self._sky_obj.id)
        elif isinstance(self._sky_obj, Star):
            obj_id = OBJ_ID_STAR_PREFIX + str(self._sky_obj.id)
        else:
            obj_id = str(self._sky_obj.id)

        if back == 'observation':
            return url_for(
                'main_observing_session.observing_session_chart',
                observing_session_id=back_id,
                obj_id=obj_id,
                back=back,
                back_id=back_id,
                season=season,
                splitview='true',
            )
        if back == 'wishlist':
            return url_for(
                'main_wishlist.wish_list_chart',
                obj_id=obj_id,
                back=back,
                back_id=back_id,
                season=season,
                splitview='true',
            )
        if back == 'session_plan':
            return url_for(
                'main_sessionplan.session_plan_chart',
                session_plan_id=back_id,
                obj_id=obj_id,
                back=back,
                back_id=back_id,
                season=season,
                splitview='true',
            )

        if isinstance(self._sky_obj, DeepskyObject):
            return url_for(
                'main_deepskyobject.deepskyobject_chart',
                dso_id=self._sky_obj.name,
                back=back,
                back_id=back_id,
                season=season,
                splitview='true',
            )

        if isinstance(self._sky_obj, DoubleStar):
            return url_for(
                'main_double_star.double_star_chart',
                double_star_id=self._sky_obj.id,
                back=back,
                back_id=back_id,
                season=season,
                splitview='true',
            )

        if isinstance(self._sky_obj, Comet):
            return url_for(
                'main_comet.comet_info',
                comet_id=self._sky_obj.comet_id,
                back=back,
                back_id=back_id,
                splitview='true',
            )

        return ''

    def label(self):
        if self._label:
            return self._label
        if isinstance(self._sky_obj, DeepskyObject):
            return self._sky_obj.denormalized_name()
        if isinstance(self._sky_obj, Star):
            if self._sky_obj.var_id is not None:
                return self._sky_obj.var_id
            if self._sky_obj.hd is not None:
                return 'HD' + self._sky_obj.hd
            return ''
        if isinstance(self._sky_obj, DoubleStar):
            return self._sky_obj.common_cat_id
        if isinstance(self._sky_obj, Comet):
            return self._sky_obj.designation
        return None

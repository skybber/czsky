from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from flask import url_for
from sqlalchemy import text

from app import db
from app.commons.dso_description_utils import get_dso_descriptions_with_master_fallback
from app.commons.md_utils import parse_extended_commonmark
from app.commons.search_sky_object_utils import search_dsos
from app.models import (
    Constellation,
    DeepskyObject,
    ObservedList,
    ObservedListItem,
    User,
    WishList,
    WishListItem,
)

MAX_STATUS_NAMES = 500
MAX_NAME_LENGTH = 64


def _clean_name(name: Any) -> str | None:
    if not isinstance(name, str):
        return None
    stripped = name.strip()
    if not stripped or len(stripped) > MAX_NAME_LENGTH:
        return None
    return stripped


def resolve_dsos(names: Iterable[str]) -> dict[str, DeepskyObject | None]:
    """Resolve user typed names (e.g. 'NGC 891', 'M31') to master DSOs using a constant number of SQL queries."""
    found = search_dsos(names)
    master_ids = {dso.master_id for dso in found.values() if dso is not None and dso.master_id}
    masters = {}
    if master_ids:
        masters = {dso.id: dso for dso in DeepskyObject.query.filter(DeepskyObject.id.in_(master_ids))}
    return {
        name: masters.get(dso.master_id, dso) if dso is not None and dso.master_id else dso
        for name, dso in found.items()
    }


def resolve_dso(name: str) -> DeepskyObject | None:
    return resolve_dsos([name])[name]


def _dso_groups(master_ids: Iterable[int]) -> dict[int, set[int]]:
    """Map master id -> ids of the master and all its child (alias) objects."""
    master_ids = set(master_ids)
    groups = {master_id: {master_id} for master_id in master_ids}
    if master_ids:
        rows = db.session.query(DeepskyObject.id, DeepskyObject.master_id) \
            .filter(DeepskyObject.master_id.in_(master_ids)).all()
        for child_id, master_id in rows:
            groups[master_id].add(child_id)
    return groups


def _observed_dso_ids(user_id: int, dso_ids: set[int]) -> set[int]:
    if not dso_ids:
        return set()
    rows = db.session.query(ObservedListItem.dso_id) \
        .join(ObservedList, ObservedList.id == ObservedListItem.observed_list_id) \
        .filter(ObservedList.user_id == user_id, ObservedListItem.dso_id.in_(dso_ids)).all()
    return {row[0] for row in rows}


def _wishlist_dso_ids(user_id: int, dso_ids: set[int]) -> set[int]:
    if not dso_ids:
        return set()
    rows = db.session.query(WishListItem.dso_id) \
        .join(WishList, WishList.id == WishListItem.wish_list_id) \
        .filter(WishList.user_id == user_id, WishListItem.dso_id.in_(dso_ids)).all()
    return {row[0] for row in rows}


def dso_status_payload(user_id: int, names: list[Any], include_observed: bool, include_wishlist: bool) -> dict[str, Any]:
    if not isinstance(names, list):
        raise ValueError('names must be a list')
    if len(names) > MAX_STATUS_NAMES:
        raise ValueError('too many names (max {})'.format(MAX_STATUS_NAMES))

    clean_names = {name for name in (_clean_name(raw_name) for raw_name in names) if name is not None}
    resolved = resolve_dsos(clean_names)

    groups = _dso_groups(dso.id for dso in resolved.values() if dso is not None)
    all_ids = set().union(*groups.values()) if groups else set()
    observed_ids = _observed_dso_ids(user_id, all_ids) if include_observed else set()
    wishlist_ids = _wishlist_dso_ids(user_id, all_ids) if include_wishlist else set()

    result = {}
    for name, dso in resolved.items():
        if dso is None:
            result[name] = {'found': False}
            continue
        group = groups[dso.id]
        result[name] = {
            'found': True,
            'dsoId': dso.id,
            'name': dso.name,
            'observed': bool(group & observed_ids) if include_observed else None,
            'wishlist': bool(group & wishlist_ids) if include_wishlist else None,
        }
    return {'objects': result}


def _lock_user_row(user_id: int) -> None:
    """
    Serializes wishlist changes of one user until the end of the current transaction.
    PostgreSQL: row lock on the user. SQLite: no row locks, a write statement acquires the database write lock instead.
    """
    if db.engine.dialect.name == 'sqlite':
        db.session.execute(text('UPDATE users SET id = id WHERE id = :user_id'), {'user_id': user_id})
    else:
        db.session.query(User.id).filter(User.id == user_id).with_for_update().one()


def _get_or_create_wishlist_locked(user_id: int) -> WishList:
    # Must be called with the user row locked. Unlike WishList.create_get_wishlist_by_user_id() it doesn't commit.
    wish_list = WishList.query.filter_by(user_id=user_id).order_by(WishList.id).first()
    if wish_list is None:
        wish_list = WishList(user_id=user_id, create_date=datetime.now(), update_date=datetime.now())
        db.session.add(wish_list)
        db.session.flush()
    return wish_list


def wishlist_add_payload(user_id: int, name: Any) -> dict[str, Any] | None:
    """
    Add DSO to user's wishlist. Idempotent also for concurrent requests: the existence check, wishlist creation and insert run
    in one transaction with the user row locked. Returns None if the object was not found.
    """
    clean_name = _clean_name(name)
    if clean_name is None:
        raise ValueError('name must be a non-empty string')

    dso = resolve_dso(clean_name)
    if dso is None:
        return None
    group = _dso_groups([dso.id])[dso.id]

    # Finish the read-only transaction so that the checks below see data committed by concurrent requests.
    db.session.commit()
    try:
        _lock_user_row(user_id)
        wish_list = _get_or_create_wishlist_locked(user_id)
        if _wishlist_dso_ids(user_id, group):
            result = 'already_present'
        else:
            item = wish_list.create_new_deepsky_object_item(dso.id)
            wish_list.update_date = datetime.now()
            db.session.add(item)
            result = 'added'
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return {'result': result, 'dsoId': dso.id, 'name': dso.name}


def _format_axis(arcsec: float) -> str:
    # same format as the convert_dso_size macro in common_macros.html
    if arcsec >= 600.0:
        return "{}'".format(int(arcsec / 60.0))
    if arcsec >= 100.0:
        return "{}'".format(int(arcsec / 6.0) / 10.0)
    return "{}''".format(int(arcsec))


def _format_size(dso: DeepskyObject) -> str | None:
    if not dso.major_axis:
        return None
    size = _format_axis(dso.major_axis)
    if dso.minor_axis:
        size += ' / ' + _format_axis(dso.minor_axis)
    return size


def _aperture_label(aperture_class: str) -> str:
    # same as the norm_aperture_class macro in common_macros.html
    return aperture_class if aperture_class == 'Naked-eye' else aperture_class + 'mm'


def _render_md(md_text: str | None, dso_name: str) -> str | None:
    if not md_text or not md_text.strip():
        return None
    return str(parse_extended_commonmark(md_text, dso_name, ''))


def dso_detail_payload(user_id: int, name: Any, include_observed: bool, include_wishlist: bool) -> dict[str, Any] | None:
    """
    Detail of a DSO for the browser extension panel. Description HTML is rendered the same way as on the DSO info page;
    it contains site-relative links and is NOT sanitized, the client must sanitize it before inserting it into a page.
    Must be called within a request context (descriptions depend on the request language). Returns None if not found.
    """
    clean_name = _clean_name(name)
    if clean_name is None:
        raise ValueError('name must be a non-empty string')

    dso = resolve_dso(clean_name)
    if dso is None:
        return None

    user_descr, apert_descriptions, title_img = get_dso_descriptions_with_master_fallback(dso)

    descr_md = ''
    if title_img:
        descr_md += '![<]({})\n'.format(title_img)
    if user_descr and user_descr.text:
        descr_md += user_descr.text

    group = _dso_groups([dso.id])[dso.id]
    other_names = [row[0] for row in db.session.query(DeepskyObject.name)
                   .filter(DeepskyObject.master_id == dso.id).order_by(DeepskyObject.name)]
    constellation = Constellation.get_constellation_by_id(dso.constellation_id) if dso.constellation_id else None

    return {
        'dsoId': dso.id,
        'name': dso.name,
        'denormalizedName': dso.denormalized_name(),
        'commonName': (user_descr.common_name if user_descr and user_descr.common_name else None) or dso.common_name,
        'otherNames': other_names,
        'type': dso.type,
        'subtype': dso.subtype,
        'constellation': {'iauCode': constellation.iau_code, 'name': constellation.name.capitalize()} if constellation else None,
        'mag': dso.mag if dso.mag is not None and dso.mag < 100.0 else None,
        'size': _format_size(dso),
        'ra': dso.ra_str(),
        'dec': dso.dec_str(),
        'descriptionHtml': _render_md(descr_md, dso.name),
        'apertureDescriptions': [
            {'aperture': _aperture_label(ap_class), 'html': _render_md(text, dso.name)}
            for ap_class, text in apert_descriptions if text
        ],
        'referencesHtml': _render_md(user_descr.references if user_descr else None, dso.name),
        'observed': bool(_observed_dso_ids(user_id, group)) if include_observed else None,
        'wishlist': bool(_wishlist_dso_ids(user_id, group)) if include_wishlist else None,
        'urls': {
            'info': url_for('main_deepskyobject.deepskyobject_info', dso_id=dso.name, _external=True),
            'chart': url_for('main_deepskyobject.deepskyobject_chart', dso_id=dso.name, _external=True),
        },
    }

import hashlib
import math
import os
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from flask import abort, request

import fchart3

from .chart_generator import (
    DSO_MAG_SCALES,
    FIELD_SIZES,
    FlagValue,
    MAG_SCALES,
    MOBILE_WIDTH,
    MAX_IMG_HEIGHT,
    MAX_IMG_WIDTH,
    _get_dso_hide_filter,
    _load_used_catalogs,
    get_fld_size_mags_from_request,
    resolve_active_chart_theme_definition,
    deg2rad,
    get_chart_datetime,
    get_utc_time,
    rad2deg,
    resolve_chart_city_lat_lon,
    to_float,
)
from .solar_system_chart_utils import get_planet_moons, get_solsys_bodies

SCENE_VERSION = "scene-v1"
MW_VERSION = "milkyway-v1"
STARS_VERSION = "stars-v1"
STAR_ZONE_BATCH_MAX = 64

_mw_cache_lock = threading.Lock()
_mw_dataset_cache: Dict[Tuple[str, bool], Dict[str, Any]] = {}
_stars_catalog_id_lock = threading.Lock()
_stars_catalog_id_cache: Dict[str, str] = {}


def _field_size_index(fld_size_deg: float) -> int:
    for idx, size in enumerate(FIELD_SIZES):
        if size >= fld_size_deg:
            return idx
    return len(FIELD_SIZES) - 1


def _clamp_mag_interval(value: float, interval: Tuple[float, float]) -> float:
    if value < interval[0]:
        return float(interval[0])
    if value > interval[1]:
        return float(interval[1])
    return float(value)


@dataclass(frozen=True)
class SceneRequest:
    is_equatorial: bool
    phi: float
    theta: float
    width: int
    height: int
    fld_size_deg: float
    maglim: float
    dso_maglim: float
    flags: str
    debug_stars: str


def _normalize_ra(ra: float) -> float:
    return ra % (2.0 * math.pi)


def _cart_to_radec(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    ra = np.arctan2(y, x)
    ra = np.where(ra < 0.0, ra + 2.0 * np.pi, ra)
    dec = np.arcsin(np.clip(z, -1.0, 1.0))
    return ra, dec


def _ang_sep(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    return math.acos(
        np.clip(
            math.sin(dec1) * math.sin(dec2)
            + math.cos(dec1) * math.cos(dec2) * math.cos(ra1 - ra2),
            -1.0,
            1.0,
        )
    )


def _field_size_rad(fld_size_deg: float, width: int, height: int) -> Tuple[float, float]:
    field_radius = deg2rad(fld_size_deg) / 2.0
    wh = max(width, height)
    field_size = field_radius * math.hypot(width, height) / wh
    return field_radius, field_size


def _resolve_scene_request() -> SceneRequest:
    is_equatorial = request.args.get("ra") is not None
    if is_equatorial:
        phi = request.args.get("ra", type=float)
        theta = request.args.get("dec", type=float)
    else:
        phi = request.args.get("az", type=float)
        theta = request.args.get("alt", type=float)

    if phi is None or theta is None:
        abort(404)

    width = request.args.get("width", type=int)
    height = request.args.get("height", type=int)
    if width is None or height is None:
        abort(404)

    width = min(width, MAX_IMG_WIDTH)
    height = min(height, MAX_IMG_HEIGHT)

    fld_size_deg = request.args.get("fsz", type=float)
    if fld_size_deg is None:
        abort(404)

    fld_size_idx = _field_size_index(fld_size_deg)
    _, _, default_maglim, default_dso_maglim = get_fld_size_mags_from_request()
    maglim = to_float(request.args.get("maglim"), float(default_maglim))
    dso_maglim = to_float(request.args.get("dso_maglim"), float(default_dso_maglim))
    maglim = _clamp_mag_interval(maglim, MAG_SCALES[fld_size_idx])
    dso_maglim = _clamp_mag_interval(dso_maglim, DSO_MAG_SCALES[fld_size_idx])

    flags = request.args.get("flags") or ""
    debug_stars = (request.args.get("debug_stars") or "all").strip().lower()
    if debug_stars not in ("preview_only", "all"):
        debug_stars = "all"

    return SceneRequest(
        is_equatorial=is_equatorial,
        phi=phi,
        theta=theta,
        width=width,
        height=height,
        fld_size_deg=fld_size_deg,
        maglim=maglim,
        dso_maglim=dso_maglim,
        flags=flags,
        debug_stars=debug_stars,
    )


def _resolve_center_equatorial(req: SceneRequest, lat: float, lon: float) -> Tuple[float, float]:
    if req.is_equatorial:
        return req.phi, req.theta
    dt = get_chart_datetime()
    from astropy.time import Time

    try:
        tm = Time(dt)
    except Exception:
        tm = Time.now()
    lst = tm.sidereal_time("apparent", longitude=rad2deg(lon)).radian
    return fchart3.astrocalc.horizontal_to_radec(lst, (math.sin(lat), math.cos(lat)), req.theta, req.phi)


def _stars_lod(req: SceneRequest) -> int:
    if req.fld_size_deg <= 2.0:
        return 3
    if req.fld_size_deg <= 8.0:
        return 2
    if req.fld_size_deg <= 30.0:
        return 1
    return 0


def _stars_catalog_id(star_catalog) -> str:
    comp_paths = []
    for comp in getattr(star_catalog, "_cat_components", []):
        path = getattr(comp, "file_name", "")
        if path:
            comp_paths.append(path)
    sig_parts = []
    for path in sorted(comp_paths):
        st = None
        try:
            st = os.stat(path)
        except OSError:
            st = None
        if st is None:
            sig_parts.append(f"{path}|missing")
        else:
            sig_parts.append(f"{path}|{int(st.st_size)}|{int(st.st_mtime)}")
    signature = "||".join(sig_parts)
    if not signature:
        signature = "empty"
    with _stars_catalog_id_lock:
        cached = _stars_catalog_id_cache.get(signature)
        if cached is not None:
            return cached
        value = hashlib.sha1(signature.encode("utf-8")).hexdigest()[:16]
        catalog_id = f"stars-{value}"
        _stars_catalog_id_cache[signature] = catalog_id
        return catalog_id


def _serialize_star_selection(star_sel, star_catalog) -> List[dict]:
    stars_out: List[dict] = []
    if star_sel is None or len(star_sel) == 0:
        return stars_out
    sel_names = star_sel.dtype.names if getattr(star_sel, "dtype", None) is not None else ()
    has_bvind = bool(sel_names) and "bvind" in sel_names
    ra_ar, dec_ar = _cart_to_radec(star_sel["x"], star_sel["y"], star_sel["z"])
    for i in range(len(ra_ar)):
        star_color = star_catalog.get_star_color(star_sel[i]) if has_bvind else None
        stars_out.append(
            {
                "id": f"HIP{int(star_sel['hip'][i])}" if int(star_sel["hip"][i]) > 0 else f"STAR{i}",
                "ra": float(ra_ar[i]),
                "dec": float(dec_ar[i]),
                "mag": float(star_sel["mag"][i]),
                "bvind": int(star_sel["bvind"][i]) if has_bvind else None,
                "color": [float(star_color[0]), float(star_color[1]), float(star_color[2])] if star_color else None,
            }
        )
    return stars_out


def _parse_zone_refs_arg(raw: str) -> List[Tuple[int, int]]:
    refs: List[Tuple[int, int]] = []
    if not raw:
        return refs
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    for part in parts:
        if not part.startswith("L") or "Z" not in part:
            raise ValueError("invalid zone token")
        lidx = part.find("Z")
        lev_s = part[1:lidx]
        zone_s = part[lidx + 1:]
        if not lev_s or not zone_s:
            raise ValueError("invalid zone token")
        lev = int(lev_s)
        zone = int(zone_s)
        refs.append((lev, zone))
    return refs


def _mw_mode(req: SceneRequest) -> Dict[str, Any]:
    if req.fld_size_deg <= 10.0:
        return {"mode": "off", "quality": None, "optimized": False}
    quality = "10k" if (req.width and req.width <= MOBILE_WIDTH) else "30k"
    optimized = request.args.get("hqual", "") != "1"
    return {
        "mode": "enhanced_10k" if quality == "10k" else "enhanced_30k",
        "quality": quality,
        "optimized": optimized,
    }


def _mw_mode_with_overrides(req: SceneRequest) -> Dict[str, Any]:
    mode = _mw_mode(req)
    q = (request.args.get("quality") or "").lower()
    if q in ("10k", "30k"):
        mode["quality"] = q
        mode["mode"] = "enhanced_10k" if q == "10k" else "enhanced_30k"
    opt = request.args.get("optimized")
    if opt in ("0", "1"):
        mode["optimized"] = opt == "1"
    return mode


def _mw_fade(req: SceneRequest, bg_color: Tuple[float, float, float], mw_color: Tuple[float, float, float]) -> Optional[List[float]]:
    fade = (req.fld_size_deg - 10.0) / (70.0 - 10.0)
    if fade <= 0:
        return None
    fade = min(fade, 1.0)
    bg_shift_frac = 0.10
    bg_r = bg_color[0] + (mw_color[0] - bg_color[0]) * bg_shift_frac
    bg_g = bg_color[1] + (mw_color[1] - bg_color[1]) * bg_shift_frac
    bg_b = bg_color[2] + (mw_color[2] - bg_color[2]) * bg_shift_frac
    mw_scale_fac = 3.0
    return [
        bg_r, (mw_color[0] - bg_r) * fade * mw_scale_fac,
        bg_g, (mw_color[1] - bg_g) * fade * mw_scale_fac,
        bg_b, (mw_color[2] - bg_b) * fade * mw_scale_fac,
    ]


def _mw_dataset_from_catalog(used_catalogs, quality: str, optimized: bool) -> Dict[str, Any]:
    enhanced = used_catalogs.enhanced_milky_way_10k if quality == "10k" else used_catalogs.enhanced_milky_way_30k
    points = enhanced.mw_points
    polygons = enhanced.mw_opti_polygons if optimized and enhanced.mw_opti_polygons is not None else enhanced.mw_polygons

    points_out = [[float(p[0]), float(p[1])] for p in points]
    polygons_out = [
        {
            "indices": [int(i) for i in polygon],
            "rgb": [float(rgb[0]), float(rgb[1]), float(rgb[2])],
        }
        for polygon, rgb in polygons
    ]
    sig = hashlib.sha1(f"{quality}|{int(optimized)}|{len(points_out)}|{len(polygons_out)}".encode("utf-8")).hexdigest()[:16]
    return {
        "version": MW_VERSION,
        "dataset_id": f"mw-{quality}-{'opti' if optimized else 'full'}-{sig}",
        "quality": quality,
        "optimized": optimized,
        "points": points_out,
        "polygons": polygons_out,
        "stats": {"points_count": len(points_out), "polygons_count": len(polygons_out)},
    }


def _get_mw_dataset(quality: str, optimized: bool) -> Dict[str, Any]:
    key = (quality, optimized)
    with _mw_cache_lock:
        cached = _mw_dataset_cache.get(key)
        if cached is not None:
            return cached
    used_catalogs = _load_used_catalogs()
    dataset = _mw_dataset_from_catalog(used_catalogs, quality, optimized)
    with _mw_cache_lock:
        _mw_dataset_cache[key] = dataset
    return dataset


def _select_mw_polygons(used_catalogs, quality: str, optimized: bool, center_ra: float, center_dec: float, field_size: float) -> List[int]:
    enhanced = used_catalogs.enhanced_milky_way_10k if quality == "10k" else used_catalogs.enhanced_milky_way_30k
    if optimized and enhanced.mw_opti_polygons is not None:
        return [int(i) for i in enhanced.select_opti_polygons((center_ra, center_dec), field_size)]
    return [int(i) for i in enhanced.select_polygons((center_ra, center_dec), field_size)]


def _stereographic_project_px(
    ra: float,
    dec: float,
    center_ra: float,
    center_dec: float,
    width: int,
    height: int,
    fov_deg: float,
    mirror_x: bool,
    mirror_y: bool,
) -> Optional[Tuple[float, float]]:
    dra = ra - center_ra
    while dra > math.pi:
        dra -= 2.0 * math.pi
    while dra < -math.pi:
        dra += 2.0 * math.pi

    sin_dec, cos_dec = math.sin(dec), math.cos(dec)
    sin_c, cos_c = math.sin(center_dec), math.cos(center_dec)

    denom = 1.0 + sin_c * sin_dec + cos_c * cos_dec * math.cos(dra)
    if denom <= 1e-9:
        return None

    k = 2.0 / denom
    x = k * cos_dec * math.sin(dra)
    y = k * (cos_c * sin_dec - sin_c * cos_dec * math.cos(dra))

    field_radius = math.radians(fov_deg) / 2.0
    plane_r = 2.0 * math.tan(field_radius / 2.0)
    if plane_r <= 1e-9:
        return None

    scale = (max(width, height) / 2.0) / plane_r
    if mirror_x:
        x = -x
    if mirror_y:
        y = -y

    px = width / 2.0 + x * scale
    py = height / 2.0 - y * scale
    return px, py


def _bbox_from_point(px: float, py: float, radius_px: float, width: int, height: int) -> Optional[Tuple[int, int, int, int]]:
    x1 = int(max(0, math.floor(px - radius_px)))
    y1 = int(max(0, math.floor(py - radius_px)))
    x2 = int(min(width - 1, math.ceil(px + radius_px)))
    y2 = int(min(height - 1, math.ceil(py + radius_px)))
    if x2 < 0 or y2 < 0 or x1 >= width or y1 >= height:
        return None
    return x1, y1, x2, y2


def _star_radius_px(mag: float) -> float:
    if mag <= 0:
        return 4.0
    if mag <= 2:
        return 3.0
    if mag <= 4:
        return 2.2
    if mag <= 6:
        return 1.8
    return 1.2


def _build_scene_index(req: SceneRequest, center_ra: float, center_dec: float, lat: float, lon: float):
    used_catalogs = _load_used_catalogs()
    _, field_size = _field_size_rad(req.fld_size_deg, req.width, req.height)
    active_theme, active_theme_name, active_theme_id = resolve_active_chart_theme_definition()
    scene_theme = active_theme.to_scene_theme_dict()
    bg_color = active_theme.background_color
    mw_color = active_theme.milky_way_color

    star_sel = None
    stars_preview: List[dict] = []
    stars_zone_selection: List[dict] = []
    stars_catalog_id = None
    stars_max_level = 0
    if used_catalogs.star_catalog is not None:
        stars_catalog_id = _stars_catalog_id(used_catalogs.star_catalog)
        stars_max_level = int(getattr(used_catalogs.star_catalog, "max_geodesic_grid_level", 0))
        star_sel = used_catalogs.star_catalog.select_stars((center_ra, center_dec), field_size, req.maglim, None)
        star_objects = _serialize_star_selection(star_sel, used_catalogs.star_catalog)
        for st in star_objects:
            # bright preview stars for initial render
            if st["mag"] <= min(4.0, req.maglim - 3.0):
                stars_preview.append(st)

    dso_items: List[dict] = []
    if FlagValue.SHOW_DEEPSKY.value in req.flags and used_catalogs.deepsky_catalog is not None:
        dso_list = used_catalogs.deepsky_catalog.select_deepsky((center_ra, center_dec), field_size, req.dso_maglim)
        dso_hide = set(_get_dso_hide_filter() or [])
        for dso in dso_list:
            if dso in dso_hide:
                continue
            dso_items.append(
                {
                    "id": dso.primary_label().replace(" ", ""),
                    "label": dso.primary_label(),
                    "ra": float(dso.ra),
                    "dec": float(dso.dec),
                    "mag": float(dso.mag),
                    "type": dso.type.name,
                    "rlong_rad": float(dso.rlong) if dso.rlong is not None else -1.0,
                    "rshort_rad": float(dso.rshort) if dso.rshort is not None else -1.0,
                    "position_angle_rad": float(dso.position_angle) if dso.position_angle is not None else (math.pi * 0.5),
                }
            )

    const_lines: List[dict] = []
    const_bounds: List[dict] = []
    const_catalog = used_catalogs.constell_catalog
    if const_catalog is not None:
        if FlagValue.CONSTELL_SHAPES.value in req.flags:
            lines = const_catalog.all_constell_lines
            for i, line in enumerate(lines):
                ra1, dec1, ra2, dec2 = float(line[0]), float(line[1]), float(line[2]), float(line[3])
                d1 = _ang_sep(ra1, dec1, center_ra, center_dec)
                d2 = _ang_sep(ra2, dec2, center_ra, center_dec)
                if min(d1, d2) <= field_size * 1.2:
                    const_lines.append({"id": f"cl{i}", "ra1": ra1, "dec1": dec1, "ra2": ra2, "dec2": dec2})

        if FlagValue.CONSTELL_BORDERS.value in req.flags:
            bp = const_catalog.boundaries_points
            for i, (idx1, idx2, cons1, cons2) in enumerate(const_catalog.boundaries_lines):
                ra1, dec1 = float(bp[idx1][0]), float(bp[idx1][1])
                ra2, dec2 = float(bp[idx2][0]), float(bp[idx2][1])
                d1 = _ang_sep(ra1, dec1, center_ra, center_dec)
                d2 = _ang_sep(ra2, dec2, center_ra, center_dec)
                if min(d1, d2) <= field_size * 1.2:
                    const_bounds.append(
                        {
                            "id": f"cb{i}",
                            "cons1": cons1,
                            "cons2": cons2,
                            "ra1": ra1,
                            "dec1": dec1,
                            "ra2": ra2,
                            "dec2": dec2,
                        }
                    )

    planets: List[dict] = []
    if FlagValue.SHOW_SOLAR_SYSTEM.value in req.flags:
        sl_bodies = get_solsys_bodies(get_utc_time(), rad2deg(lat), rad2deg(lon))
        if sl_bodies:
            for body in sl_bodies:
                label = body.solar_system_body.label.lower().replace(" ", "")
                planets.append(
                    {
                        "id": label,
                        "label": body.solar_system_body.label,
                        "ra": float(body.ra),
                        "dec": float(body.dec),
                        "type": "planet",
                    }
                )

        if req.fld_size_deg <= 12:
            pl_moons = get_planet_moons(get_utc_time(), req.maglim)
            if pl_moons:
                for moon in pl_moons:
                    planets.append(
                        {
                            "id": moon.moon_name.lower().replace(" ", ""),
                            "label": moon.moon_name,
                            "ra": float(moon.ra),
                            "dec": float(moon.dec),
                            "type": "moon",
                        }
                    )

    mirror_x = FlagValue.MIRROR_X.value in req.flags
    mirror_y = FlagValue.MIRROR_Y.value in req.flags

    selection_index: List[dict] = []
    img_map: List[object] = []

    def add_selectable(obj_id: str, ra: float, dec: float, radius_px: float):
        pxy = _stereographic_project_px(
            ra,
            dec,
            center_ra,
            center_dec,
            req.width,
            req.height,
            req.fld_size_deg,
            mirror_x,
            mirror_y,
        )
        if pxy is None:
            return
        bbox = _bbox_from_point(pxy[0], pxy[1], radius_px, req.width, req.height)
        if bbox is None:
            return
        x1, y1, x2, y2 = bbox
        selection_index.append({"id": obj_id, "bbox": [x1, y1, x2, y2]})
        # Keep compatibility with existing fchart.js flat img_map parser.
        img_map.extend([obj_id, x1, y1, x2, y2])

    for dso in dso_items:
        add_selectable(dso["id"], dso["ra"], dso["dec"], 8.0)
    for pl in planets:
        add_selectable(pl["id"], pl["ra"], pl["dec"], 6.0)
    for st in stars_preview:
        add_selectable(st["id"], st["ra"], st["dec"], max(3.0, _star_radius_px(st["mag"])))

    if req.debug_stars == "preview_only":
        lod_level = 0
    else:
        lod_level = _stars_lod(req)
        if used_catalogs.star_catalog is not None:
            stars_zone_selection = used_catalogs.star_catalog.select_star_zones(
                (center_ra, center_dec), field_size, req.maglim
            )
    mw = _mw_mode(req)
    mw_selection: List[int] = []
    mw_fade = None
    mw_dataset_id = None
    if mw["mode"] != "off":
        mw_fade = _mw_fade(req, bg_color, mw_color)
        if mw_fade is None:
            mw["mode"] = "off"
        else:
            mw_dataset = _get_mw_dataset(mw["quality"], mw["optimized"])
            mw_dataset_id = mw_dataset["dataset_id"]
            mw_selection = _select_mw_polygons(used_catalogs, mw["quality"], mw["optimized"], center_ra, center_dec, field_size)

    return {
        "version": SCENE_VERSION,
        "meta": {
            "projection": "stereographic",
            "coord_system": "equatorial" if req.is_equatorial else "horizontal",
            "fov_deg": req.fld_size_deg,
            "maglim": req.maglim,
            "dso_maglim": req.dso_maglim,
            "center": {"phi": req.phi, "theta": req.theta, "equatorial_ra": center_ra, "equatorial_dec": center_dec},
            "observer": {"lat": lat, "lon": lon},
            "mirror_x": mirror_x,
            "mirror_y": mirror_y,
            "flags": req.flags,
            "show_equatorial_grid": FlagValue.SHOW_EQUATORIAL_GRID.value in req.flags,
            "show_horizontal_grid": FlagValue.SHOW_HORIZONTAL_GRID.value in req.flags,
            "theme_name": active_theme_name,
            "theme_id": active_theme_id,
            "theme_version": active_theme.scene_theme_hash(),
            "theme": scene_theme,
            "stars_lod": lod_level,
            "stars_stream": {
                "enabled": used_catalogs.star_catalog is not None and req.debug_stars != "preview_only",
                "catalog_id": stars_catalog_id,
                "max_level": stars_max_level,
                "batch_max": STAR_ZONE_BATCH_MAX,
            },
            "milky_way": {
                "mode": mw["mode"],
                "quality": mw["quality"],
                "optimized": mw["optimized"],
                "dataset_id": mw_dataset_id,
                "fade": mw_fade,
            },
        },
        "layers": [
            "milky_way",
            "stars",
            "dso",
            "constellation_lines",
            "constellation_boundaries",
            "planets",
            "grid_eq",
            "grid_hor",
            "highlights",
        ],
        "objects": {
            "stars_preview": stars_preview,
            "stars_zone_selection": stars_zone_selection,
            "dso": dso_items,
            "constellation_lines": const_lines,
            "constellation_boundaries": const_bounds,
            "planets": planets,
            "milky_way_selection": mw_selection,
            "grid_eq": [],
            "grid_hor": [],
            "highlights": [],
        },
        "selection_index": selection_index,
        "img_map": img_map,
        "legend_url": request.url_root.rstrip("/") + request.path.replace("/scene-v1", "/chart-legend-img"),
    }


def build_scene_v1() -> Dict:
    req = _resolve_scene_request()
    _, lat_deg, lon_deg = resolve_chart_city_lat_lon()
    lat = deg2rad(lat_deg)
    lon = deg2rad(lon_deg)
    center_ra, center_dec = _resolve_center_equatorial(req, lat, lon)
    center_ra = _normalize_ra(center_ra)

    return _build_scene_index(req, center_ra, center_dec, lat, lon)


def build_stars_zones_v1() -> Dict:
    req = _resolve_scene_request()
    raw_zones = request.args.get("zones", "")
    try:
        zone_refs = _parse_zone_refs_arg(raw_zones)
    except Exception:
        abort(400)
    if len(zone_refs) > STAR_ZONE_BATCH_MAX:
        abort(400)

    used_catalogs = _load_used_catalogs()
    star_catalog = used_catalogs.star_catalog
    if star_catalog is None:
        return {
            "version": STARS_VERSION,
            "catalog_id": None,
            "maglim": req.maglim,
            "zones": [],
            "missing": [],
            "stats": {"zones_count": 0, "stars_count": 0},
        }

    expected_catalog_id = request.args.get("catalog_id")
    catalog_id = _stars_catalog_id(star_catalog)

    _, lat_deg, lon_deg = resolve_chart_city_lat_lon()
    lat = deg2rad(lat_deg)
    lon = deg2rad(lon_deg)
    center_ra, center_dec = _resolve_center_equatorial(req, lat, lon)
    center_ra = _normalize_ra(center_ra)
    _, field_size = _field_size_rad(req.fld_size_deg, req.width, req.height)

    zones_out: List[dict] = []
    missing: List[str] = []
    stars_total = 0
    for level, zone in zone_refs:
        zone_sel = star_catalog.select_zone_stars((center_ra, center_dec), field_size, req.maglim, level, zone, None)
        stars = _serialize_star_selection(zone_sel, star_catalog)
        if zone_sel is None:
            missing.append(f"L{level}Z{zone}")
        stars_total += len(stars)
        zones_out.append({"level": level, "zone": zone, "stars": stars})

    return {
        "version": STARS_VERSION,
        "catalog_id": catalog_id,
        "catalog_mismatch": bool(expected_catalog_id and expected_catalog_id != catalog_id),
        "maglim": req.maglim,
        "zones": zones_out,
        "missing": missing,
        "stats": {"zones_count": len(zones_out), "stars_count": stars_total},
    }


def build_milkyway_catalog_v1() -> Dict:
    req = _resolve_scene_request()
    mode = _mw_mode_with_overrides(req)
    if mode["mode"] == "off":
        return {
            "version": MW_VERSION,
            "mode": "off",
            "dataset_id": None,
            "quality": None,
            "optimized": False,
            "points": [],
            "polygons": [],
            "stats": {"points_count": 0, "polygons_count": 0},
        }
    return _get_mw_dataset(mode["quality"], mode["optimized"])


def build_milkyway_select_v1() -> Dict:
    req = _resolve_scene_request()
    mode = _mw_mode_with_overrides(req)
    if mode["mode"] == "off":
        return {
            "version": MW_VERSION,
            "mode": "off",
            "dataset_id": None,
            "selection": [],
            "fade": None,
        }

    _, lat_deg, lon_deg = resolve_chart_city_lat_lon()
    lat = deg2rad(lat_deg)
    lon = deg2rad(lon_deg)
    center_ra, center_dec = _resolve_center_equatorial(req, lat, lon)
    center_ra = _normalize_ra(center_ra)
    _, field_size = _field_size_rad(req.fld_size_deg, req.width, req.height)
    used_catalogs = _load_used_catalogs()
    active_theme, _, _ = resolve_active_chart_theme_definition()
    fade = _mw_fade(req, active_theme.background_color, active_theme.milky_way_color)
    if fade is None:
        return {
            "version": MW_VERSION,
            "mode": "off",
            "dataset_id": None,
            "selection": [],
            "fade": None,
        }
    dataset = _get_mw_dataset(mode["quality"], mode["optimized"])
    selection = _select_mw_polygons(used_catalogs, mode["quality"], mode["optimized"], center_ra, center_dec, field_size)
    return {
        "version": MW_VERSION,
        "mode": mode["mode"],
        "dataset_id": dataset["dataset_id"],
        "quality": mode["quality"],
        "optimized": mode["optimized"],
        "selection": selection,
        "fade": fade,
    }

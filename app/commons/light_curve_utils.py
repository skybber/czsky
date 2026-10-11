import io
import math
from datetime import datetime, timedelta, timezone

import numpy as np
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_svg import FigureCanvasSVG

from skyfield.api import load
from skyfield.data import mpc
from skyfield.constants import GM_SUN_Pitjeva_2005_km3_s2 as GM_SUN

from app.commons.visibility_utils import THEMES

# Sized for the default left (embed) panel (~430 px wide), so the SVG is shown 1:1 there.
# matplotlib SVG uses 72 pt per inch and browsers render 1 pt as 4/3 px.
LIGHT_CURVE_FIGSIZE = (4.4, 3.4)
FONT_TITLE = 10
FONT_LABEL = 9
FONT_TICKS = 8
FONT_ANNOTATION = 7.5

LIGHT_CURVE_RANGES = (90, 180, 365, 730)
DEFAULT_LIGHT_CURVE_RANGE = 180
MAX_LIGHT_CURVE_SAMPLES = 800


def parse_light_curve_range(value):
    try:
        days = int(value)
    except (TypeError, ValueError):
        return DEFAULT_LIGHT_CURVE_RANGE
    return days if days in LIGHT_CURVE_RANGES else DEFAULT_LIGHT_CURVE_RANGE


def light_curve_dates(center_dt, half_range_days):
    """Return equidistant UTC datetimes covering center_dt +- half_range_days."""
    if center_dt.tzinfo is None:
        center_dt = center_dt.replace(tzinfo=timezone.utc)
    start = center_dt - timedelta(days=half_range_days)
    sample_count = max(200, min(MAX_LIGHT_CURVE_SAMPLES, 2 * half_range_days + 1))
    span = timedelta(days=2 * half_range_days)
    return [start + span * i / (sample_count - 1) for i in range(sample_count)]


def body_geometry(body_orbit_factory, dates):
    """Heliocentric distance r, geocentric distance delta and phase angle (deg) of a body."""
    ts = load.timescale(builtin=True)
    eph = load('de421.bsp')
    sun, earth = eph['sun'], eph['earth']
    t = ts.from_datetimes(dates)
    body = sun + body_orbit_factory(ts)

    sun_body = (body.at(t).position.au - sun.at(t).position.au)
    earth_at = earth.at(t)
    earth_body = earth_at.observe(body).position.au
    earth_sun = earth_at.observe(sun).position.au

    r = np.linalg.norm(sun_body, axis=0)
    delta = np.linalg.norm(earth_body, axis=0)
    earth_sun_dist = np.linalg.norm(earth_sun, axis=0)
    cos_phase = (r ** 2 + delta ** 2 - earth_sun_dist ** 2) / (2.0 * r * delta)
    phase = np.degrees(np.arccos(np.clip(cos_phase, -1.0, 1.0)))
    return r, delta, phase


def hg_magnitude(h_mag, g_slope, r, delta, phase_deg):
    """IAU H-G magnitude system (Bowell et al. 1989)."""
    if g_slope is None or not math.isfinite(g_slope):
        g_slope = 0.15
    tan_half = np.tan(np.radians(np.clip(phase_deg, 0.0, 179.9)) / 2.0)
    phi1 = np.exp(-3.33 * np.power(tan_half, 0.63))
    phi2 = np.exp(-1.87 * np.power(tan_half, 1.22))
    flux = np.maximum((1.0 - g_slope) * phi1 + g_slope * phi2, 1e-12)
    return h_mag + 5.0 * np.log10(r * delta) - 2.5 * np.log10(flux)


def comet_magnitude(g_mag, k_slope, r, delta):
    """Total cometary magnitude m = g + 5 log(delta) + 2.5 k log(r)."""
    return g_mag + 5.0 * np.log10(delta) + 2.5 * k_slope * np.log10(r)


def minor_planet_light_curve(mpc_minor_planet, h_mag, g_slope, dates):
    r, delta, phase = body_geometry(lambda ts: mpc.mpcorb_orbit(mpc_minor_planet, ts, GM_SUN), dates)
    return hg_magnitude(h_mag, g_slope, r, delta, phase)


def comet_light_curve(mpc_comet, dates):
    r, delta, _ = body_geometry(lambda ts: mpc.comet_orbit(mpc_comet, ts, GM_SUN), dates)
    return comet_magnitude(mpc_comet['magnitude_g'], mpc_comet['magnitude_k'], r, delta)


def _label_align(dates, dt):
    """Keep annotations near the plot edges inside the axes."""
    span = dates[-1] - dates[0]
    if dt < dates[0] + span * 0.15:
        return 'left'
    if dt > dates[-1] - span * 0.15:
        return 'right'
    return 'center'


def create_light_curve_svg(dates, magnitudes, cursor_dt=None, observations=None, theme='dark',
                           title=None, model_label=None, observations_label=None,
                           x_label='Date', y_label='Magnitude'):
    """
    Render predicted light curve as SVG string.

    observations: optional list of (datetime, mag) pairs drawn as scatter points.
    """
    colors = THEMES.get(theme, THEMES['dark'])
    fg = colors['fg_color']

    fig = Figure(figsize=LIGHT_CURVE_FIGSIZE, dpi=100)
    FigureCanvasSVG(fig)
    fig.patch.set_facecolor(colors['bg_color'])
    ax = fig.add_subplot(111)
    ax.set_facecolor(colors['bg_color'])

    mags = np.asarray(magnitudes, dtype=float)
    finite = np.isfinite(mags)
    ax.plot(np.array(dates)[finite], mags[finite], color=colors['object_color'], lw=1.6, label=model_label)

    if observations:
        start, stop = dates[0], dates[-1]
        obs = [(d, m) for d, m in observations if m is not None and start <= d <= stop]
        if obs:
            ax.scatter([o[0] for o in obs], [o[1] for o in obs], s=6, color=fg, alpha=0.6,
                       edgecolors='none', label=observations_label, zorder=4)

    show_cursor = cursor_dt is not None and dates[0] <= cursor_dt <= dates[-1]
    if finite.any():
        i_max = int(np.nanargmin(np.where(finite, mags, np.nan)))
        span = dates[-1] - dates[0]
        # cursor label already describes the maximum when they are close together
        max_near_cursor = show_cursor and abs(dates[i_max] - cursor_dt) < span * 0.08
        ax.margins(y=0.12)
    if finite.any() and not max_near_cursor:
        ax.scatter([dates[i_max]], [mags[i_max]], s=14, color=colors['object_color'], zorder=5)
        ax.annotate(f'{dates[i_max]:%Y-%m-%d}\n{mags[i_max]:.1f} mag', (dates[i_max], mags[i_max]),
                    xytext=(0, 5), textcoords='offset points', ha=_label_align(dates, dates[i_max]), va='bottom',
                    color=fg, fontsize=FONT_ANNOTATION)

    if show_cursor:
        i_cur = min(range(len(dates)), key=lambda i: abs(dates[i] - cursor_dt))
        ax.axvline(cursor_dt, color=colors['horizon_color'], lw=0.9, alpha=0.9)
        if finite[i_cur]:
            ax.scatter([cursor_dt], [mags[i_cur]], s=22, color=colors['horizon_color'], edgecolors=fg,
                       linewidths=0.6, zorder=6)
            right_half = cursor_dt > dates[0] + (dates[-1] - dates[0]) / 2
            ax.annotate(f'{cursor_dt:%Y-%m-%d}\n{mags[i_cur]:.2f} mag', (cursor_dt, mags[i_cur]),
                        xytext=(-5 if right_half else 5, 5), textcoords='offset points',
                        ha='right' if right_half else 'left', color=fg, fontsize=FONT_ANNOTATION)

    if not ax.yaxis_inverted():
        ax.invert_yaxis()
    ax.grid(True, color=colors['grid_color'], alpha=colors['grid_alpha'], linestyle='--', linewidth=0.6)
    ax.set_xlabel(x_label, color=fg, fontsize=FONT_LABEL)
    ax.set_ylabel(y_label, color=fg, fontsize=FONT_LABEL)
    if title:
        ax.set_title(title, color=fg, fontsize=FONT_TITLE)
    ax.tick_params(colors=fg, labelsize=FONT_TICKS)
    for spine in ax.spines.values():
        spine.set_color(colors['grid_color'])
    locator = mdates.AutoDateLocator(minticks=3, maxticks=6)
    ax.xaxis.set_major_locator(locator)
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_formatter(formatter)
    ax.xaxis.get_offset_text().set_color(fg)
    ax.xaxis.get_offset_text().set_fontsize(FONT_TICKS)
    if model_label or (observations and observations_label):
        legend = ax.legend(loc='best', fontsize=FONT_TICKS, facecolor=colors['bg_color'], edgecolor=colors['grid_color'])
        for text in legend.get_texts():
            text.set_color(fg)
    fig.tight_layout(pad=0.4)

    out = io.StringIO()
    fig.savefig(out, format='svg', facecolor=fig.get_facecolor())
    return out.getvalue()

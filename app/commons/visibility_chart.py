import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for speed
import matplotlib.pyplot as plt
from datetime import datetime
import matplotlib.dates as mdates
from matplotlib.patches import Patch
import io

try:
    from astropy import units as u
    from astropy.time import Time
    from astropy.coordinates import SkyCoord, EarthLocation, get_sun
    from astroplan import Observer, FixedTarget
    import warnings
    warnings.filterwarnings('ignore')
    ASTRO_AVAILABLE = True
except ImportError:
    ASTRO_AVAILABLE = False


THEMES = {
    'light': {
        'bg_color': 'white',
        'fg_color': 'black',
        'grid_color': 'gray',
        'grid_alpha': 0.3,
        'object_color': '#D32F2F',
        'horizon_color': '#8B4513',
        'day': ('#87CEEB', 0.3),
        'civil': ('#FFA500', 0.2),
        'nautical': ('#4169E1', 0.2),
        'astronomical': ('#191970', 0.2),
        'night': ('#000033', 0.3),
    },
    'dark': {
        'bg_color': '#1a1a1a',
        'fg_color': 'white',
        'grid_color': '#666666',
        'grid_alpha': 0.3,
        'object_color': '#FF5252',
        'horizon_color': '#CD853F',
        'day': ('#4A90E2', 0.2),
        'civil': ('#FF8C00', 0.15),
        'nautical': ('#1E3A8A', 0.2),
        'astronomical': ('#0F1729', 0.25),
        'night': ('#000000', 0.3),
    },
    'night': {
        'bg_color': '#1a0000',
        'fg_color': '#ff3333',
        'grid_color': '#660000',
        'grid_alpha': 0.4,
        'object_color': '#ff0000',
        'horizon_color': '#cc0000',
        'day': ('#330000', 0.3),
        'civil': ('#4d0000', 0.2),
        'nautical': ('#660000', 0.2),
        'astronomical': ('#1a0000', 0.25),
        'night': ('#000000', 0.3),
    }
}


def _make_target_from_coords(ra, dec):
    """
    Build SkyCoord from RA/Dec inputs.

    Supported formats:
    - floats/ints: interpreted as degrees (RA rad, Dec rad)
    - strings:
        RA: 'hh:mm:ss' or 'hh mm ss' -> hourangle
            or '1.45' -> radians
        Dec: '+dd:mm:ss' or '+dd mm ss' -> degrees
             or '-1.34' -> radians
    """
    # Numeric -> degrees
    if isinstance(ra, (int, float, np.floating)) and isinstance(dec, (int, float, np.floating)):
        return SkyCoord(ra=float(ra) * u.rad, dec=float(dec) * u.rad, frame='icrs')

    # String parsing
    ra_s = str(ra).strip()
    dec_s = str(dec).strip()

    # Heuristic: if RA contains ':' or whitespace, assume hourangle
    ra_is_hms = (':' in ra_s) or ((' ' in ra_s) and any(ch.isdigit() for ch in ra_s))

    if ra_is_hms:
        return SkyCoord(ra=ra_s, dec=dec_s, unit=(u.hourangle, u.deg), frame='icrs')
    else:
        # RA as degrees string
        return SkyCoord(ra=float(ra_s) * u.rad, dec=float(dec_s) * u.rad, frame='icrs')


def create_visibility_chart(
        location_name,
        latitude, longitude, elevation,
        date_str,
        ra, dec,                       # <-- coordinates ONLY
        object_label=None,             # optional label for legend/title
        output_file=None,
        theme='light',
        return_svg_string=False,
        num_points=73,                 # Reduced from 145 for speed
        panel_mode=True,               # True = tuned for small left panel (bigger text, fewer ticks)
        scale=1.0,                     # Global scaling for fonts/line widths
        font_sizes=None,               # Optional overrides: {"title":18,"label":15,"ticks":13,"legend":12}
        x_major_hours=3,               # Major ticks/grid every N hours (reduces "X mesh" density)
        x_minor_minutes=30,            # Minor ticks every N minutes (minor grid usually off)
        grid_major=True,
        grid_minor=False,              # Keep False to avoid dense "X mesh"
        grid_linestyle='--',
        grid_linewidth=1.0,
        grid_alpha=None,               # If None, use theme grid_alpha
        rotate_xticks=30               # Less rotation helps in narrow panels
):
    """
    FAST version: Create SVG visibility chart for an astronomical target (RA/Dec only)

    New parameters allow controlling font sizes and x-grid density for small panels.
    Backwards compatible: existing calls still work.
    """
    if theme not in THEMES:
        raise ValueError(f"Unknown theme '{theme}'")
    colors = THEMES[theme]

    # ---- Font sizing defaults (tuned for a small side panel) ----
    # Note: font_sizes overrides individual fields after base+scale.
    base_fonts = {
        "title": 15,
        "label": 13,
        "ticks": 11,
        "legend": 10,
    }
    if panel_mode:
        base_fonts = {
            "title": 18,
            "label": 15,
            "ticks": 14,
            "legend": 14,
        }

    # Apply global scale
    scale = float(scale)
    base_fonts = {k: v * scale for k, v in base_fonts.items()}

    # Apply optional per-field overrides
    if font_sizes:
        for k, v in font_sizes.items():
            if k in base_fonts and v is not None:
                base_fonts[k] = float(v)

    # Grid alpha default
    if grid_alpha is None:
        grid_alpha = colors['grid_alpha']

    # Create observer
    location = EarthLocation(lat=latitude * u.deg, lon=longitude * u.deg, height=elevation * u.m)
    observer = Observer(location=location, name=location_name, timezone='UTC')

    # Observation date
    obs_date = datetime.strptime(date_str, '%Y-%m-%d')
    obs_time = Time(obs_date)

    # Time range
    midnight = observer.midnight(obs_time, which='next')
    time_range = midnight + np.linspace(-12, 12, num_points) * u.hour

    # Target from coordinates (NO name resolution)
    coord = _make_target_from_coords(ra, dec)
    target = FixedTarget(coord=coord, name='target')

    # Altitude of target (vectorized)
    altaz = observer.altaz(time_range, target)
    altitudes = altaz.alt.degree

    # Sun altitude (vectorized)
    sun_coords = get_sun(time_range)
    sun_altaz = observer.altaz(time_range, sun_coords)
    sun_altitudes = sun_altaz.alt.degree

    times_plot = time_range.to_datetime()

    # Auto label if not provided
    if object_label is None:
        ra_fmt = coord.ra.to_string(unit=u.hourangle, sep=':', precision=1, pad=True)
        dec_fmt = coord.dec.to_string(unit=u.deg, sep=':', precision=1, alwayssign=True, pad=True)
        object_label = f"RA {ra_fmt}  Dec {dec_fmt}"

    # Figure sizing: for small panels, smaller figsize + higher DPI tends to render nicer
    dpi = 140 if panel_mode else 100
    figsize = (12, 6.5) if panel_mode else (16, 9)

    fig, ax = plt.subplots(figsize=figsize, facecolor=colors['bg_color'], dpi=dpi)
    ax.set_facecolor(colors['bg_color'])

    twilight_colors = {
        'day': (colors['day'][0], colors['day'][1]),
        'civil': (colors['civil'][0], colors['civil'][1]),
        'nautical': (colors['nautical'][0], colors['nautical'][1]),
        'astronomical': (colors['astronomical'][0], colors['astronomical'][1]),
        'night': (colors['night'][0], colors['night'][1]),
    }

    # Background twilight bands
    for i in range(len(times_plot) - 1):
        sun_alt = sun_altitudes[i]

        if sun_alt > -0.5:
            color, alpha = twilight_colors['day']
        elif sun_alt > -6:
            color, alpha = twilight_colors['civil']
        elif sun_alt > -12:
            color, alpha = twilight_colors['nautical']
        elif sun_alt > -18:
            color, alpha = twilight_colors['astronomical']
        else:
            color, alpha = twilight_colors['night']

        ax.axvspan(times_plot[i], times_plot[i + 1], facecolor=color, alpha=alpha, zorder=1)

    # Target curve (scale line width slightly too)
    ax.plot(
        times_plot,
        altitudes,
        color=colors['object_color'],
        linewidth=3 * scale,
        label=object_label,
        zorder=10
    )

    # Horizon line
    ax.axhline(
        y=0,
        color=colors['horizon_color'],
        linestyle='-',
        linewidth=2.5 * scale,
        label='Horizon',
        zorder=5
    )

    # Helper lines
    for alt in [30, 60]:
        ax.axhline(
            y=alt,
            color=colors['grid_color'],
            linestyle=':',
            linewidth=1.0 * scale,
            alpha=0.5,
            zorder=2
        )

    # ---- X axis formatting (controls "X mesh" density) ----
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=int(x_major_hours)))

    # Minor ticks can be enabled, but keep minor grid off by default to avoid dense mesh
    if x_minor_minutes and int(x_minor_minutes) > 0:
        ax.xaxis.set_minor_locator(mdates.MinuteLocator(interval=int(x_minor_minutes)))

    # Major grid only by default (prevents "too dense X mesh")
    ax.grid(
        grid_major,
        which='major',
        alpha=grid_alpha,
        linestyle=grid_linestyle,
        linewidth=grid_linewidth * scale,
        color=colors['grid_color'],
        zorder=2
    )
    if grid_minor:
        ax.grid(
            True,
            which='minor',
            alpha=grid_alpha * 0.6,
            linestyle=':',
            linewidth=max(0.5, grid_linewidth * 0.7) * scale,
            color=colors['grid_color'],
            zorder=2
        )

    # Tick styling + font sizes
    plt.setp(
        ax.xaxis.get_majorticklabels(),
        rotation=rotate_xticks,
        ha='right',
        color=colors['fg_color'],
        fontsize=base_fonts["ticks"]
    )
    plt.setp(
        ax.yaxis.get_majorticklabels(),
        color=colors['fg_color'],
        fontsize=base_fonts["ticks"]
    )
    ax.tick_params(axis='x', colors=colors['fg_color'])
    ax.tick_params(axis='y', colors=colors['fg_color'])

    # Labels
    ax.set_xlabel('Time (UTC)', fontsize=base_fonts["label"], fontweight='bold', color=colors['fg_color'])
    ax.set_ylabel('Altitude [°]', fontsize=base_fonts["label"], fontweight='bold', color=colors['fg_color'])
    ax.set_title(
        f'{object_label} — {location_name} — {date_str}',
        fontsize=base_fonts["title"],
        fontweight='bold',
        pad=20,
        color=colors['fg_color']
    )

    # Y axis range
    ax.set_ylim(-25, 90)
    ax.set_yticks(np.arange(-20, 91, 10))

    # Spines
    for spine in ax.spines.values():
        spine.set_edgecolor(colors['fg_color'])

    # Legend (simplified for speed)
    legend_elements = [
        plt.Line2D([0], [0], color=colors['object_color'], linewidth=3 * scale, label=object_label),
        plt.Line2D([0], [0], color=colors['horizon_color'], linewidth=2.5 * scale, label='Horizon'),
        Patch(facecolor=colors['day'][0], alpha=colors['day'][1], label='Day'),
        Patch(facecolor=colors['night'][0], alpha=colors['night'][1], label='Night'),
    ]
    legend = ax.legend(
        handles=legend_elements,
        loc='upper right',
        fontsize=base_fonts["legend"],
        framealpha=0.9,
        facecolor=colors['bg_color'],
        edgecolor=colors['fg_color']
    )
    plt.setp(legend.get_texts(), color=colors['fg_color'])

    plt.tight_layout()

    # Save or return SVG
    if return_svg_string:
        svg_buffer = io.BytesIO()
        plt.savefig(svg_buffer, format='svg', bbox_inches='tight')
        plt.close(fig)
        svg_buffer.seek(0)
        return svg_buffer.getvalue().decode('utf-8')
    else:
        if not output_file:
            raise ValueError("output_file must be set when return_svg_string=False")
        plt.savefig(output_file, format='svg', dpi=dpi, bbox_inches='tight')
        plt.close(fig)
        return None

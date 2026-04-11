import os

# Load the application before forking workers so that the catalog data
# (UsedCatalogs / GeodesicGrid / star_blocks numpy arrays) is mapped into the
# master process address space.  Linux COW semantics then let every worker
# share those read-only pages without copying them, giving significant RSS
# savings when running with multiple workers.
preload_app = True

# ── tunables ──────────────────────────────────────────────────────────────────
workers = int(os.environ.get('GUNICORN_WORKERS', 1))
worker_class = 'sync'
bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:5000')
timeout = int(os.environ.get('GUNICORN_TIMEOUT', 120))
# ──────────────────────────────────────────────────────────────────────────────


def when_ready(server):
    """Called in master after the app has been loaded but before forking.

    Triggering load_used_catalogs() here ensures the heavy catalog data
    (star files, GeodesicGrid, MilkyWay, etc.) lives in the master's address
    space.  Each worker inherits the already-mapped pages via fork(); as long as
    workers only read the catalog (they do), the OS never needs to copy the
    pages, so total RSS grows by at most one copy instead of N copies.
    """
    try:
        from app.commons.chart_generator import load_used_catalogs
        server.log.info('Preloading star catalogs in master process …')
        load_used_catalogs()
        server.log.info('Star catalogs preloaded – workers will share read-only pages.')
    except Exception as exc:
        server.log.warning('Could not preload star catalogs: %s', exc)


def post_fork(server, worker):
    """Called in each worker right after fork().

    SQLAlchemy and other connection-based resources must not be shared across
    the fork boundary.  Disposing the engine makes each worker open its own
    fresh connections.
    """
    try:
        from app import db
        db.engine.dispose()
    except Exception as exc:
        server.log.warning('post_fork: could not dispose DB engine: %s', exc)

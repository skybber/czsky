from __future__ import annotations

import os

from app import create_app

_APP = None


def get_app():
    global _APP
    if _APP is None:
        _APP = create_app(os.getenv("FLASK_CONFIG") or "default", web=False)
    return _APP

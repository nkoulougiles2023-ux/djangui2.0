"""Vercel serverless entry point — exposes the Django WSGI app as `app`."""
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangui.settings")

_import_error = None
try:
    from djangui.wsgi import application as _django_app
except Exception:
    _import_error = traceback.format_exc()
    _django_app = None


def app(environ, start_response):
    if _django_app is None:
        start_response(
            "500 Internal Server Error",
            [("Content-Type", "text/plain; charset=utf-8")],
        )
        body = (
            "DJANGUI boot error — Django failed to initialize.\n\n"
            + (_import_error or "unknown")
        )
        return [body.encode("utf-8")]
    try:
        return _django_app(environ, start_response)
    except Exception:
        tb = traceback.format_exc()
        start_response(
            "500 Internal Server Error",
            [("Content-Type", "text/plain; charset=utf-8")],
        )
        return [f"DJANGUI request error:\n\n{tb}".encode("utf-8")]

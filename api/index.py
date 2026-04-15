"""Vercel serverless entry point — exposes the Django WSGI app as `app`."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangui.settings")

from djangui.wsgi import application  # noqa: E402

app = application

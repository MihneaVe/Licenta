"""ASGI config for the CivicPulse / social_mood_meter project."""

import os
import sys
from pathlib import Path

from django.core.asgi import get_asgi_application


_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
for _entry in (str(_BACKEND_DIR), str(_PROJECT_ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_asgi_application()

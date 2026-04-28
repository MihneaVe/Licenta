#!/usr/bin/env python
import os
import sys
from pathlib import Path


def main():
    # `api/`, `scrapers/`, `interpreters/`, `geo/` live at the project
    # root (one level above this file's parent). Put both directories on
    # sys.path so `manage.py` can be invoked from anywhere.
    backend_dir = Path(__file__).resolve().parent
    project_root = backend_dir.parent
    for entry in (str(backend_dir), str(project_root)):
        if entry not in sys.path:
            sys.path.insert(0, entry)

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()

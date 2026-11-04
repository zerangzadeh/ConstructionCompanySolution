"""Local visual review of the saved pre-change templates or current implementation."""
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django
django.setup()
from django.conf import settings
from django.core.management import call_command
mode = sys.argv[1] if len(sys.argv) > 1 else "after"
if mode not in {"before", "after"}:
    raise SystemExit("Choose before or after")
if mode == "before":
    settings.TEMPLATES[0]["DIRS"] = [str(Path(__file__).parent / "baseline/templates"), *settings.TEMPLATES[0]["DIRS"]]
call_command("runserver", "127.0.0.1:" + ("8012" if mode == "before" else "8011"), use_reloader=False)

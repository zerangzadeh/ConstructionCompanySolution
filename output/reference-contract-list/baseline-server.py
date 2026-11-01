"""Render the starting HEAD templates for matched before screenshots only."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
from django.conf import settings
from django.core.management import execute_from_command_line

baseline = Path(tempfile.mkdtemp(prefix="bonira-list-baseline-"))
for name in ("base.html", "contracts/list.html", "components/filter_bar.html"):
    target = baseline / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(subprocess.check_output(["git", "show", "HEAD:templates/" + name], cwd=root))
settings.TEMPLATES[0]["DIRS"].insert(0, baseline)
execute_from_command_line(["manage.py", "runserver", "127.0.0.1:8001", "--noreload"])

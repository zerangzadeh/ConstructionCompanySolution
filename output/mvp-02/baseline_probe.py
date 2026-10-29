"""Read-only HEAD probe for unrelated registry/platform baseline failures."""

import importlib
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
import pytest

for name in ("apps.organizations.permission_registry", "core.product_surface"):
    module = importlib.import_module(name)
    path = name.replace(".", "/") + ".py"
    original = subprocess.check_output(["git", "show", "HEAD:" + path])
    exec(compile(original, str(Path(path).resolve()), "exec"), module.__dict__)  # noqa: S102 -- trusted recorded HEAD, isolated verification process
print(
    "HEAD source probe:",
    subprocess.check_output(["git", "rev-parse", "HEAD"], encoding="utf-8").strip(),
)
sys.exit(pytest.main(sys.argv[1:]))

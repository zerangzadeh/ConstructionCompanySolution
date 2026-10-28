"""Reproduce selected baseline debt from HEAD without editing the working tree.

Runs in a disposable Python process against Django's test DB. Original affected
Python modules and templates are loaded from read-only git show; product-surface
middleware is omitted. No checkout, index, commit, branch or worktree writes.
"""

import importlib
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import django
import pytest
from django.conf import settings
from django.test import override_settings

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

MODULES = (
    "apps.organizations.context_processors",
    "core.financial_navigation",
    "core.home",
    "core.search",
    "core.views",
    "apps.workflows.workbench",
    "apps.workflows.views",
    "apps.reporting.views",
)


def head_bytes(path):
    return subprocess.check_output(["git", "show", f"HEAD:{path}"])


for module_name in MODULES:
    module = importlib.import_module(module_name)
    path = module_name.replace(".", "/") + ".py"
    # Execute only the trusted repository's recorded HEAD in this test process.
    exec(compile(head_bytes(path), str(Path(path).resolve()), "exec"), module.__dict__)  # noqa: S102

templates = {}
changed = subprocess.check_output(
    ["git", "diff", "--name-only"], text=True, stderr=subprocess.DEVNULL
).splitlines()
for path in changed:
    if path.endswith(".html") and "templates/" in path:
        templates[path.split("templates/", 1)[1]] = head_bytes(path).decode("utf-8")
configuration = deepcopy(settings.TEMPLATES)
configuration[0]["APP_DIRS"] = False
configuration[0]["OPTIONS"]["loaders"] = [
    ("django.template.loaders.locmem.Loader", templates),
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
]
baseline = override_settings(
    MIDDLEWARE=[
        value
        for value in settings.MIDDLEWARE
        if value != "core.product_surface_middleware.ProductSurfaceMiddleware"
    ],
    TEMPLATES=configuration,
)
baseline.enable()
print(
    "Read-only HEAD baseline:",
    subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
)
print(
    f"Original modules={len(MODULES)}, original templates={len(templates)}; isolated test process"
)
sys.exit(pytest.main(sys.argv[1:]))

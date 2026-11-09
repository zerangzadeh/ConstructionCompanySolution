"""Read-only A/B template comparison for existing workbench query failures."""

import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from copy import deepcopy

import pytest
from django.conf import settings
from django.db import connections
from django.test import override_settings

connections["default"].settings_dict["TEST"]["NAME"] = "test_bonira_f2_20261102"
replacements = {}
base = (root / "templates/base.html").read_text(encoding="utf-8")
base = (
    base.replace('    {% include "components/interaction_styles.html" %}\n', "")
    .replace('    {% include "components/interaction_scripts.html" %}\n', "")
    .replace('            <div id="bonira-feedback"></div>\n', "")
)
replacements["base.html"] = base
row = (root / "apps/workflows/templates/workflows/_work_item_row.html").read_text(encoding="utf-8")
replacements["workflows/_work_item_row.html"] = row.replace(
    '{% if request.META.HTTP_HX_REQUEST == \'true\' and messages %}<template><div hx-swap-oob="beforeend:#bonira-feedback">{% include "components/messages.html" %}</div></template>{% endif %}',
    "",
)
config = deepcopy(settings.TEMPLATES)
config[0]["APP_DIRS"] = False
config[0]["OPTIONS"]["loaders"] = [
    ("django.template.loaders.locmem.Loader", replacements),
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
]
with override_settings(TEMPLATES=config):
    raise SystemExit(
        pytest.main(
            [
                "apps/workflows/test_workbench.py::WorkbenchTests::test_high_open_item_volume_keeps_page_and_query_count_bounded",
                "apps/workflows/test_workbench.py::WorkbenchTests::test_pagination_responsive_context_and_query_bound",
                "--reuse-db",
                "-q",
                "--tb=short",
            ]
        )
    )

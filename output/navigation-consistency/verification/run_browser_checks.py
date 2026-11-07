"""Run an explicit navigation scenario class against the dedicated disposable DB."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(Path(__file__).resolve().parent)]
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
os.environ["BONIRA_BROWSER_LOCAL_ONLY"] = "1"
import django

django.setup()
from django.db import connections
from django.test.runner import DiscoverRunner

connections["default"].settings_dict["TEST"]["NAME"] = (
    "test_bonira_navigation_browser_20261106"
)
labels = sys.argv[1:] or [
    "browser_scenarios.TenantNavigation.test_changed_routes_and_permissions",
    "browser_scenarios.ProcurementNavigation.test_rfq",
    "browser_scenarios.EvidenceNavigation.test_evidence_return",
    "browser_scenarios.PlatformNavigation.test_platform_contexts",
    "browser_scenarios.ModuleJourneys.test_module_home_round_trips",
    "browser_scenarios.Inventory.test_compile_templates_and_inventory_routes",
]
raise SystemExit(
    bool(DiscoverRunner(keepdb=True, verbosity=1, interactive=False).run_tests(labels))
)

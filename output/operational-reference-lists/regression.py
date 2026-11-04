"""Affected regression using the isolated, migrated PostgreSQL test database."""
import os
import sys
from pathlib import Path
from importlib import import_module
sys.path.insert(0, str(Path.cwd()))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()
from django.conf import settings
from django.test.runner import DiscoverRunner
from django.db import connection
from django.apps import apps
settings.PRODUCT_SURFACE_PROFILE = 'FULL_ERP'
class Runner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        state = super().setup_databases(**kwargs)
        assert connection.settings_dict['NAME'].startswith('test_')
        # LiveServer's governed retained-FK cleanup flushes data-migration seeds.
        # Restore the canonical expense-group fixture, only in this test database.
        import_module('apps.expenses.migrations.0006_platformexpensegroup_expensecategory_primary_group').seed_and_link_groups(apps, None)
        for migration, seed in [('0013_safety_compatibility_catalog','seed_safety_catalog'), ('0014_quality_compatibility_catalog','seed_quality_catalog')]:
            getattr(import_module('apps.workflows.migrations.'+migration),seed)(apps,None)
        return state
from apps.contracts.test_reference_list_browser import ReferenceContractListBrowserTests
ReferenceContractListBrowserTests.browser_evidence_directory = Path("output/operational-reference-lists/contracts-regression")
labels = sys.argv[1:] or [
 'apps.expenses.tests', 'apps.safety.tests', 'apps.quality.tests',
 'apps.contracts.test_filter_bar',
 'tests.test_mvp05_xlsx.OperationalExportsTests',
 'tests.test_mvp06_print.OperationalPrintTests',
 'tests.test_operational_list_adapter', 'tests.test_list_filters',
]
sys.exit(bool(Runner(keepdb=True, interactive=False, verbosity=1).run_tests(labels)))

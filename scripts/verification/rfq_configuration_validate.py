"""RFQ-only validation with the qualified retained-FK test cleanup policy."""

import os
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.core.management import call_command
from django.db import connections
from django.test import TransactionTestCase


def disposable_teardown(self):
    for alias in self._databases_names(include_mirrors=False):
        if connections[alias].settings_dict["NAME"] != "test_bonira_f2_20261102":
            raise RuntimeError("RFQ cleanup requires the dedicated disposable test DB")
        # Same retained Payment FK handling as the qualified browser fixtures.
        call_command(
            "flush",
            database=alias,
            interactive=False,
            verbosity=0,
            allow_cascade=True,
            inhibit_post_migrate=True,
        )


TransactionTestCase._fixture_teardown = disposable_teardown
runpy.run_path(str(Path(__file__).with_name("f2_validate.py")), run_name="__main__")

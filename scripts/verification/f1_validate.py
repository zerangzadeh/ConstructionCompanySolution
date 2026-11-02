"""Run F1 verification in a dedicated migrated PostgreSQL test database."""

import os
import subprocess
import sys
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

import pytest
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command
from django.db import connections
from django.test import TransactionTestCase, override_settings

connections["default"].settings_dict["TEST"]["NAME"] = "test_bonira_f1_20261102"
evidence_root = Path(os.environ.get("F1_EVIDENCE_ROOT", root / "output/f1")).resolve()
allowed_evidence_root = (root / "output/f1").resolve()
if not evidence_root.is_relative_to(allowed_evidence_root):
    raise RuntimeError("F1 evidence must remain under output/f1")
os.environ["F1_EVIDENCE_ROOT"] = str(evidence_root)

# Serialized rollback replays the migration seed snapshot. An interrupted/reused
# database can still contain published workflow versions; Django's UPDATE-based
# deserializer correctly encounters their immutable-history database guard.
# Empty only the isolated test database before replay, retaining all triggers and
# restoring the exact migration snapshot. Cascade also includes retained Payment
# tables, as the existing browser fixtures' teardown already does.
original_fixture_setup = TransactionTestCase._fixture_setup.__func__


@classmethod
def isolated_fixture_setup(cls):
    for alias in cls._databases_names(include_mirrors=False):
        connection = connections[alias]
        if cls.serialized_rollback and hasattr(connection, "_test_serialized_contents"):
            if connection.settings_dict["NAME"] != "test_bonira_f1_20261102":
                raise RuntimeError("F1 fixture reset requires its dedicated test DB")
            call_command(
                "flush",
                database=alias,
                interactive=False,
                verbosity=0,
                allow_cascade=True,
                inhibit_post_migrate=True,
            )
    original_fixture_setup(cls)


TransactionTestCase._fixture_setup = isolated_fixture_setup


class EvidenceLocation:
    """Keep existing browser tests from overwriting historical screenshots."""

    def pytest_collection_modifyitems(self, items):
        os.environ["MVP02_BROWSER_EVIDENCE_DIRECTORY"] = str(
            evidence_root / "existing-browser/workforce"
        )
        for item in items:
            cls = getattr(item, "cls", None)
            if cls and hasattr(cls, "evidence_root"):
                cls.evidence_root = evidence_root / "test-evidence" / cls.__name__
                cls.evidence_root.mkdir(parents=True, exist_ok=True)
            if cls and issubclass(cls, StaticLiveServerTestCase):
                cls.browser_evidence_directory = (
                    evidence_root / "existing-browser" / cls.__name__
                )

    def pytest_runtest_logstart(self, nodeid, location):
        evidence_root.mkdir(parents=True, exist_ok=True)
        (evidence_root / "current-test.txt").write_text(nodeid, encoding="utf-8")


arguments = sys.argv[1:]
template_context = nullcontext()
if "--head-template" in arguments:
    # The shared base is the only changed existing product source. Re-render its
    # exact HEAD version in memory to attribute HTTP assertions without checkout,
    # modifying working files, or changing any domain/authorization behavior.
    arguments.remove("--head-template")
    baseline = subprocess.check_output(
        ["git", "show", "HEAD:templates/base.html"], cwd=root
    ).decode("utf-8")
    templates = deepcopy(settings.TEMPLATES)
    templates[0]["APP_DIRS"] = False
    templates[0]["OPTIONS"]["loaders"] = [
        ("django.template.loaders.locmem.Loader", {"base.html": baseline}),
        "django.template.loaders.filesystem.Loader",
        "django.template.loaders.app_directories.Loader",
    ]
    template_context = override_settings(TEMPLATES=templates)

with template_context:
    raise SystemExit(
        pytest.main(
            arguments or ["tests/test_f1_offline_browser.py", "--reuse-db", "-q"],
            plugins=[EvidenceLocation()],
        )
    )

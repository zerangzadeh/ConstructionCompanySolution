"""Isolated Batch-01 tests, with optional in-memory replay of entry Billing code."""

import importlib.abc
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[4]
MODULES = {
    f"apps.billing.{kind}": f"apps/billing/{kind}.py" for kind in ("forms", "views")
}


class EntryLoader(importlib.abc.Loader):
    def __init__(self, source):
        self.source = source

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        exec(compile(self.source, module.__file__, "exec"), module.__dict__)  # noqa: S102


class EntryFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in MODULES:
            relative = MODULES[fullname]
            source = subprocess.check_output(
                ["git", "show", f"HEAD:{relative}"], cwd=ROOT
            )
            return importlib.util.spec_from_file_location(
                fullname, ROOT / relative, loader=EntryLoader(source)
            )
        return None


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    arguments = sys.argv[1:]
    if "--entry-billing" in arguments:
        arguments.remove("--entry-billing")
        sys.meta_path.insert(0, EntryFinder())
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    with TemporaryDirectory(prefix="bonira-batch01-tests-") as storage:
        os.environ["DOCUMENT_PROTECTED_ROOT"] = storage
        import django

        django.setup()
        from django.conf import settings
        from django.contrib.auth.hashers import reset_hashers

        assert settings.SETTINGS_MODULE == "config.settings.development"
        settings.DATABASES["default"]["TEST"]["NAME"] = "test_bonira_uiux_batch01"
        settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
        reset_hashers(setting="PASSWORD_HASHERS")
        import pytest

        sys.exit(pytest.main(arguments))

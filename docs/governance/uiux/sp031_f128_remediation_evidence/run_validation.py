"""Disposable F128 PostgreSQL DB; optional immutable dirty-entry replay."""

import importlib.abc
import importlib.util
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


class EntryLoader(importlib.abc.Loader):
    def create_module(self, spec):
        return None

    def exec_module(self, module):
        kind = module.__name__.split(".")[-1]
        source = (OUT / f"workforce_{kind}_entry.txt").read_bytes()
        exec(compile(source, module.__file__, "exec"), module.__dict__)


class EntryFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {"apps.workforce.forms", "apps.workforce.views"}:
            kind = fullname.split(".")[-1]
            return importlib.util.spec_from_file_location(
                fullname, ROOT / f"apps/workforce/{kind}.py", loader=EntryLoader()
            )
        return None


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    arguments = sys.argv[1:]
    if "--entry" in arguments:
        arguments.remove("--entry")
        sys.meta_path.insert(0, EntryFinder())
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    with TemporaryDirectory(prefix="bonira-f128-tests-") as storage:
        os.environ["DOCUMENT_PROTECTED_ROOT"] = storage
        import django

        django.setup()
        from django.conf import settings
        from django.contrib.auth.hashers import reset_hashers

        assert settings.SETTINGS_MODULE == "config.settings.development"
        assert settings.DATABASES["default"]["HOST"] in ("localhost", "127.0.0.1", "::1")
        # Verified fully migrated, empty disposable DB; no Development data is used.
        settings.DATABASES["default"]["TEST"]["NAME"] = "test_bonira_uiux_batch09"
        settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
        reset_hashers(setting="PASSWORD_HASHERS")
        import pytest

        sys.exit(pytest.main(arguments))

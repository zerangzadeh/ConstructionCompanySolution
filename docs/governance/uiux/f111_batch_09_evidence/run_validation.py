"""Disposable BATCH-09 DB/files, optional exact dirty-entry form replay."""

import importlib.abc
import importlib.util
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[4]


class EntryLoader(importlib.abc.Loader):
    def create_module(self, spec):
        return None

    def exec_module(self, module):
        app, name = module.__name__.split(".")[1:]
        source = Path(__file__).with_name(f"{app}_{name}_entry.txt").read_bytes()
        exec(compile(source, module.__file__, "exec"), module.__dict__)  # noqa: S102


class EntryFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {
            f"apps.{app}.{name}"
            for app in ("equipment", "quality", "safety")
            for name in ("forms", "views")
        }:
            app, name = fullname.split(".")[1:]
            return importlib.util.spec_from_file_location(
                fullname, ROOT / f"apps/{app}/{name}.py", loader=EntryLoader()
            )
        return None


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    arguments = sys.argv[1:]
    if "--entry-forms" in arguments:
        arguments.remove("--entry-forms")
        sys.meta_path.insert(0, EntryFinder())
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    with TemporaryDirectory(prefix="bonira-batch09-tests-") as storage:
        os.environ["DOCUMENT_PROTECTED_ROOT"] = storage
        import django

        django.setup()
        from django.conf import settings
        from django.contrib.auth.hashers import reset_hashers

        assert settings.SETTINGS_MODULE == "config.settings.development"
        database = os.environ.get(
            "BONIRA_BATCH09_TEST_DATABASE", "test_bonira_uiux_batch09"
        )
        assert database in {"test_bonira_uiux_batch01", "test_bonira_uiux_batch09"}
        settings.DATABASES["default"]["TEST"]["NAME"] = database
        settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
        reset_hashers(setting="PASSWORD_HASHERS")
        import pytest

        sys.exit(pytest.main(arguments))

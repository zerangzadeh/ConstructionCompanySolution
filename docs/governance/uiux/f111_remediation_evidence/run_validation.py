"""Run bounded F111 validation, optionally freezing eight modules at HEAD.

Run from the repository root, using the same pytest arguments as the changed run.
With --frozen-baseline, sources are loaded in memory; the checkout is never
replaced or reset. Only the named disposable local test database is used. A fast
Django password hasher is confined to the test process; hashing strength is not
part of this selector/permission regression boundary.
"""

import importlib.abc
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BASELINE = "43ac319c6e73e48ca9626461b73987922c498ec3"
MODULES = {
    f"apps.{app}.{kind}": f"apps/{app}/{kind}.py"
    for app in ("daily_reports", "equipment", "procurement", "workforce")
    for kind in ("forms", "views")
}
LOADED = set()


class FrozenLoader(importlib.abc.Loader):
    def __init__(self, name, source):
        self.name = name
        self.source = source

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        LOADED.add(self.name)
        # Trusted repository source at the explicit frozen commit, not user input.
        exec(compile(self.source, module.__file__, "exec"), module.__dict__)  # noqa: S102


class FrozenFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname not in MODULES:
            return None
        relative = MODULES[fullname]
        source = subprocess.check_output(
            ["git", "show", f"{BASELINE}:{relative}"], cwd=ROOT
        )
        return importlib.util.spec_from_file_location(
            fullname, ROOT / relative, loader=FrozenLoader(fullname, source)
        )


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    assert (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        == BASELINE
    )
    arguments = sys.argv[1:]
    frozen = "--frozen-baseline" in arguments
    if frozen:
        arguments.remove("--frozen-baseline")
        sys.meta_path.insert(0, FrozenFinder())
    if arguments and arguments[0] == "--args-file":
        arguments = json.loads(Path(arguments[1]).read_text(encoding="utf-8-sig"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    import django

    django.setup()
    from django.conf import settings
    from django.contrib.auth.hashers import reset_hashers

    settings.DATABASES["default"]["TEST"]["NAME"] = "test_bonira_f111_998219b0_clean"
    import pytest

    class SeedBaseline:
        @pytest.fixture(scope="session", autouse=True)
        def preserve_migration_seed(self, django_db_setup, django_db_blocker):
            from django.core.management import call_command
            from django.db import connection

            from apps.accounts.models import User
            from apps.organizations.models import Organization

            expected = "test_bonira_f111_998219b0_clean"
            with django_db_blocker.unblock():
                assert connection.settings_dict["NAME"] == expected
                assert not User.objects.exists()
                assert not Organization.objects.exists()
                snapshot = connection.creation.serialize_db_to_string()
            yield
            # Restore the clean migration seed before pytest restores NAME.
            with django_db_blocker.unblock():
                assert connection.settings_dict["NAME"] == expected
                call_command(
                    "flush",
                    database="default",
                    verbosity=0,
                    interactive=False,
                    reset_sequences=False,
                    allow_cascade=True,
                    inhibit_post_migrate=True,
                )
                connection.creation.deserialize_db_from_string(snapshot)

    # UserSettingsHolder.SETTINGS_MODULE is None under override_settings().
    # Keep actual Development identity for existing fail-closed local guards.
    assert settings.SETTINGS_MODULE == "config.settings.development"
    original_hashers = settings.PASSWORD_HASHERS
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    reset_hashers(setting="PASSWORD_HASHERS")
    try:
        result = pytest.main(arguments, plugins=[SeedBaseline()])
    finally:
        settings.PASSWORD_HASHERS = original_hashers
        reset_hashers(setting="PASSWORD_HASHERS")
    print("Frozen baseline:" if frozen else "Checkout HEAD:", BASELINE)
    print("Test-only fast password hasher; persistent settings unchanged.")
    if frozen:
        print("Modules loaded from baseline:", ", ".join(sorted(LOADED)))
    sys.exit(result)

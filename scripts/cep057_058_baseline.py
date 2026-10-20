"""Reproduce the affected registry failure with unmodified HEAD product sources.

No checkout or workspace mutation: an import loader reads the Git blobs in memory.
"""

import importlib.abc
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")


class HeadLoader(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    modules: ClassVar[dict[str, str]] = {
        "apps.payroll.models": "apps/payroll/models.py",
        "apps.payroll.cumulative_services": "apps/payroll/cumulative_services.py",
    }

    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.modules:
            return importlib.util.spec_from_loader(fullname, self)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        path = self.modules[module.__name__]
        source = subprocess.check_output(["git", "show", "HEAD:" + path])
        module.__file__ = str(ROOT / path)
        exec(compile(source, "HEAD:" + path, "exec"), module.__dict__)  # noqa: S102 -- trusted, version-pinned repository source loader


if __name__ == "__main__":
    sys.meta_path.insert(0, HeadLoader())
    import pytest

    raise SystemExit(
        pytest.main(
            [
                "apps/payroll/test_p7_s13_s22_core_payroll.py::CorePayrollTests::test_payroll_registry_is_complete_and_default_roles_are_denied",
                "-q",
                "--reuse-db",
            ]
        )
    )

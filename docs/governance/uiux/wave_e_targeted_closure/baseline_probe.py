"""Replay only the exposed assertion using entry-identical templates in memory."""
import contextlib
import io
import json
import subprocess
from unittest.mock import patch

from entry import ROOT, OUT, save, sha
from django.template.loaders.filesystem import Loader
import pytest

entry = json.loads((OUT / "ENTRY.json").read_text(encoding="utf-8"))
paths = ("templates/base.html", "templates/components/table_filter_row.html", "templates/organizations/role_catalog.html")
baseline = {}
for path in paths:
    source = subprocess.check_output(["git", "show", "HEAD:" + path], cwd=ROOT)
    import hashlib
    # Git-normalized contents can differ in CRLF, so compare normalized source.
    current_entry_hash = entry["hashes"][path]
    assert f" M {path}" not in entry["status"], path
    baseline[str((ROOT / path).resolve()).casefold()] = source.decode("utf-8")

original = Loader.get_contents


def contents(self, origin):
    return baseline.get(str(origin.name).casefold(), None) or original(self, origin)


class Evidence:
    results = []

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            message = str(report.longrepr).split("in the following response")[0]
            self.results.append({"nodeid": report.nodeid, "outcome": report.outcome, "failure_excerpt": message[-1300:]})


plugin = Evidence()
with patch.object(Loader, "get_contents", contents), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    code = pytest.main(["apps/projects/tests.py::ProjectServiceTests::test_project_list_is_tenant_scoped", "--reuse-db", "-q", "--tb=short"], plugins=[plugin])
assert int(code) == 1
assert len(plugin.results) == 1 and plugin.results[0]["outcome"] == "failed"
assert "/projects/sites/" in plugin.results[0]["failure_excerpt"]
save("BASELINE_PROBE.json", {"result": "SAME_FAILURE_WITH_ENTRY_TEMPLATES", "method": "Filesystem template loader returns immutable HEAD versions for the three changed templates in memory; they were clean at session entry. No repository file/Git/DB restoration.", "results": plugin.results, "unchanged_hashes": {p: {"entry": entry["hashes"][p], "current": sha(ROOT / p), "unchanged": sha(ROOT / p) == entry["hashes"][p]} for p in ("apps/projects/tests.py", "apps/projects/views.py", "templates/projects/list.html", "apps/organizations/authorization.py")}, "html_and_csrf_saved": False})
print("Pre-entry Projects navigation assertion reproduced with entry templates; scope assertions pass before obsolete link assertion.")

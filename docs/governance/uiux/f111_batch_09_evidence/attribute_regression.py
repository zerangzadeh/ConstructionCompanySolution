"""Attribute regressions through the exact six captured dirty-entry modules."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path(__file__).resolve().parent


def rows(name):
    result = {}
    for case in ET.parse(OUT / name).findall(".//testcase"):
        failure = case.find("failure")
        error = case.find("error")
        issue = failure if failure is not None else error
        key = case.get("classname") + "." + case.get("name")
        result.setdefault(key, []).append(None if issue is None else issue.get("message"))
    return result


current, entry = rows("regression.xml"), rows("baseline_regression.xml")
assert current == entry
failures = []
for case in ET.parse(OUT / "regression.xml").findall(".//testcase"):
    failure = case.find("failure")
    error = case.find("error")
    issue = failure if failure is not None else error
    if issue is None:
        continue
    failures.append({"test": case.get("classname") + "." + case.get("name"), "classification": "BASELINE TEST DEBT", "message": issue.get("message"), "exact_dirty_entry_message_match": True, "trace": issue.text})
(OUT / "REGRESSION_ATTRIBUTION.json").write_text(json.dumps({"baseline_identical_to_current": True, "tests_compared": sum(map(len, current.values())), "passed": sum(map(len, current.values())) - len(failures), "failures": failures, "new_failures": [], "replay": "Import loader executes all six captured dirty-entry form/view files; no working source replacement; same disposable PostgreSQL database and regression set"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Exact dirty-entry comparison PASS:", len(failures), "unchanged failures; zero new failures")

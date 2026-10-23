"""Compare identical per-test outcomes with exact dirty-entry source replay."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path(__file__).resolve().parent


def results(name):
    rows = []
    for case in ET.parse(OUT / name).findall(".//testcase"):
        failure = case.find("failure")
        assert case.find("error") is None
        rows.append(
            (
                case.get("classname"),
                case.get("name"),
                None if failure is None else failure.get("message"),
            )
        )
    return rows


current, entry = results("regression.xml"), results("baseline_regression.xml")
assert current == entry
failures = []
for case in ET.parse(OUT / "regression.xml").findall(".//testcase"):
    failure = case.find("failure")
    if failure is None:
        continue
    contract = case.get("classname").startswith("apps.contracts")
    expected = (
        "apps\\projects\\services.py:169: in create_project"
        if contract
        else "apps\\procurement\\services.py:268: in create_purchase_request"
    )
    assert expected in failure.text
    failures.append(
        {
            "test": case.get("classname") + "." + case.get("name"),
            "classification": "BASELINE TEST DEBT",
            "message": failure.get("message"),
            "source_not_reached": "BATCH-08 forms/views",
            "cause": "Legacy role-only ContractServiceTests setup denies create_project"
            if contract
            else "Legacy Procurement fixtures deny create_purchase_request",
            "exact_baseline_message_match": True,
        }
    )
assert len(failures) == 22
(OUT / "REGRESSION_ATTRIBUTION.json").write_text(
    json.dumps(
        {
            "baseline_identical_to_current": True,
            "tests_compared": len(current),
            "passed": len(current) - len(failures),
            "failures": failures,
            "new_failures": [],
            "replay": "Import loader executes all eight captured dirty-entry source files; no working file replaced",
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
print(
    "Exact baseline comparison PASS:",
    len(failures),
    "unchanged failures; zero new failures",
)

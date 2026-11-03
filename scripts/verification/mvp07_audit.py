"""Reopen the completed Chrome downloads and retain bounded integrity evidence."""

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from openpyxl import load_workbook

from apps.daily_reports.xlsx_exports import CHILD_CONTEXT, CHILD_SPECS, REPORT_COLUMNS
from apps.equipment.xlsx_exports import (
    ASSIGNMENT_COLUMNS,
    EQUIPMENT_COLUMNS,
    USAGE_COLUMNS,
)
from apps.estimates.xlsx_exports import ESTIMATE_COLUMNS, LINE_COLUMNS
from apps.timekeeping.xlsx_exports import (
    ATTENDANCE_COLUMNS,
    ENTRY_COLUMNS,
    OVERTIME_COLUMNS,
    TIMESHEET_COLUMNS,
)

expected = (
    [("گزارش‌های روزانه", REPORT_COLUMNS)]
    + [(title, CHILD_CONTEXT + columns) for title, _, columns in CHILD_SPECS],
    [("برآوردها", ESTIMATE_COLUMNS), ("ردیف‌های برآورد", LINE_COLUMNS)],
    [
        ("حضور", ATTENDANCE_COLUMNS),
        ("کارکرد", TIMESHEET_COLUMNS),
        ("توزیع زمان", ENTRY_COLUMNS),
        ("اضافه‌کاری", OVERTIME_COLUMNS),
    ],
    [("تجهیزات", EQUIPMENT_COLUMNS)],
    [("تخصیص تجهیزات", ASSIGNMENT_COLUMNS)],
    [("کارکرد تجهیزات", USAGE_COLUMNS)],
)
directory = ROOT / "output/mvp-07"
cases = json.loads(
    (directory / "browser/after/results.json").read_text(encoding="utf-8")
)
results = []
for case in cases:
    if not case["downloads"]:
        assert case["state"].get("clearFiltersRestored"), case["name"]
        continue
    index = int(case["name"].split("-")[1])
    for file in case["downloads"]:
        path = Path(file["filename"])
        assert (
            file["state"] == "completed" and path.stat().st_size == file["totalBytes"]
        )
        workbook = load_workbook(path, data_only=False)
        assert workbook.sheetnames == [name for name, _ in expected[index]]
        numbers = dates = 0
        for sheet, (_, columns) in zip(workbook, expected[index], strict=True):
            assert sheet.sheet_view.rightToLeft and sheet.freeze_panes == "A2"
            assert sheet.max_row == 2
            assert [cell.value for cell in sheet[1]] == [
                column.label for column in columns
            ]
            for row in sheet.iter_rows(min_row=2):
                for cell in row:
                    assert cell.data_type != "f" and cell.hyperlink is None
                    if isinstance(cell.value, str):
                        assert not re.search(
                            r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-", cell.value
                        )
                        assert "test-internal-key" not in cell.value
                    numbers += cell.data_type == "n" and cell.value is not None
                    dates += cell.data_type == "d"
        if index in (0, 1, 2, 5):
            assert numbers > 0
        if index != 1:
            assert dates > 0
        results.append(
            {
                "scenario": case["name"],
                "file": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "sheets": workbook.sheetnames,
                "rows": [s.max_row - 1 for s in workbook],
                "numeric_cells": numbers,
                "date_cells": dates,
                "rtl": True,
                "headers": "PASS",
                "formula_and_technical_leakage": "PASS",
            }
        )
        workbook.close()
assert len(results) == 18
(directory / "workbook-integrity.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)

protected = [
    "core/xlsx.py",
    "core/printing.py",
    "core/product_surface.py",
    "templates/print",
    "apps/accounts/static/js/erp_module_selector.js",
    "apps/accounts/static/css/erp_module_selector.css",
    "apps/accounts/static/js/erp_interactions.js",
    "apps/accounts/static/css/erp_interactions.css",
    "apps/accounts/static/js/erp_print.js",
    "apps/accounts/static/css/erp_print.css",
    "apps/billing/xlsx_exports.py",
    "apps/procurement/xlsx_exports.py",
    "apps/inventory/xlsx_exports.py",
    "apps/expenses/xlsx_exports.py",
    "CEP_EXECUTION_REGISTRY.yaml",
    "ROADMAP.md",
    "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml",
    "requirements.txt",
    "requirements",
]
result = subprocess.run(
    ["git", "diff", "--exit-code", "HEAD", "--", *protected],
    cwd=ROOT,
    capture_output=True,
    check=False,
)
assert result.returncode == 0, "Protected foundation changed"
preserved = {
    "protected_paths": protected,
    "protected_git_diff": "PASS",
    "download_count": len(results),
    "clear_filter_scenarios": sum(
        bool(c["state"].get("clearFiltersRestored")) for c in cases
    ),
    "viewport_widths": sorted({c["width"] for c in cases}),
    "js_errors": sum(len(c["jsErrors"]) for c in cases),
}
(directory / "static-and-preservation.json").write_text(
    json.dumps(preserved, indent=2), encoding="utf-8"
)
print(
    json.dumps({"downloads": len(results), "integrity": "PASS", "preservation": "PASS"})
)

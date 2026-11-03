"""Read-only template and URL contract checks; no database or migrations."""

import json
import os
import sys
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.template import engines
from django.template.loader import get_template, render_to_string
from django.test import RequestFactory


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def controls(html):
    return [
        (tag, attrs)
        for tag, attrs in Elements(html).elements
        if "erp-output-action" in attrs.get("class", "").split()
    ]


def main():
    request = RequestFactory().get(
        "/source/",
        {
            "q": "آهن & مصالح",
            "status": "approved",
            "project": "preserved-project",
            "sort": "date",
            "page": "3",
            "attendance_page": "2",
            "timesheet_page": "4",
            "overtime_page": "5",
            "leave_page": "6",
            "correction_page": "7",
        },
    )
    request.user = AnonymousUser()
    request.organization = None
    request.session = {}
    checks = []
    engine = engines["django"]
    expected = {k: list(v) for k, v in request.GET.lists()}
    all_pages = {
        "page",
        "attendance_page",
        "timesheet_page",
        "overtime_page",
        "leave_page",
        "correction_page",
    }
    for template, kind, removed in (
        ("components/xlsx_action.html", "xlsx", all_pages),
        ("components/print_action.html", "print", {"page"}),
    ):
        rendered = render_to_string(template, request=request)
        [(tag, attrs)] = controls(rendered)
        assert tag == "a"
        actual = parse_qs(urlsplit(attrs["href"]).query)
        assert actual == {
            **{k: v for k, v in expected.items() if k not in removed},
            "format": [kind],
        }, (template, actual)
        assert ("data-xlsx-export" if kind == "xlsx" else "data-print-preview") in attrs
        checks.append(template + ": exact filter/pagination URL preserved")

    # Billing retains its distinct detail/list pagination contracts and help IDs.
    for name, help_id, removed in (
        ("billing/claim_list.html", "claim-export-scope", all_pages),
        ("billing/claim_detail.html", "claim-export-help", {"page"}),
    ):
        source = get_template(name).template.source
        start = source.index("{% querystring format='xlsx'")
        end = source.index("only %}", start) + len("only %}")
        rendered = engine.from_string(source[start:end]).render({}, request=request)
        [(tag, attrs)] = controls(rendered)
        assert tag == "a" and attrs["aria-describedby"] == help_id
        assert parse_qs(urlsplit(attrs["href"]).query) == {
            **{k: v for k, v in expected.items() if k not in removed},
            "format": ["xlsx"],
        }
        checks.append(name + ": exact URL and accessible help preserved")

    for kind in ("xlsx", "print"):
        html = render_to_string(
            "components/output_action.html",
            {"kind": kind, "disabled": True, "href": "/must-not-be-available/"},
        )
        [(tag, attrs)] = controls(html)
        assert tag == "span" and attrs["aria-disabled"] == "true"
        assert not any(
            k in attrs
            for k in ("href", "tabindex", "data-xlsx-export", "data-print-preview")
        )
        assert "<svg" in html and 'aria-hidden="true"' in html
        checks.append(kind + ": disabled has no actionable URL or event hook")

    printed = render_to_string(
        "print/document.html",
        {
            "document": SimpleNamespace(title="نمونه بررسی چاپ", reference="TEST"),
            "print_back_url": "/source/?status=approved",
        },
    )
    [(tag, attrs)] = controls(printed)
    assert (
        tag == "button" and attrs["type"] == "button" and "data-print-document" in attrs
    )
    assert 'href="/source/?status=approved"' in printed
    assert "css/erp_print.css" in printed and "css/erp_output_actions.css" in printed
    checks.append("print/document.html: original print hook and return link preserved")

    inventory = {"xlsx": [], "print": []}
    for folder in [ROOT / "templates", *sorted((ROOT / "apps").glob("*/templates"))]:
        for path in sorted(folder.rglob("*.html")):
            if "components" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for kind, placements in inventory.items():
                if f"components/{kind}_action.html" in text or f'kind="{kind}"' in text:
                    placements.append(path.relative_to(ROOT).as_posix())
                    get_template(path.relative_to(folder).as_posix())
    assert len(inventory["xlsx"]) == 14, inventory
    assert len(inventory["print"]) == 6, inventory
    checks.append(
        "all 20 existing placements compile (14 Excel, 6 print including toolbar)"
    )
    for path in (
        ROOT / "templates/base.html",
        ROOT / "templates/components/form_icon.html",
        ROOT / "templates/components/output_action.html",
        ROOT / "apps/accounts/static/css/erp_output_actions.css",
    ):
        text = path.read_text(encoding="utf-8")
        assert not any(s in text for s in ("\ufffd", "Ø", "Ù", "Û", "Ã")), path
    result = {
        "checks": checks,
        "inventory": inventory,
        "database": "not accessed",
        "migrations": "not executed",
    }
    (Path(__file__).parent / "template-results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Template/URL checks: {len(checks)}/{len(checks)} PASS; placements: 20")


if __name__ == "__main__":
    with patch.object(
        connection, "cursor", side_effect=AssertionError("Database access forbidden")
    ):
        main()

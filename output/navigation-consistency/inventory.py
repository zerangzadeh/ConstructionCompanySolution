"""Reproducible source inventory for the navigation audit. Run from the repository root."""

import csv
import hashlib
import inspect
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from django.urls import URLResolver, get_resolver

OUT = ROOT / "output/navigation-consistency"
paths = sorted(
    [
        *Path("templates").rglob("*.html"),
        *(p for p in Path("apps").rglob("*.html") if "templates" in p.parts),
    ]
)
anchor_pattern = re.compile(
    r"<a\b((?:\{%.*?%\}|\{\{.*?\}\}|[^>])*)>(.*?)</a>", re.S | re.I
)
templates = []
controls = []


def record(path, text, start, label, destination, category, reason):
    controls.append(
        {
            "template": path.as_posix(),
            "line": text.count("\n", 0, start) + 1,
            "label": " ".join(label.split()),
            "destination": destination,
            "decision": category,
            "reason": reason,
        }
    )


section_parents = {
    "templates/components/commercial_project_context.html",
    "templates/contracts/list.html",
    "templates/estimates/list.html",
    "apps/billing/templates/billing/claim_list.html",
    "apps/billing/templates/billing/progress_list.html",
    "templates/procurement/scope_form.html",
}
form_returns = {
    "apps/fixed_assets/templates/fixed_assets/form.html",
    "apps/workforce/templates/workforce/ess_timekeeping_form.html",
    "templates/accounts/password_reset_form.html",
    "templates/compliance/form.html",
    "templates/expenses/platform_group_form.html",
    "templates/inventory/reversal_form.html",
    "templates/procurement/addendum_form.html",
    "templates/procurement/form.html",
    "templates/procurement/receipt_create.html",
    "templates/procurement/rfq_form.html",
    "templates/procurement/sealed_evidence_custody.html",
    "templates/workforce/foundation_form.html",
}
for path in paths:
    text = path.read_text(encoding="utf-8")
    for match in anchor_pattern.finditer(text):
        attrs, body = match.groups()
        label = re.sub(r"<[^>]*>", "", re.sub(r"<svg\b.*?</svg>", "", body, flags=re.S))
        href = re.search(r'href="([^"]+)"', attrs)
        href = href[1] if href else ""
        if path.as_posix() == "templates/components/form_footer.html":
            continue
        if re.search(r"بازگشت|cd-back", attrs + label):
            reason = "Destination is absent from the rendered breadcrumb. Keep the meaningful return path."
            if path.as_posix() in section_parents:
                reason = "Preserves a project/contract section or query destination that the breadcrumb does not carry."
            elif path.as_posix() in form_returns:
                reason = "Form cancellation or originating-source return. Keep despite Back/Return wording."
            elif path.as_posix() == "templates/contracts/detail.html":
                reason = "Shown only for estimate-origin breadcrumbs, where the contracts collection is not a breadcrumb parent."
            elif path.as_posix() == "templates/documents/detail.html":
                reason = "Returns to the authorized originating record and related-document section. Breadcrumb points to the document collection."
            elif path.as_posix().startswith("templates/admin/"):
                reason = "Exits Django Admin to the ERP. Admin breadcrumbs remain inside Admin."
            elif path.as_posix() == "templates/print/document.html":
                reason = "Standalone printable output has no equivalent breadcrumb."
            record(path, text, match.start(), label, href, "preserved_return", reason)
        elif "انصراف" in label:
            record(
                path,
                text,
                match.start(),
                label,
                href,
                "preserved_cancel",
                "Cancels or discards the current form without submitting.",
            )
    for match in re.finditer(r'{% include "components/form_footer.html".*?%}', text):
        record(
            path,
            text,
            match.start(),
            "انصراف",
            match[0],
            "preserved_shared_cancel",
            "Shared form cancellation invocation. Counted once per source declaration, with inherited runtime instances unexpanded.",
        )
    templates.append(
        {
            "template": path.as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "extends": re.findall(r'{% extends "([^"]+)"', text),
            "includes": sorted(set(re.findall(r'{% include "([^"]+)"', text))),
            "navigation_source_present": any(
                word in text for word in ("breadcrumb", "page_header", "<nav", "بازگشت")
            ),
            "inspection": "Template source inventory, navigation control extraction, inheritance/include mapping and Django compilation. Runtime validation is recorded separately.",
        }
    )

removed = [
    (
        "templates/expenses/detail.html",
        "بازگشت به هزینه‌ها",
        "expenses:list",
        "Exact expense collection breadcrumb.",
    ),
    (
        "apps/billing/templates/billing/progress_detail.html",
        "بازگشت به سوابق کارکرد این قلم",
        "billing:progress_list",
        "Breadcrumb already carries the exact contract and line_key query.",
    ),
    (
        "apps/billing/templates/billing/baseline_list.html",
        "بازگشت به قرارداد",
        "contracts:detail",
        "Existing authorized contract breadcrumb.",
    ),
    (
        "apps/billing/templates/billing/baseline_detail.html",
        "همه نسخه‌های این قرارداد",
        "billing:baseline_list",
        "Exact contract and versions=1 breadcrumb.",
    ),
    (
        "apps/billing/templates/billing/claim_list.html",
        "بازگشت به قرارداد",
        "contracts:detail",
        "Full source-validated breadcrumb restored through the shared renderer.",
    ),
    (
        "apps/timekeeping/templates/timekeeping/record_detail.html",
        "بازگشت به حضور و کارکرد",
        "timekeeping:workbench",
        "Exact scoped back_url already supplies the breadcrumb.",
    ),
    (
        "templates/timekeeping/timesheet_detail.html",
        "بازگشت به حضور و کارکرد",
        "timekeeping:workbench",
        "Breadcrumb uses the view-supplied return context. Form cancellation remains.",
    ),
    (
        "apps/workforce/templates/workforce/field_detail.html",
        "بازگشت به نیروها",
        "workforce:field_list",
        "Existing authorized workforce parent carries validated project/site scope.",
    ),
    (
        "templates/documents/evidence_detail.html",
        "بازگشت به منبع شاهد",
        "source.url",
        "Existing exact source URL now has its source title in the breadcrumb.",
    ),
    (
        "templates/equipment/operations_workbench.html",
        "فهرست تجهیزات",
        "equipment:list",
        "Existing permitted equipment collection breadcrumb.",
    ),
    (
        "templates/projects/detail.html",
        "همه پروژه‌ها",
        "projects:list",
        "Existing projects collection breadcrumb.",
    ),
    (
        "templates/projects/control_comparison.html",
        "ساختار شکست و فعالیت‌ها",
        "projects:controls",
        "Corrected project hierarchy with existing object permission check.",
    ),
    (
        "templates/projects/control_exceptions.html",
        "ساختار شکست و فعالیت‌ها",
        "projects:controls",
        "Corrected project hierarchy with existing object permission check.",
    ),
    (
        "templates/procurement/rfq_buyer_workspace.html",
        "بازگشت به استعلام",
        "procurement:rfq_detail",
        "Shared header retains the scoped RFQ parent. Duplicate breadcrumb also consolidated.",
    ),
    (
        "templates/contracts/detail.html",
        "قراردادها",
        "contracts:list",
        "Removed for standard detail only. Retained when an authorized estimate replaces the collection breadcrumb.",
    ),
]
for path, label, destination, reason in removed:
    controls.append(
        {
            "template": path,
            "line": "",
            "label": label,
            "destination": destination,
            "decision": "removed_redundant",
            "reason": reason,
        }
    )


def patterns(resolver, prefix="", namespaces=()):
    for pattern in resolver.url_patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            yield from patterns(
                pattern,
                route,
                (*namespaces, pattern.namespace) if pattern.namespace else namespaces,
            )
        else:
            callback = pattern.callback
            identifier = ":".join((*namespaces, pattern.name or ""))
            filename = inspect.getsourcefile(inspect.unwrap(callback))
            yield {
                "pattern": route,
                "name": identifier,
                "callback": f"{callback.__module__}.{callback.__qualname__}",
                "source": Path(filename).relative_to(ROOT).as_posix()
                if filename and Path(filename).is_relative_to(ROOT)
                else "framework",
            }


routes = list(patterns(get_resolver()))
OUT.mkdir(parents=True, exist_ok=True)
for filename, rows in (
    ("template_inventory.json", templates),
    ("route_inventory.json", routes),
):
    (OUT / filename).write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
with (OUT / "control_decisions.csv").open(
    "w", encoding="utf-8-sig", newline=""
) as stream:
    writer = csv.DictWriter(
        stream,
        fieldnames=("template", "line", "label", "destination", "decision", "reason"),
    )
    writer.writeheader()
    writer.writerows(controls)
counts = Counter(row["decision"] for row in controls)
summary = {
    "templates": len(templates),
    "url_patterns": len(routes),
    "namespaces": len(
        {row["name"].partition(":")[0] for row in routes if ":" in row["name"]}
    ),
    "control_declarations": dict(counts),
}
(OUT / "source_summary.json").write_text(
    json.dumps(summary, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(summary))

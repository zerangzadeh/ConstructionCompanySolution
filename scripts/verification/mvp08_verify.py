"""Current installed-Chrome MVP journeys in a retained, isolated demo database.

Uses the accepted Chrome driver and native business forms from MVP-04F, without
calling their broad fixture setup or changing global policies. Never flushes.
"""

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from unittest import TestCase
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.db import connection
from django.test import Client, override_settings
from django.test.testcases import LiveServerThread
from django.urls import reverse
from django.utils import timezone

from apps.accounts.management.commands.seed_mvp_demo import SLUG, guard_environment
from apps.accounts.models import User
from apps.billing import models as bm
from apps.contracts.models import Contract
from apps.daily_reports.models import DailyReport
from apps.estimates.models import Estimate
from apps.inventory.models import Warehouse
from apps.materials.models import Material
from apps.organizations.models import Organization
from apps.organizations.policy_services import resolve_active_tenant_policy
from apps.organizations.services import set_active_organization
from apps.parties.models import BusinessParty
from apps.procurement import models as m
from apps.procurement.test_mvp04b2_browser import BrowserMixin
from apps.projects.models import Project, ProjectSite
from core.jalali import format_jalali

OUT = ROOT / "output/mvp-08"


class CurrentJourney(BrowserMixin, TestCase):
    """Reuse only form/navigation helpers; no historical test setup/teardown."""

    @property
    def live_server_url(self):
        return f"http://localhost:{type(self).server_thread.port}"

    def browser(self, actor, scenarios):
        self.login(actor)
        env = os.environ.copy()
        env["MVP02_SESSION"] = self.client.cookies["sessionid"].value
        env["MVP02_SCENARIOS"] = json.dumps(scenarios)
        directory = OUT / "browser"
        directory.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                "node",
                str(ROOT / "scripts/verification/mvp08_browser.mjs"),
                self.live_server_url,
                str(directory),
                actor.username,
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf8",
            timeout=240,
            check=False,
        )
        if result.returncode:
            (directory / f"failed-{scenarios[0]['name']}.txt").write_text(
                result.stderr + result.stdout,
                encoding="utf8",
            )
        self.assertEqual(result.returncode, 0, (result.stderr + result.stdout)[-2500:])
        values = json.loads(result.stdout)
        self.assertEqual(len(values), len(scenarios))
        (directory / f"batch-{scenarios[0]['name']}.json").write_text(
            json.dumps(values, ensure_ascii=False, indent=2),
            encoding="utf8",
        )

    def login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        set_active_organization(
            session,
            self.other_organization if actor == self.outsider else self.organization,
        )
        session.save()


def prepare():
    guard_environment()
    if connection.settings_dict["NAME"] != "test_bonira_mvp08_demo_20261103":
        raise RuntimeError(
            "Verification requires the exact retained MVP-08 test database"
        )
    fixture = CurrentJourney()
    fixture.client = Client()
    fixture.organization = Organization.objects.get(slug=SLUG)
    fixture.other_organization = Organization.objects.get(slug=SLUG + "-isolated")
    fixture.owner = User.objects.get(username="mvp08.buyer")
    fixture.member = User.objects.get(username="mvp08.operator")
    fixture.approver = User.objects.get(username="mvp08.reviewer")
    fixture.evaluator = User.objects.get(username="mvp08.evaluator")
    fixture.outsider = User.objects.get(username="mvp08.foreign")
    fixture.project = Project.objects.get(
        organization=fixture.organization, code="MVP08-P01"
    )
    fixture.site = Warehouse.objects.get(
        organization=fixture.organization, code="MVP08-WH01"
    )
    fixture.material = Material.objects.get(
        organization=fixture.organization, code="MVP08-M01"
    )
    fixture.unit = fixture.material.unit_of_measure
    fixture.supplier = BusinessParty.objects.get(
        organization=fixture.organization, display_name__startswith="تأمین مصالح"
    )
    fixture.evidence_root = OUT
    return fixture


def journey2(f):
    org = f.organization
    estimate = Estimate.objects.get(organization=org, estimate_number="MVP08-EST01")
    contract = Contract.objects.get(organization=org, contract_number="MVP08-CTR01")
    baseline = bm.ProjectBaseline.objects.get(organization=org)
    contract_url = reverse("contracts:detail", args=[contract.pk])
    create = reverse("billing:claim_create")
    f.browser(
        f.member,
        [
            f.case(
                "J2-approved-baseline",
                reverse("billing:baseline_detail", args=[baseline.pk]),
                mustText=[f.project.name, contract.title, "بتن‌ریزی فونداسیون"],
            ),
            f.case(
                "J2-verified-progress",
                reverse("billing:progress_list") + f"?contract={contract.pk}",
                mustText=[contract.title, "بتن‌ریزی فونداسیون"],
                absentText=[
                    "daily_report",
                    "source_reference",
                    "source_type",
                    "ProjectBaseline",
                    "ProgressRecord",
                ],
            ),
        ],
    )
    if not bm.ProgressClaim.objects.filter(organization=org).exists():
        f.browser(
            f.member,
            [
                f.case(
                    "J2-estimate-contract",
                    reverse("estimates:detail", args=[estimate.pk]),
                    steps=[
                        {
                            "clickHref": contract_url + f"?estimate={estimate.pk}",
                            "afterPath": contract_url,
                        },
                        {
                            "clickHref": create + f"?contract={contract.pk}",
                            "afterPath": create,
                        },
                        f.inspect(
                            f"document.querySelector('[name=baseline]').value==='{baseline.pk}'",
                            "valid contract/baseline context",
                        ),
                        {
                            "formSelector": "main form[method=post]",
                            "fill": {
                                "period_start": format_jalali(date(2026, 11, 1)),
                                "period_end": format_jalali(date(2026, 11, 30)),
                                "measurement_cutoff": format_jalali(date(2026, 11, 3)),
                            },
                            "submit": True,
                            "afterPrefix": "/billing/claims/",
                        },
                    ],
                )
            ],
        )
    claim = bm.ProgressClaim.objects.get(organization=org)
    detail = reverse("billing:claim_detail", args=[claim.pk])
    if claim.status == "draft":
        f.browser(
            f.member,
            [
                f.case(
                    "J2-deductions-submit",
                    detail,
                    mustText=["کسور تضمین"],
                    steps=[
                        {
                            "clickSelector": "form[action$='/recalculate/'] button",
                            "afterPath": detail,
                        },
                        {
                            "clickSelector": "form[action$='/submit/'] button",
                            "afterPath": detail,
                        },
                    ],
                )
            ],
        )
    claim.refresh_from_db()
    if claim.status == "submitted":
        f.browser(
            f.approver,
            [
                f.case(
                    "J2-independent-approval",
                    detail,
                    steps=[
                        {
                            "formSelector": "form[action$='/approve/']",
                            "fill": {"reason": "کنترل مستقل مقادیر و کسور نمونه"},
                            "submit": True,
                            "afterPath": detail,
                        },
                    ],
                    mustText=["این نسخه تأیید و نهایی شده"],
                )
            ],
        )
    claim.refresh_from_db()
    assert claim.status == "approved" and claim.approved_by_id == f.approver.pk
    snapshot = {
        "status": claim.status,
        "gross": str(claim.gross_amount),
        "net": str(claim.net_amount),
        "calculation_snapshot": claim.calculation_snapshot,
        "adjustments": list(claim.adjustments.values("amount", "adjustment_type")),
    }
    (OUT / "billing-source.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, default=str), encoding="utf8"
    )


def journey1(f):
    site = ProjectSite.objects.get(organization=f.organization, code="MVP08-S01")
    project = reverse("projects:detail", args=[f.project.pk])
    sites = reverse("projects:site_list", args=[f.project.pk])
    detail = reverse("projects:site_detail", args=[f.project.pk, site.pk])
    query = f"?project={f.project.pk}&site={site.pk}"
    workers = reverse("workforce:field_list") + query
    times = reverse("timekeeping:workbench") + query
    report = DailyReport.objects.get(organization=f.organization)
    report_url = reverse("daily_reports:detail", args=[report.pk])
    f.browser(
        f.member,
        [
            f.case(
                "J1-project-site-workers-time",
                project,
                steps=[
                    {"clickHref": sites, "afterPath": sites},
                    {"clickHref": detail, "afterPath": detail},
                    {
                        "clickHref": workers,
                        "afterPath": reverse("workforce:field_list"),
                    },
                    {"clickHref": times, "afterPath": reverse("timekeeping:workbench")},
                ],
                mustText=[f.project.name, site.name],
            ),
            f.case(
                "J1-report-observed", report_url, mustText=[f.project.name, site.name]
            ),
            f.case(
                "J1-report-leakage",
                report_url,
                steps=[
                    f.inspect(
                        "!document.querySelector('main').innerText.includes('شناسه فنی')",
                        "Daily Report must not expose technical identifier terminology",
                    )
                ],
            ),
        ],
    )
    if report.status == "draft":
        f.browser(
            f.member,
            [
                f.case(
                    "J1-report-add-and-submit",
                    report_url,
                    steps=[
                        {
                            "formSelector": "form[action$='/labor/']",
                            "fill": {
                                "team_name": "اکیپ تکمیلی نمونه",
                                "worker_count": "1",
                                "hours_worked": "2",
                            },
                            "submit": True,
                            "afterPath": report_url,
                        },
                        {
                            "clickSelector": "form[action$='/submit/'] button",
                            "afterPath": report_url,
                        },
                    ],
                )
            ],
        )
    report.refresh_from_db()
    if report.status == "submitted":
        f.browser(
            f.approver,
            [
                f.case(
                    "J1-report-approve",
                    report_url,
                    steps=[
                        {
                            "clickSelector": "form[action$='/approve/'] button",
                            "afterPath": report_url,
                        },
                    ],
                )
            ],
        )
    report.refresh_from_db()
    assert report.status == "approved"
    f.browser(
        f.member,
        [
            f.case(
                "J1-equipment-deployment",
                reverse("equipment:assignment_list")
                + "?"
                + urlencode({"project": f.project.name}),
                mustText=[f.project.name, site.name, "پمپ بتن نمونه"],
            ),
            f.case(
                "J1-equipment-usage",
                reverse("equipment:operations_workbench"),
                mustText=["صلاحیت و کارکرد"],
            ),
            f.case(
                "J1-safety",
                reverse(
                    "safety:detail", args=[f.organization.safety_incidents.get().pk]
                ),
                mustText=[f.project.name, site.name],
            ),
            f.case(
                "J1-quality",
                reverse(
                    "quality:detail", args=[f.organization.quality_issues.get().pk]
                ),
                mustText=[f.project.name, site.name],
            ),
        ],
    )


def surfaces(f, isolated_only=False):
    site = ProjectSite.objects.get(organization=f.organization, code="MVP08-S01")
    claim = bm.ProgressClaim.objects.get(organization=f.organization)
    pr = m.PurchaseRequest.objects.filter(organization=f.organization).first()
    paths = [
        ("home", reverse("home")),
        ("project", reverse("projects:detail", args=[f.project.pk])),
        (
            "daily",
            reverse(
                "daily_reports:detail",
                args=[DailyReport.objects.get(organization=f.organization).pk],
            ),
        ),
        (
            "workers",
            reverse("workforce:field_list") + f"?project={f.project.pk}&site={site.pk}",
        ),
        ("claim", reverse("billing:claim_detail", args=[claim.pk])),
        ("rfq", reverse("procurement:rfq_list")),
    ]
    for width in () if isolated_only else (1440, 1024, 390):
        f.browser(
            f.member,
            [
                f.case(
                    f"surface-{name}-{width}",
                    path,
                    width=width,
                    mobile=width == 390,
                    absentText=[
                        "شناسه فنی",
                        "UUID",
                        "idempotency",
                        "Django",
                        "Traceback",
                        "ClaimAdjustment",
                    ],
                    steps=(
                        [
                            {"toggleSelector": "[data-module-trigger]"},
                            f.inspect(
                                "document.querySelector('#erp-module-selector')?.open && document.querySelectorAll('[data-module-card]').length>0",
                                "Module Selector opens with authorized destinations",
                            ),
                            {"toggleSelector": "[data-module-close]"},
                        ]
                        if name == "home"
                        else []
                    ),
                )
                for name, path in paths
            ],
        )
    hidden = [
        "/accounting/",
        "/treasury/",
        "/payroll/",
        "/financials/",
        "/workforce/departments/",
    ]
    if not isolated_only:
        f.browser(
            f.member,
            [
                f.case(f"hidden-{i}", path, status=403, noHttpErrors=False)
                for i, path in enumerate(hidden)
            ],
        )
    objects = [paths[1][1], paths[2][1], paths[4][1]]
    if pr:
        objects.append(reverse("procurement:request_detail", args=[pr.pk]))
    # Source, print and export all retain object authorization.
    denials = []
    for actor in (f.outsider, User.objects.get(username="mvp08.restricted")):
        f.login(actor)
        for path in objects:
            for suffix in ("", "?format=print", "?format=xlsx"):
                response = f.client.get(path + suffix)
                # Restricted MEMBER can read normal operational records; policy
                # is checked rather than assuming every restricted read is denied.
                if actor == f.outsider:
                    assert response.status_code in (403, 404), (
                        path,
                        response.status_code,
                    )
                    assert f.project.name not in response.content.decode()
                denials.append(
                    {
                        "persona": actor.username,
                        "path": path + suffix,
                        "status": response.status_code,
                    }
                )
        if actor != f.outsider:
            response = f.client.get(reverse("billing:claim_detail", args=[claim.pk]))
            assert response.status_code in (403, 404)
            f.browser(
                actor,
                [
                    f.case(
                        "restricted-claim",
                        paths[4][1],
                        status=response.status_code,
                        noHttpErrors=False,
                        plainBusinessDenial=True,
                    )
                ],
            )
    f.login(f.outsider)
    foreign_project_status = f.client.get(objects[0]).status_code
    assert foreign_project_status in (403, 404)
    f.browser(
        f.outsider,
        [
            f.case(
                "foreign-project",
                objects[0],
                status=foreign_project_status,
                noHttpErrors=False,
            ),
            f.case(
                "foreign-claim",
                paths[4][1],
                status=404,
                noHttpErrors=False,
                plainBusinessDenial=True,
            ),
        ],
    )
    (OUT / "authorization.json").write_text(
        json.dumps(denials, indent=2), encoding="utf8"
    )


def outputs(f):
    claim = bm.ProgressClaim.objects.get(organization=f.organization)
    report = DailyReport.objects.get(organization=f.organization)
    downloads = [
        ("billing", reverse("billing:claim_detail", args=[claim.pk])),
        ("procurement", reverse("procurement:request_list")),
        ("inventory", reverse("inventory:transaction_list")),
        ("expenses", reverse("expenses:list")),
        ("daily", reverse("daily_reports:list")),
        ("estimates", reverse("estimates:list")),
        ("timekeeping", reverse("timekeeping:workbench")),
        ("equipment", reverse("equipment:list")),
    ]
    f.login(f.member)
    env = os.environ.copy()
    env["MVP07_SESSION"] = f.client.cookies["sessionid"].value
    env["MVP07_SCENARIOS"] = json.dumps(
        [{"name": name, "path": path} for name, path in downloads]
    )
    result = subprocess.run(
        [
            "node",
            str(ROOT / "scripts/verification/mvp07_browser.mjs"),
            f.live_server_url,
            str(OUT / "downloads"),
        ],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf8",
        timeout=240,
        check=False,
    )
    assert result.returncode == 0, (result.stderr + result.stdout)[-2000:]
    env["MVP06_SESSION"] = env["MVP07_SESSION"]
    env["MVP06_SCENARIOS"] = json.dumps(
        [
            {
                "name": "billing",
                "path": reverse("billing:claim_detail", args=[claim.pk]),
            },
            {
                "name": "daily",
                "path": reverse("daily_reports:detail", args=[report.pk]),
            },
            {"name": "expenses", "path": reverse("expenses:list")},
        ]
    )
    result = subprocess.run(
        [
            "node",
            str(ROOT / "scripts/verification/mvp06_browser.mjs"),
            f.live_server_url,
            str(OUT / "print"),
        ],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf8",
        timeout=240,
        check=False,
    )
    assert result.returncode == 0, (result.stderr + result.stdout)[-2000:]


def responsive_forms(f):
    contract = Contract.objects.get(
        organization=f.organization, contract_number="MVP08-CTR01"
    )
    pr = m.PurchaseRequest.objects.get(
        organization=f.organization, request_number="PR-F"
    )
    routes = [
        ("worker", reverse("workforce:field_create")),
        ("claim", reverse("billing:claim_create") + f"?contract={contract.pk}"),
        ("pr", reverse("procurement:request_create") + f"?project_id={f.project.pk}"),
    ]
    for width in (1440, 1024, 390):
        cases = [
            f.case(f"form-{name}-{width}", path, width=width, mobile=width == 390)
            for name, path in routes
        ]
        cases.append(
            f.case(
                f"pr-confirm-cancel-{width}",
                reverse("procurement:request_detail", args=[pr.pk]),
                width=width,
                mobile=width == 390,
                steps=[
                    {"toggleSelector": "form[action$='/submit/'] button"},
                    {
                        "inspect": "Swal.isVisible() && !!document.querySelector('.swal2-cancel')",
                        "description": "native local confirmation dialog",
                        "waitMs": 200,
                    },
                    {"toggleSelector": ".swal2-cancel"},
                ],
            )
        )
        f.browser(f.member, cases)
    pr.refresh_from_db()
    assert pr.status == "draft"


def sourcing_preflight(f):
    today = timezone.localdate()
    rows = []
    for code in (
        "rfq-admissibility-self-approval",
        "rfq-comparison-self-finalization",
        "rfq-sourcing-award-self-finalization",
    ):
        version = resolve_active_tenant_policy(
            organization=f.organization,
            policy_code=code,
        )
        rows.append(
            {
                "code": code,
                "version": version.version,
                "effective_from": str(version.effective_from),
                "effective_to": str(version.effective_to),
                "parameters": version.parameters,
                "effective_today": version.effective_from <= today
                and (version.effective_to is None or today < version.effective_to),
            }
        )
    directory = OUT / "continuation-20261103"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "policy-preflight.json").write_text(
        json.dumps(
            {
                "on_date": str(today),
                "policies": rows,
                "scope": "Native current tenant-policy preflight only; not Journey 3 E2E acceptance.",
            },
            indent=2,
        ),
        encoding="utf8",
    )
    if not all(
        row["effective_today"] and row["parameters"] == {"allow_self_approval": False}
        for row in rows
    ):
        raise RuntimeError(
            "BLOCKER-MVP08-RFQ-POLICY-EXPIRED: no current published independent-review configuration"
        )


def main():
    f = prepare()
    mode = sys.argv[1] if len(sys.argv) > 1 else "sourcing-preflight"
    server = LiveServerThread(
        "localhost", StaticFilesHandler, connections_override={}, port=0
    )
    with override_settings(
        ALLOWED_HOSTS=["localhost", "127.0.0.1", "testserver"],
        PRODUCT_SURFACE_PROFILE="MVP",
        DEBUG=False,
    ):
        server.start()
        server.is_ready.wait(30)
        if server.error:
            raise server.error
        CurrentJourney.server_thread = server
        try:
            if mode == "journeys":
                journey2(f)
                sourcing_preflight(f)
            elif mode == "journey2":
                journey2(f)
            elif mode in {"journey3", "sourcing-preflight"}:
                sourcing_preflight(f)
            elif mode == "journey1":
                journey1(f)
            elif mode == "surfaces":
                surfaces(f)
            elif mode == "isolation":
                surfaces(f, isolated_only=True)
            elif mode == "outputs":
                outputs(f)
            elif mode == "forms":
                responsive_forms(f)
            else:
                raise ValueError(mode)
        finally:
            server.terminate()
            server.join(30)
    if mode in {"journeys", "journey3", "sourcing-preflight"}:
        print("RFQ POLICY PREFLIGHT: PASS (not Journey 3 E2E acceptance)")
    else:
        print("MVP-08", mode, "PASS")


if __name__ == "__main__":
    main()

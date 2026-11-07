import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.template import engines
from django.test import SimpleTestCase, override_settings
from django.urls import get_resolver, reverse, URLResolver

from apps.accounts.models import User
from apps.billing.test_mvp03 import JourneyFixture
from apps.billing.test_mvp03_browser import ContractBillingBrowserTests
from apps.documents.services import add_document_link
from apps.documents.test_evidence_integration import EvidenceIntegrationTests
from apps.expenses.models import Expense
from apps.procurement.test_mvp04b_scope import CommercialScopeFixture
from apps.projects.test_command_center import scoped_reader
from apps.timekeeping.services import (
    capture_attendance,
    create_timesheet,
    create_work_calendar,
)
from apps.workforce.test_mvp02 import make_field_fixture

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "output/navigation-consistency/browser"
NAV = 'main nav[aria-label="مسیر صفحه"]'


def check(js, description):
    return {"inspect": js, "description": description}


def case(name, path, steps=(), mobile=False):
    return {
        "name": name,
        "path": path,
        "status": 200,
        "mobile": mobile,
        "steps": list(steps),
    }


def one_link(target, count=1):
    return check(
        f"""(() => {{
            const nav=document.querySelector({json.dumps(NAV)});
            const matches=[...document.querySelectorAll('main a[href]')].filter(a=>a.getAttribute('href')==={json.dumps(target)});
            return nav?.querySelectorAll('[aria-current=page]').length===1 && matches.length==={count} && nav.contains(matches[0]) &&
              document.documentElement.dir==='rtl' && nav.scrollWidth<=nav.clientWidth+1;
        }})()""",
        f"one breadcrumb, RTL layout and {count} expected main-content destination link(s)",
    )


def crumb_click(target):
    return {
        "clickSelector": f'{NAV} a[href="{target}"]',
        "afterPath": urlsplit(target).path,
    }


class Inventory(SimpleTestCase):
    def test_compile_templates_and_inventory_routes(self):
        files = [
            *Path("templates").rglob("*.html"),
            *(p for p in Path("apps").rglob("*.html") if "templates" in p.parts),
        ]
        for file in files:
            with self.subTest(file=str(file)):
                engines["django"].from_string(file.read_text(encoding="utf-8"))

        def leaves(resolver, prefix=""):
            for pattern in resolver.url_patterns:
                route = prefix + str(pattern.pattern)
                if isinstance(pattern, URLResolver):
                    yield from leaves(pattern, route)
                else:
                    yield (route, pattern.name or "")

        routes = list(leaves(get_resolver()))
        (RESULTS / "route-inventory.json").write_text(json.dumps(routes, indent=2))
        print(
            f"Inventory: {len(files)} app/project templates, {len(routes)} configured URL patterns"
        )


class BrowserBase:
    browser = ContractBillingBrowserTests.browser
    _fixture_teardown = ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = RESULTS


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    PRODUCT_SURFACE_PROFILE="FULL_ERP",
)
class TenantNavigation(BrowserBase, JourneyFixture, StaticLiveServerTestCase):
    serialized_rollback = True

    def test_changed_routes_and_permissions(self):
        self.make_fixture(persian=True)
        claim = self._claim()
        record = claim.baseline.progress_records.first()
        project, site, _, employee, _ = make_field_fixture(
            self.owner, self.organization
        )
        expense = Expense.objects.create(
            organization=self.organization,
            project=project,
            description="هزینه مسیر آزمایشی",
            incurred_on=date(2026, 10, 1),
            amount=20,
            created_by=self.owner,
        )
        start = datetime(2026, 10, 1, 8, tzinfo=ZoneInfo("Asia/Tehran"))
        calendar = create_work_calendar(
            organization=self.organization,
            actor=self.owner,
            code="NAV-CAL",
            name="تقویم آزمایشی",
            effective_from=start.date(),
            working_weekdays=list(range(1, 8)),
        )
        attendance = capture_attendance(
            organization=self.organization,
            actor=self.owner,
            employee=employee,
            calendar=calendar,
            project=project,
            site=site,
            work_date=start.date(),
            check_in_at=start,
            check_out_at=start + timedelta(hours=8),
            source_reference="NAV-ATT",
        )
        sheet = create_timesheet(
            organization=self.organization,
            actor=self.owner,
            employee=employee,
            period_start=start.date(),
            period_end=start.date(),
            declared_minutes=480,
        )
        scoped = f"?project={project.pk}&site={site.pk}"
        workbench = (
            reverse("timekeeping:workbench") + scoped + f"&employee={employee.pk}"
        )
        worker = reverse("workforce:field_list") + scoped
        contract = reverse("contracts:detail", args=[self.contract.pk])
        contract_filter = f"?contract={self.contract.pk}"
        baseline_list = (
            reverse("billing:baseline_list") + contract_filter + "&versions=1"
        )
        progress_list = (
            reverse("billing:progress_list")
            + contract_filter
            + f"&line_key={record.baseline_item.line_key}"
        )
        controls = reverse("projects:controls", args=[project.pk])
        expense_list = reverse("expenses:list")
        expense_detail = reverse("expenses:detail", args=[expense.pk])
        gallery = reverse("projects:gallery", args=[project.pk])
        timesheet = (
            reverse("timekeeping:timesheet_detail", args=[sheet.pk])
            + scoped
            + f"&employee={employee.pk}"
        )
        cases = [
            case(
                "expense-detail-history",
                expense_detail,
                [
                    one_link(expense_list),
                    crumb_click(expense_list),
                    {"history": "back"},
                    check(
                        f"location.pathname==={json.dumps(expense_detail)}",
                        "Back restores detail",
                    ),
                    {"history": "forward"},
                    check(
                        f"location.pathname==={json.dumps(expense_list)}",
                        "Forward restores list",
                    ),
                ],
                True,
            ),
            case(
                "billing-line",
                reverse("billing:progress_detail", args=[record.pk]),
                [
                    one_link(progress_list),
                    crumb_click(progress_list),
                    check(
                        f"location.search==={json.dumps(urlsplit(progress_list).query.join(['?', '']))}",
                        "contract and line retained",
                    ),
                ],
                True,
            ),
            case(
                "billing-baseline-detail",
                reverse("billing:baseline_detail", args=[claim.baseline.pk]),
                [one_link(baseline_list), crumb_click(baseline_list)],
            ),
            case(
                "billing-baseline-list",
                baseline_list,
                [one_link(contract), crumb_click(contract)],
                True,
            ),
            case(
                "billing-claim-list",
                reverse("billing:claim_list") + contract_filter,
                [one_link(contract), crumb_click(contract)],
            ),
            case(
                "contract-detail",
                contract,
                [
                    one_link(reverse("contracts:list")),
                    crumb_click(reverse("contracts:list")),
                ],
            ),
            case(
                "worker-detail",
                reverse("workforce:field_detail", args=[employee.pk]) + scoped,
                [one_link(worker, 2), crumb_click(worker)],
                True,
            ),
            case(
                "attendance-detail",
                reverse("timekeeping:record_detail", args=["attendance", attendance.pk])
                + scoped
                + f"&employee={employee.pk}",
                [one_link(workbench), crumb_click(workbench)],
                True,
            ),
            case(
                "timesheet-detail",
                timesheet,
                [one_link(workbench, 2), crumb_click(workbench)],
                True,
            ),
            case(
                "equipment-operations",
                reverse("equipment:operations_workbench"),
                [
                    one_link(reverse("equipment:list")),
                    crumb_click(reverse("equipment:list")),
                ],
            ),
            case(
                "project-detail",
                reverse("projects:detail", args=[project.pk]),
                [
                    one_link(reverse("projects:list")),
                    crumb_click(reverse("projects:list")),
                ],
            ),
            case(
                "project-controls-comparison",
                reverse("projects:controls_comparison", args=[project.pk]),
                [one_link(controls), crumb_click(controls)],
            ),
            case(
                "project-controls-exceptions",
                reverse("projects:controls_exceptions", args=[project.pk]),
                [one_link(controls), crumb_click(controls)],
                True,
            ),
            case(
                "project-photo-cancel",
                reverse("projects:photo_add", args=[project.pk]),
                [
                    one_link(gallery, 2),
                    {
                        "clickSelector": "main form a[href="
                        + json.dumps(gallery)
                        + "]",
                        "afterPath": gallery,
                    },
                ],
                True,
            ),
            case(
                "expense-create-cancel",
                reverse("expenses:create"),
                [
                    {
                        "clickSelector": "main form a[href="
                        + json.dumps(expense_list)
                        + "]",
                        "afterPath": expense_list,
                    }
                ],
                True,
            ),
            case("retained-workflow", reverse("workflows:workbench")),
        ]
        for scenario in cases:
            self.login(self.owner)
            response = self.client.get(scenario["path"])
            self.assertEqual(
                response.status_code, 200, (scenario["name"], response.status_code)
            )
        self.browser(self.owner, cases[:8])
        self.browser(self.owner, cases[8:])
        visual = []
        for scenario in cases:
            if scenario["name"] == "retained-workflow":
                continue
            for width in (1440, 320):
                visual.append(
                    {
                        **scenario,
                        "name": scenario["name"] + "-visual-" + str(width),
                        "width": width,
                        "mobile": width < 640,
                        "steps": [scenario["steps"][0]]
                        if scenario["steps"] and "inspect" in scenario["steps"][0]
                        else [],
                        "screenshot": True,
                    }
                )
        for offset in range(0, len(visual), 8):
            self.browser(self.owner, visual[offset : offset + 8])
        restricted, _, _ = scoped_reader(
            self.organization,
            project,
            ["projects.view", "project_controls.compare", "timesheets.view"],
            username="nav-limited",
        )
        self.login(restricted)
        comparison = reverse("projects:controls_comparison", args=[project.pk])
        self.assertEqual(self.client.get(controls).status_code, 403)
        self.browser(
            restricted,
            [
                case(
                    "restricted-comparison",
                    comparison,
                    [
                        check(
                            f"!document.querySelector('main a[href='+{json.dumps(json.dumps(controls))} +']')",
                            "restricted user receives no controls link",
                        )
                    ],
                ),
            ],
        )


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ProcurementNavigation(
    BrowserBase, CommercialScopeFixture, StaticLiveServerTestCase
):
    serialized_rollback = True

    def test_rfq(self):
        rfq = self.draft_rfq()
        detail = reverse("procurement:rfq_detail", args=[rfq.pk])
        workspace = reverse("procurement:rfq_buyer_workspace", args=[rfq.pk])
        scope = reverse("procurement:rfq_scope_define", args=[rfq.pk])
        action = reverse("procurement:rfq_buyer_action", args=[rfq.pk, "capture"])
        self.browser(
            self.owner,
            [
                {
                    **case("rfq-workspace-visual", workspace, [one_link(detail)], True),
                    "screenshot": True,
                },
                case(
                    "rfq-workspace",
                    workspace,
                    [one_link(detail), crumb_click(detail)],
                    True,
                ),
                case(
                    "rfq-scope-cancel",
                    scope,
                    [
                        one_link(detail, 2),
                        check(
                            f"!!document.querySelector('main a[href='+{json.dumps(json.dumps(detail + '#supplier-selection'))}+']')",
                            "section-specific return survives",
                        ),
                        {
                            "clickSelector": "main form a[href="
                            + json.dumps(detail)
                            + "]",
                            "afterPath": detail,
                        },
                    ],
                    True,
                ),
                case(
                    "rfq-action-cancel",
                    action,
                    [
                        one_link(workspace, 2),
                        {
                            "clickSelector": "main form a[href="
                            + json.dumps(workspace)
                            + "]",
                            "afterPath": workspace,
                        },
                    ],
                ),
            ],
        )


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class EvidenceNavigation(BrowserBase, StaticLiveServerTestCase):
    serialized_rollback = True
    setUp = EvidenceIntegrationTests.setUp
    login = EvidenceIntegrationTests.login
    material = EvidenceIntegrationTests.material
    panel = EvidenceIntegrationTests.panel
    url = EvidenceIntegrationTests.url
    clean_version = EvidenceIntegrationTests.clean_version
    _create_document = EvidenceIntegrationTests._create_document
    _pdf_upload = staticmethod(EvidenceIntegrationTests._pdf_upload)

    def test_evidence_return(self):
        material = self.material()
        document = self._create_document()
        version = document.current_version
        self.clean_version(version)
        add_document_link(document=document, actor=self.owner, target=material)
        parent = self.panel("material", material).source.url
        self.browser(
            self.owner,
            [
                case(
                    "evidence-breadcrumb",
                    self.url("detail", "material", material, version),
                    [one_link(parent), crumb_click(parent)],
                    True,
                )
            ],
        )


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    PRODUCT_SURFACE_PROFILE="FULL_ERP",
)
class PlatformNavigation(BrowserBase, StaticLiveServerTestCase):
    serialized_rollback = True

    def login(self, actor):
        self.client.force_login(actor)

    def test_platform_contexts(self):
        from apps.organizations.models import PlatformRoleAssignment, PlatformRoleCode

        admin = User.objects.create_superuser(
            username="navigation-admin-proof", password="fixture-only"
        )
        actor = User.objects.create_user(
            username="navigation-platform-proof", password="fixture-only"
        )
        PlatformRoleAssignment.objects.create(
            user=actor,
            role=PlatformRoleCode.PLATFORM_ADMIN,
            assigned_by=admin,
            approved_by=admin,
            reason="Disposable Platform Admin browser fixture",
        )
        self.browser(
            admin,
            [
                case("django-admin-index", reverse("admin:index")),
                case(
                    "django-admin-group-list",
                    reverse("admin:auth_group_changelist"),
                    [
                        check(
                            "document.documentElement.dir==='rtl' && !!document.querySelector('.breadcrumbs a')",
                            "Django Admin RTL breadcrumb",
                        )
                    ],
                ),
                {
                    **case(
                        "django-admin-tenant-model-denied",
                        reverse("admin:organizations_organization_changelist"),
                    ),
                    "status": 403,
                },
            ],
        )
        self.browser(
            actor,
            [
                case(
                    "platform-groups-cancel",
                    reverse("expenses:platform_group_create"),
                    [
                        {
                            "clickHref": reverse("expenses:platform_group_list"),
                            "afterPath": reverse("expenses:platform_group_list"),
                        }
                    ],
                    True,
                ),
                case(
                    "platform-role-catalog",
                    reverse("organizations:platform_role_catalog"),
                ),
            ],
        )


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    PRODUCT_SURFACE_PROFILE="FULL_ERP",
)
class ModuleJourneys(BrowserBase, JourneyFixture, StaticLiveServerTestCase):
    serialized_rollback = True

    def test_module_home_round_trips(self):
        from apps.organizations.models import (
            OrganizationSettings,
            OrganizationRole,
            BusinessPermission,
            MembershipRoleAssignment,
        )

        self.make_fixture(persian=True)
        OrganizationSettings.objects.get_or_create(organization=self.organization)
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="nav-journeys",
            name="Navigation fixture",
        )
        role.permissions.set(BusinessPermission.objects.all())
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=self.organization.memberships.get(user=self.owner),
            role=role,
            reason="Disposable navigation coverage",
        )
        self.login(self.owner)
        self.client.raise_request_exception = False
        scenarios = []
        for resolver in get_resolver().url_patterns:
            if (
                not isinstance(resolver, URLResolver)
                or resolver.namespace == "admin"
                or not resolver.namespace
            ):
                continue
            prefix = "/" + str(resolver.pattern)
            candidates = [prefix] + [
                prefix + str(pattern.pattern)
                for pattern in resolver.url_patterns
                if pattern.name
                and re.search(
                    r"list|index|workbench|dashboard|^select$|^settings$|^report$",
                    pattern.name,
                )
                and not any(symbol in str(pattern.pattern) for symbol in "<^")
            ]
            for path in dict.fromkeys(candidates):
                response = self.client.get(path)
                if response.status_code == 200 and response.headers.get(
                    "Content-Type", ""
                ).startswith("text/html"):
                    break
            else:
                raise AssertionError("No permitted entrypoint " + resolver.namespace)
            scenarios.append(
                case(
                    "module-journey-" + resolver.namespace,
                    path,
                    [
                        {"clickSelector": 'a[href="/"]', "afterPath": "/"},
                        {"history": "back"},
                        check(
                            "location.pathname===" + json.dumps(path),
                            "Browser Back restores original module",
                        ),
                        {"history": "forward"},
                        check(
                            "location.pathname==='/'", "Browser Forward returns home"
                        ),
                    ],
                    mobile=False,
                )
            )
        for offset in range(0, len(scenarios), 8):
            self.browser(self.owner, scenarios[offset : offset + 8])

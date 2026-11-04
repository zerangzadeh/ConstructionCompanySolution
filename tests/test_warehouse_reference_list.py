"""B1 Warehouse List: existing GET behavior, access boundaries and real Chrome."""

import os
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.billing import test_mvp03_browser as browser_fixture
from apps.contracts.models import Contract
from apps.inventory.models import Warehouse
from apps.organizations.models import (
    BusinessPermission,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    Organization,
    OrganizationRole,
)
from apps.organizations.services import set_active_organization
from apps.projects.models import Project


class RenderedControls(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.nodes = []
        self.feed(content.decode("utf-8"))

    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs)))


class WarehouseListFixture:
    def make_fixture(self):
        self.organization = Organization.objects.create(
            name="شرکت آزمون انبار", slug="b1"
        )
        self.project = Project.objects.create(
            organization=self.organization, code="B1-P", name="پروژه نمونه سازه"
        )
        self.hidden_project = Project.objects.create(
            organization=self.organization, code="B1-H", name="پروژه خارج از محدوده"
        )
        self.owner = User.objects.create_user(
            username="b1-owner", first_name="کاربر", last_name="آزمون"
        )
        membership = self.organization.memberships.create(
            user=self.owner, role="company_owner", status="active"
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=OrganizationRole.objects.get(
                organization__isnull=True, code="company_owner"
            ),
            reason="Synthetic B1 owner fixture",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="organization",
            reason="Synthetic B1 organization scope",
        )
        role = OrganizationRole.objects.create(
            organization=self.organization, code="b1-reader", name="مشاهده انبار"
        )
        role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=["warehouses.view", "stock_transactions.view"]
            )
        )
        self.reader = User.objects.create_user(username="b1-reader")
        membership = self.organization.memberships.create(
            user=self.reader, role_definition=role, status="active"
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="Synthetic B1 reader fixture",
        )
        self.reader_scope = MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="project",
            project=self.project,
            reason="Synthetic B1 single-project scope",
        )
        self.denied = User.objects.create_user(username="b1-denied")
        self.organization.memberships.create(
            user=self.denied, role="member", status="active"
        )
        self.warehouses = [
            Warehouse.objects.create(
                organization=self.organization,
                project=self.project,
                code=f"B1-{index:02}",
                name=f"انبار نمونه {index:02}",
                location="تهران، کارگاه مرکزی" if index < 14 else "کرج، کارگاه غرب",
                created_by=self.owner,
            )
            for index in range(28)
        ]
        self.hidden = Warehouse.objects.create(
            organization=self.organization,
            project=self.hidden_project,
            code="B1-HIDDEN",
            name="انبار پروژه غیرمجاز",
            location="تبریز",
        )
        self.central = Warehouse.objects.create(
            organization=self.organization,
            code="B1-CENTRAL",
            name="انبار مرکزی",
        )
        self.other_organization = Organization.objects.create(
            name="شرکت دیگر", slug="b1-other"
        )
        self.foreign = Warehouse.objects.create(
            organization=self.other_organization,
            code="FOREIGN",
            name="انبار شرکت دیگر",
        )
        Contract.objects.create(
            organization=self.organization,
            project=self.project,
            contract_number="B1-REF",
            title="قرارداد نمونه مرجع",
            counterparty_name="طرف نمونه",
            contract_value=Decimal(1000000),
            created_by=self.owner,
        )

    def login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        set_active_organization(session, self.organization)
        session.save()

    def empty_reader_scope(self):
        empty = Project.objects.create(
            organization=self.organization, code="B1-EMPTY", name="پروژه بدون انبار"
        )
        self.reader_scope.project = empty
        self.reader_scope.save(update_fields=["project"])


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class WarehouseReferenceListTests(WarehouseListFixture, TestCase):
    def setUp(self):
        self.make_fixture()
        self.login(self.owner)

    def test_existing_filters_compose_and_count_all_results(self):
        response = self.client.get(
            "/inventory/",
            {
                "warehouse": "B1-",
                "project": "نمونه",
                "location": "تهران",
            },
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 14)
        self.assertEqual(set(response.context["warehouses"]), set(self.warehouses[:14]))
        self.assertContains(response, "data-filter-bar", count=1)
        self.assertContains(response, 'id="list-filter-bar"', count=1)
        self.assertNotContains(response, 'name="status"')
        self.assertNotContains(response, 'id="table-filters"')
        self.assertNotContains(response, "data-table-filter-row")
        self.assertContains(response, "<strong>14</strong>", html=True)

    def test_sort_pagination_and_query_preservation(self):
        response = self.client.get(
            f"/inventory/?warehouse=B1-&project={self.project.pk}&sort=warehouse&direction=desc&page=2"
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 28)
        self.assertEqual(
            [w.code for w in response.context["warehouses"]],
            ["B1-02", "B1-01", "B1-00"],
        )
        self.assertContains(response, 'aria-sort="descending"')
        self.assertContains(response, "warehouse=B1-")
        self.assertContains(response, "direction=desc")
        # All four existing server sort keys remain available; none is a new filter.
        for key in ("warehouse", "project", "location", "status"):
            result = self.client.get("/inventory/", {"sort": key})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.context["page_obj"].paginator.count, 30)

    def test_chips_clear_and_get_form_retain_sort_without_mutating_context(self):
        session = self.client.session
        session["active_project_id"] = str(self.hidden_project.pk)
        session.save()
        session_before = dict(self.client.session)
        response = self.client.get(
            f"/inventory/?warehouse=B1&project={self.project.pk}&location=تهران&sort=location&direction=desc&page=2"
        )
        nodes = RenderedControls(response.content).nodes
        chip = next(
            attrs for tag, attrs in nodes if attrs.get("data-filter-chip") == "location"
        )
        query = parse_qs(urlsplit(chip["href"]).query)
        self.assertNotIn("location", query)
        self.assertNotIn("page", query)
        self.assertEqual(query["warehouse"], ["B1"])
        self.assertEqual(query["project"], [str(self.project.pk)])
        self.assertEqual(query["sort"], ["location"])
        clear = next(
            attrs for tag, attrs in nodes if "data-table-filter-clear" in attrs
        )
        self.assertEqual(
            parse_qs(urlsplit(clear["href"]).query),
            {
                "sort": ["location"],
                "direction": ["desc"],
            },
        )
        form = next(
            attrs for tag, attrs in nodes if attrs.get("id") == "list-filter-bar"
        )
        self.assertEqual(form["method"], "get")
        self.assertEqual(
            {
                attrs["name"]
                for tag, attrs in nodes
                if tag in {"input", "select"}
                and attrs.get("name")
                in {"warehouse", "project", "location", "sort", "direction"}
            },
            {
                "warehouse",
                "project",
                "location",
                "sort",
                "direction",
            },
        )
        self.assertEqual(dict(self.client.session), session_before)

    def test_project_options_and_exact_filter_follow_warehouse_scope(self):
        self.hidden_project.name = self.project.name
        self.hidden_project.save(update_fields=["name"])
        exact = self.client.get("/inventory/", {"project": self.project.pk})
        self.assertEqual(exact.context["page_obj"].paginator.count, 28)
        legacy = self.client.get("/inventory/", {"project": "نمونه"})
        self.assertEqual(legacy.context["page_obj"].paginator.count, 29)
        self.login(self.reader)
        options = self.client.get(
            "/inventory/", {"filter_options": "project", "q": "B1-"}
        )
        self.assertEqual(options.status_code, 200)
        self.assertEqual(
            [row["value"] for row in options.json()["results"]], [str(self.project.pk)]
        )
        forged = self.client.get("/inventory/", {"project": self.hidden_project.pk})
        self.assertEqual(forged.context["page_obj"].paginator.count, 0)
        self.assertNotIn(
            str(self.hidden_project.pk),
            [
                attrs.get("value")
                for tag, attrs in RenderedControls(forged.content).nodes
                if tag == "option"
            ],
        )
        self.login(self.denied)
        self.assertEqual(
            self.client.get("/inventory/?filter_options=project").status_code, 403
        )

    def test_location_options_are_distinct_searchable_and_scoped(self):
        self.foreign.location = "اصفهان"
        self.foreign.save(update_fields=["location"])
        self.login(self.reader)
        url = "/inventory/?filter_options=location"
        response = self.client.get(url)
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        self.assertCountEqual(
            [row["value"] for row in response.json()["results"]],
            ["تهران، کارگاه مرکزی", "کرج، کارگاه غرب"],
        )
        self.assertEqual(
            self.client.get(f"{url}&q=غرب").json()["results"],
            [{"value": "کرج، کارگاه غرب", "label": "کرج، کارگاه غرب"}],
        )
        self.assertEqual(
            self.client.get("/inventory/?location=تهران")
            .context["page_obj"]
            .paginator.count,
            14,
        )
        self.login(self.denied)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_empty_and_filtered_empty_offer_only_real_authorized_recovery(self):
        response = self.client.get("/inventory/?warehouse=NO-MATCH")
        self.assertContains(response, "با فیلترهای فعلی نتیجه‌ای یافت نشد")
        self.assertNotContains(response, "اولین انبار")
        self.login(self.reader)
        self.empty_reader_scope()
        response = self.client.get("/inventory/")
        self.assertEqual(response.context["page_obj"].paginator.count, 0)
        self.assertContains(response, "هنوز انباری ثبت نشده است")
        self.assertNotContains(response, reverse("inventory:warehouse_create"))
        self.assertNotContains(response, self.hidden.name)

    def test_reader_scope_tenant_isolation_and_create_visibility(self):
        self.login(self.reader)
        response = self.client.get("/inventory/")
        self.assertEqual(response.context["page_obj"].paginator.count, 28)
        for warehouse in (self.hidden, self.central, self.foreign):
            self.assertNotContains(response, warehouse.name)
        self.assertNotContains(response, reverse("inventory:warehouse_create"))
        for field, value in (
            ("warehouse", "FOREIGN"),
            ("project", self.hidden_project.name),
        ):
            response = self.client.get("/inventory/", {field: value})
            self.assertEqual(response.context["page_obj"].paginator.count, 0)
        self.assertEqual(
            self.client.get(
                reverse("inventory:warehouse_detail", args=[self.foreign.pk])
            ).status_code,
            404,
        )

    def test_denied_and_suspended_memberships_remain_denied(self):
        self.login(self.denied)
        self.assertEqual(self.client.get("/inventory/").status_code, 403)
        self.reader_scope.revoked_at = timezone.now()
        self.reader_scope.save(update_fields=["revoked_at"])
        self.login(self.reader)
        self.assertEqual(self.client.get("/inventory/").status_code, 403)
        membership = self.organization.memberships.get(user=self.reader)
        membership.status = "suspended"
        membership.save(update_fields=["status", "updated_at"])
        self.login(self.reader)
        self.assertNotEqual(self.client.get("/inventory/").status_code, 200)

    def test_real_create_detail_navigation_and_preserved_status_meaning(self):
        self.warehouses[0].archived_at = timezone.now()
        self.warehouses[0].is_active = False
        self.warehouses[0].save(update_fields=["archived_at", "is_active"])
        response = self.client.get("/inventory/?warehouse=B1-00")
        self.assertContains(response, "بایگانی‌شده")
        for name, args in (
            ("warehouse_create", []),
            ("warehouse_detail", [self.warehouses[0].pk]),
        ):
            url = reverse(f"inventory:{name}", args=args)
            self.assertContains(response, url)
            self.assertEqual(self.client.get(url).status_code, 200)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class WarehouseReferenceBrowserTests(WarehouseListFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown

    def test_warehouse_reference_journeys(self):
        self.make_fixture()
        phase = os.environ.get("BONIRA_B1_PHASE", "after")
        self.browser_evidence_directory = Path("output/b1-warehouse-list") / phase
        common = {
            "status": 200,
            "screenshot": True,
            "viewportScreenshot": True,
            "noJsErrors": True,
        }
        scenarios = [
            {**common, "name": f"{page}-{width}", "path": path, "width": width}
            for page, path in (
                ("warehouses", "/inventory/"),
                ("contracts", "/contracts/"),
            )
            for width in (1440, 1024, 390)
        ]
        self.browser(self.owner, scenarios)
        if phase == "before":
            return

        def check(expression, description):
            return {"inspect": expression, "description": description}

        coherent = "document.querySelectorAll('#list-filter-bar').length===1 && !document.querySelector('#table-filters') && !document.querySelector('[data-table-filter-row]') && !document.querySelector('input[name=status],select[name=status]')"
        filter_layout = """(() => {
            const bar = document.querySelector('[data-fit-quick-filters]');
            const search = bar.querySelector('input[name=warehouse]');
            const project = bar.querySelector('select[name=project]');
            const control = project.tomselect?.control;
            const locationSelect = bar.querySelector('select[name=location]');
            const location = locationSelect.tomselect?.control;
            const apply = bar.querySelector('[data-filter-apply]');
            const clear = bar.querySelector('[data-table-filter-clear]');
            const aligned = [control, location, clear].every(el => Math.abs(el.getBoundingClientRect().top - apply.getBoundingClientRect().top) < 3);
            return search.type === 'search' && search.dir === 'auto'
                && project.tomselect.control_input.placeholder === 'همه پروژه‌ها'
                && locationSelect.tomselect.control_input.placeholder === 'همه محل‌ها'
                && location.offsetWidth >= 176
                && !bar.querySelector('details,[data-more-toggle]')
                && bar.querySelectorAll('button[type=submit]').length===1
                && bar.querySelectorAll('[data-table-filter-clear]').length===1
                && [search, control, location, apply, clear].every(el => el.offsetWidth > 0)
                && (innerWidth < 1280 || aligned && Math.abs(search.getBoundingClientRect().top - apply.getBoundingClientRect().top) < 3);
        })()"""
        self.browser(
            self.owner,
            [
                {
                    **common,
                    "name": f"interactions-{width}",
                    "path": "/inventory/",
                    "width": width,
                    "steps": [
                        check(coherent, "single supported GET filter workspace"),
                        check(
                            filter_layout,
                            "prominent search and compact searchable filters",
                        ),
                        {
                            "searchChoice": {
                                "name": "project",
                                "query": "B1-P",
                                "value": str(self.project.pk),
                            }
                        },
                        {
                            "fill": {"warehouse": "B1-"},
                            "clickSelector": "[data-filter-apply]",
                            "afterPath": "/inventory/",
                        },
                        check(
                            f"document.querySelector('[data-filter-result-count] strong').textContent==='28' && new URLSearchParams(location.search).get('project')==='{self.project.pk}'",
                            "authorized count and stable project identifier",
                        ),
                        {"clickSelector": "[rel=next]", "afterPath": "/inventory/"},
                        check(
                            "document.querySelectorAll('tbody tr').length===3 && new URLSearchParams(location.search).get('page')==='2' && document.querySelector('[name=warehouse]').value==='B1-'",
                            "pagination preserves filters",
                        ),
                        {"history": "back"},
                        check(
                            "!new URLSearchParams(location.search).has('page') && document.querySelectorAll('tbody tr').length===25",
                            "Back restores filters and first page",
                        ),
                        {"history": "forward"},
                        {"reload": True, "afterPath": "/inventory/"},
                        check(
                            f"new URLSearchParams(location.search).get('page')==='2' && document.querySelectorAll('tbody tr').length===3 && document.querySelector('#id_project').value==='{self.project.pk}'",
                            "Forward and refresh restore second page",
                        ),
                        {
                            "clickSelector": "[data-filter-chip=project]",
                            "afterPath": "/inventory/",
                        },
                        check(
                            "!new URLSearchParams(location.search).has('project') && !new URLSearchParams(location.search).has('page')",
                            "chip removal resets page",
                        ),
                        {"toggleSelector": ".erp-list-sort-menu summary"},
                        {
                            "clickSelector": ".erp-list-sort-menu a[href*='sort=warehouse']",
                            "afterPath": "/inventory/",
                        },
                        check(
                            "new URLSearchParams(location.search).get('sort')==='warehouse' && new URLSearchParams(location.search).get('warehouse')==='B1-'",
                            "existing sorting preserves filter",
                        ),
                        {
                            "clickSelector": "[data-table-filter-clear]",
                            "afterPath": "/inventory/",
                        },
                        check(
                            "!new URLSearchParams(location.search).has('warehouse') && new URLSearchParams(location.search).get('sort')==='warehouse'",
                            "clear preserves sorting",
                        ),
                        {"toggleSelector": ".erp-list-row-menu summary"},
                        check(
                            "document.querySelector('.erp-list-row-menu[open] a').target==='_blank'",
                            "real detail row menu",
                        ),
                    ],
                }
                for width in (1440, 1024, 390)
            ]
            + [
                {
                    **common,
                    "name": f"location-filter-{width}",
                    "path": f"/inventory/?warehouse=B1-&project={self.project.pk}",
                    "width": width,
                    "mustText": ["14", "تهران"],
                    "steps": [
                        {
                            "searchChoice": {
                                "name": "location",
                                "query": "تهران",
                                "value": "تهران، کارگاه مرکزی",
                            }
                        },
                        {
                            "clickSelector": "[data-filter-apply]",
                            "afterPath": "/inventory/",
                        },
                        check(
                            "document.querySelectorAll('tbody tr').length===14 && document.querySelectorAll('[data-filter-chip]').length===3 && document.querySelector('select[name=location]').value==='تهران، کارگاه مرکزی' && new URLSearchParams(location.search).get('location')==='تهران، کارگاه مرکزی' && getComputedStyle(document.querySelector('[name=warehouse]')).direction==='ltr'",
                            "all three filters compose, and the active location and LTR search are restored",
                        ),
                        {
                            "clickSelector": "[data-filter-chip=location]",
                            "afterPath": "/inventory/",
                        },
                        check(
                            "!new URLSearchParams(location.search).has('location') && document.querySelector('[data-filter-result-count] strong').textContent==='28'",
                            "removing the location chip preserves search and project",
                        ),
                        {"history": "back"},
                        check(
                            "document.querySelector('select[name=location]').value==='تهران، کارگاه مرکزی'",
                            "Back restores the location selection",
                        ),
                        {"history": "forward"},
                        check(
                            "document.querySelector('select[name=location]').value===''",
                            "Forward restores the cleared location selection",
                        ),
                        {"history": "back"},
                    ],
                }
                for width in (1440, 1024, 390)
            ]
            + [
                {
                    **common,
                    "name": "filtered-empty",
                    "path": "/inventory/?warehouse=NO-MATCH",
                    "mustText": ["با فیلترهای فعلی نتیجه‌ای یافت نشد"],
                    "steps": [
                        check(
                            "!!document.querySelector('[data-filter-chip=warehouse]') && !!document.querySelector('[data-table-filter-clear]')",
                            "filter and clear remain accessible on empty results",
                        )
                    ],
                },
                {
                    **common,
                    "name": "clear-empty",
                    "path": "/inventory/?location=NO-MATCH&sort=location&direction=desc",
                    "steps": [
                        {
                            "clickSelector": "[data-table-filter-clear]",
                            "afterPath": "/inventory/",
                        },
                        check(
                            "!new URLSearchParams(location.search).has('location') && new URLSearchParams(location.search).get('sort')==='location' && document.querySelector('[data-filter-result-count] strong').textContent==='30'",
                            "clearing an empty result restores the authorized list and retains sort",
                        ),
                    ],
                },
                {
                    **common,
                    "name": "native-get-no-js",
                    "path": "/inventory/",
                    "noJS": True,
                    "steps": [
                        {
                            "fill": {
                                "warehouse": "B1-",
                                "project": str(self.project.pk),
                                "location": "تهران، کارگاه مرکزی",
                            },
                            "clickSelector": "[data-filter-apply]",
                            "afterPath": "/inventory/",
                        },
                        check(
                            "document.querySelectorAll('tbody tr').length===14 && document.querySelector('select[name=location]').value==='تهران، کارگاه مرکزی'",
                            "native GET submission without JavaScript",
                        ),
                    ],
                },
                {
                    **common,
                    "name": "create-navigation",
                    "path": "/inventory/",
                    "steps": [
                        {
                            "clickHref": "/inventory/create/",
                            "afterPath": "/inventory/create/",
                        },
                        check(
                            "!!document.querySelector('form[method=post]')",
                            "real existing create form",
                        ),
                    ],
                },
                {
                    **common,
                    "name": "detail-navigation",
                    "path": "/inventory/?warehouse=B1-00",
                    "steps": [
                        {
                            "clickHref": reverse(
                                "inventory:warehouse_detail",
                                args=[self.warehouses[0].pk],
                            ),
                            "afterPath": reverse(
                                "inventory:warehouse_detail",
                                args=[self.warehouses[0].pk],
                            ),
                        },
                        {"history": "back"},
                        check(
                            "document.querySelector('[name=warehouse]').value==='B1-00'",
                            "detail Back restores list query",
                        ),
                    ],
                },
            ],
        )
        self.browser(
            self.reader,
            [
                {
                    **common,
                    "name": f"reader-{width}",
                    "path": "/inventory/",
                    "width": width,
                    "absentLinks": ["/inventory/create/"],
                    "absentText": [
                        self.hidden.name,
                        self.central.name,
                        self.foreign.name,
                    ],
                    "steps": [
                        check(coherent, "restricted list uses the same workspace")
                    ],
                }
                for width in (1440, 1024, 390)
            ]
            + [
                {
                    **common,
                    "name": "reader-forged-project",
                    "path": "/inventory/?project=خارج",
                    "mustText": ["با فیلترهای فعلی نتیجه‌ای یافت نشد"],
                    "absentText": [self.hidden.name, self.foreign.name],
                }
            ],
        )
        self.empty_reader_scope()
        self.browser(
            self.reader,
            [
                {
                    **common,
                    "name": "empty-scope",
                    "path": "/inventory/",
                    "mustText": ["هنوز انباری ثبت نشده است"],
                    "absentLinks": ["/inventory/create/"],
                    "absentText": [self.hidden.name, self.foreign.name],
                }
            ],
        )
        self.browser(
            self.denied,
            [
                {
                    "name": "denied",
                    "path": "/inventory/",
                    "status": 403,
                    "screenshot": True,
                    "plainBusinessDenial": True,
                    "absentText": [self.hidden.name, self.foreign.name],
                }
            ],
        )

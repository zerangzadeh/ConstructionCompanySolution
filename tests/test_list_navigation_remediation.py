"""Real Chrome evidence for the requested list and navigation corrections."""

import os
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from test_warehouse_reference_list import WarehouseListFixture

from apps.billing import test_mvp03_browser as browser_fixture
from apps.equipment.models import Equipment
from apps.materials.models import Material, MaterialCategory, UnitOfMeasure
from apps.organizations.models import BusinessPermission, MembershipScopeGrant
from apps.workforce.models import WorkTeam
from core.product_surface import navigation_groups


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class ListNavigationRemediationTests(WarehouseListFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = Path("output/list-navigation-remediation")

    def seed_lists(self):
        self.make_fixture()
        unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="NAV-U",
            name="عدد",
            symbol="عدد",
            category="count",
        )
        category = MaterialCategory.objects.create(
            organization=self.organization, code="NAV-C", name="مصالح نمونه"
        )
        self.material = Material.objects.create(
            organization=self.organization,
            code="NAV-M",
            name="مصالح آزمون",
            category=category,
            unit_of_measure=unit,
        )
        self.equipment = Equipment.objects.create(
            organization=self.organization,
            code="NAV-E",
            name="تجهیز آزمون",
            category="ماشین‌آلات",
            ownership_type="owned",
            created_by=self.owner,
            updated_by=self.owner,
        )
        WorkTeam.objects.create(
            organization=self.organization, code="NAV-T", name="گروه آزمون"
        )

    def test_rendered_lists_and_navigation(self):
        self.seed_lists()
        baseline = os.environ.get("BONIRA_CAPTURE_BEFORE") == "1"
        phase = "before" if baseline else "after"
        self.browser_evidence_directory /= phase
        routes = (
            ("materials", "materials:material_list"),
            ("categories", "materials:category_list"),
            ("equipment", "equipment:list"),
            ("safety-reference", "safety:list"),
            ("teams", "workforce:work_team_list"),
            ("equipment-operations", "equipment:operations_workbench"),
        )
        common = {
            "status": 200,
            "screenshot": True,
            "viewportScreenshot": True,
            "noJsErrors": True,
        }
        self.browser(
            self.owner,
            [
                dict(common, name=f"{name}-{width}", path=reverse(route), width=width)
                for name, route in routes
                for width in ((1440,) if baseline else (1440, 1024, 390))
            ],
        )
        if baseline:
            return
        self.browser(
            self.owner,
            [
                dict(
                    common,
                    name=f"{name}-row-menu-{width}",
                    path=reverse(route),
                    width=width,
                    preserveScrollScreenshot=True,
                    steps=[
                        {
                            "toggleSelector": "main .erp-list-row-menu summary",
                            "inspect": "(()=>{const p=document.querySelector('main .erp-list-row-menu[open] .erp-list-row-menu__items');if(!p)return false;const r=p.getBoundingClientRect();return getComputedStyle(p).position==='fixed' && r.left>=0 && r.right<=innerWidth && r.top>=0 && r.bottom<=innerHeight && !!document.elementFromPoint(r.left+r.width/2,r.top+r.height/2)?.closest('.erp-list-row-menu__items');})()",
                            "description": "row action menu stays visible and usable inside the viewport",
                        }
                    ],
                )
                for name, route in routes[:3]
                for width in (1440, 390)
            ],
        )
        root = reverse("equipment:list")
        operations = reverse("equipment:operations_workbench")
        create = reverse("equipment:create")
        self.browser(
            self.owner,
            [
                dict(
                    common,
                    name="equipment-entry-journey",
                    path=root,
                    steps=[
                        {
                            "inspect": f"!!document.querySelector('aside a[href=\"{root}\"]') && !document.querySelector('aside a[href=\"{operations}\"]')",
                            "description": "one primary equipment menu destination",
                        },
                        {
                            "clickSelector": f"main nav a[href='{operations}']",
                            "afterPath": operations,
                        },
                        {
                            "inspect": f"!document.querySelector('main a[href=\"{create}\"]')",
                            "description": "operations offers no equipment master creation action",
                        },
                        {
                            "clickSelector": f"main nav a[href='{root}']",
                            "afterPath": root,
                        },
                        {
                            "clickSelector": "main .erp-page-header__action",
                            "afterPath": create,
                        },
                        {
                            "inspect": "!!document.querySelector('main .erp-compact-form input[name=code]')",
                            "description": "create belongs to the equipment list",
                        },
                    ],
                )
            ],
        )
        self.browser(
            self.owner,
            [
                dict(
                    common,
                    name="equipment-filter-history",
                    path=root,
                    steps=[
                        {
                            "fill": {"equipment": "NAV-E"},
                            "clickSelector": "#list-filter-bar [data-filter-apply]",
                            "afterPath": root,
                        },
                        {
                            "inspect": "location.search.includes('equipment=NAV-E') && document.querySelectorAll('main tbody tr').length === 1 && !!document.querySelector('main .erp-list-chip')",
                            "description": "GET search and removable active filter",
                        },
                        {
                            "fill": {"equipment": "NO-RESULTS"},
                            "clickSelector": "#list-filter-bar [data-filter-apply]",
                            "afterPath": root,
                        },
                        {
                            "inspect": "!document.querySelector('main tbody tr')",
                            "description": "filtered empty state",
                        },
                        {"history": "back", "afterPath": root},
                        {
                            "inspect": "document.querySelector('[name=equipment]').value === 'NAV-E'",
                            "description": "Back retains filter",
                        },
                        {"history": "forward", "afterPath": root},
                        {"reload": True, "afterPath": root},
                        {"clickSelector": "main .erp-list-clear", "afterPath": root},
                        {
                            "inspect": "!location.search.includes('equipment=') && document.querySelectorAll('main tbody tr').length === 1",
                            "description": "Clear resets filter and restores records",
                        },
                    ],
                )
            ],
        )
        self.login(self.owner)
        for route, key, collection in (
            ("materials:material_list", "q", "materials"),
            ("materials:category_list", "q", "categories"),
            ("equipment:list", "equipment", "equipment"),
        ):
            response = self.client.get(
                reverse(route),
                {
                    key: "NAV",
                    "sort": "name" if collection != "equipment" else "equipment",
                    "direction": "desc",
                },
            )
            self.assertEqual(response.context["page_obj"].paginator.count, 1)
            response = self.client.get(reverse(route), {key: "NO-RESULTS"})
            self.assertEqual(response.context["page_obj"].paginator.count, 0)
            self.assertContains(response, "erp-list-chip")
        role = self.reader_scope.membership.role_definition
        role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=[
                    "equipment.view",
                    "equipment_operations.view",
                    "materials.view",
                    "material_categories.view",
                    "work_teams.view",
                ]
            )
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=self.reader_scope.membership,
            scope_type="organization",
            reason="Synthetic master data read access",
        )
        self.browser(
            self.reader,
            [dict(common, name="equipment-read-only", path=root, absentLinks=[create])],
        )
        self.assertEqual(self.client.get(create).status_code, 403)
        self.login(self.denied)
        for _, route in routes:
            self.assertEqual(self.client.get(reverse(route)).status_code, 403)

    def test_menu_permission_fallback(self):
        def routes(codes):
            return {
                link.route
                for group in navigation_groups(set(codes))
                for link in group.links
            }

        self.assertIn(
            "equipment:list", routes(["equipment.view", "equipment_operations.view"])
        )
        self.assertNotIn(
            "equipment:operations_workbench",
            routes(["equipment.view", "equipment_operations.view"]),
        )
        self.assertIn("equipment:list", routes(["equipment.view"]))
        self.assertIn(
            "equipment:operations_workbench", routes(["equipment_operations.view"])
        )
        parent = next(
            link
            for group in navigation_groups(
                {"equipment.view", "equipment_operations.view"}
            )
            for link in group.links
            if link.route == "equipment:list"
        )
        for name in ("create", "detail", "operations_workbench", "usage_create"):
            self.assertTrue(parent.is_active_for(f"equipment:{name}"))

    def test_get_filters_pagination_and_isolation(self):
        self.seed_lists()
        unit = self.material.unit_of_measure
        category = self.material.category
        for index in range(27):
            MaterialCategory.objects.create(
                organization=self.organization,
                code=f"PAGE-C-{index:02}",
                name=f"دسته {index:02}",
            )
            Material.objects.create(
                organization=self.organization,
                code=f"PAGE-M-{index:02}",
                name=f"مصالح {index:02}",
                category=category,
                unit_of_measure=unit,
            )
            Equipment.objects.create(
                organization=self.organization,
                code=f"PAGE-E-{index:02}",
                name=f"تجهیز {index:02}",
                category="ماشین‌آلات",
                ownership_type="owned",
                created_by=self.owner,
                updated_by=self.owner,
            )
        foreign_unit = UnitOfMeasure.objects.create(
            organization=self.other_organization,
            code="FOREIGN-U",
            name="واحد دیگر",
            symbol="عدد",
            category="count",
        )
        foreign_category = MaterialCategory.objects.create(
            organization=self.other_organization,
            code="FOREIGN-C",
            name="دسته شرکت دیگر",
        )
        Material.objects.create(
            organization=self.other_organization,
            code="FOREIGN-M",
            name="مصالح شرکت دیگر",
            category=foreign_category,
            unit_of_measure=foreign_unit,
        )
        Equipment.objects.create(
            organization=self.other_organization,
            code="FOREIGN-E",
            name="تجهیز شرکت دیگر",
            category="ماشین‌آلات",
            ownership_type="owned",
        )
        self.login(self.owner)
        for route, key, collection, sort in (
            ("materials:material_list", "q", "materials", "name"),
            ("materials:category_list", "q", "categories", "name"),
            ("equipment:list", "equipment", "equipment", "equipment"),
        ):
            response = self.client.get(
                reverse(route), {"page": "2", "sort": sort, "direction": "desc"}
            )
            self.assertEqual(response.context["page_obj"].paginator.count, 28)
            self.assertEqual(len(response.context[collection]), 3)
            self.assertEqual(
                response.context["pagination_query"], f"sort={sort}&direction=desc"
            )
            self.assertNotContains(response, "FOREIGN-")
            response = self.client.get(
                reverse(route), {key: "PAGE", "sort": sort, "direction": "desc"}
            )
            self.assertEqual(response.context["page_obj"].paginator.count, 27)
            names = [item.name for item in response.context[collection]]
            self.assertEqual(names, sorted(names, reverse=True))
            response = self.client.get(reverse(route), {key: "FOREIGN"})
            self.assertEqual(response.context["page_obj"].paginator.count, 0)
        response = self.client.get(
            reverse("materials:material_list"),
            {"code": "NAV-M", "name": "آزمون", "category": category.name},
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        response = self.client.get(
            reverse("equipment:list"),
            {
                "equipment": "NAV-E",
                "category": "ماشین",
                "ownership": "owned",
                "status": self.equipment.status,
            },
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 1)

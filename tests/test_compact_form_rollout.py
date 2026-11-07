"""MVP Compact Form rollout through the actual routes and Chrome."""

from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from test_warehouse_reference_list import WarehouseListFixture

from apps.billing import test_mvp03_browser as browser_fixture
from apps.equipment.models import Equipment, EquipmentMeterKind
from apps.equipment.p8_models import EquipmentMeter
from apps.expenses.models import ExpenseCategory, PlatformExpenseGroup
from apps.materials.models import Material, MaterialCategory, UnitOfMeasure
from apps.organizations.models import (
    BusinessPermission,
    MembershipScopeGrant,
    OrganizationSettings,
)
from apps.projects.models import ProjectSite
from apps.timekeeping.models import ShiftDefinition, WorkCalendar
from apps.workforce.models import Employee, EmployeeQualification, QualificationKind


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class CompactFormRolloutTests(WarehouseListFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = Path("output/compact-form-rollout")

    def test_equipment_records(self):
        self.make_fixture()
        org = self.organization
        equipment = Equipment.objects.create(
            organization=org,
            code="CF-OPS",
            name="تجهیز آزمون",
            category="آزمون",
            ownership_type="owned",
            created_by=self.owner,
            updated_by=self.owner,
        )
        meter = EquipmentMeter.objects.create(
            organization=org,
            equipment=equipment,
            kind=EquipmentMeterKind.HOURS,
            name="کنتور آزمون",
            unit="hour",
            created_by=self.owner,
        )
        employee = Employee.objects.create(
            organization=org,
            employee_number="CF-OP",
            first_name="اپراتور",
            last_name="آزمون",
            created_by=self.owner,
            updated_by=self.owner,
        )
        qualification = EmployeeQualification.objects.create(
            organization=org,
            employee=employee,
            kind=QualificationKind.CERTIFICATE,
            title="صلاحیت آزمون",
            issued_on="2026-10-01",
            recorded_by=self.owner,
        )
        records = [
            (
                "assignment_create",
                "equipment:assignment_list",
                {
                    "equipment": equipment.pk,
                    "project": self.project.pk,
                    "start_date": "1405/07/23",
                    "end_date": "1405/07/24",
                },
            ),
            (
                "operator_qualification_create",
                "equipment:operations_workbench",
                {
                    "equipment": equipment.pk,
                    "employee": employee.pk,
                    "workforce_qualification": qualification.pk,
                    "effective_from": "1405/07/23",
                },
            ),
            (
                "downtime_create",
                "equipment:operations_workbench",
                {
                    "equipment": equipment.pk,
                    "reason_code": "CF-DOWN",
                    "started_at": "1405/07/23 11:00",
                },
            ),
            (
                "meter_reading_create",
                "equipment:operations_workbench",
                {
                    "meter": meter.pk,
                    "value": "100",
                    "observed_at": "1405/07/23 09:00",
                    "source_key": "CF-METER",
                },
            ),
            (
                "usage_create",
                "equipment:operations_workbench",
                {
                    "equipment": equipment.pk,
                    "started_at": "1405/07/23 08:00",
                    "ended_at": "1405/07/23 09:00",
                    "runtime_hours": "1",
                    "source_key": "CF-USAGE",
                },
            ),
            (
                "fuel_create",
                "equipment:operations_workbench",
                {
                    "equipment": equipment.pk,
                    "occurred_at": "1405/07/23 09:00",
                    "quantity": "10",
                    "unit": "litre",
                    "source_key": "CF-FUEL",
                },
            ),
            (
                "maintenance_plan_create",
                "equipment:operations_workbench",
                {
                    "equipment": equipment.pk,
                    "name": "برنامه آزمون",
                    "maintenance_type": "preventive",
                    "interval_days": "30",
                },
            ),
            (
                "work_order_create",
                "equipment:operations_workbench",
                {
                    "equipment": equipment.pk,
                    "number": "CF-WO",
                    "summary": "دستورکار آزمون",
                },
            ),
        ]
        self.login(self.owner)
        screenshots = [
            {
                "name": f"equipment-{name}-{width}",
                "path": reverse(f"equipment:{name}"),
                "width": width,
                "status": 200,
                "screenshot": True,
                "viewportScreenshot": True,
                "noJsErrors": True,
                "steps": [
                    {
                        "inspect": "document.querySelectorAll('main .erp-compact-form').length === 1 && getComputedStyle(document.querySelector('main footer')).position === 'static'",
                        "description": "a single Compact Form action area",
                    }
                ],
            }
            for name, _cancel, _payload in records
            for width in (1440, 390)
        ]
        self.browser(self.owner, screenshots)
        journeys = []
        cancels = []
        for name, cancel, payload in records:
            url = reverse(f"equipment:{name}")
            first = next(iter(payload))
            invalid = self.client.post(url, {**payload, first: ""})
            self.assertEqual(invalid.status_code, 200)
            self.assertIn(first, invalid.context["form"].errors)
            journeys.append(
                {
                    "name": f"equipment-{name}-save",
                    "path": url,
                    "width": 390,
                    "status": 200,
                    "steps": [
                        {
                            "inspect": "document.querySelector('.erp-compact-form').noValidate = true",
                            "description": "exercise server validation",
                        },
                        {
                            "fill": {
                                **{key: str(value) for key, value in payload.items()},
                                first: "",
                            },
                            "submit": True,
                            "afterPath": url,
                        },
                        {
                            "inspect": "!!document.querySelector('main .erp-field-error')",
                            "description": "the existing required field error is visible",
                        },
                        {
                            "fill": {key: str(value) for key, value in payload.items()},
                            "submit": True,
                        },
                        {
                            "inspect": "!document.querySelector('main .erp-compact-form')",
                            "description": "valid submission follows the existing success destination",
                        },
                    ],
                }
            )
            cancels.append(
                {
                    "name": f"equipment-{name}-cancel",
                    "path": url,
                    "width": 390,
                    "status": 200,
                    "steps": [
                        {"clickSelector": "main footer a", "afterPath": reverse(cancel)}
                    ],
                }
            )
        self.browser(self.owner, journeys)
        self.browser(self.owner, cancels)
        self.login(self.denied)
        for name, _cancel, payload in records:
            self.assertEqual(
                self.client.post(reverse(f"equipment:{name}"), payload).status_code, 403
            )

    def test_calendar_forms(self):
        self.make_fixture()
        org = self.organization
        OrganizationSettings.objects.create(organization=org, timezone="Asia/Tehran")
        calendar = WorkCalendar.objects.create(
            organization=org,
            code="CF-CAL",
            name="تقویم آزمون",
            effective_from="2026-01-01",
            timezone="Asia/Tehran",
            working_weekdays=[6, 7, 1, 2, 3],
            created_by=self.owner,
        )
        shift = ShiftDefinition.objects.create(
            organization=org,
            calendar=calendar,
            code="CF-SH",
            name="شیفت آزمون",
            starts_at="08:00",
            ends_at="16:00",
            effective_from="2026-01-01",
            created_by=self.owner,
        )
        records = [
            (
                "calendar_create",
                {
                    "code": "CF-CAL2",
                    "name": "تقویم تازه",
                    "effective_from": "1405/01/01",
                    "working_weekdays": [6, 7, 1, 2, 3],
                },
            ),
            (
                "shift_create",
                {
                    "calendar": calendar.pk,
                    "code": "CF-SH2",
                    "name": "شیفت تازه",
                    "starts_at": "09:00",
                    "ends_at": "17:00",
                    "effective_from": "1405/01/01",
                },
            ),
            (
                "holiday_create",
                {
                    "calendar": calendar.pk,
                    "holiday_date": "1405/01/02",
                    "name": "تعطیلی آزمون",
                    "reason": "ثبت آزمایشی",
                    "source_reference": "آزمون",
                },
            ),
            (
                "shift_break_create",
                {
                    "shift": shift.pk,
                    "sequence": "1",
                    "starts_at": "12:00",
                    "ends_at": "12:30",
                },
            ),
        ]
        scenarios = [
            {
                "name": f"{name}-{width}",
                "path": reverse(f"timekeeping:{name}"),
                "width": width,
                "status": 200,
                "screenshot": True,
                "viewportScreenshot": True,
                "noJsErrors": True,
                "steps": [
                    {
                        "inspect": "document.querySelectorAll('main .erp-compact-form').length === 1 && getComputedStyle(document.querySelector('main footer')).position === 'static'",
                        "description": "calendar master uses the Compact Form",
                    }
                ],
            }
            for name, _payload in records
            for width in (1440, 390)
        ]
        self.browser(self.owner, scenarios)
        for name, payload in records:
            with self.subTest(form=name):
                url = reverse(f"timekeeping:{name}")
                invalid = self.client.post(url, {"code": "retain"})
                self.assertEqual(invalid.status_code, 200)
                self.assertTrue(invalid.context["form"].errors)
                saved = self.client.post(url, payload)
                self.assertEqual(
                    saved.status_code,
                    302,
                    saved.context["form"].errors if saved.status_code == 200 else "",
                )
                self.assertEqual(self.client.get(saved.url).status_code, 200)
        calendar_journeys = []
        for name, payload in records:
            browser_payload = {
                key: str(value)
                for key, value in payload.items()
                if key != "working_weekdays"
            }
            if "code" in browser_payload:
                browser_payload["code"] += "-B"
            if name == "holiday_create":
                browser_payload["holiday_date"] = "1405/01/03"
            if name == "shift_break_create":
                browser_payload.update(sequence="2", starts_at="14:00", ends_at="14:30")
            steps = [
                {"submit": True, "afterPath": reverse(f"timekeeping:{name}")},
                {
                    "inspect": "!!document.querySelector('.erp-field-error')",
                    "description": "server errors remain visible",
                },
            ]
            if name == "calendar_create":
                steps.append(
                    {"toggleSelector": "main input[name=working_weekdays][value='6']"}
                )
            steps += [
                {"fill": browser_payload, "submit": True},
                {
                    "inspect": "!document.querySelector('main .erp-compact-form')",
                    "description": "valid calendar master submission returns to the workbench",
                },
            ]
            calendar_journeys.append(
                {
                    "name": f"{name}-journey",
                    "path": reverse(f"timekeeping:{name}"),
                    "width": 390,
                    "status": 200,
                    "steps": steps,
                }
            )
        self.browser(self.owner, calendar_journeys)
        self.login(self.denied)
        for name, _payload in records:
            self.assertEqual(
                self.client.get(reverse(f"timekeeping:{name}")).status_code, 403
            )

    def test_migrated_forms(self):
        self.make_fixture()
        org = self.organization
        unit = UnitOfMeasure.objects.create(
            organization=org,
            code="CF-U",
            name="واحد آزمون",
            symbol="آزمون",
            category="count",
        )
        category = MaterialCategory.objects.create(
            organization=org, code="CF-C", name="دسته آزمون"
        )
        material = Material.objects.create(
            organization=org,
            code="CF-M",
            name="مصالح آزمون",
            category=category,
            unit_of_measure=unit,
        )
        group = PlatformExpenseGroup.objects.create(
            code="cf-group", name="گروه آزمون هزینه"
        )
        expense_category = ExpenseCategory.objects.create(
            organization=org, code="cf-e", name="دسته هزینه آزمون", primary_group=group
        )
        site = ProjectSite.objects.create(
            organization=org, project=self.project, code="CF-S", name="کارگاه آزمون"
        )
        records = [
            (
                "unit",
                reverse("materials:unit_create"),
                reverse("materials:unit_list"),
                {
                    "code": "CF-U2",
                    "name": "واحد تازه",
                    "symbol": "آزمایشی",
                    "category": "count",
                    "decimal_places": "0",
                },
            ),
            (
                "material-category",
                reverse("materials:category_create"),
                reverse("materials:category_list"),
                {"code": "CF-C2", "name": "دسته تازه"},
            ),
            (
                "material",
                reverse("materials:material_create"),
                reverse("materials:material_list"),
                {
                    "code": "CF-M2",
                    "name": "مصالح تازه",
                    "category": category.pk,
                    "unit_of_measure": unit.pk,
                },
            ),
            (
                "expense-category",
                reverse("expenses:category_create"),
                reverse("expenses:category_list"),
                {"code": "cf-e2", "name": "دسته هزینه تازه", "primary_group": group.pk},
            ),
            (
                "party",
                reverse("parties:create"),
                reverse("parties:list"),
                {"party_kind": "company", "display_name": "طرف تجاری آزمایشی"},
            ),
            (
                "project",
                reverse("projects:create"),
                reverse("projects:list"),
                {
                    "code": "CF-P2",
                    "name": "پروژه تازه",
                    "status": "planning",
                    "estimated_budget": "0",
                    "actual_budget": "0",
                },
            ),
            (
                "site",
                reverse("projects:site_create", args=[self.project.pk]),
                reverse("projects:site_list", args=[self.project.pk]),
                {"code": "CF-S2", "name": "کارگاه تازه"},
            ),
            (
                "phase",
                reverse("projects:phase_create", args=[self.project.pk, site.pk]),
                reverse("projects:phase_list", args=[self.project.pk, site.pk]),
                {"code": "CF-PH", "name": "فاز تازه", "status": "planning"},
            ),
            (
                "equipment",
                reverse("equipment:create"),
                reverse("equipment:list"),
                {
                    "code": "CF-EQ",
                    "name": "تجهیز تازه",
                    "category": "آزمون",
                    "ownership_type": "owned",
                },
            ),
            (
                "team",
                reverse("workforce:work_team_create"),
                reverse("workforce:work_team_list"),
                {"code": "CF-TEAM", "name": "گروه کاری تازه"},
            ),
            (
                "material-category-edit",
                reverse("materials:category_detail", args=[category.pk]),
                reverse("materials:category_list"),
                {"code": category.code, "name": "دسته ویرایش شده"},
            ),
            (
                "material-edit",
                reverse("materials:material_detail", args=[material.pk]),
                reverse("materials:material_list"),
                {
                    "code": material.code,
                    "name": "مصالح ویرایش شده",
                    "category": category.pk,
                    "unit_of_measure": unit.pk,
                },
            ),
            (
                "expense-category-edit",
                reverse("expenses:category_detail", args=[expense_category.pk]),
                reverse("expenses:category_list"),
                {
                    "code": expense_category.code,
                    "name": "دسته هزینه ویرایش شده",
                    "primary_group": group.pk,
                },
            ),
        ]

        scenarios = []
        for name, url, cancel, _payload in records:
            for width in (1440, 390):
                scenarios.append(
                    {
                        "name": f"{name}-{width}",
                        "path": url,
                        "width": width,
                        "status": 200,
                        "screenshot": True,
                        "viewportScreenshot": True,
                        "noJsErrors": True,
                        "steps": [
                            {
                                "inspect": f"""(() => {{
                            const form = document.querySelector('main .erp-compact-form');
                            const footer = form.querySelector('footer');
                            return document.querySelectorAll('header .erp-list-context--header').length === 1
                                && document.querySelectorAll('[data-context-project]').length === 1
                                && getComputedStyle(footer).position === 'static'
                                && footer.querySelectorAll('button[type=submit]').length === 1
                                && footer.querySelector('a').getAttribute('href') === '{cancel}'
                                && getComputedStyle(form.querySelector('.erp-form-grid')).gridTemplateColumns.split(' ').length === (innerWidth < 640 ? 1 : 2);
                        }})()""",
                                "description": "compact RTL grid, one global context and one in-flow action area",
                            }
                        ],
                    }
                )
        _name, unit_url, unit_cancel, _payload = records[0]
        scenarios += [
            dict(
                scenarios[1],
                name="unit-errors-390",
                steps=[
                    {
                        "inspect": "document.querySelector('.erp-compact-form').noValidate = true",
                        "description": "exercise server validation",
                    },
                    {
                        "fill": {"code": "CF-RETAIN"},
                        "submit": True,
                        "afterPath": unit_url,
                    },
                    {
                        "inspect": "document.querySelector('#id_name').getAttribute('aria-describedby').includes('id_name-errors') && document.querySelector('#id_code').value === 'CF-RETAIN'",
                        "description": "the field error is associated and code is retained",
                    },
                ],
            ),
            dict(
                scenarios[1],
                name="unit-cancel-390",
                screenshot=False,
                steps=[
                    {
                        "clickSelector": "main .erp-compact-form footer a",
                        "afterPath": unit_cancel,
                    },
                ],
            ),
        ]
        self.browser(self.owner, scenarios)

        for name, url, cancel, payload in records:
            with self.subTest(form=name):
                invalid = self.client.post(
                    url, {**payload, "display_name" if name == "party" else "name": ""}
                )
                self.assertEqual(invalid.status_code, 400 if name == "party" else 200)
                field = "display_name" if name == "party" else "name"
                self.assertContains(
                    invalid, f'id="id_{field}-errors"', status_code=invalid.status_code
                )
                for key, value in payload.items():
                    if key != field:
                        self.assertEqual(
                            invalid.context["form"][key].value(), str(value)
                        )
                saved = self.client.post(url, payload)
                self.assertEqual(
                    saved.status_code, 302, getattr(saved, "context", None)
                )
                self.assertEqual(self.client.get(cancel).status_code, 200)

        journeys = []
        for name, url, cancel, payload in records:
            browser_payload = {key: str(value) for key, value in payload.items()}
            if "edit" not in name:
                for key in ("code", "symbol", "display_name"):
                    if key in browser_payload:
                        browser_payload[key] += "-B"
            field = "display_name" if name == "party" else "name"
            journeys.append(
                {
                    "name": f"{name}-journey",
                    "path": url,
                    "width": 390,
                    "status": 200,
                    "screenshot": True,
                    "noJsErrors": True,
                    "steps": [
                        {
                            "inspect": "document.querySelector('.erp-compact-form').noValidate = true",
                            "description": "exercise server validation",
                        },
                        {
                            "fill": {**browser_payload, field: ""},
                            "submit": True,
                            "afterPath": url,
                        },
                        {
                            "inspect": f"!!document.querySelector('#id_{field}-errors')",
                            "description": "the required-field error appears below the field",
                        },
                        {"fill": browser_payload, "submit": True},
                        {
                            "inspect": "!document.querySelector('main .erp-form-field--invalid')",
                            "description": "the corrected submission follows the existing success destination",
                        },
                    ],
                }
            )
        self.browser(self.owner, journeys)
        self.browser(
            self.owner,
            [
                {
                    "name": f"{name}-cancel",
                    "path": url,
                    "width": 390,
                    "status": 200,
                    "steps": [{"clickSelector": "main footer a", "afterPath": cancel}],
                }
                for name, url, cancel, _payload in records
            ],
        )

        self.login(self.denied)
        for name, url, _cancel, payload in records:
            with self.subTest(denied=name):
                self.assertEqual(self.client.post(url, payload).status_code, 403)

        role = self.reader_scope.membership.role_definition
        MembershipScopeGrant.objects.create(
            organization=org,
            membership=self.reader_scope.membership,
            scope_type="organization",
            reason="Synthetic Compact Form read-only fixture",
        )
        role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=(
                    "materials.view",
                    "material_categories.view",
                    "expense_categories.view",
                )
            )
        )
        self.login(self.reader)
        for _name, url, _cancel, _payload in records[-3:]:
            response = self.client.get(url)
            self.assertContains(response, "erp-compact-form")
            self.assertNotContains(response, 'type="submit"><svg class="erp-form-icon"')
            self.assertTrue(
                all(
                    field.disabled for field in response.context["form"].fields.values()
                )
            )

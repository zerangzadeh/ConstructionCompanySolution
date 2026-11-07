"""Equipment selector semantics and approved Maintenance Create presentation."""

from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from test_daily_report_references import DailyReferenceFixture

from apps.billing import test_mvp03_browser as browser_fixture
from apps.equipment.forms import EquipmentForm
from apps.equipment.models import Equipment, MaintenanceRecord


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class EquipmentSelectorRemediationTests(
    DailyReferenceFixture, StaticLiveServerTestCase
):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = Path("output/equipment-selector-remediation")

    def setup_equipment(self):
        self.setup_daily()
        self.equipment = Equipment.objects.create(
            organization=self.organization,
            code="SELECT-E",
            name="بیل مکانیکی آزمون",
            category="ماشین‌آلات سنگین",
            ownership_type="owned",
            created_by=self.owner,
            updated_by=self.owner,
        )
        Equipment.objects.create(
            organization=self.organization,
            code="SELECT-R",
            name="جرثقیل آزمون",
            category="تجهیزات بالابری",
            ownership_type="rented",
            created_by=self.owner,
            updated_by=self.owner,
        )
        Equipment.objects.create(
            organization=self.other_organization,
            code="SECRET-E",
            name="تجهیز شرکت دیگر",
            category="دسته محرمانه شرکت دیگر",
            ownership_type="owned",
        )

    def scenarios(self, name, path, **kwargs):
        return [
            dict(
                name=f"{name}-{width}",
                path=path,
                width=width,
                status=200,
                screenshot=True,
                viewportScreenshot=True,
                fullPageScreenshot=True,
                bottomScreenshot=True,
                noJsErrors=True,
                **kwargs,
            )
            for width in (1440, 1024, 390)
        ]

    def test_selectors_and_existing_filter_semantics(self):
        self.setup_equipment()
        path = reverse("equipment:list")
        self.browser(
            self.owner,
            self.scenarios(
                "equipment-selectors",
                path,
                steps=[
                    {
                        "inspect": "document.querySelector('select[name=ownership] option[value=\"\"]').textContent === 'نوع مالکیت' && document.querySelector('select[name=category]') && !document.querySelector('select[name=category]').innerText.includes('دسته محرمانه')",
                        "description": "clear ownership label and tenant-scoped category selector",
                    }
                ],
            ),
        )
        self.browser(
            self.owner,
            [
                dict(
                    self.scenarios("equipment-filter-journey", path)[2],
                    steps=[
                        {
                            "fill": {
                                "category": "ماشین‌آلات سنگین",
                                "ownership": "owned",
                            },
                            "formSelector": "#list-filter-bar",
                            "submit": True,
                            "afterPath": path,
                        },
                        {
                            "inspect": "document.querySelectorAll('main tbody tr').length === 1 && document.querySelectorAll('main .erp-list-chip').length === 2",
                            "description": "combined filters and removable chips",
                        },
                        {"clickSelector": "main .erp-list-clear", "afterPath": path},
                        {"history": "back", "afterPath": path},
                        {"reload": True, "afterPath": path},
                        {
                            "inspect": "document.querySelector('select[name=category]').value === 'ماشین‌آلات سنگین' && document.querySelectorAll('main tbody tr').length === 1",
                            "description": "Back and refresh retain category and ownership",
                        },
                        {"history": "forward", "afterPath": path},
                        {
                            "inspect": "!location.search.includes('category=') && document.querySelectorAll('main tbody tr').length === 2",
                            "description": "Forward restores cleared filters",
                        },
                    ],
                )
            ],
        )
        self.login(self.owner)
        response = self.client.get(
            path, {"category": "ماشین", "sort": "equipment", "direction": "desc"}
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertContains(response, 'value="ماشین" selected')
        self.assertNotContains(response, "دسته محرمانه")
        self.assertEqual(
            self.client.get(path, {"category": "بدون نتیجه"})
            .context["page_obj"]
            .paginator.count,
            0,
        )
        self.browser(
            self.owner,
            [
                dict(
                    self.scenarios("equipment-no-js", path)[0],
                    noJS=True,
                    steps=[
                        {
                            "fill": {"category": "تجهیزات بالابری"},
                            "formSelector": "#list-filter-bar",
                            "submit": True,
                            "afterPath": path,
                        }
                    ],
                    mustText=["جرثقیل آزمون"],
                )
            ],
        )

    def test_create_category_and_maintenance(self):
        self.setup_equipment()
        create = reverse("equipment:create")
        maintenance = reverse("equipment:maintenance_create")
        self.browser(
            self.owner,
            self.scenarios(
                "equipment-create-category",
                create,
                steps=[
                    {
                        "inspect": "(() => {const e=document.querySelector('[name=category]');return !!e.tomselect && !!e.list && e.list.options.length===2 && !e.list.innerText.includes('محرمانه') && e.maxLength===120;})()",
                        "description": "editable native selector preserves existing text limit and scoped suggestions",
                    },
                    {
                        "searchChoice": {
                            "name": "category",
                            "selector": "input[name=category]",
                            "query": "سنگین",
                            "value": "ماشین‌آلات سنگین",
                        }
                    },
                ],
            ),
        )
        for category in ("ماشین‌آلات سنگین", "دسته تازه آزمون"):
            form = EquipmentForm(
                {
                    "code": "CATEGORY",
                    "name": "نام آزمون",
                    "category": category,
                    "ownership_type": "owned",
                },
                organization=self.organization,
            )
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["category"], category)
        self.assertEqual(EquipmentForm().fields["category"].widget.categories, ())
        self.browser(
            self.owner,
            [
                dict(
                    self.scenarios("equipment-new-category-submit", create)[2],
                    steps=[
                        {
                            "searchChoice": {
                                "name": "category",
                                "selector": "input[name=category]",
                                "query": "دسته تازه مرورگر",
                                "value": "دسته تازه مرورگر",
                                "createNew": True,
                            }
                        },
                        {
                            "fill": {
                                "code": "SELECT-NEW",
                                "name": "تجهیز دسته جدید",
                                "ownership_type": "owned",
                            },
                            "submit": True,
                            "afterPrefix": "/equipment/",
                        },
                        {
                            "inspect": "!document.querySelector('main form input[name=code]') && document.querySelector('main').innerText.includes('دسته تازه مرورگر')",
                            "description": "new text category is saved through the existing equipment service",
                        },
                    ],
                )
            ],
        )
        self.assertEqual(
            Equipment.objects.get(code="SELECT-NEW").category, "دسته تازه مرورگر"
        )
        self.browser(
            self.owner,
            [
                dict(
                    self.scenarios("equipment-category-no-js", create)[0],
                    noJS=True,
                    steps=[
                        {
                            "inspect": "!!document.querySelector('input[name=category]').list && !document.querySelector('input[name=category]').tomselect",
                            "description": "native editable datalist survives without JavaScript",
                        }
                    ],
                )
            ],
        )
        self.browser(
            self.owner,
            self.scenarios(
                "maintenance-sectioned",
                maintenance,
                steps=[
                    {
                        "inspect": "document.querySelectorAll('main .erp-form-section').length===3 && document.querySelectorAll('main footer').length===1 && document.querySelectorAll('main form').length===1 && document.querySelectorAll('[data-context-project]').length===1 && getComputedStyle(document.querySelector('main footer')).position==='static'",
                        "description": "three logical sections, one global context and one in-flow action footer",
                    }
                ],
            ),
        )
        payload = {
            "equipment": str(self.equipment.pk),
            "record_number": "MAINT-SELECT",
            "maintenance_type": "preventive",
            "summary": "سرویس نمونه",
            "scheduled_date": "1405/08/14",
            "project": str(self.project.pk),
            "site": str(self.site.pk),
            "description": "شرح کار آزمون",
            "cost": "1200.00",
            "notes": "یادداشت آزمون",
        }
        self.browser(
            self.owner,
            [
                dict(
                    self.scenarios("maintenance-validation-submit", maintenance)[2],
                    steps=[
                        {
                            "inspect": "document.querySelector('main form').noValidate=true",
                            "description": "exercise server validation",
                        },
                        {
                            "fill": {**payload, "summary": ""},
                            "submit": True,
                            "afterPath": maintenance,
                        },
                        {
                            "inspect": "!!document.querySelector('#id_summary-errors') && document.querySelector('[name=record_number]').value==='MAINT-SELECT' && document.querySelectorAll('main .erp-form-section').length===3",
                            "description": "field error and values stay in their logical sections",
                        },
                        {
                            "fill": {"summary": "سرویس نمونه"},
                            "submit": True,
                            "afterPath": reverse(
                                "equipment:detail", args=[self.equipment.pk]
                            ),
                        },
                    ],
                )
            ],
        )
        record = MaintenanceRecord.objects.get(record_number="MAINT-SELECT")
        self.assertEqual(record.equipment_id, self.equipment.pk)
        self.assertEqual(record.project_id, self.project.pk)
        self.assertEqual(record.site_id, self.site.pk)
        self.assertEqual(record.description, payload["description"])
        self.browser(
            self.owner,
            [
                dict(
                    self.scenarios("maintenance-cancel", maintenance)[2],
                    steps=[
                        {
                            "clickSelector": "main footer a",
                            "afterPath": reverse("equipment:maintenance_list"),
                        }
                    ],
                )
            ],
        )
        self.login(self.owner)
        invalid = self.client.post(
            maintenance,
            {
                **payload,
                "record_number": "MAINT-DENIED",
                "project": str(self.hidden_project.pk),
                "site": str(self.site.pk),
            },
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertTrue(invalid.context["form"].errors)
        self.login(self.denied)
        self.assertEqual(self.client.get(maintenance).status_code, 403)
        self.assertEqual(self.client.get(create).status_code, 403)

    def test_category_retention_and_native_submission(self):
        self.setup_equipment()
        create = reverse("equipment:create")
        self.browser(
            self.owner,
            [
                dict(
                    self.scenarios("category-validation-retained", create)[2],
                    steps=[
                        {
                            "searchChoice": {
                                "name": "category",
                                "selector": "input[name=category]",
                            "query": "دسته, ثبت موقت",
                            "value": "دسته, ثبت موقت",
                                "createNew": True,
                            }
                        },
                        {
                            "inspect": "document.querySelector('main form').noValidate=true",
                            "description": "exercise existing server validation",
                        },
                        {
                            "fill": {"code": "SELECT-ERROR", "ownership_type": "owned"},
                            "submit": True,
                            "afterPath": create,
                        },
                        {
                        "inspect": "!!document.querySelector('#id_name-errors') && document.querySelector('[name=category]').tomselect.getValue()==='دسته, ثبت موقت'",
                            "description": "editable category survives a validation error without changing validation",
                        },
                    ],
                )
            ],
        )
        self.browser(
            self.owner,
            [
                dict(
                    self.scenarios("category-native-save", create)[2],
                    noJS=True,
                    steps=[
                        {
                            "fill": {
                                "code": "SELECT-NATIVE",
                                "name": "تجهیز بدون جاوااسکریپت",
                                "category": "دسته تازه بومی",
                                "ownership_type": "owned",
                            },
                            "submit": True,
                            "afterPrefix": "/equipment/",
                        },
                    ],
                )
            ],
        )
        self.assertEqual(
            Equipment.objects.get(code="SELECT-NATIVE").category, "دسته تازه بومی"
        )

"""Warehouse Create compact form evidence in real Chrome."""

import os
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from test_warehouse_reference_list import WarehouseListFixture

from apps.billing import test_mvp03_browser as browser_fixture
from apps.inventory.models import Warehouse
from apps.organizations.models import BusinessPermission
from apps.projects.models import ProjectSite


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class WarehouseCompactFormBrowserTests(WarehouseListFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown

    def test_compact_footer_layout(self):
        self.make_fixture()
        self.browser_evidence_directory = Path("output/warehouse-compact-footer")
        create_url = reverse("inventory:warehouse_create")
        geometry = """(() => {
            const form = document.querySelector('main .erp-compact-form');
            const section = form.querySelector('.erp-form-section');
            const footer = form.querySelector('.erp-form-footer');
            const location = form.elements.location;
            return {
                footerCount: document.querySelectorAll('.erp-form-footer').length,
                submitCount: form.querySelectorAll('button[type=submit]').length,
                cancelCount: footer.querySelectorAll('a[href]').length,
                footerPosition: getComputedStyle(footer).position,
                contextCount: document.querySelectorAll('header .erp-list-context--header').length,
                viewportHeight: innerHeight,
                documentHeight: document.documentElement.scrollHeight,
                mainBottom: form.closest('main').getBoundingClientRect().bottom + scrollY,
                formBottom: form.getBoundingClientRect().bottom + scrollY,
                footerBottom: footer.getBoundingClientRect().bottom + scrollY,
                sectionBottom: section.getBoundingClientRect().bottom + scrollY,
                footerTop: footer.getBoundingClientRect().top + scrollY,
                locationBottom: location.getBoundingClientRect().bottom + scrollY,
            };
        })()"""
        layout = {
            "inspect": f"""(() => {{
                const g = {geometry};
                return g.footerCount === 1 && g.submitCount === 1 && g.cancelCount === 1
                    && g.footerPosition === 'static' && g.contextCount === 1
                    && Math.abs(g.footerTop - g.sectionBottom) <= 1
                    && Math.abs(g.formBottom - g.footerBottom - 1) <= 1
                    && g.footerTop - g.locationBottom <= 20
                    && Math.abs(g.documentHeight - Math.max(g.viewportHeight, g.mainBottom)) <= 1;
            }})()""",
            "description": "the single in-flow footer follows the fields and the document has no extra content height",
        }
        bottom = {
            "inspect": """(() => {
                window.scrollTo({top: document.documentElement.scrollHeight, behavior: 'instant'});
                const footer = document.querySelector('.erp-compact-form .erp-form-footer');
                return Math.abs(scrollY - Math.max(0, document.documentElement.scrollHeight - innerHeight)) <= 1
                    && Array.from(footer.querySelectorAll('button, a')).every(action => {
                        const r = action.getBoundingClientRect();
                        return r.top >= 0 && r.bottom <= innerHeight
                            && action.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2));
                    });
            })()""",
            "description": "both footer actions are visible and reachable at the bottom",
        }
        common = {
            "path": create_url,
            "status": 200,
            "screenshot": True,
            "viewportScreenshot": True,
            "fullPageScreenshot": True,
            "bottomScreenshot": True,
            "noJsErrors": True,
            "measure": geometry,
        }
        scenarios = [
            dict(common, name=f"create-{width}", width=width, steps=[layout, bottom])
            for width in (1440, 1024, 390)
        ]
        scenarios += [
            dict(
                common,
                name="validation-390",
                width=390,
                steps=[
                    {"submit": True, "afterPath": create_url},
                    {
                        "inspect": "document.querySelector('#id_code-errors') && document.querySelector('#id_name-errors')",
                        "description": "required field errors render before checking the footer geometry",
                    },
                    layout,
                    bottom,
                ],
            ),
            dict(
                common,
                name="short-mobile-viewport",
                width=390,
                height=480,
                mobile=True,
                steps=[
                    {
                        "searchChoice": {
                            "name": "project",
                            "query": "نمونه",
                            "value": str(self.project.pk),
                            "keyboard": True,
                        },
                    },
                    {
                        "toggleSelector": "main textarea[name=location]",
                        "inspect": "document.activeElement === document.querySelector('main textarea[name=location]') && document.activeElement.getBoundingClientRect().bottom <= innerHeight",
                        "description": "the location field can receive focus in a reduced mobile viewport",
                    },
                    layout,
                    bottom,
                ],
            ),
            {
                "name": "contract-footer-regression",
                "path": reverse("contracts:create"),
                "status": 200,
                "noJsErrors": True,
                "steps": [
                    {
                        "inspect": "document.querySelectorAll('main .erp-form-footer').length === 1 && getComputedStyle(document.querySelector('main .erp-form-footer')).position === 'sticky'",
                        "description": "Contract Create retains its single sticky footer",
                    }
                ],
            },
        ]
        self.browser(self.owner, scenarios)

    def test_working_context_header(self):
        self.make_fixture()
        phase = os.environ.get("BONIRA_WAREHOUSE_CONTEXT_PHASE", "after")
        self.browser_evidence_directory = (
            Path("output/warehouse-create-context") / phase
        )
        create_url = reverse("inventory:warehouse_create")
        list_url = reverse("inventory:warehouse_list")
        company_url = reverse("organizations:select")
        common = {
            "status": 200,
            "screenshot": True,
            "viewportScreenshot": True,
            "noJsErrors": True,
        }
        header = ".erp-list-context--header"
        header_check = {
            "inspect": f"""(() => {{
                const disclosure = document.querySelector('header {header}');
                const projects = document.querySelectorAll('[data-context-project]');
                const sites = document.querySelectorAll('[data-context-site]');
                return disclosure && !disclosure.open && projects.length === 1 && sites.length === 1
                    && disclosure.contains(projects[0]) && disclosure.contains(sites[0])
                    && disclosure.parentElement.querySelectorAll(':scope > a[href="{company_url}"]').length === 1;
            }})()""",
            "description": "exactly one global project and site selector in the closed shared header",
        }
        screenshots = [
            dict(common, name=f"{page}-{width}", path=path, width=width)
            for page, path in (("list", list_url), ("create", create_url))
            for width in (1440, 1024, 390)
        ]
        if phase == "before":
            self.browser(self.owner, screenshots)
            return

        site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="B1-SITE",
            name="کارگاه مرکزی نمونه",
        )
        for scenario in screenshots:
            scenario["steps"] = [header_check]
        panel_check = {
            "inspect": f"""(() => {{
                const panel = document.querySelector('{header}[open] .erp-list-context__panel');
                const box = panel.getBoundingClientRect();
                return box.left >= 0 && box.right <= innerWidth
                    && panel.textContent.includes('{self.organization.name}');
            }})()""",
            "description": "shared disclosure reveals the company and fits the viewport",
        }
        for width in (1440, 1024, 390):
            screenshots.append(
                dict(
                    common,
                    name=f"open-{width}",
                    path=create_url,
                    width=width,
                    steps=[
                        {"toggleSelector": f"{header} summary"},
                        panel_check,
                    ],
                )
            )
        self.browser(
            self.owner,
            screenshots
            + [
                dict(
                    common,
                    name="context-switch",
                    path=create_url,
                    width=390,
                    steps=[
                        {"toggleSelector": f"{header} summary"},
                        {
                            "formSelector": f"{header} form",
                            "fill": {"project_id": str(self.project.pk)},
                            "submit": True,
                            "afterPath": create_url,
                        },
                        {"toggleSelector": f"{header} summary"},
                        {
                            "formSelector": f"{header} form",
                            "fill": {"site_id": str(site.pk)},
                            "submit": True,
                            "afterPath": create_url,
                        },
                        {
                            "inspect": f"document.querySelector('[data-context-project]').value === '{self.project.pk}' && document.querySelector('[data-context-site]').value === '{site.pk}' && document.querySelector('main select[name=project]').value === ''",
                            "description": "global project and site persist without populating the warehouse field",
                        },
                        {
                            "searchChoice": {
                                "name": "project",
                                "query": "خارج",
                                "value": str(self.hidden_project.pk),
                            }
                        },
                        {
                            "inspect": f"document.querySelector('[data-context-project]').value === '{self.project.pk}' && document.querySelector('[data-context-site]').value === '{site.pk}'",
                            "description": "changing the warehouse project leaves global context untouched",
                        },
                    ],
                )
            ],
        )

        self.reader_scope.membership.role_definition.permissions.add(
            BusinessPermission.objects.get(code="warehouses.create")
        )
        self.browser(
            self.reader,
            [
                dict(
                    common,
                    name="scoped-context",
                    path=create_url,
                    steps=[
                        header_check,
                        {"toggleSelector": f"{header} summary"},
                        {
                            "inspect": f"Array.from(document.querySelector('[data-context-project]').options).map(option => option.value).filter(Boolean).join(',') === '{self.project.pk}'",
                            "description": "project-scoped creator cannot see the other project's global option",
                        },
                    ],
                )
            ],
        )

    def test_create_form_journey(self):
        self.make_fixture()
        create_url = reverse("inventory:warehouse_create")
        list_url = reverse("inventory:warehouse_list")
        phase = os.environ.get("BONIRA_COMPACT_FORM_PHASE", "after")
        self.browser_evidence_directory = Path("output/compact-form-reference") / phase
        common = {
            "path": create_url,
            "status": 200,
            "screenshot": True,
            "viewportScreenshot": True,
            "noJsErrors": True,
        }
        views = [
            dict(common, name=f"create-{width}", width=width)
            for width in (1440, 1024, 390)
        ]
        if phase == "before":
            self.browser(self.owner, views)
            return

        def check(expression, description):
            return {"inspect": expression, "description": description}

        layout = """(() => {
            const form = document.querySelector('main form.erp-compact-form');
            const grid = form.querySelector('.erp-form-grid');
            const footer = form.querySelector('.erp-form-footer');
            const fields = [...grid.querySelectorAll('.erp-form-field')];
            const code = form.elements.code, name = form.elements.name;
            const project = form.elements.project, location = form.elements.location;
            return document.documentElement.dir === 'rtl' && fields.length === 4
                && code.required && name.required && !project.required && !location.required
                && location.tagName === 'TEXTAREA' && project.tomselect && project.value === ''
                && form.querySelectorAll('button[type=submit]').length === 1
                && getComputedStyle(grid).gridTemplateColumns.split(' ').length === (innerWidth < 640 ? 1 : 2)
                && getComputedStyle(footer).flexDirection === (innerWidth < 640 ? 'column' : 'row');
        })()"""
        popup = """(() => {
            const widget = document.querySelector('main select[name=project]').tomselect;
            const popup = widget.dropdown.getBoundingClientRect();
            const control = widget.control.getBoundingClientRect();
            return widget.isOpen && popup.left >= 0 && popup.right <= innerWidth
                && Math.abs(popup.top - control.bottom) <= 12 && popup.bottom <= innerHeight;
        })()"""
        scenarios = []
        for view in views:
            view["steps"] = [check(layout, "RTL field grid and bottom actions")]
            scenarios.extend(
                [
                    view,
                    dict(
                        view,
                        name=f"project-menu-{view['width']}",
                        preserveScrollScreenshot=True,
                        steps=[
                            {"openChoice": "project"},
                            check(
                                popup,
                                "project dropdown is anchored and stays inside the viewport",
                            ),
                        ],
                    ),
                ]
            )

        required_error = """(() => {
            const field = document.querySelector('#id_name');
            const error = document.querySelector('#id_name-errors');
            return field.getAttribute('aria-invalid') === 'true' && error?.textContent.trim()
                && field.getAttribute('aria-describedby').includes(error.id)
                && error.closest('.erp-form-field') === field.closest('.erp-form-field');
        })()"""
        select_project = {
            "searchChoice": {
                "name": "project",
                "query": "نمونه",
                "value": str(self.project.pk),
            }
        }
        retained = f"""(() => {{
            const fields = document.querySelector('main form.erp-compact-form').elements;
            return fields.code.value === 'COMPACT-01' && fields.location.value === 'سالن جنوبی'
                && fields.project.value === '{self.project.pk}';
        }})()"""
        scenarios += [
            dict(
                common,
                name="required-error-390",
                width=390,
                steps=[
                    {
                        "searchChoice": dict(
                            select_project["searchChoice"], keyboard=True
                        )
                    },
                    {
                        "fill": {"code": "COMPACT-01", "location": "سالن جنوبی"},
                        "submit": True,
                        "afterPath": create_url,
                    },
                    check(
                        required_error,
                        "server required error is associated and appears below the field",
                    ),
                    check(
                        retained,
                        "bound code, location and authorized project survive redisplay",
                    ),
                ],
            ),
            dict(
                common,
                name="duplicate-error",
                steps=[
                    select_project,
                    {
                        "fill": {
                            "code": self.warehouses[0].code,
                            "name": "انبار آزمایشی",
                            "location": "سالن جنوبی",
                        },
                        "submit": True,
                        "afterPath": create_url,
                    },
                    check(
                        "document.querySelector('main form [role=alert]').textContent.includes('تکراری') && document.querySelector('#id_name').value==='انبار آزمایشی'",
                        "duplicate code surfaces the existing non-field error and retains values",
                    ),
                ],
            ),
            dict(
                common,
                name="cancel-390",
                width=390,
                steps=[
                    {"clickSelector": "main .erp-form-footer a", "afterPath": list_url},
                ],
            ),
            dict(
                common,
                name="native-fallback",
                noJS=True,
                steps=[
                    check(
                        f"Array.from(document.querySelector('main select[name=project]').options).some(option => option.value === '{self.project.pk}') && document.querySelector('main select[name=project]').value === ''",
                        "the authorized projects remain available without JavaScript",
                    ),
                ],
            ),
            dict(
                common,
                name="saved",
                steps=[
                    select_project,
                    {
                        "fill": {
                            "code": "compact-01",
                            "name": "انبار آزمایشی",
                            "location": "سالن جنوبی",
                        },
                        "submit": True,
                        "afterPrefix": list_url,
                    },
                    check(
                        f"location.pathname !== '{create_url}' && document.querySelector('main').innerText.includes('انبار آزمایشی')",
                        "valid POST follows the existing detail redirect",
                    ),
                ],
            ),
        ]
        self.browser(self.owner, scenarios)
        warehouse = Warehouse.objects.get(
            organization=self.organization, code="COMPACT-01"
        )
        self.assertEqual(warehouse.project, self.project)
        self.assertEqual(warehouse.location, "سالن جنوبی")

        self.reader_scope.membership.role_definition.permissions.add(
            BusinessPermission.objects.get(code="warehouses.create")
        )
        self.browser(
            self.reader,
            [
                dict(
                    common,
                    name="scoped-projects",
                    steps=[
                        {"openChoice": "project"},
                        check(
                            f"Object.keys(document.querySelector('main select[name=project]').tomselect.options).filter(Boolean).join(',') === '{self.project.pk}'",
                            "project-scoped creator sees only the authorized project",
                        ),
                    ],
                )
            ],
        )
        self.browser(
            self.denied,
            [
                {
                    "name": "create-denied",
                    "path": create_url,
                    "status": 403,
                    "plainBusinessDenial": True,
                }
            ],
        )

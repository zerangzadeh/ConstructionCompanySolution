"""Real scoped queues, shared filters and browser actions on disposable data."""

from datetime import timedelta
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.billing import test_mvp03_browser as browser_fixture
from apps.organizations.models import BusinessPermission, BusinessPermissionCode
from apps.organizations.services import set_active_organization
from apps.procurement.services import (
    add_purchase_request_item,
    create_purchase_request,
    submit_purchase_request,
)
from apps.procurement.tests import ProcurementFixtureMixin
from apps.workflows import test_workbench as workbench_fixture
from apps.workflows.models import WorkItem, WorkItemStatus


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class OperationalInboxBrowserTests(ProcurementFixtureMixin, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    _item = workbench_fixture.WorkbenchTests._item
    browser_evidence_directory = Path("output/operational-workspace/inbox")

    def login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        set_active_organization(session, self.organization)
        session.save()

    def _submitted_request(self, number):
        from decimal import Decimal

        record = create_purchase_request(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            request_number=number,
            title="تأیید درخواست خرید مصالح پروژه",
        )
        add_purchase_request_item(
            organization=self.organization,
            actor=self.owner,
            purchase_request=record,
            material=self.material,
            quantity=Decimal(1),
        )
        submit_purchase_request(
            organization=self.organization,
            actor=self.owner,
            purchase_request=record,
        )
        return record

    def test_shared_project_context_header(self):
        from apps.organizations.catalog_bootstrap import (
            synchronize_authorization_catalog,
        )
        from apps.projects.models import Project

        synchronize_authorization_catalog(using="default")
        context_project = Project.objects.create(
            organization=self.organization, code="CONTEXT", name="پروژه زمینه کاری"
        )
        record = self._submitted_request("CTX-001")
        WorkItem.objects.filter(pk=self._item(record).pk).update(priority=10)
        self.browser_evidence_directory = Path(
            "output/operational-workspace/context-alignment"
        )
        inbox = reverse("workflows:workbench")
        path = inbox + "?priority=low"
        common = {
            "status": 200,
            "screenshot": True,
            "viewportScreenshot": True,
            "noJsErrors": True,
            "noHttpErrors": True,
        }
        geometry = (
            "document.documentElement.scrollWidth<=innerWidth+1 && "
            "document.querySelectorAll('header .erp-list-context--header').length===1 && "
            "document.querySelectorAll('form[action$=\"/context/\"]').length===1 && "
            "document.querySelector('header .erp-list-context--fit-tablet')"
        )
        panel_fits = (
            "(() => {const p=document.querySelector('.erp-list-context__panel').getBoundingClientRect(); "
            "return p.width>0 && p.left>=0 && p.right<=innerWidth && p.top>=0 && p.bottom<=innerHeight;})()"
        )
        scenarios = []
        for width in (1440, 1024, 390):
            scenarios.append(
                dict(
                    common,
                    name=f"context-closed-{width}",
                    path=path,
                    width=width,
                    steps=[
                        {
                            "inspect": geometry,
                            "description": "one shared header context selector and no old context strip",
                        }
                    ],
                )
            )
            scenarios.append(
                dict(
                    common,
                    name=f"context-open-{width}",
                    path=path,
                    width=width,
                    steps=[
                        {"toggleSelector": "header .erp-list-context > summary"},
                        {
                            "inspect": panel_fits,
                            "description": "the same form context panel fits desktop/tablet/mobile",
                        },
                    ],
                )
            )
        scenarios.append(
            dict(
                common,
                name="context-select-clear",
                path=path,
                width=390,
                steps=[
                    {"toggleSelector": "header .erp-list-context > summary"},
                    {
                        "fill": {"project_id": str(context_project.pk)},
                        "formSelector": "header .erp-list-context form",
                        "submit": True,
                        "afterPath": inbox,
                    },
                    {
                        "inspect": "document.querySelector('header .erp-list-context__value').innerText.includes('پروژه زمینه کاری') && new URLSearchParams(location.search).get('priority')==='low' && document.querySelectorAll('.erp-workspace-queue tbody tr').length===1",
                        "description": "context selection preserves URL filters and the authoritative cross-project queue",
                    },
                    {"toggleSelector": "header .erp-list-context > summary"},
                    {
                        "fill": {"project_id": ""},
                        "formSelector": "header .erp-list-context form",
                        "submit": True,
                        "afterPath": inbox,
                    },
                    {
                        "inspect": "document.querySelector('header .erp-list-context__value').innerText.includes('همه پروژه‌های در دسترس') && new URLSearchParams(location.search).get('priority')==='low' && document.querySelectorAll('.erp-workspace-queue tbody tr').length===1",
                        "description": "clearing global context retains the queue and independent filter",
                    },
                ],
            )
        )
        self.browser(self.owner, scenarios)
        self.login(self.owner)
        forbidden = self.client.post(
            reverse("organizations:update_context"),
            {
                "project_id": str(self.other_project.pk),
                "next": path,
            },
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_inbox_render_filters_actions_and_navigation(self):
        from apps.organizations.catalog_bootstrap import (
            synchronize_authorization_catalog,
        )

        synchronize_authorization_catalog(using="default")
        self.organization.name = "شرکت نمونه فضای عملیات"
        self.organization.save(update_fields=["name"])
        self.project.name = "پروژه نمونه سازه"
        self.project.save(update_fields=["name"])
        self.owner.first_name = "کاربر"
        self.owner.last_name = "نمونه"
        self.owner.save(update_fields=["first_name", "last_name"])
        first = self._submitted_request("WS-001")
        item = self._item(first)
        WorkItem.objects.filter(pk=item.pk).update(
            due_at=timezone.now() - timedelta(hours=2), priority=65
        )
        second = self._submitted_request("WS-002")
        second_item = self._item(second)
        WorkItem.objects.filter(pk=second_item.pk).update(priority=10)
        inbox = reverse("workflows:workbench")
        common = {
            "status": 200,
            "screenshot": True,
            "fullPageScreenshot": True,
            "bottomScreenshot": True,
            "noJsErrors": True,
            "noHttpErrors": True,
        }
        geometry = "document.documentElement.scrollWidth<=innerWidth+1 && getComputedStyle(document.querySelector('main')).direction==='rtl' && document.querySelectorAll('main h1').length===1"
        self.browser(
            self.owner,
            [
                dict(
                    common,
                    name=f"inbox-{width}",
                    path=inbox,
                    width=width,
                    steps=[
                        {
                            "inspect": geometry,
                            "description": "RTL, one heading, no document overflow",
                        }
                    ],
                )
                for width in (1440, 1024, 390)
            ],
        )
        self.browser(
            self.owner,
            [
                dict(
                    common,
                    name="inbox-filter-history",
                    path=inbox,
                    width=390,
                    steps=[
                        {"toggleSelector": "[data-more-toggle]"},
                        {
                            "fill": {"priority": "high"},
                            "formSelector": "#list-filter-bar",
                            "submit": True,
                            "afterPath": inbox,
                        },
                        {
                            "inspect": "document.querySelectorAll('.erp-workspace-queue tbody tr').length===1 && document.querySelector('[name=priority]').value==='high' && document.querySelector('.erp-list-chip').innerText.includes('زیاد')",
                            "description": "server filtering and visible active chip",
                        },
                        {"clickSelector": ".erp-list-clear", "afterPath": inbox},
                        {
                            "inspect": "document.querySelectorAll('.erp-workspace-queue tbody tr').length===2",
                            "description": "clear restores authorized queue",
                        },
                        {"history": "back", "afterPath": inbox},
                        {
                            "inspect": "document.querySelector('[name=priority]').value==='high' && document.querySelectorAll('.erp-workspace-queue tbody tr').length===1",
                            "description": "Back restores URL and filter state",
                        },
                        {"reload": True, "afterPath": inbox},
                    ],
                ),
                dict(
                    common,
                    name="inbox-empty",
                    path=inbox + "?due=upcoming",
                    width=390,
                    mustText=["کاری در این نما وجود ندارد"],
                    steps=[
                        {"inspect": geometry, "description": "empty state RTL geometry"}
                    ],
                ),
                dict(
                    common,
                    name="inbox-source-navigation",
                    path=inbox,
                    width=1024,
                    steps=[
                        {
                            "clickSelector": f"#work-item-{item.pk} td:first-child a",
                            "afterPath": reverse(
                                "procurement:request_detail", args=[first.pk]
                            ),
                        },
                        {"history": "back", "afterPath": inbox},
                    ],
                ),
                dict(
                    common,
                    name="inbox-no-javascript",
                    path=inbox,
                    width=1024,
                    noJS=True,
                    steps=[
                        {"toggleSelector": "[data-more-filters] summary"},
                        {
                            "fill": {"priority": "low"},
                            "formSelector": "#list-filter-bar",
                            "submit": True,
                            "afterPath": inbox,
                        },
                        {
                            "inspect": "document.querySelectorAll('.erp-workspace-queue tbody tr').length===1 && document.querySelector('[name=priority]').value==='low'",
                            "description": "plain GET filtering works without application JavaScript",
                        },
                    ],
                ),
                dict(
                    common,
                    name="inbox-claim-release",
                    path=inbox,
                    width=390,
                    steps=[
                        {
                            "toggleSelector": f"#work-item-{item.pk} .erp-list-row-menu > summary"
                        },
                        {
                            "clickSelector": f"#work-item-{item.pk} form[action$='/claim/'] button",
                            "afterPath": inbox,
                        },
                        {
                            "inspect": f"!!document.querySelector('#work-item-{item.pk} form[action$=\"/release/\"]')",
                            "description": "claim confirmed by server",
                        },
                        {
                            "toggleSelector": f"#work-item-{item.pk} .erp-list-row-menu > summary"
                        },
                        {
                            "clickSelector": f"#work-item-{item.pk} form[action$='/release/'] button",
                            "afterPath": inbox,
                        },
                        {
                            "inspect": f"!!document.querySelector('#work-item-{item.pk} form[action$=\"/claim/\"]')",
                            "description": "release confirmed by server",
                        },
                    ],
                ),
            ],
        )
        item.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.OPEN)
        viewer_membership = self.organization.memberships.get(user=self.viewer)
        item.candidates.create(
            organization=self.organization,
            membership=viewer_membership,
            routing_basis=[{"resolver": "explicit_membership"}],
        )
        self.browser(
            self.viewer,
            [
                dict(
                    common,
                    name="inbox-read-only",
                    path=inbox,
                    width=390,
                    steps=[
                        {
                            "inspect": "document.querySelectorAll('.erp-workspace-queue tbody tr').length===1 && !document.querySelector('.erp-workspace-queue form')",
                            "description": "candidate read permission does not grant mutations",
                        }
                    ],
                )
            ],
        )
        viewer_membership.role_definition.permissions.remove(
            BusinessPermission.objects.get(code=BusinessPermissionCode.WORK_ITEMS_VIEW)
        )
        self.browser(
            self.viewer,
            [
                {
                    "name": "inbox-denied",
                    "path": inbox,
                    "width": 390,
                    "status": 403,
                    "screenshot": True,
                    "plainBusinessDenial": True,
                }
            ],
        )
        self.browser(
            self.owner,
            [
                dict(
                    common,
                    name="inbox-complete-action",
                    path=inbox,
                    width=390,
                    steps=[
                        {
                            "toggleSelector": f"#work-item-{item.pk} .erp-list-row-menu > summary"
                        },
                        {
                            "clickSelector": f"#work-item-{item.pk} form[action$='/claim/'] button",
                            "afterPath": inbox,
                        },
                        {
                            "toggleSelector": f"#work-item-{item.pk} .erp-list-row-menu > summary"
                        },
                        {
                            "clickSelector": f"#work-item-{item.pk} form[action$='/action/']:has(input[value='approved']) button",
                            "afterPath": inbox,
                        },
                        {
                            "inspect": f"!document.querySelector('#work-item-{item.pk}')",
                            "description": "completed item leaves authoritative queue after server confirmation",
                        },
                    ],
                )
            ],
        )
        first.refresh_from_db()
        self.assertEqual(first.status, "approved")

    def test_populated_inbox_reference_density(self):
        from apps.organizations.catalog_bootstrap import (
            synchronize_authorization_catalog,
        )

        synchronize_authorization_catalog(using="default")
        self.organization.name = "شرکت نمونه فضای عملیات"
        self.organization.save(update_fields=["name"])
        self.owner.first_name = "کاربر"
        self.owner.last_name = "نمونه"
        self.owner.save(update_fields=["first_name", "last_name"])
        for index in range(21):
            self._submitted_request(f"DENSE-{index + 1:03}")
        self.browser_evidence_directory = Path(
            "output/operational-workspace/reference-alignment"
        )
        inbox = reverse("workflows:workbench")
        common = {
            "status": 200,
            "screenshot": True,
            "viewportScreenshot": True,
            "fullPageScreenshot": True,
            "noJsErrors": True,
            "noHttpErrors": True,
        }
        scenarios = []
        for width in (1440, 1024, 390):
            density = (
                "document.querySelectorAll('.erp-workspace-queue tbody tr').length===21 && "
                "document.documentElement.scrollWidth<=innerWidth+1 && "
                "[...document.querySelectorAll('.erp-list-row-menu')].every(m=>!m.open)"
            )
            if width >= 1024:
                density += " && document.querySelector('.erp-workspace-queue tbody tr').getBoundingClientRect().height<=60 && document.querySelector('.erp-list-filters__top').getBoundingClientRect().height<=48"
            scenarios.append(
                dict(
                    common,
                    name=f"reference-density-{width}",
                    path=inbox,
                    width=width,
                    steps=[
                        {
                            "inspect": density,
                            "description": "21 real queue records, compact rows and one-line filters at desktop/tablet",
                        }
                    ],
                )
            )
        self.browser(
            self.owner,
            scenarios
            + [
                dict(
                    common,
                    name="reference-action-menu",
                    path=inbox,
                    width=1024,
                    steps=[
                        {
                            "toggleSelector": ".erp-workspace-queue .erp-list-row-menu > summary"
                        },
                        {
                            "inspect": "(() => {const menu=document.querySelector('.erp-list-row-menu[open]'); const r=menu.querySelector('.erp-list-row-menu__items').getBoundingClientRect(); return r.left>=0 && r.right<=innerWidth && r.top>=0 && r.bottom<=innerHeight && !!menu.querySelector('form[action$=\"/claim/\"]');})()",
                            "description": "scoped action menu fits viewport and retains real claim form",
                        },
                    ],
                )
            ],
        )

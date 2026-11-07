"""Real rendered evidence for the MVP Record Detail rollout."""

import os
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from test_warehouse_reference_list import WarehouseListFixture

from apps.billing import test_mvp03_browser as browser_fixture
from apps.expenses.models import Expense, ExpenseStatus
from apps.organizations.catalog_bootstrap import synchronize_authorization_catalog
from apps.organizations.models import BusinessPermission, OrganizationSettings


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class RecordDetailBrowserTests(WarehouseListFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = Path("output/detail-page-rollout")

    def detail_fixture(self):
        synchronize_authorization_catalog(using="default")
        self.make_fixture()
        OrganizationSettings.objects.get_or_create(
            organization=self.organization, defaults={"timezone": "Asia/Tehran"}
        )
        self.expenses = {}
        for state in ("draft", "recorded", "submitted", "returned", "approved", "void"):
            self.expenses[state] = Expense.objects.create(
                organization=self.organization,
                project=self.project,
                description=f"هزینه نمونه - {ExpenseStatus(state).label}",
                category="materials",
                amount=Decimal(85000000),
                incurred_on=date(2026, 11, 5),
                status=state,
                source_reference=f"EXP-DETAIL-{state}",
                source_fingerprint=f"fixture-{state}",
                created_by=self.owner,
                updated_by=self.owner,
                submitted_at=timezone.now()
                if state in ("submitted", "approved", "returned")
                else None,
                submitted_by=self.owner
                if state in ("submitted", "approved", "returned")
                else None,
                approved_at=timezone.now() if state == "approved" else None,
                approved_by=self.reader if state == "approved" else None,
                return_reason="اصلاح مرجع رسید" if state == "returned" else "",
                void_reason="ثبت تکراری" if state == "void" else "",
                voided_at=timezone.now() if state == "void" else None,
                voided_by=self.owner if state == "void" else None,
            )

    def test_expense_pilot(self):
        self.detail_fixture()
        before = os.environ.get("BONIRA_DETAIL_BEFORE") == "1"
        self.browser_evidence_directory /= "before" if before else "expense"
        common = {
            "status": 200,
            "screenshot": True,
            "viewportScreenshot": True,
            "fullPageScreenshot": True,
            "noJsErrors": True,
            "bottomScreenshot": True,
        }
        self.browser(
            self.owner,
            [
                dict(
                    common,
                    name=f"expense-{state}-{width}",
                    path=reverse("expenses:detail", args=[expense.pk]),
                    width=width,
                    steps=[]
                    if before
                    else [
                        {
                            "inspect": "document.querySelectorAll('.erp-record-summary__item').length === 4 && !document.querySelector('main form[action$=\"/approve/\"]') && (!['approved','void'].includes("
                            + repr(state)
                            + ") || !document.querySelector('main form[action$=\"/void/\"]'))",
                            "description": "real summary, maker separation and terminal-state action visibility",
                        }
                    ],
                )
                for state, expense in self.expenses.items()
                for width in ((1440,) if before else (1440, 1024, 390))
            ],
        )
        if before:
            return
        self.browser(
            self.owner,
            [
                dict(
                    common,
                    name="expense-actions-navigation",
                    width=390,
                    path=reverse(
                        "expenses:detail", args=[self.expenses["recorded"].pk]
                    ),
                    steps=[
                        {
                            "inspect": "[...document.querySelectorAll('main [id]')].map(e=>e.id).length === new Set([...document.querySelectorAll('main [id]')].map(e=>e.id)).size && !document.querySelector('main form[action$=\"/approve/\"]')",
                            "description": "unique field IDs and maker separation",
                        },
                        {
                            "toggleSelector": "a[href='#expense-actions']",
                            "inspect": "location.hash === '#expense-actions'",
                            "description": "real section navigation",
                        },
                        {"pressTab": True},
                        {
                            "inspect": "document.activeElement.id === 'expense-void-reason'",
                            "description": "keyboard reaches labeled reason field",
                        },
                        {
                            "fill": {"reason": "ابطال نمونه مرورگر"},
                            "formSelector": "main form[action$='/void/']",
                            "submit": True,
                            "afterPath": reverse("expenses:list"),
                        },
                        {
                            "history": "back",
                            "afterPath": reverse(
                                "expenses:detail", args=[self.expenses["recorded"].pk]
                            ),
                        },
                        {
                            "reload": True,
                            "afterPath": reverse(
                                "expenses:detail", args=[self.expenses["recorded"].pk]
                            ),
                        },
                        {
                            "inspect": "!document.querySelector('main form[action$=\"/void/\"]')",
                            "description": "refresh reflects completed lifecycle action",
                        },
                    ],
                )
            ],
        )
        self.expenses["recorded"].refresh_from_db()
        self.assertEqual(self.expenses["recorded"].status, "void")
        self.assertEqual(self.expenses["recorded"].void_reason, "ابطال نمونه مرورگر")
        self.reader_scope.membership.role_definition.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=["expenses.view", "expenses.approve"]
            )
        )
        self.browser(
            self.reader,
            [
                dict(
                    common,
                    name="expense-independent-reviewer",
                    path=reverse(
                        "expenses:detail", args=[self.expenses["submitted"].pk]
                    ),
                    steps=[
                        {
                            "inspect": "!!document.querySelector('main form[action$=\"/approve/\"]') && !document.querySelector('main form[action$=\"/void/\"]')",
                            "description": "only authorized independent actions appear",
                        }
                    ],
                )
            ],
        )
        self.login(self.denied)
        self.assertEqual(
            self.client.get(
                reverse("expenses:detail", args=[self.expenses["draft"].pk])
            ).status_code,
            403,
        )

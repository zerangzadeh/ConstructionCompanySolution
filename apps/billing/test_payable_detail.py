"""Bounded certificate presentation and actual Chrome validation in isolated DB."""

from datetime import date
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.billing import test_payable_certificates as domain_fixture
from apps.billing import test_payable_list as list_fixture
from apps.billing.payable_services import create_payable_certificate_correction
from apps.billing.test_payable_list import PayableListFixture
from apps.projects.test_command_center import scoped_reader


def detail(row):
    return reverse("billing:payable_certificate_detail", args=[row.pk])


class PayableDetailTests(PayableListFixture, TestCase):
    test_calculations = domain_fixture.PayableCertificateTests.test_measurement_calculation_caps_back_charge_and_stable_line
    test_correction_history = domain_fixture.PayableCertificateTests.test_linked_replacement_and_cancellation_preserve_history
    test_workflow = domain_fixture.PayableCertificateTests.test_workflow_candidacy_sod_immutability_and_audit

    def test_actions_follow_permission_scope_and_candidacy(self):
        approved, submitted, draft = self.make_rows()
        reader, _, grant = scoped_reader(
            self.organization,
            self.project,
            ["payable_certificates.view"],
            username="certificate-reader",
        )
        grant.scope_type, grant.project = "organization", None
        grant.save()
        self.login(reader)
        for row in (approved, submitted, draft):
            response = self.client.get(detail(row))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "data-pc-open=")
            self.assertNotContains(response, 'name="reason"')
        self.login(self.owner)
        self.assertFalse(self.client.get(detail(submitted)).context["can_decide"])
        self.assertContains(self.client.get(detail(draft)), "ارسال برای تأیید")
        self.login(self.manager)
        response = self.client.get(detail(submitted))
        self.assertTrue(response.context["can_decide"])
        self.assertContains(response, 'id="pc-approve"')
        # Existing mutation endpoint still denies a reader even with a forged POST.
        self.login(reader)
        self.assertEqual(
            self.client.post(
                reverse("billing:payable_certificate_submit", args=[draft.pk])
            ).status_code,
            403,
        )

    def test_snapshot_format_and_lineage(self):
        approved, _, _ = self.make_rows()
        self.login(self.owner)
        response = self.client.get(detail(approved))
        self.assertContains(response, "10٪")
        self.assertNotContains(response, "10.0000")
        self.assertContains(response, "ریال")
        correction = create_payable_certificate_correction(
            organization=self.organization,
            actor=self.owner,
            certificate=approved,
            correction_kind="replacement",
            reason="نسخه اصلاحی آزمایشی",
        )
        self.assertContains(self.client.get(detail(correction)), detail(approved))
        self.assertContains(self.client.get(detail(approved)), detail(correction))


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PayableDetailBrowserTests(PayableListFixture, StaticLiveServerTestCase):
    serialized_rollback = False
    browser = list_fixture.PayableListBrowserTests.browser

    @classmethod
    def _fixture_setup(cls):
        from django.db import connections

        super()._fixture_setup()
        cls.seed_contents = connections["default"].creation.serialize_db_to_string()

    _fixture_teardown = list_fixture.PayableListBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/payable-detail-reference/browser"
    )

    def test_chrome_states_actions_and_mobile(self):
        approved, submitted, draft = self.make_rows()
        from decimal import Decimal

        from apps.contracts.services import (
            approve_contract_term_version,
            create_contract_term_version,
        )

        term = create_contract_term_version(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            effective_from=date(2026, 4, 1),
            retention_rate=Decimal(0),
            advance_recovery_rate=Decimal(0),
            reason="شرایط آزمایشی بدون کسور",
        )
        approve_contract_term_version(
            organization=self.organization,
            actor=self.manager,
            term_version=term,
            reason="تأیید مستقل شرایط آزمایشی",
        )
        self._measurement(
            measured_on=date(2026, 4, 15), period=Decimal(1), cumulative=Decimal(9)
        )
        empty = self._certificate(
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            cutoff=date(2026, 4, 30),
        )
        self.assertGreater(empty.net_amount, 0)
        self.assertFalse(empty.adjustments.exists())
        base = {
            "status": 200,
            "screenshot": True,
            "noJsErrors": True,
            "noHttpErrors": True,
            "absentText": ["stable_line_id", "None", "شناسه پایدار", "contract_term."],
            "mustText": ["خالص قابل پرداخت", "مبنای محاسبه و سقف"],
        }

        def scenario(name, row, **kwargs):
            return {**base, "name": name, "path": detail(row), **kwargs}

        def inspect(expression, description):
            return {"inspect": expression, "description": description}

        def opened(dialog):
            return {
                "toggleSelector": f'[data-pc-open="{dialog}"]',
                "inspect": f'document.getElementById("{dialog}").open && document.activeElement.closest("dialog").id==="{dialog}"',
                "description": "modal opens and traps focus",
            }

        self.browser(
            self.owner,
            [
                scenario(
                    "draft-desktop",
                    draft,
                    steps=[
                        inspect(
                            '!!document.querySelector(".pc-actions form button") && !document.querySelector("dialog[open]")',
                            "draft CTA and collapsed forms",
                        )
                    ],
                ),
                scenario("draft-mobile", draft, mobile=True),
                scenario("approved-desktop", approved),
                scenario("approved-mobile", approved, mobile=True),
                scenario(
                    "submitted-submitter",
                    submitted,
                    steps=[
                        inspect(
                            '!document.querySelector("[data-pc-open=pc-approve]")',
                            "submitter cannot approve own work",
                        )
                    ],
                ),
                scenario(
                    "without-deductions",
                    empty,
                    mustText=["هیچ کسر هزینه‌ای ثبت نشده است."],
                ),
                scenario(
                    "add-deduction-panel",
                    draft,
                    mobile=True,
                    steps=[
                        opened("pc-back-charge"),
                        {
                            "fill": {
                                "amount": "5",
                                "description": "کسر آزمایشی مستند",
                                "evidence": "QA-17",
                            },
                            "formSelector": "#pc-back-charge form",
                            "submit": True,
                            "afterPath": detail(draft),
                            "mustText": "کسر آزمایشی مستند",
                        },
                    ],
                ),
                scenario(
                    "draft-submit",
                    draft,
                    steps=[
                        {
                            "clickSelector": ".pc-actions form button",
                            "afterPath": detail(draft),
                            "mustText": "گواهی پرداخت برای تأیید ارسال شد.",
                        }
                    ],
                ),
            ],
        )
        self.browser(
            self.manager,
            [
                scenario(
                    "submitted-approve-dialog", submitted, steps=[opened("pc-approve")]
                ),
                scenario(
                    "submitted-return-dialog-mobile",
                    submitted,
                    mobile=True,
                    steps=[opened("pc-return")],
                ),
                scenario(
                    "approve-action",
                    submitted,
                    steps=[
                        opened("pc-approve"),
                        {
                            "fill": {"reason": "تأیید مستقل آزمایشی"},
                            "formSelector": "#pc-approve form",
                            "submit": True,
                            "afterPath": detail(submitted),
                            "mustText": "گواهی پرداخت تأیید شد.",
                        },
                    ],
                ),
                scenario(
                    "return-action",
                    draft,
                    steps=[
                        opened("pc-return"),
                        {
                            "fill": {"reason": "بازگردانی مستند آزمایشی"},
                            "formSelector": "#pc-return form",
                            "submit": True,
                            "afterPath": detail(draft),
                            "mustText": "گواهی پرداخت برای اصلاح بازگردانده شد.",
                        },
                    ],
                ),
                scenario(
                    "returned-mobile",
                    draft,
                    mobile=True,
                    mustText=["بازگردانی مستند آزمایشی", "پیش‌نویس پس از بازگردانی"],
                ),
            ],
        )
        self.browser(
            self.owner,
            [
                scenario("correction-dialog", approved, steps=[opened("pc-correct")]),
                scenario(
                    "correction-action",
                    approved,
                    steps=[
                        opened("pc-correct"),
                        {
                            "fill": {
                                "correction_kind": "replacement",
                                "reason": "اصلاح آزمایشی پیوندخورده",
                            },
                            "formSelector": "#pc-correct form",
                            "submit": True,
                            "afterPrefix": "/billing/payable-certificates/",
                            "mustText": "نسخه اصلاحی پیوندخورده ایجاد شد.",
                        },
                    ],
                ),
            ],
        )
        approved.refresh_from_db()
        correction = approved.correction_certificates.get()
        self.browser(
            self.owner,
            [
                scenario(
                    "corrected-mobile",
                    correction,
                    mobile=True,
                    mustText=["نسخه مبنا:", "اصلاح آزمایشی پیوندخورده"],
                )
            ],
        )
        reader, _, grant = scoped_reader(
            self.organization,
            self.project,
            ["payable_certificates.view"],
            username="certificate-restricted",
        )
        grant.scope_type, grant.project = "organization", None
        grant.save()
        self.browser(
            reader,
            [
                scenario(
                    "restricted-" + str(width),
                    submitted,
                    width=width,
                    steps=[
                        inspect(
                            '!document.querySelector("[data-pc-open]") && !document.querySelector("dialog")',
                            "read-only user has no mutation controls",
                        )
                    ],
                )
                for width in (1440, 390)
            ],
        )

    def test_section_selection_on_rendered_detail(self):
        _, _, draft = self.make_rows()
        sections = (
            "pc-summary",
            "pc-basis",
            "pc-measurements",
            "pc-deductions",
            "pc-history",
        )
        steps = []
        for section in (*sections[1:], sections[0], sections[1]):
            steps.append(
                {
                    "toggleSelector": f'.pc-sections a[href="#{section}"]',
                    "inspect": f"document.querySelectorAll('.pc-sections [aria-current=location]').length === 1 && document.querySelector('.pc-sections [aria-current=location]').hash === '#{section}' && getComputedStyle(document.querySelector('.pc-sections [aria-current=location]')).borderBottomWidth === '4px' && [...document.querySelectorAll('.pc-sections a:not([aria-current])')].every(a=>getComputedStyle(a).borderBottomWidth === '0px')",
                    "description": "Only clicked section has the active underline",
                }
            )
        steps.extend(
            [
                {"reload": True},
                {
                    "inspect": "document.querySelector('.pc-sections [aria-current=location]').hash === '#pc-basis'",
                    "description": "Active section survives reload",
                },
            ]
        )
        self.browser(
            self.owner,
            [
                {
                    "name": f"actual-detail-section-selection-{width}",
                    "path": detail(draft),
                    "width": width,
                    "status": 200,
                    "steps": steps,
                    "screenshot": True,
                    "noJsErrors": True,
                    "noHttpErrors": True,
                }
                for width in (1440, 390)
            ],
        )

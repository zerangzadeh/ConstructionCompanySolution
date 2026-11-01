"""State-aware Contract Detail adapters: existing services, exact scope and Chrome."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as chrome_fixture
from apps.contracts.models import Contract, ContractTermVersion
from apps.contracts.services import create_contract, create_contract_term_version
from apps.contracts.test_detail_dashboard import DetailFixture
from apps.materials.models import UnitOfMeasure
from apps.organizations.models import Organization, OrganizationSettings
from apps.organizations.services import set_active_organization


class StateFixture(DetailFixture):
    def prepare_states(self):
        self.ready()
        OrganizationSettings.objects.get_or_create(
            organization=self.organization, defaults={"currency": "IRR"}
        )
        self.unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="CD-EA",
            name="واحد نمونه",
            symbol="ea",
            category="count",
        )
        self.states = {}
        for name, direction, kind, status in (
            ("draft-receivable", "receivable", "client", "draft"),
            ("active-receivable", "receivable", "client", "active"),
            ("draft-subcontract", "payable", "subcontract", "draft"),
            ("active-subcontract", "payable", "subcontract", "active"),
            ("draft-supplier", "payable", "supplier", "draft"),
            ("active-supplier", "payable", "supplier", "active"),
            ("completed-subcontract", "payable", "subcontract", "completed"),
            ("terminated-receivable", "receivable", "client", "terminated"),
        ):
            self.states[name] = create_contract(
                organization=self.organization,
                project=self.project,
                actor=self.owner,
                contract_number="STATE-" + name.upper(),
                title="قرارداد نمونه " + name.split("-")[0],
                counterparty_name=self.party.display_name,
                party=self.party,
                direction=direction,
                contract_type=kind,
                contract_value=Decimal(120000000),
            )
            # Explicit synthetic lifecycle states; no production transition bypass.
            Contract.objects.filter(pk=self.states[name].pk).update(status=status)
            self.states[name].refresh_from_db()

    def state_url(self, key):
        return reverse("contracts:detail", args=[self.states[key].pk])

    def base_data(self, key="draft-receivable"):
        c = self.states[key]
        return {
            "detail_action": "edit_base",
            "title": "قرارداد اصلاح‌شده نمونه",
            "party": str(self.party.pk),
            "counterparty_name": self.party.display_name,
            "direction": c.direction,
            "contract_type": c.contract_type,
            "contract_value": "125000000",
            "notes": "یادداشت اصلاحی پیش‌نویس",
        }

    def item_data(self):
        return {
            "detail_action": "add_item",
            "description": "ردیف نمونه نما",
            "quantity": "2.5000",
            "unit_price": "100000",
            "unit_of_measure": str(self.unit.pk),
        }

    def term_data(self):
        return {
            "detail_action": "create_term",
            "effective_from": "2026-09-01",
            "payment_due_days": "15",
            "retention_rate": "5",
            "retention_cap": "1000000",
            "advance_recovery_rate": "0",
            "advance_recovery_cap": "0",
            "contractual_insurance_rate": "0",
            "contractual_insurance_cap": "0",
            "retention_release_requirement": "unconfigured",
            "retention_release_cap": "0",
            "reason": "شرایط قراردادی نمونه برای آزمون",
        }


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class StateAwareDetailTests(StateFixture, TestCase):
    def setUp(self):
        self.prepare_states()

    def test_state_matrix_visibility_and_supported_journeys(self):
        for key, c in self.states.items():
            with self.subTest(key=key):
                r = self.client.get(self.state_url(key))
                self.assertEqual(r.status_code, 200)
                w = r.context["workspace"]
                main = r.content.decode().split('class="contract-detail"', 1)[1]
                self.assertEqual(w["can_edit"], c.status == "draft")
                self.assertEqual(w["can_add_item"], c.status == "draft")
                self.assertEqual(
                    w["can_terms"],
                    c.contract_type != "supplier" and c.status != "terminated",
                )
                self.assertEqual(
                    w["show_financial"],
                    c.status != "draft" and c.contract_type != "supplier",
                )
                self.assertEqual(
                    w["show_billing"],
                    c.status != "draft" and c.contract_type != "supplier",
                )
                self.assertNotIn("در دسترس نیست", main)
                if c.status == "draft":
                    self.assertContains(r, "ویرایش قرارداد")
                    self.assertContains(r, "مرور آماده‌سازی قرارداد")
                    self.assertNotIn("contract-financial-chart", main)
                    self.assertNotIn("/billing/claims/new/", main)
                    self.assertNotIn("آخرین صورت‌وضعیت", main)
                else:
                    self.assertNotIn("data-draft-edit", main)
                    self.assertNotIn('id="contract-draft-base"', main)
                    self.assertNotIn('id="contract-draft-item"', main)
                if c.contract_type == "supplier":
                    self.assertNotIn('id="terms"', main)
                    self.assertNotIn('id="progress"', main)
                    self.assertNotIn("cd-financial", main)
                    self.assertIn("تأمین‌کننده", main)
                if c.direction == "payable":
                    self.assertNotIn("/billing/claims/", main)
                    self.assertNotIn("/billing/baselines/", main)

    def test_draft_base_and_item_writes_use_existing_services(self):
        c = self.states["draft-receivable"]
        protected = (
            c.contract_number,
            c.project_id,
            c.signed_at,
            c.start_date,
            c.end_date,
        )
        self.assertEqual(
            self.client.post(
                self.state_url("draft-receivable"), self.base_data()
            ).status_code,
            302,
        )
        c.refresh_from_db()
        self.assertEqual(c.title, "قرارداد اصلاح‌شده نمونه")
        self.assertEqual(c.contract_value, Decimal(125000000))
        self.assertEqual(
            (c.contract_number, c.project_id, c.signed_at, c.start_date, c.end_date),
            protected,
        )
        self.assertEqual(
            self.client.post(
                self.state_url("draft-receivable"), self.item_data()
            ).status_code,
            302,
        )
        self.assertEqual(c.items.get().line_total, Decimal("250000.00"))
        self.assertEqual(c.items.get().organization_id, self.organization.pk)
        self.assertEqual(c.status, "draft")

    def test_terms_are_drafts_and_prior_versions_are_retained(self):
        for key in ("draft-receivable", "draft-subcontract"):
            with self.subTest(key=key):
                url = self.state_url(key)
                self.assertEqual(
                    self.client.post(url, self.term_data()).status_code, 302
                )
                first = self.states[key].term_versions.get()
                first_snapshot = ContractTermVersion.objects.values().get(pk=first.pk)
                changed = {
                    **self.term_data(),
                    "payment_due_days": "25",
                    "reason": "نسخه جدید برای آزمون؛ نگهداری نسخه پیشین",
                }
                self.assertEqual(self.client.post(url, changed).status_code, 302)
                self.assertEqual(
                    ContractTermVersion.objects.values().get(pk=first.pk),
                    first_snapshot,
                )
                self.assertEqual(
                    list(
                        self.states[key]
                        .term_versions.order_by("version")
                        .values_list("status", flat=True)
                    ),
                    ["draft", "draft"],
                )
                self.assertEqual(
                    self.states[key].term_versions.get(version=2).payment_due_days, 25
                )

    def test_finalized_and_restricted_mutation_attempts_fail(self):
        for key in (
            "active-receivable",
            "active-subcontract",
            "completed-subcontract",
            "terminated-receivable",
        ):
            c = self.states[key]
            before = Contract.objects.values().get(pk=c.pk)
            self.assertEqual(
                self.client.post(self.state_url(key), self.base_data(key)).status_code,
                403,
            )
            self.assertEqual(
                self.client.post(self.state_url(key), self.item_data()).status_code, 403
            )
            self.assertEqual(Contract.objects.values().get(pk=c.pk), before)
            self.assertFalse(c.items.exists())
        self.login(self.reader())
        for action in (self.base_data(), self.item_data(), self.term_data()):
            self.assertEqual(
                self.client.post(
                    self.state_url("draft-receivable"), action
                ).status_code,
                403,
            )
        main = (
            self.client.get(self.state_url("draft-receivable"))
            .content.decode()
            .split('class="contract-detail"', 1)[1]
        )
        self.assertNotIn("data-draft-edit", main)
        self.assertNotIn("<form", main)
        self.assertNotIn("در دسترس نیست", main)

    def test_tenant_input_validation_and_csrf(self):
        other = Organization.objects.create(name="Other", slug="state-other")
        unit = UnitOfMeasure.objects.create(
            organization=other,
            code="FOREIGN",
            name="Foreign",
            symbol="foreign",
            category="count",
        )
        r = self.client.post(
            self.state_url("draft-receivable"),
            {**self.item_data(), "unit_of_measure": str(unit.pk)},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["workspace"]["item_form"].errors)
        self.assertFalse(self.states["draft-receivable"].items.exists())
        r = self.client.post(
            self.state_url("draft-receivable"),
            {**self.base_data(), "contract_value": "-1"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["workspace"]["base_form"].errors)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        session = csrf.session
        set_active_organization(session, self.organization)
        session.save()
        self.assertEqual(
            csrf.post(self.state_url("draft-receivable"), self.base_data()).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                self.state_url("draft-receivable"), {"detail_action": "activate"}
            ).status_code,
            403,
        )

    def test_state_is_rechecked_after_form_validation(self):
        from apps.contracts import detail_workspace

        original = detail_workspace.DraftContractEditForm.is_valid
        c = self.states["draft-receivable"]

        def transition_during_validation(form):
            valid = original(form)
            Contract.objects.filter(pk=c.pk).update(status="active")
            return valid

        with patch.object(
            detail_workspace.DraftContractEditForm,
            "is_valid",
            transition_during_validation,
        ):
            self.assertEqual(
                self.client.post(
                    self.state_url("draft-receivable"), self.base_data()
                ).status_code,
                403,
            )
        c.refresh_from_db()
        self.assertNotEqual(c.title, "قرارداد اصلاح‌شده نمونه")

    def test_approved_terms_protected_and_draft_insurance_still_editable(self):
        approved = self.contract.term_versions.get(status="approved")
        before = ContractTermVersion.objects.values().get(pk=approved.pk)
        url = reverse("contracts:detail", args=[self.contract.pk])
        self.assertEqual(self.client.post(url, self.term_data()).status_code, 302)
        draft = self.contract.term_versions.get(status="draft")
        selection = {
            f"{draft.pk}-insurance_classification": str(
                self.insurance_classification.pk
            ),
            f"{draft.pk}-reason": "Explicit draft classification edit",
        }
        self.assertEqual(
            self.client.post(
                reverse(
                    "contracts:term_insurance_select", args=[self.contract.pk, draft.pk]
                ),
                selection,
            ).status_code,
            302,
        )
        draft.refresh_from_db()
        self.assertEqual(
            draft.insurance_classification_id, self.insurance_classification.pk
        )
        self.assertEqual(draft.status, "draft")
        rejected = self.client.post(
            reverse(
                "contracts:term_insurance_select", args=[self.contract.pk, approved.pk]
            ),
            {
                f"{approved.pk}-insurance_classification": str(
                    self.insurance_classification.pk
                ),
                f"{approved.pk}-reason": "Attempt forbidden approved-term edit",
            },
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(
            ContractTermVersion.objects.values().get(pk=approved.pk), before
        )

    def test_each_existing_write_permission_is_independent(self):
        from apps.projects.test_command_center import scoped_reader

        editor, _role, _grant = scoped_reader(
            self.organization,
            self.project,
            ["contracts.view", "contracts.change"],
            username="base-only-editor",
        )
        self.login(editor)
        r = self.client.get(self.state_url("draft-receivable"))
        self.assertTrue(r.context["workspace"]["can_edit"])
        self.assertFalse(r.context["workspace"]["can_add_item"])
        self.assertFalse(r.context["workspace"]["can_terms"])
        self.assertEqual(
            self.client.post(
                self.state_url("draft-receivable"), self.base_data()
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(
                self.state_url("draft-receivable"), self.item_data()
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                self.state_url("draft-receivable"), self.term_data()
            ).status_code,
            403,
        )

    def test_supplier_rule_enforced_by_service_and_model(self):
        c = self.states["draft-supplier"]
        with self.assertRaises(ValidationError):
            create_contract_term_version(
                organization=self.organization,
                actor=self.owner,
                contract=c,
                effective_from=date(2026, 9, 1),
                reason="Test forbidden supplier type",
            )
        with self.assertRaises(ValidationError):
            ContractTermVersion(
                organization=self.organization,
                contract=c,
                version=1,
                effective_from=date(2026, 9, 1),
                reason="Test model boundary",
                created_by=self.owner,
            ).full_clean()
        self.assertEqual(
            self.client.post(
                self.state_url("draft-supplier"), self.term_data()
            ).status_code,
            403,
        )
        self.assertFalse(c.term_versions.exists())


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class StateAwareBrowserTests(StateFixture, StaticLiveServerTestCase):
    browser = chrome_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = chrome_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/contract-state-aware/browser"
    )

    def test_state_matrix_and_real_form_submissions(self):
        self.prepare_states()
        base = {
            "status": 200,
            "screenshot": True,
            "noJsErrors": True,
            "noHttpErrors": True,
            "absentText": ["در دسترس نیست", "None"],
        }
        inspect = lambda expression, label: {
            "inspect": expression,
            "description": label,
        }
        scenarios = []
        for key, c in self.states.items():
            draft = c.status == "draft"
            check = (
                "!!document.querySelector('[data-draft-edit]') && !!document.querySelector('#contract-draft-base') && !!document.querySelector('#contract-draft-item') && !document.querySelector('canvas,.cd-claims')"
                if draft
                else "!document.querySelector('[data-draft-edit],#contract-draft-base,#contract-draft-item')"
            )
            if c.contract_type == "supplier":
                check += " && !document.querySelector('#contract-draft-term,#terms,#progress,.cd-claims,canvas') && !!document.querySelector('.cd-supplier-note')"
            elif draft:
                check += " && !!document.querySelector('#contract-draft-term') && document.querySelectorAll('.cd-kpi').length===4"
            else:
                check += " && document.querySelectorAll('.cd-claims tbody tr').length===0 && document.querySelectorAll('canvas').length===1"
            if c.direction == "payable":
                check += " && ![...document.querySelectorAll('.contract-detail a')].some(a=>/billing\\/(claims|baselines)/.test(a.href))"
            for width in (1440, 390):
                scenarios.append(
                    {
                        **base,
                        "name": key + "-" + str(width),
                        "path": self.state_url(key),
                        "mobile": width == 390,
                        "steps": [
                            inspect(
                                check,
                                "state-specific CTA, editor, operational widgets and supported journeys",
                            )
                        ],
                    }
                )
        self.browser(self.owner, scenarios)
        data = {
            key: value
            for key, value in self.base_data().items()
            if key != "detail_action"
        }
        data["title"] = "ذخیره واقعی پیش‌نویس در مرورگر"
        self.browser(
            self.owner,
            [
                {
                    **base,
                    "name": "draft-edit-submit-desktop",
                    "path": self.state_url("draft-receivable"),
                    "steps": [
                        {
                            "toggleSelector": "[data-draft-edit]",
                            "inspect": "document.querySelector('#draft-edit').open",
                            "description": "draft primary CTA opens the existing local editor",
                        },
                        inspect(
                            "document.querySelector('#draft-edit').open",
                            "draft primary CTA opens editor",
                        ),
                        {
                            "fill": data,
                            "formSelector": "#contract-draft-base",
                            "clickSelector": "#contract-draft-base button[type=submit]",
                            "afterPath": self.state_url("draft-receivable"),
                            "mustText": "ذخیره واقعی پیش‌نویس در مرورگر",
                        },
                    ],
                },
                {
                    **base,
                    "name": "draft-item-submit-mobile",
                    "path": self.state_url("draft-subcontract"),
                    "mobile": True,
                    "steps": [
                        {
                            "fill": {
                                k: v
                                for k, v in self.item_data().items()
                                if k != "detail_action"
                            },
                            "formSelector": "#contract-draft-item",
                            "clickSelector": "#contract-draft-item button[type=submit]",
                            "afterPath": self.state_url("draft-subcontract"),
                            "mustText": "ردیف نمونه نما",
                        },
                    ],
                },
                {
                    **base,
                    "name": "draft-term-submit-mobile",
                    "path": self.state_url("draft-subcontract"),
                    "mobile": True,
                    "steps": [
                        {
                            "toggleSelector": "#terms>summary",
                            "inspect": "document.querySelector('#terms').open",
                            "description": "terms editor opens",
                        },
                        {
                            "fill": {
                                k: v
                                for k, v in self.term_data().items()
                                if k != "detail_action"
                            },
                            "formSelector": "#contract-draft-term",
                            "clickSelector": "#contract-draft-term button[type=submit]",
                            "afterPath": self.state_url("draft-subcontract"),
                            "mustText": "نسخه 1",
                        },
                    ],
                },
            ],
        )
        self.states["draft-receivable"].refresh_from_db()
        self.assertEqual(self.states["draft-receivable"].title, data["title"])
        self.assertEqual(self.states["draft-subcontract"].items.count(), 1)
        self.assertEqual(
            self.states["draft-subcontract"].term_versions.get().status, "draft"
        )
        self.browser(
            self.reader(),
            [
                {
                    **base,
                    "name": "restricted-" + str(width),
                    "path": self.state_url("draft-receivable"),
                    "mobile": width == 390,
                    "steps": [
                        inspect(
                            "!document.querySelector('[data-draft-edit],main form,canvas,.cd-claims')",
                            "restricted draft remains read-only without permission leakage",
                        )
                    ],
                }
                for width in (1440, 390)
            ],
        )
        from apps.projects.test_command_center import scoped_reader

        editor, _role, _grant = scoped_reader(
            self.organization,
            self.project,
            ["contracts.view", "contracts.change"],
            username="project-editor-browser",
        )
        self.browser(
            editor,
            [
                {
                    **base,
                    "name": "project-editor-submit-390",
                    "path": self.state_url("draft-receivable"),
                    "mobile": True,
                    "steps": [
                        {
                            "toggleSelector": "[data-draft-edit]",
                            "inspect": "document.querySelector('#draft-edit').open",
                            "description": "project-scoped editor can open the permitted base editor",
                        },
                        {
                            "fill": {**data, "title": "ویرایش مجاز در محدوده پروژه"},
                            "formSelector": "#contract-draft-base",
                            "clickSelector": "#contract-draft-base button[type=submit]",
                            "afterPath": self.state_url("draft-receivable"),
                            "mustText": "ویرایش مجاز در محدوده پروژه",
                        },
                        inspect(
                            "!document.querySelector('#contract-draft-item,#contract-draft-term')",
                            "base edit permission does not grant item or term mutations",
                        ),
                    ],
                }
            ],
        )

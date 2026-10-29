"""MVP-03 HTTP journey, selectors, scope and existing workflow integration."""

from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.billing import tests as billing_fixture
from apps.billing.journey_forms import ClaimCreateForm
from apps.billing.models import ProgressClaim
from apps.billing.services import submit_progress_claim
from apps.estimates.services import create_estimate
from apps.organizations.models import Organization
from apps.organizations.services import set_active_organization


class JourneyMessageTests(SimpleTestCase):
    def test_business_error_does_not_expose_source_pinning_terminology(self):
        from django.core.exceptions import ValidationError

        from apps.billing.journey_views import error_text

        text = error_text(ValidationError("نسخه مقرراتی پین‌شده شواهد معتبر ندارد."))
        self.assertNotIn("پین‌شده", text)
        self.assertIn("ثبت‌شده برای این صورت‌وضعیت", text)


class JourneyFixture:
    _publish_regulatory_rules = (
        billing_fixture.ProjectBaselineWorkflowTests._publish_regulatory_rules
    )
    _baseline = billing_fixture.ProjectBaselineWorkflowTests._baseline
    _approved_baseline = billing_fixture.ProgressRecordWorkflowTests._approved_baseline
    _record = billing_fixture.ProgressRecordWorkflowTests._record
    _verified_record = billing_fixture.ProgressClaimCalculationTests._verified_record
    _claim = billing_fixture.ProgressClaimCalculationTests._claim

    def make_fixture(self, *, persian=False):
        from importlib import import_module

        from django.apps import apps

        for migration, seed in (
            (
                "0018_project_baseline_compatibility_catalog",
                "seed_project_baseline_catalog",
            ),
            (
                "0019_progress_verification_compatibility_catalog",
                "seed_progress_catalog",
            ),
            (
                "0020_progress_claim_approval_compatibility_catalog",
                "seed_progress_claim_catalog",
            ),
        ):
            getattr(import_module("apps.workflows.migrations." + migration), seed)(
                apps, None
            )
        if persian:
            from unittest.mock import patch

            from apps.contracts.services import create_contract

            def named_contract(**kwargs):
                kwargs["title"] = "اجرای سازه بتنی"
                return create_contract(**kwargs)

            with patch(
                "apps.billing.tests.create_contract", side_effect=named_contract
            ):
                billing_fixture.ProjectBaselineWorkflowTests.setUp(self)
        else:
            billing_fixture.ProjectBaselineWorkflowTests.setUp(self)

    def login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        set_active_organization(session, self.organization)
        session.save()

    def action_url(self, claim, action):
        return reverse("billing:claim_action", args=[claim.pk, action])


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ContractBillingJourneyTests(JourneyFixture, TestCase):
    def setUp(self):
        self.make_fixture()
        self.login(self.owner)

    def test_estimate_to_contract_and_related_claim_navigation(self):
        claim = self._claim()
        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            contract=self.contract,
            actor=self.owner,
            estimate_number="MVP03-E",
            title="برآورد اجرایی",
        )
        response = self.client.get(reverse("estimates:detail", args=[estimate.pk]))
        self.assertContains(
            response, reverse("contracts:detail", args=[self.contract.pk])
        )
        response = self.client.get(reverse("contracts:detail", args=[self.contract.pk]))
        self.assertContains(response, reverse("billing:claim_detail", args=[claim.pk]))
        self.assertContains(
            response, f"/billing/claims/new/?contract={self.contract.pk}"
        )
        self.assertContains(response, "برآورد اجرایی")

    def test_create_from_contract_and_baseline_then_calculate_deductions(self):
        record = self._verified_record()
        url = reverse("billing:claim_create")
        response = self.client.get(
            url, {"contract": self.contract.pk, "baseline": record.baseline_id}
        )
        self.assertContains(response, "صورت‌وضعیت جدید")
        self.assertEqual(
            str(response.context["form"].initial["baseline"]), str(record.baseline_id)
        )
        response = self.client.post(
            url,
            {
                "contract": self.contract.pk,
                "baseline": record.baseline_id,
                "period_start": "2026-09-01",
                "period_end": "2026-09-30",
                "measurement_cutoff": "2026-09-30",
            },
        )
        claim = ProgressClaim.objects.get(organization=self.organization)
        self.assertRedirects(response, reverse("billing:claim_detail", args=[claim.pk]))
        self.assertEqual(str(claim.gross_amount), "60.0000")
        response = self.client.post(self.action_url(claim, "recalculate"), follow=True)
        self.assertContains(response, "مقادیر و کسور پیش‌نویس به‌روز شد")

    def test_forged_parent_child_and_invalid_dates_fail_closed(self):
        record = self._verified_record()
        data = {
            "contract": "00000000-0000-0000-0000-000000000001",
            "baseline": record.baseline_id,
            "period_start": "2026-09-30",
            "period_end": "2026-09-01",
            "measurement_cutoff": "2026-08-01",
        }
        form = ClaimCreateForm(data, organization=self.organization, actor=self.owner)
        self.assertFalse(form.is_valid())
        self.assertIn("contract", form.errors)
        self.assertIn("baseline", form.errors)
        self.assertIn("period_end", form.errors)
        self.assertFalse(ProgressClaim.objects.exists())

    def test_real_workflow_separation_decision_validation_and_approval(self):
        claim = self._claim()
        response = self.client.post(self.action_url(claim, "submit"), follow=True)
        self.assertContains(response, "صورت‌وضعیت برای بررسی ارسال شد")
        claim.refresh_from_db()
        self.assertEqual(claim.status, "submitted")
        response = self.client.post(
            self.action_url(claim, "approve"), {"reason": "self"}, follow=True
        )
        claim.refresh_from_db()
        self.assertEqual(claim.status, "submitted")
        self.login(self.manager)
        response = self.client.post(self.action_url(claim, "approve"), {"reason": ""})
        self.assertTrue(response.context["can_decide_claim"])
        self.assertContains(response, "دلیل تصمیم را وارد کنید")
        response = self.client.post(
            self.action_url(claim, "approve"), {"reason": "بررسی مستقل"}, follow=True
        )
        self.assertContains(response, "صورت‌وضعیت تأیید شد")
        claim.refresh_from_db()
        self.assertEqual(claim.status, "approved")
        before = claim.calculation_snapshot
        self.client.post(self.action_url(claim, "recalculate"))
        claim.refresh_from_db()
        self.assertEqual(claim.calculation_snapshot, before)

    def test_return_links_new_editable_revision(self):
        claim = self._claim()
        submit_progress_claim(
            organization=self.organization, actor=self.owner, claim=claim
        )
        self.login(self.manager)
        response = self.client.post(
            self.action_url(claim, "return"), {"reason": "اصلاح کارکرد"}, follow=True
        )
        claim.refresh_from_db()
        self.assertEqual(claim.status, "returned")
        self.assertContains(
            response, reverse("billing:claim_detail", args=[claim.returned_revision_id])
        )
        self.assertEqual(claim.returned_revision.status, "draft")

    def test_mvp_has_no_finance_or_technical_calculation_leakage(self):
        claim = self._claim()
        response = self.client.get(reverse("billing:claim_detail", args=[claim.pk]))
        for text in (
            "contract_term.",
            "regulatory.",
            "ClaimAdjustment",
            "idempotency",
            "حد برش",
            "تسویهٔ دستی",
            "AR",
            "شناسه تراکنش",
        ):
            self.assertNotContains(response, text)
        self.assertEqual(
            self.client.post(
                reverse("billing:claim_settlement_allocate", args=[claim.pk])
            ).status_code,
            403,
        )

    def test_filters_and_context_do_not_write_global_session(self):
        claim = self._claim()
        before = dict(self.client.session)
        for route in (
            "billing:claim_list",
            "billing:baseline_list",
            "billing:progress_list",
        ):
            response = self.client.get(
                reverse(route), {"contract": self.contract.pk, "q": "Receivable"}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(dict(self.client.session), before)
        response = self.client.get(
            reverse("billing:claim_list"), {"contract": "invalid"}
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 0)
        self.assertEqual(claim.status, "draft")

    def test_lookup_authorization_parent_scope_and_no_result(self):
        baseline = self._approved_baseline()
        url = reverse("billing:journey_choices", args=["claim", "baseline"])
        self.assertEqual(self.client.get(url).json()["results"], [])
        self.assertEqual(
            self.client.get(url, {"contract": self.contract.pk}).json()["results"][0][
                "value"
            ],
            str(baseline.pk),
        )
        self.assertEqual(
            self.client.get(url, {"contract": "bad"}).json()["results"], []
        )
        self.assertEqual(
            self.client.get(
                url, {"contract": self.contract.pk, "q": "no-such-contract"}
            ).json()["results"],
            [],
        )
        self.login(self.member)
        self.assertEqual(
            self.client.get(url, {"contract": self.contract.pk}).status_code, 403
        )

    def test_cross_tenant_claim_and_lookup_are_inaccessible(self):
        claim = self._claim()
        other = Organization.objects.create(name="Other tenant", slug="mvp03-other")
        from apps.accounts.models import User
        from tests.retirement_fixtures import explicit_fixture_roles

        outsider = User.objects.create_user(username="mvp03-outsider")
        other.memberships.create(user=outsider, role="company_owner", status="active")
        explicit_fixture_roles(other)
        self.client.force_login(outsider)
        session = self.client.session
        set_active_organization(session, other)
        session.save()
        self.assertEqual(
            self.client.get(
                reverse("billing:claim_detail", args=[claim.pk])
            ).status_code,
            404,
        )
        url = reverse("billing:journey_choices", args=["claim", "baseline"])
        self.assertEqual(
            self.client.get(url, {"contract": self.contract.pk}).json()["results"], []
        )
        self.assertEqual(
            self.client.post(self.action_url(claim, "submit")).status_code, 404
        )

    def test_csrf_and_method_controls(self):
        claim = self._claim()
        self.assertEqual(
            self.client.get(self.action_url(claim, "submit")).status_code, 405
        )
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        session = client.session
        set_active_organization(session, self.organization)
        session.save()
        self.assertEqual(client.post(self.action_url(claim, "submit")).status_code, 403)

    def test_native_refresh_never_creates_a_claim(self):
        baseline = self._approved_baseline()
        response = self.client.post(
            reverse("billing:claim_create") + "?native_choices=1",
            {
                "contract": self.contract.pk,
                "baseline": baseline.pk,
                "period_start": "2026-09-01",
                "period_end": "2026-09-30",
                "measurement_cutoff": "2026-09-30",
                "_refresh_choices": "1",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ProgressClaim.objects.exists())

    def test_contract_form_uses_one_party_master_and_copies_snapshot(self):
        from apps.contracts.models import Contract

        response = self.client.get(reverse("contracts:create"))
        self.assertNotIn("counterparty_name", response.context["form"].fields)
        response = self.client.post(
            reverse("contracts:create"),
            {
                "project": self.project.pk,
                "party": self.party.pk,
                "contract_number": "MVP03-NEW",
                "title": "قرارداد جدید",
                "status": "active",
                "direction": "receivable",
                "contract_value": "100",
                "contract_type": "",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        contract = Contract.objects.get(
            organization=self.organization, contract_number="MVP03-NEW"
        )
        self.assertEqual(contract.counterparty_name, self.party.display_name)
        self.assertEqual(contract.party, self.party)

    def test_estimate_parent_context_and_one_unit_master(self):
        from apps.materials.models import UnitOfMeasure

        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            contract=self.contract,
            actor=self.owner,
            estimate_number="MVP03-UNIT",
            title="برآورد واحد",
        )
        unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="MVP03-M3",
            name="متر مکعب نمونه",
            symbol="m3-test",
            category="volume",
        )
        response = self.client.get(
            reverse("estimates:create"),
            {"project": self.project.pk, "contract": self.contract.pk},
        )
        self.assertIn(
            self.contract, response.context["form"].fields["contract"].queryset
        )
        response = self.client.post(
            reverse("estimates:detail", args=[estimate.pk]),
            {
                "description": "بتن",
                "quantity": "2",
                "unit_price": "10",
                "unit_of_measure": unit.pk,
                "sort_order": "0",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(estimate.items.get().unit_of_measure, unit)
        self.assertEqual(estimate.items.get().unit, unit.symbol)

    def test_selector_pagination_preserves_off_page_selected_master(self):
        from apps.contracts.forms import ContractForm
        from apps.parties.models import BusinessParty

        parties = [
            BusinessParty(
                organization=self.organization,
                party_kind="company",
                display_name=f"کارفرمای نمونه {i:03}",
            )
            for i in range(45)
        ]
        BusinessParty.objects.bulk_create(parties)
        url = reverse("billing:journey_choices", args=["contract", "party"])
        first = self.client.get(url).json()
        self.assertEqual(len(first["results"]), 40)
        self.assertTrue(first["next"])
        second = self.client.get(first["next"]).json()
        self.assertTrue(second["results"])
        chosen = second["results"][-1]["value"]
        form = ContractForm(
            organization=self.organization,
            membership=self.organization.memberships.get(user=self.owner),
            initial={"party": chosen},
        )
        self.assertIn(
            chosen, [value for value, label in form.fields["party"].widget.choices]
        )

    def test_project_reader_cannot_open_an_out_of_scope_claim(self):
        from apps.accounts.models import User
        from apps.organizations.models import (
            BusinessPermission,
            MembershipRoleAssignment,
            MembershipScopeGrant,
            OrganizationRole,
        )
        from apps.projects.models import Project

        claim = self._claim()
        reader = User.objects.create_user(username="mvp03-project-reader")
        role = OrganizationRole.objects.create(
            organization=self.organization, code="mvp03-reader", name="خواننده پروژه"
        )
        role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=(
                    "claims.view",
                    "contracts.view",
                    "baselines.view",
                    "progress.view",
                )
            )
        )
        member = self.organization.memberships.create(
            user=reader, status="active", role_definition=role
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=member,
            role=role,
            reason="Explicit test scope",
        )
        other = Project.objects.create(
            organization=self.organization, code="MVP03-OUT", name="پروژه دیگر"
        )
        grant = MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=member,
            scope_type="project",
            project=other,
            reason="Explicit test grant",
        )
        self.login(reader)
        self.assertEqual(
            self.client.get(
                reverse("billing:claim_detail", args=[claim.pk])
            ).status_code,
            404,
        )
        grant.project = self.project
        grant.save()
        response = self.client.get(reverse("billing:claim_detail", args=[claim.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["contract_visible"])

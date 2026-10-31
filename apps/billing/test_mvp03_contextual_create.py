"""Inherited business parents remain scoped and survive real form submissions."""

from datetime import date
from html.parser import HTMLParser

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.billing.models import ProgressClaim, ProjectBaseline
from apps.billing.test_mvp03 import JourneyFixture
from apps.contracts.models import Contract
from apps.estimates.models import Estimate
from apps.estimates.services import create_estimate
from apps.organizations.models import Organization
from apps.projects.models import Project


class ParentMarkup(HTMLParser):
    def __init__(self, response):
        super().__init__()
        self.hidden = {}
        self.selects = set()
        self.text = []
        self.feed(response.content.decode())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if (
            tag == "input"
            and attrs.get("type") == "hidden"
            and attrs.get("name") in {"project", "contract"}
        ):
            self.hidden[attrs["name"]] = attrs.get("value")
        if tag == "select":
            self.selects.add(attrs.get("name"))

    def handle_data(self, data):
        self.text.append(data)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ContextualCreateTests(JourneyFixture, TestCase):
    def setUp(self):
        self.make_fixture()
        self.login(self.owner)

    def context_url(self, route, name, parent):
        return reverse(route) + f"?{name}={parent.pk}"

    def estimate_data(self, **overrides):
        return {
            "project": self.project.pk,
            "estimate_number": "CTX-E",
            "title": "برآورد زمینه‌دار",
            "contract": "",
            "phase": "",
            **overrides,
        }

    def contract_data(self, **overrides):
        return {
            "project": self.project.pk,
            "contract_number": "CTX-C",
            "title": "قرارداد زمینه‌دار",
            "party": self.party.pk,
            "status": "active",
            "direction": "receivable",
            "contract_value": "100",
            **overrides,
        }

    def claim_data(self, baseline_record, **overrides):
        return {
            "contract": self.contract.pk,
            "baseline": baseline_record.pk,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "measurement_cutoff": "2026-09-30",
            **overrides,
        }

    def assert_parent(self, response, name, parent):
        self.assertEqual(response.status_code, 200)
        page = ParentMarkup(response)
        self.assertEqual(page.hidden[name], str(parent.pk))
        self.assertNotIn(name, page.selects)
        self.assertNotIn(str(parent.pk), " ".join(page.text))
        self.assertContains(response, getattr(parent, "name", None) or parent.title)

    def test_project_estimate_context_validation_success_and_parent_navigation(self):
        url = self.context_url("estimates:create", "project", self.project)
        before = dict(self.client.session)
        self.assert_parent(self.client.get(url), "project", self.project)
        response = self.client.post(url, self.estimate_data(title=""))
        self.assert_parent(response, "project", self.project)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(
            response.context["cancel_url"],
            reverse("projects:detail", args=[self.project.pk]),
        )
        self.assertFalse(Estimate.objects.exists())
        response = self.client.post(url, self.estimate_data())
        estimate = Estimate.objects.get(estimate_number="CTX-E")
        self.assertEqual(estimate.project, self.project)
        self.assertRedirects(response, reverse("estimates:detail", args=[estimate.pk]))
        self.assertContains(
            self.client.get(response.url),
            reverse("projects:detail", args=[self.project.pk]),
        )
        self.assertEqual(dict(self.client.session), before)

    def test_project_contract_context_validation_success_and_parent_navigation(self):
        url = self.context_url("contracts:create", "project", self.project)
        self.assert_parent(self.client.get(url), "project", self.project)
        response = self.client.post(url, self.contract_data(contract_number=""))
        self.assert_parent(response, "project", self.project)
        self.assertTrue(response.context["form"].errors)
        response = self.client.post(url, self.contract_data())
        contract = Contract.objects.get(contract_number="CTX-C")
        self.assertEqual(contract.project, self.project)
        self.assertRedirects(response, reverse("contracts:detail", args=[contract.pk]))
        self.assertContains(
            self.client.get(response.url),
            reverse("projects:detail", args=[self.project.pk]),
        )

    def test_contract_claim_single_baseline_validation_success_and_back_links(self):
        baseline = self._approved_baseline()
        url = self.context_url("billing:claim_create", "contract", self.contract)
        response = self.client.get(url)
        self.assert_parent(response, "contract", self.contract)
        self.assertEqual(response.context["form"]["baseline"].value(), baseline.pk)
        self.assertEqual(
            response.context["cancel_url"],
            reverse("contracts:detail", args=[self.contract.pk]),
        )
        response = self.client.post(
            url, self.claim_data(baseline, period_end="2026-08-01")
        )
        self.assert_parent(response, "contract", self.contract)
        self.assertEqual(
            str(response.context["form"]["baseline"].value()), str(baseline.pk)
        )
        self.assertFalse(ProgressClaim.objects.exists())
        response = self.client.post(url, self.claim_data(baseline))
        claim = ProgressClaim.objects.get()
        self.assertEqual(
            (claim.contract, claim.project, claim.baseline),
            (self.contract, self.project, baseline),
        )
        self.assertRedirects(response, reverse("billing:claim_detail", args=[claim.pk]))
        detail = self.client.get(response.url)
        self.assertContains(
            detail, reverse("contracts:detail", args=[self.contract.pk])
        )
        self.assertContains(detail, reverse("projects:detail", args=[self.project.pk]))

    def test_contract_claim_without_eligible_baseline_explains_prerequisite(self):
        url = self.context_url("billing:claim_create", "contract", self.contract)
        response = self.client.get(url)
        self.assert_parent(response, "contract", self.contract)
        self.assertTrue(response.context["form"].no_eligible_baseline)
        self.assertContains(response, "مبنای اندازه‌گیری تأییدشده‌ای در دسترس نیست")
        self.assertFalse(response.context["form"].fields["baseline"].queryset.exists())
        response = self.client.post(url, {"contract": self.contract.pk})
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(ProgressClaim.objects.exists())

    def test_multiple_approved_baselines_are_forbidden_by_existing_domain(self):
        baseline = self._approved_baseline()
        with self.assertRaises(IntegrityError) as raised, transaction.atomic():
            ProjectBaseline.objects.bulk_create(
                [
                    ProjectBaseline(
                        organization=self.organization,
                        project=self.project,
                        contract=self.contract,
                        version=baseline.version + 1,
                        effective_date=date(2026, 9, 1),
                        status="approved",
                    )
                ]
            )
        self.assertEqual(
            raised.exception.__cause__.diag.constraint_name,
            "baseline_one_current_approved_contract",
        )
        self.assertEqual(
            ProjectBaseline.objects.filter(
                contract=self.contract, status="approved"
            ).count(),
            1,
        )
        response = self.client.get(
            self.context_url("billing:claim_create", "contract", self.contract)
        )
        self.assertEqual(response.context["form"]["baseline"].value(), baseline.pk)

    def test_general_entry_points_keep_explicit_selectors_and_create_successfully(self):
        for route, field in (
            ("estimates:create", "project"),
            ("contracts:create", "project"),
            ("billing:claim_create", "contract"),
        ):
            response = self.client.get(reverse(route))
            self.assertIn(field, ParentMarkup(response).selects)
            self.assertNotIn(field, ParentMarkup(response).hidden)
        self.assertEqual(
            self.client.post(
                reverse("estimates:create"),
                self.estimate_data(contract=self.contract.pk),
            ).status_code,
            302,
        )
        self.assertEqual(Estimate.objects.get().contract, self.contract)
        self.assertEqual(
            self.client.post(
                reverse("contracts:create"), self.contract_data()
            ).status_code,
            302,
        )
        baseline = self._approved_baseline()
        self.assertEqual(
            self.client.post(
                reverse("billing:claim_create"), self.claim_data(baseline)
            ).status_code,
            302,
        )

    def test_existing_estimate_contract_is_opened_without_creating_duplicates(self):
        estimate = create_estimate(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            contract=self.contract,
            estimate_number="CTX-LINK",
            title="برآورد متصل",
        )
        url = self.context_url("contracts:create", "estimate", estimate)
        for method in (self.client.get, self.client.post):
            response = method(url)
            self.assertRedirects(
                response, reverse("contracts:detail", args=[self.contract.pk])
            )
        self.assertEqual(Contract.objects.count(), 1)

    def test_unlinked_estimate_does_not_claim_an_unsupported_attachment_flow(self):
        estimate = create_estimate(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            estimate_number="CTX-UNLINK",
            title="برآورد مستقل",
        )
        url = self.context_url("contracts:create", "estimate", estimate)
        response = self.client.post(url, self.contract_data())
        self.assertRedirects(
            response,
            reverse("estimates:detail", args=[estimate.pk]),
            fetch_redirect_response=False,
        )
        self.assertContains(self.client.get(response.url), "پشتیبانی نمی‌شود")
        estimate.refresh_from_db()
        self.assertIsNone(estimate.contract_id)
        self.assertEqual(Contract.objects.count(), 1)
        self.assertEqual(
            self.client.post(
                reverse("contracts:create"), self.contract_data(estimate=estimate.pk)
            ).status_code,
            403,
        )

    def test_forged_project_is_rejected_even_if_user_can_access_both_projects(self):
        other = Project.objects.create(
            organization=self.organization, code="CTX-OTHER", name="پروژه دیگر"
        )
        for route, data in (
            ("estimates:create", self.estimate_data(project=other.pk)),
            ("contracts:create", self.contract_data(project=other.pk)),
        ):
            response = self.client.post(
                self.context_url(route, "project", self.project), data
            )
            self.assert_parent(response, "project", self.project)
            self.assertIn("project", response.context["form"].errors)
        self.assertFalse(Estimate.objects.exists())
        self.assertEqual(Contract.objects.count(), 1)

    def test_forged_contract_baseline_and_derived_project_are_rejected(self):
        baseline = self._approved_baseline()
        other = Contract.objects.create(
            organization=self.organization,
            project=self.project,
            contract_number="CTX-OTHER",
            title="قرارداد دیگر",
            counterparty_name="طرف نمونه",
            direction="receivable",
            status="active",
        )
        foreign_baseline = ProjectBaseline.objects.create(
            organization=self.organization,
            project=self.project,
            contract=other,
            version=1,
            effective_date=date(2026, 9, 1),
            status="approved",
            approved_by=self.manager,
            approved_at=timezone.now(),
            approval_reason="Synthetic isolated validation fixture",
        )
        url = self.context_url("billing:claim_create", "contract", self.contract)
        for values, error in (
            ({"contract": other.pk}, "contract"),
            ({"baseline": foreign_baseline.pk}, "baseline"),
            ({"project": "00000000-0000-0000-0000-000000000001"}, "__all__"),
        ):
            response = self.client.post(url, self.claim_data(baseline, **values))
            self.assert_parent(response, "contract", self.contract)
            self.assertIn(error, response.context["form"].errors)
        self.assertFalse(ProgressClaim.objects.exists())

    def test_foreign_tenant_invalid_and_ambiguous_contexts_fail_closed(self):
        organization = Organization.objects.create(
            name="Other tenant", slug="ctx-other"
        )
        project = Project.objects.create(
            organization=organization, code="CTX-PRIVATE", name="پروژه محرمانه"
        )
        contract = Contract.objects.create(
            organization=organization,
            project=project,
            contract_number="PRIVATE-C",
            title="قرارداد محرمانه",
            counterparty_name="طرف محرمانه",
            direction="receivable",
            status="active",
        )
        for route, name, parent in (
            ("estimates:create", "project", project),
            ("contracts:create", "project", project),
            ("billing:claim_create", "contract", contract),
        ):
            for method in (self.client.get, self.client.post):
                response = method(self.context_url(route, name, parent))
                self.assertEqual(response.status_code, 404)
                self.assertNotContains(
                    response,
                    parent.name if name == "project" else parent.title,
                    status_code=404,
                )
            for query in (
                f"{name}=",
                f"{name}=invalid",
                f"{name}={parent.pk}&{name}={parent.pk}",
            ):
                self.assertEqual(
                    self.client.get(reverse(route) + "?" + query).status_code, 404
                )

    def test_stale_parent_and_revoked_membership_are_rechecked_on_submission(self):
        url = self.context_url("estimates:create", "project", self.project)
        self.assertEqual(self.client.get(url).status_code, 200)
        Project.objects.filter(pk=self.project.pk).update(deleted_at=timezone.now())
        self.assertEqual(self.client.post(url, self.estimate_data()).status_code, 404)
        Project.objects.filter(pk=self.project.pk).update(deleted_at=None)
        self.organization.memberships.filter(user=self.owner).update(status="removed")
        self.assertEqual(self.client.post(url, self.estimate_data()).status_code, 403)
        self.assertFalse(Estimate.objects.exists())

    def test_global_application_project_remains_separate_and_general_form_editable(
        self,
    ):
        other = Project.objects.create(
            organization=self.organization, code="CTX-GLOBAL", name="پروژه فعال دیگر"
        )
        session = self.client.session
        session["active_project_id"] = str(other.pk)
        session.save()
        before = dict(self.client.session)
        for route in ("estimates:create", "contracts:create"):
            self.assert_parent(
                self.client.get(self.context_url(route, "project", self.project)),
                "project",
                self.project,
            )
            general = self.client.get(reverse(route))
            self.assertIn("project", ParentMarkup(general).selects)
            self.assertEqual(dict(self.client.session), before)

    def test_explicit_project_scope_and_create_permission_are_both_required(self):
        from apps.accounts.models import User
        from apps.organizations.models import (
            BusinessPermission,
            MembershipRoleAssignment,
            MembershipScopeGrant,
            OrganizationRole,
        )

        actor = User.objects.create_user(username="ctx-scoped-creator")
        role = OrganizationRole.objects.create(
            organization=self.organization, code="ctx-creator", name="ایجادکننده"
        )
        role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=("projects.view", "estimates.create", "contracts.create")
            )
        )
        membership = self.organization.memberships.create(
            user=actor, status="active", role_definition=role
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="Explicit contextual-create test role",
        )
        other = Project.objects.create(
            organization=self.organization, code="CTX-SCOPE", name="پروژه مجاز"
        )
        grant = MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="project",
            project=other,
            reason="Explicit test scope",
        )
        self.login(actor)
        for route, data in (
            ("estimates:create", self.estimate_data()),
            ("contracts:create", self.contract_data()),
        ):
            url = self.context_url(route, "project", self.project)
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url, data).status_code, 404)
        grant.project = self.project
        grant.save()
        for route in ("estimates:create", "contracts:create"):
            self.assert_parent(
                self.client.get(self.context_url(route, "project", self.project)),
                "project",
                self.project,
            )
        role.permissions.remove(
            *BusinessPermission.objects.filter(
                code__in=("estimates.create", "contracts.create")
            )
        )
        for route, data in (
            ("estimates:create", self.estimate_data()),
            ("contracts:create", self.contract_data()),
        ):
            url = self.context_url(route, "project", self.project)
            self.assertEqual(self.client.post(url, data).status_code, 403)
        self.assertFalse(Estimate.objects.exists())
        self.assertEqual(Contract.objects.count(), 1)

    def test_contract_and_baseline_lifecycle_is_rechecked_after_form_load(self):
        baseline = self._approved_baseline()
        url = self.context_url("billing:claim_create", "contract", self.contract)
        self.assertEqual(self.client.get(url).status_code, 200)
        Contract.objects.filter(pk=self.contract.pk).update(status="closed")
        self.assertEqual(
            self.client.post(url, self.claim_data(baseline)).status_code, 404
        )
        Contract.objects.filter(pk=self.contract.pk).update(status="active")
        replacement = self._approved_baseline()
        baseline.refresh_from_db()
        self.assertEqual(baseline.superseded_by_id, replacement.pk)
        response = self.client.post(url, self.claim_data(baseline))
        self.assert_parent(response, "contract", self.contract)
        self.assertIn("baseline", response.context["form"].errors)
        self.assertFalse(ProgressClaim.objects.exists())

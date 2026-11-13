"""Regression coverage for the B07 tenant, workflow, and master-data fixes."""

from uuid import uuid4

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounting.test_cep042_regression import explicit_fixture_authority
from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.materials import test_cep031 as material_fixtures
from apps.organizations import tests as organization_fixtures
from apps.organizations.forms import (
    MembershipRoleAssignmentForm,
    MembershipScopeGrantForm,
)
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipStatus,
    OrganizationRole,
)
from apps.organizations.services import request_existing_account_connection
from apps.parties import services as party_services
from apps.parties import test_cep030 as party_fixtures
from apps.parties.models import BusinessParty, PartyRole
from apps.procurement.tests import ProcurementFixtureMixin
from apps.projects.models import Project
from apps.workflows import test_workbench as workflow_fixtures
from core.forms import parse_jalali_datetime


class TenantFormRegressionTests(TestCase):
    setUp = organization_fixtures.OwnerAccountManagementTests.setUp

    def test_membership_expiry_forms_share_jalali_input_and_aware_storage(self):
        approver = User.objects.create_user(username="b07-date-approver")
        approver_membership = self.organization.memberships.create(
            user=approver, role_definition=self.owner_role, status=MembershipStatus.ACTIVE
        )
        actor_membership = self.organization.memberships.get(user=self.owner)
        project = Project.objects.create(
            organization=self.organization, code="B07-DATE", name="Expiry test project"
        )
        kwargs = {
            "organization": self.organization,
            "actor_membership": actor_membership,
            "target_membership": self.member_membership,
        }
        fields = {
            "approver_membership": approver_membership.pk,
            "reason": "Synthetic expiry qualification",
            "ends_at": "1405/12/20 10:30",
        }
        forms = (
            MembershipRoleAssignmentForm(
                data={**fields, "role": self.member_role.pk}, **kwargs
            ),
            MembershipScopeGrantForm(
                data={**fields, "scope_type": "project", "project": project.pk}, **kwargs
            ),
        )
        for form in forms:
            with self.subTest(form=type(form).__name__):
                self.assertEqual(
                    form.fields["ends_at"].widget.attrs["data-jalali-date"], "datetime"
                )
                self.assertTrue(form.is_valid(), form.errors)
                expiry = form.cleaned_data["ends_at"]
                self.assertTrue(timezone.is_aware(expiry))
                self.assertEqual(
                    timezone.localtime(expiry).replace(tzinfo=None),
                    parse_jalali_datetime(fields["ends_at"]),
                )

    def test_status_form_saves_without_the_disabled_role_field(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("organizations:member_update", args=[self.member_membership.pk]),
            {"status": MembershipStatus.SUSPENDED},
        )
        self.assertRedirects(response, reverse("organizations:members"))
        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.status, MembershipStatus.SUSPENDED)
        self.assertEqual(self.member_membership.role_definition, self.member_role)
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.MEMBERSHIP_STATUS_CHANGED,
                organization=self.organization,
                actor=self.owner,
            ).count(),
            1,
        )

    def test_view_only_authorization_keeps_history_and_hides_mutation_controls(self):
        reader = User.objects.create_user(username="b07-grants-reader")
        role = OrganizationRole.objects.create(
            organization=self.organization, code="grant-reader", name="Grant reader"
        )
        role.permissions.set(
            BusinessPermission.objects.filter(
                code__in=[
                    BusinessPermissionCode.MEMBERSHIP_VIEW,
                    BusinessPermissionCode.AUTHORIZATION_ROLES_VIEW,
                    BusinessPermissionCode.AUTHORIZATION_GRANTS_VIEW,
                ]
            )
        )
        reader_membership = self.organization.memberships.create(
            user=reader, role_definition=role, status=MembershipStatus.ACTIVE
        )
        explicit_fixture_authority(reader_membership, role)
        explicit_fixture_authority(self.member_membership, self.member_role)
        self.client.force_login(reader)

        response = self.client.get(
            reverse("organizations:member_authorization", args=[self.member_membership.pk])
        )

        self.assertContains(response, self.member_role.name)
        self.assertNotContains(response, 'name="action" value="assign_role"')
        self.assertNotContains(response, 'name="action" value="revoke_role"')
        self.assertNotContains(response, 'name="action" value="grant_scope"')
        self.assertNotContains(response, 'name="action" value="revoke_scope"')

    def test_invalid_provisioning_retains_username_without_echoing_credentials(self):
        self.client.force_login(self.owner)
        password = "Synthetic-Provisioning-81!"
        confirmation = "Synthetic-Provisioning-82!"
        response = self.client.post(
            reverse("organizations:account_create"),
            {
                "action": "create",
                "create-username": "b07-new-user",
                "create-first_name": "کاربر",
                "create-last_name": "آزمایشی",
                "create-role_definition": self.member_role.code,
                "create-temporary_password": password,
                "create-temporary_password_confirm": confirmation,
            },
        )
        self.assertContains(response, 'value="b07-new-user"')
        self.assertNotContains(response, password)
        self.assertNotContains(response, confirmation)
        self.assertFalse(User.objects.filter(username="b07-new-user").exists())

    def test_missing_or_unknown_connection_decision_preserves_pending_request(self):
        target = User.objects.create_user(username="b07-connection-target")
        pending = request_existing_account_connection(
            organization=self.organization,
            actor=self.owner,
            username=target.username,
            role=self.member_role,
        )
        self.client.force_login(target)
        route = reverse("accounts:connection_request_respond", args=[pending.pk])
        audit_before = AuditEvent.objects.count()

        for data in ({}, {"decision": "unknown"}):
            with self.subTest(data=data):
                response = self.client.post(route, data, follow=True)
                self.assertContains(response, "پذیرش یا رد درخواست را انتخاب کنید.")
                pending.refresh_from_db()
                self.assertEqual(pending.status, "pending")
                self.assertFalse(target.organization_memberships.exists())
                self.assertEqual(AuditEvent.objects.count(), audit_before)


class PartyRegressionTests(TestCase):
    setUp = party_fixtures.PartySurfaceTests.setUp
    member = party_fixtures.PartySurfaceTests.member
    login = party_fixtures.PartySurfaceTests.login
    url = party_fixtures.PartySurfaceTests.url

    def test_operational_party_list_offers_one_management_entry(self):
        response = self.client.get(self.url("list"))
        self.assertContains(response, f'href="{self.url("governance")}"', count=1)

    def test_canonical_merge_reference_cannot_be_archived(self):
        survivor = party_services.create_business_party(
            actor=self.owner,
            organization=self.organization,
            party_kind="company",
            display_name="مرجع آزمایشی",
        )
        party_services.record_business_party_merge(
            actor=self.owner,
            organization=self.organization,
            source=self.party,
            survivor=survivor,
            reason="تأیید هویت یکسان",
        )
        archive_url = self.url("archive", survivor)
        response = self.client.get(self.url("governance_detail", survivor))
        self.assertNotContains(response, f'action="{archive_url}"')
        audit_before = AuditEvent.objects.count()

        response = self.client.post(archive_url)
        self.assertContains(
            response, "طرف تجاری مرجع ادغام قابل بایگانی نیست", status_code=403
        )
        self.party.refresh_from_db()
        survivor.refresh_from_db()
        self.assertEqual(self.party.merged_into_id, survivor.pk)
        self.assertIsNone(survivor.archived_at)
        self.assertEqual(AuditEvent.objects.count(), audit_before)


class MaterialsGovernanceRegressionTests(TestCase):
    setUp = material_fixtures.MaterialsGovernanceSurfaceTests.setUp
    member = material_fixtures.MaterialsGovernanceSurfaceTests.member
    login = material_fixtures.MaterialsGovernanceSurfaceTests.login
    url = material_fixtures.MaterialsGovernanceSurfaceTests.url

    def test_invalid_material_context_fails_closed_for_reads_and_writes(self):
        audit_before = AuditEvent.objects.count()
        for value in ("", "not-a-uuid", str(uuid4())):
            with self.subTest(value=value):
                if value:
                    response = self.client.get(self.url(), {"material": value})
                    self.assertEqual(response.status_code, 404)
                    self.assertIn("no-store", response["Cache-Control"])
                response = self.client.post(
                    self.url("alias"),
                    {
                        "material": value,
                        "alias-code": "B07-UNAVAILABLE",
                        "alias-reason": "Synthetic malformed reference",
                    },
                )
                self.assertEqual(response.status_code, 404)
                self.assertIn("no-store", response["Cache-Control"])
        self.assertFalse(self.material.aliases.exists())
        self.assertEqual(AuditEvent.objects.count(), audit_before)


class OrderSupplierRegressionTests(ProcurementFixtureMixin, TestCase):
    def test_create_choices_require_active_local_supplier_role(self):
        inactive = BusinessParty.objects.create(
            organization=self.organization,
            party_kind="company",
            display_name="Inactive supplier role",
        )
        PartyRole.objects.create(
            organization=self.organization,
            party=inactive,
            role="supplier",
            is_active=False,
        )
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("procurement:order_choices", args=["create", "supplier"])
        )
        self.assertContains(response, str(self.supplier.pk))
        self.assertNotContains(response, str(inactive.pk))
        self.assertNotContains(response, str(self.other_supplier.pk))


class WorkbenchRejectionRegressionTests(ProcurementFixtureMixin, TestCase):
    _submitted_request = workflow_fixtures.WorkbenchTests._submitted_request
    _item = workflow_fixtures.WorkbenchTests._item

    def test_purchase_request_rejection_points_to_the_existing_reason_form(self):
        request = self._submitted_request("B07-REJECT-REASON")
        item = self._item(request)
        self.client.force_login(self.owner)
        self.client.post(
            reverse("workflows:work_item_claim", args=[item.pk]),
            {"idempotency_key": "b07-claim"},
        )

        response = self.client.get(reverse("workflows:workbench"))
        self.assertContains(response, "مشاهده جزئیات و رد درخواست")
        self.assertNotContains(response, 'name="outcome" value="rejected"')
        self.assertContains(response, 'name="outcome" value="approved"')
        response = self.client.get(reverse("procurement:request_detail", args=[request.pk]))
        self.assertContains(response, 'name="reject-reason"')

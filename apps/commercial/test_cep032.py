"""CEP-032: Commercial source, fail-closed lifecycle and tenant authority."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.commercial.models import (
    TenderBid,
    TenderBidActivation,
    TenderBidRevision,
    TenderBidStatus,
)
from apps.commercial.services import (
    create_tender_bid,
    get_tender_bid,
    list_tender_bids,
    revise_tender_bid,
    transition_tender_bid,
)
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipScopeGrant,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.models import (
    BusinessPermissionCode as P,
)
from apps.projects.models import Project


class TenderBidLifecycleTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="CEP032", slug="cep032")
        self.other = Organization.objects.create(name="Other", slug="cep032-other")
        self.actor = self.member(
            "owner",
            {P.TENDER_BIDS_VIEW, P.TENDER_BIDS_PREPARE, P.TENDER_BIDS_TRANSITION},
        )
        self.viewer = self.member("viewer", {P.TENDER_BIDS_VIEW})
        self.outsider = User.objects.create_user(username="cep032-outsider")

    def member(self, label, codes):
        user = User.objects.create_user(username="cep032-" + label)
        role = OrganizationRole.objects.create(code="cep032-" + label, name=label)
        role.permissions.set(BusinessPermission.objects.filter(code__in=codes))
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            role_definition=role,
            status="active",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="CEP-032 test scope",
        )
        return user

    def activate(self):
        TenderBidActivation.objects.create(
            organization=self.organization,
            is_active=True,
            policy_reference="approved-test-policy",
            activated_by=self.actor,
        )

    def test_project_scoped_create_selects_only_authorized_tenant_project(self):
        self.activate()
        project = Project.objects.create(
            organization=self.organization, code="SCOPED", name="Allowed project"
        )
        foreign = Project.objects.create(
            organization=self.other, code="FOREIGN", name="Foreign project"
        )
        membership = self.organization.memberships.get(user=self.actor)
        membership.scope_grants.update(
            scope_type=AuthorizationScopeType.PROJECT, project=project
        )
        self.login(self.actor)
        url = reverse("commercial:tender_create")
        response = self.client.get(url)
        self.assertContains(response, "Allowed project")
        self.assertNotContains(response, "Foreign project")
        response = self.client.post(
            url,
            {
                "opportunity_code": "SCOPED-CREATE",
                "title": "Scoped opportunity",
                "project": str(project.pk),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            TenderBid.objects.get(opportunity_code="SCOPED-CREATE").project_id,
            project.pk,
        )
        response = self.client.post(
            url,
            {
                "opportunity_code": "FORGED",
                "title": "Forged",
                "project": str(foreign.pk),
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(TenderBid.objects.filter(opportunity_code="FORGED").exists())

    def test_evidence_picker_rejects_unknown_or_unavailable_source_without_revision(
        self,
    ):
        self.activate()
        tender = self.create()
        self.login(self.actor)
        response = self.client.get(
            reverse("commercial:tender_detail", args=[tender.pk])
        )
        self.assertContains(response, '<select name="document_version_id"')
        self.assertNotContains(
            response, '<input type="text" name="document_version_id"'
        )
        response = self.client.post(
            reverse("commercial:tender_evidence", args=[tender.pk]),
            {"document_version_id": "00000000-0000-0000-0000-000000000001"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(tender.revisions.count(), 1)

    def create(self):
        return create_tender_bid(
            actor=self.actor,
            organization=self.organization,
            opportunity_code="t-01",
            title="Contractor opportunity",
        )

    def login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

    def test_workspace_empty_detail_and_policy_absent_error(self):
        self.login(self.actor)
        response = self.client.get(reverse("commercial:tender_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "سیاست وضعیت و جزئیات مناقصه هنوز فعال نشده است")
        response = self.client.post(
            reverse("commercial:tender_create"),
            {
                "opportunity_code": "T-01",
                "title": "Denied without policy",
                "description": "",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.activate()
        tender = self.create()
        response = self.client.get(
            reverse("commercial:tender_detail", args=[tender.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contractor opportunity")
        self.assertContains(response, "تاریخچه محفوظ")
        self.login(self.viewer)
        response = self.client.post(
            reverse("commercial:tender_transition", args=[tender.pk]),
            {
                "target": "submitted",
                "reason": "denied",
                "submission_reference": "x",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.login(self.outsider)
        response = self.client.get(reverse("commercial:tender_list"))
        self.assertIn(response.status_code, (302, 403))

    def test_policy_absence_and_permission_fail_closed(self):
        with self.assertRaises(PermissionDenied):
            self.create()
        self.assertFalse(
            list_tender_bids(actor=self.viewer, organization=self.organization).exists()
        )
        self.activate()
        with self.assertRaises(PermissionDenied):
            create_tender_bid(
                actor=self.viewer,
                organization=self.organization,
                opportunity_code="t-01",
                title="Denied",
            )
        with self.assertRaises(PermissionDenied):
            create_tender_bid(
                actor=self.outsider,
                organization=self.organization,
                opportunity_code="t-01",
                title="Denied",
            )

    def test_exact_transitions_and_immutable_submitted_history(self):
        self.activate()
        tender = self.create()
        with self.assertRaises(ValueError):
            transition_tender_bid(
                actor=self.actor,
                organization=self.organization,
                tender_id=str(tender.pk),
                target=TenderBidStatus.WON,
                reason="skip",
            )
        with self.assertRaises(ValueError):
            transition_tender_bid(
                actor=self.actor,
                organization=self.organization,
                tender_id=str(tender.pk),
                target=TenderBidStatus.SUBMITTED,
                reason="submitted without proof",
            )
        submitted = transition_tender_bid(
            actor=self.actor,
            organization=self.organization,
            tender_id=str(tender.pk),
            target=TenderBidStatus.SUBMITTED,
            reason="sent",
            submission_reference="dispatch-1",
        )
        revised = revise_tender_bid(
            actor=self.actor,
            organization=self.organization,
            tender_id=str(tender.pk),
            title="Corrected title",
            description="corrected",
            submission_reference="dispatch-1",
            result_reference="",
            bid_bond_reference="bond-ref",
            bid_cost_reference="cost-ref",
            reason="documented correction",
        )
        self.assertEqual((submitted.version, revised.version), (2, 3))
        self.assertEqual(submitted.title, "Contractor opportunity")
        self.assertEqual(revised.previous_revision_id, submitted.pk)
        with self.assertRaises(ValidationError):
            submitted.title = "silent overwrite"
            submitted.save()
        with self.assertRaises(ValidationError):
            TenderBidRevision.objects.filter(pk=submitted.pk).update(title="silent")
        review = transition_tender_bid(
            actor=self.actor,
            organization=self.organization,
            tender_id=str(tender.pk),
            target=TenderBidStatus.UNDER_REVIEW,
            reason="under review",
        )
        with self.assertRaises(ValueError):
            transition_tender_bid(
                actor=self.actor,
                organization=self.organization,
                tender_id=str(tender.pk),
                target=TenderBidStatus.WON,
                reason="missing result",
            )
        won = transition_tender_bid(
            actor=self.actor,
            organization=self.organization,
            tender_id=str(tender.pk),
            target=TenderBidStatus.WON,
            reason="outcome received",
            result_reference="notice-1",
        )
        self.assertEqual((review.version, won.version), (4, 5))
        with self.assertRaises(ValueError):
            transition_tender_bid(
                actor=self.actor,
                organization=self.organization,
                tender_id=str(tender.pk),
                target=TenderBidStatus.LOST,
                reason="terminal",
            )
        self.assertEqual(tender.revisions.count(), 5)
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.TENDER_BID_REVISED,
                entity_id=str(tender.pk),
            ).exists()
        )

    def test_tenant_isolation_and_no_cross_domain_effect(self):
        self.activate()
        tender = self.create()
        with self.assertRaises(PermissionDenied):
            get_tender_bid(
                actor=self.actor, organization=self.other, tender_id=str(tender.pk)
            )
        with self.assertRaises(PermissionDenied):
            transition_tender_bid(
                actor=self.actor,
                organization=self.other,
                tender_id=str(tender.pk),
                target=TenderBidStatus.SUBMITTED,
                reason="cross-tenant",
                submission_reference="x",
            )
        self.assertEqual(
            list_tender_bids(actor=self.actor, organization=self.organization).count(),
            1,
        )
        self.assertEqual(tender.revisions.count(), 1)

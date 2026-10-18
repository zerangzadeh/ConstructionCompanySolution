"""CEP-032 buyer workspace stays on Procurement source and object scope."""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipScopeGrant,
    OrganizationRole,
)
from apps.organizations.models import (
    BusinessPermissionCode as P,
)
from apps.organizations.services import set_active_organization
from apps.procurement.models import (
    PurchaseRequest,
    PurchaseRequestItem,
    PurchaseRequestStatus,
)
from apps.procurement.rfq_services import add_rfq_line, create_rfq
from apps.procurement.tests import ProcurementFixtureMixin


class RFQBuyerWorkspaceTests(ProcurementFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.approved_request = PurchaseRequest.objects.create(
            organization=self.organization,
            project=self.project,
            request_number="CEP032-PR",
            title="Approved source request",
            status=PurchaseRequestStatus.DRAFT,
            created_by=self.member,
        )
        self.approved_item = PurchaseRequestItem.objects.create(
            organization=self.organization,
            purchase_request=self.approved_request,
            material=self.material,
            unit_of_measure=self.unit,
            description="Cement",
            quantity=Decimal(10),
            created_by=self.member,
        )
        PurchaseRequest.objects.filter(pk=self.approved_request.pk).update(
            status=PurchaseRequestStatus.APPROVED,
            approved_by=self.owner,
            approved_at=timezone.now(),
        )
        self.approved_request.refresh_from_db()
        role = OrganizationRole.objects.create(code="cep032-buyer", name="CEP032 buyer")
        role.permissions.set(
            BusinessPermission.objects.filter(
                code__in=[
                    P.RFQS_VIEW,
                    P.RFQS_CREATE,
                    P.RFQS_CHANGE,
                    P.RFQS_SUBMIT,
                    P.PURCHASE_REQUESTS_VIEW,
                ]
            )
        )
        membership = self.organization.memberships.get(user=self.member)
        membership.role_definition = role
        membership.save(update_fields=["role_definition"])
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="CEP-032 buyer test",
        )

    def login(self, user):
        self.client.force_login(user)
        session = self.client.session
        set_active_organization(session, self.organization)
        session.save()

    def test_empty_and_authorized_detail_with_source_link(self):
        self.login(self.member)
        response = self.client.get(reverse("procurement:rfq_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "استعلامی وجود ندارد")
        purchase_request, item = self.approved_request, self.approved_item
        rfq = create_rfq(
            organization=self.organization,
            actor=self.member,
            project=self.project,
            purchase_request=purchase_request,
            rfq_number="cep032-rfq",
            title="Buyer workspace RFQ",
            closing_at=timezone.now() + timedelta(days=2),
            earliest_opening_at=timezone.now() + timedelta(days=2),
        )
        add_rfq_line(
            organization=self.organization,
            actor=self.member,
            rfq=rfq,
            purchase_request_item=item,
            quantity=Decimal(5),
        )
        response = self.client.get(reverse("procurement:rfq_detail", args=[rfq.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Buyer workspace RFQ")
        self.assertContains(
            response, reverse("procurement:request_detail", args=[purchase_request.pk])
        )
        self.assertContains(response, "نمایش فراداده پیشنهاد نیازمند مجوز جداگانه")

    def test_foreign_tenant_and_unauthorized_state_do_not_leak(self):
        self.login(self.member)
        response = self.client.get(
            reverse("procurement:rfq_detail", args=[self.other_project.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.login(self.outsider)
        response = self.client.get(reverse("procurement:rfq_list"))
        self.assertIn(response.status_code, (403, 302))

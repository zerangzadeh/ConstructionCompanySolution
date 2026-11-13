from datetime import datetime
from datetime import timezone as datetime_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.inventory.models import (
    InventoryTransferStatus,
    StockTransaction,
    StockTransactionType,
)
from apps.inventory.p8_services import (
    TransferLineSpec,
    create_inventory_transfer,
    dispatch_inventory_transfer,
    mark_transfer_in_transit,
)
from apps.inventory.services import create_warehouse, get_stock_balance
from apps.inventory.tests import InventoryFixtureMixin
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipScopeGrant,
    MembershipStatus,
    OrganizationRole,
    OrganizationSettings,
)
from apps.organizations.services import set_active_organization
from apps.projects.models import Project
from core.home import authorized_home_links
from core.jalali import format_jalali


class InboundTransferFixture(InventoryFixtureMixin):
    def setUp(self):
        super().setUp()
        OrganizationSettings.objects.create(
            organization=self.organization, timezone="Asia/Tehran"
        )
        OrganizationSettings.objects.create(
            organization=self.other_organization, timezone="Asia/Tehran"
        )
        self.shipping_project = Project.objects.create(
            organization=self.organization, code="SHIP", name="پروژه ارسال آزمایشی"
        )
        self.sibling_project = Project.objects.create(
            organization=self.organization, code="SIBLING", name="پروژه مجاور آزمایشی"
        )
        self.source = self.warehouse(
            "SOURCE", "انبار ارسال آزمایشی", self.shipping_project
        )
        self.second_destination = self.warehouse(
            "SECOND", "انبار دوم آزمایشی", self.project
        )
        self.sibling_destination = self.warehouse(
            "SIBLING", "انبار مجاور آزمایشی", self.sibling_project
        )
        self.receiver = self.scoped_actor("inbound-receiver", self.project)
        self.sender = self.scoped_actor("inbound-sender", self.shipping_project)
        self.sibling = self.scoped_actor("inbound-sibling", self.sibling_project)
        self.create_and_post(
            number="INBOUND-OPENING",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal(12),
            destination=self.source,
            project=self.shipping_project,
            actor=self.owner,
        )
        self.first = self.transfer("INBOUND-FIRST", self.site, quantity=3)
        self.second = self.transfer("INBOUND-SECOND", self.second_destination)
        self.hidden = self.transfer("SIBLING-INBOUND", self.sibling_destination)
        self.dispatched = self.transfer("AWAITING-TRANSIT", self.site, in_transit=False)

    def warehouse(self, code, name, project):
        return create_warehouse(
            organization=self.organization,
            actor=self.owner,
            code=code,
            name=name,
            project=project,
        )

    def scoped_actor(self, username, project, role_definition=None):
        actor = User.objects.create_user(username=username)
        membership = self.organization.memberships.create(
            user=actor,
            role=MembershipRole.COMPANY_MANAGER,
            status=MembershipStatus.ACTIVE,
            **({"role_definition": role_definition} if role_definition else {}),
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.PROJECT,
            project=project,
            reason="Synthetic inbound transfer scope",
        )
        return actor

    def transfer(self, reference, destination, *, quantity=1, in_transit=True):
        transfer = create_inventory_transfer(
            organization=self.organization,
            actor=self.owner,
            transfer_number=reference,
            source_warehouse=self.source,
            destination_warehouse=destination,
            lines=[TransferLineSpec(self.material, Decimal(quantity))],
        )
        transfer = dispatch_inventory_transfer(
            organization=self.organization,
            actor=self.owner,
            inventory_transfer=transfer,
        )
        if in_transit:
            transfer = mark_transfer_in_transit(
                organization=self.organization,
                actor=self.owner,
                inventory_transfer=transfer,
            )
        return transfer


class InboundTransferTests(InboundTransferFixture, TestCase):
    def sign_in(self, actor, organization=None):
        self.client.force_login(actor)
        session = self.client.session
        set_active_organization(session, organization or self.organization)
        session.save()

    def test_receiver_discovers_filters_accepts_and_finds_history(self):
        self.sign_in(self.receiver)
        workbench = reverse("inventory:custody_workbench")
        inbound = reverse("inventory:custody_workbench", query={"tab": "inbound"})
        self.assertContains(
            self.client.get(reverse("inventory:warehouse_list")), f'href="{inbound}"'
        )
        response = self.client.get(inbound)
        self.assertContains(response, "انتقال‌های ورودی در انتظار دریافت")
        self.assertContains(response, self.first.transfer_number)
        self.assertContains(response, self.second.transfer_number)
        self.assertContains(response, self.source.name)
        self.assertContains(response, self.material.name)
        self.assertContains(response, "مشاهده و دریافت", count=2)
        self.assertNotContains(response, self.hidden.transfer_number)
        self.assertNotContains(response, self.dispatched.transfer_number)
        self.assertNotContains(response, "خلاصه موجودی شرکت")
        # The tenant has crossed midnight while UTC is still on the preceding date.
        dispatched_at = datetime(2026, 11, 11, 22, 0, tzinfo=datetime_timezone.utc)
        type(self.first).objects.filter(pk=self.first.pk).update(
            dispatched_at=dispatched_at
        )
        expected = format_jalali(
            dispatched_at.astimezone(ZoneInfo("Asia/Tehran")).date()
        )
        self.assertContains(self.client.get(inbound), expected)

        filtered = self.client.get(
            workbench, {"tab": "inbound", "q": "first", "destination": self.site.pk}
        )
        self.assertContains(filtered, self.first.transfer_number)
        self.assertNotContains(filtered, self.second.transfer_number)
        forged = self.client.get(
            workbench, {"tab": "inbound", "destination": self.sibling_destination.pk}
        )
        self.assertContains(forged, "انبار مقصد را از گزینه‌های مجاز انتخاب کنید.")
        self.assertNotContains(forged, self.first.transfer_number)
        self.assertNotContains(forged, self.sibling_destination.name)

        detail = reverse(
            "inventory:transfer_detail", args=[self.first.pk], query={"tab": "inbound"}
        )
        accept = reverse(
            "inventory:transfer_accept", args=[self.first.pk], query={"tab": "inbound"}
        )
        response = self.client.get(detail)
        self.assertEqual(response.context["breadcrumb_url"], inbound)
        self.assertContains(response, f'action="{accept}"')
        line = self.first.lines.get()
        payload = {f"accepted_{line.pk}": "3"}
        for _ in range(2):
            self.assertRedirects(
                self.client.post(accept, payload), detail, fetch_redirect_response=False
            )
        self.first.refresh_from_db()
        line.refresh_from_db()
        self.assertEqual(self.first.status, InventoryTransferStatus.ACCEPTED)
        self.assertEqual(self.first.accepted_by, self.receiver)
        self.assertIsNotNone(line.receipt_transaction_id)
        self.assertEqual(
            StockTransaction.objects.filter(
                organization=self.organization, reference=self.first.transfer_number
            ).count(),
            2,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                entity_id=str(self.first.pk),
                action=AuditAction.INVENTORY_TRANSFER_TRANSITIONED,
            ).count(),
            4,
        )
        self.assertEqual(
            get_stock_balance(
                user=self.owner,
                organization=self.organization,
                warehouse=self.site,
                material=self.material,
            ),
            Decimal(3),
        )
        pending = self.client.get(inbound)
        self.assertNotContains(pending, self.first.transfer_number)
        self.assertContains(pending, self.second.transfer_number)
        empty_destination = self.client.get(
            workbench, {"tab": "inbound", "destination": self.site.pk}
        )
        self.assertContains(
            empty_destination, "انتقالی با جست‌وجو و فیلترهای فعلی پیدا نشد."
        )
        self.assertFalse(empty_destination.context["filter_bar"]["form"].errors)
        history = self.client.get(workbench, {"tab": "transfer-history"})
        self.assertContains(history, self.first.transfer_number)
        self.assertContains(history, "پذیرفته‌شده")
        self.assertNotContains(history, self.second.transfer_number)
        self.assertNotContains(history, self.hidden.transfer_number)

    def test_destination_scope_and_independence_preserve_existing_outbound_access(self):
        inbound = reverse("inventory:custody_workbench", query={"tab": "inbound"})
        detail = reverse("inventory:transfer_detail", args=[self.first.pk])
        accept = reverse("inventory:transfer_accept", args=[self.first.pk])
        payload = {f"accepted_{self.first.lines.get().pk}": "3"}
        for actor, organization, detail_status in (
            (self.sender, self.organization, 200),
            (self.sibling, self.organization, 404),
            (self.outsider, self.other_organization, 404),
        ):
            with self.subTest(actor=actor):
                self.sign_in(actor, organization)
                response = self.client.get(inbound)
                self.assertNotContains(response, self.first.transfer_number)
                self.assertNotContains(response, self.site.name)
                self.assertEqual(self.client.get(detail).status_code, detail_status)
                self.assertEqual(self.client.post(accept, payload).status_code, 404)
        self.sign_in(self.owner)
        self.assertContains(self.client.get(inbound), "در حال حاضر انتقالی برای دریافت")
        self.assertNotContains(self.client.get(inbound), self.first.transfer_number)
        self.assertNotContains(self.client.get(detail), "ثبت پذیرش مستقل")
        self.assertEqual(self.client.post(accept, payload).status_code, 302)
        self.first.refresh_from_db()
        self.assertEqual(self.first.status, InventoryTransferStatus.IN_TRANSIT)
        self.sign_in(self.viewer)
        self.assertEqual(self.client.get(inbound).status_code, 403)

    def test_receiving_only_role_can_open_workbench_from_shared_navigation(self):
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="inbound-only",
            name="Synthetic receiver",
        )
        role.permissions.set(
            BusinessPermission.objects.filter(
                code__in=[
                    BusinessPermissionCode.INVENTORY_TRANSFERS_VIEW,
                    BusinessPermissionCode.INVENTORY_TRANSFERS_ACCEPT,
                ]
            )
        )
        actor = self.scoped_actor("inbound-only", self.project, role_definition=role)
        self.sign_in(actor)
        workbench = reverse("inventory:custody_workbench")
        self.assertEqual(
            self.client.get(reverse("inventory:warehouse_list")).status_code, 403
        )
        response = self.client.get(workbench)
        self.assertContains(response, self.first.transfer_number)
        self.assertContains(response, f'href="{workbench}"')
        self.assertNotContains(response, "خلاصه موجودی شرکت")
        links, _, _ = authorized_home_links(user=actor, organization=self.organization)
        self.assertIn("inventory:custody_workbench", {link.route for link in links})

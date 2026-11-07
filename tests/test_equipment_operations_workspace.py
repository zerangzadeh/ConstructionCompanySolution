"""Equipment workspace presentation against real, tenant-scoped HTTP data."""

from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.equipment.models import Equipment
from apps.equipment.p8_models import EquipmentWorkOrder
from apps.organizations.models import BusinessPermission, MembershipScopeGrant
from tests.test_warehouse_reference_list import WarehouseListFixture


@override_settings(PRODUCT_SURFACE_PROFILE="MVP")
class EquipmentOperationsWorkspaceTests(WarehouseListFixture, TestCase):
    def setUp(self):
        self.make_fixture()
        self.equipment = Equipment.objects.create(
            organization=self.organization,
            code="WORKSPACE-EQ",
            name="تجهیز آزمون فضای عملیات",
            category="ماشین‌آلات",
        )
        self.url = reverse("equipment:operations_workbench")
        self.login(self.owner)

    def order(self, number, **kwargs):
        return EquipmentWorkOrder.objects.create(
            organization=self.organization,
            equipment=self.equipment,
            number=number,
            summary="موضوع دستورکار آزمون",
            created_by=self.owner,
            **kwargs,
        )

    def test_empty_workspace_preserves_all_actions_and_truthful_summary(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "هنوز دستورکار تعمیراتی ثبت نشده است")
        self.assertContains(response, "حداکثر ۵۰ رکورد")
        self.assertContains(response, "۰ دستورکار نمایش‌داده‌شده")
        self.assertNotContains(response, "<table")
        for name in (
            "list",
            "meter_reading_create",
            "usage_create",
            "fuel_create",
            "downtime_create",
            "work_order_create",
            "operator_qualification_create",
            "maintenance_plan_create",
            "cost_workbench",
        ):
            self.assertContains(response, f'href="{reverse(f"equipment:{name}")}"')
        self.assertContains(response, 'href="?format=xlsx"')

    def test_real_work_orders_keep_dates_statuses_evidence_and_finalized_actions(self):
        active = self.order(
            "WS-OPEN", scheduled_for=timezone.localdate() - timedelta(days=1)
        )
        completed = self.order("WS-DONE", status="completed")
        response = self.client.get(self.url)
        self.assertContains(response, "موضوع دستورکار آزمون")
        self.assertContains(response, "گذشته از موعد", count=1)
        self.assertContains(response, "erp-badge--success")
        self.assertContains(response, "۲ دستورکار نمایش‌داده‌شده")
        for order in (active, completed):
            for route in (
                "work_order_detail",
                "work_order_evidence_create",
                "spare_link_create",
            ):
                self.assertContains(
                    response,
                    reverse(f"equipment:{route}", kwargs={"work_order_id": order.pk}),
                )
        self.assertContains(
            response,
            reverse(
                "equipment:work_order_transition", kwargs={"work_order_id": active.pk}
            ),
        )
        self.assertNotContains(
            response,
            reverse(
                "equipment:work_order_transition",
                kwargs={"work_order_id": completed.pk},
            ),
        )

    def test_existing_work_order_limit_is_reported_without_fleet_totals(self):
        for index in range(51):
            self.order(f"WS-{index:03}")
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["work_orders"]), 50)
        self.assertContains(response, "۵۰ دستورکار نمایش‌داده‌شده")
        self.assertNotContains(response, "تعداد تجهیزات")
        self.assertNotContains(response, "در حال کار امروز")

    def test_read_only_role_and_denied_role_keep_existing_authority(self):
        order = self.order("WS-READ")
        role = self.reader_scope.membership.role_definition
        role.permissions.add(
            BusinessPermission.objects.get(code="equipment_operations.view")
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=self.reader_scope.membership,
            scope_type="organization",
            reason="Synthetic operations read scope",
        )
        self.login(self.reader)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        for name in ("list", "usage_create", "work_order_create", "cost_workbench"):
            self.assertNotContains(response, f'href="{reverse(f"equipment:{name}")}"')
        self.assertContains(
            response,
            reverse("equipment:work_order_detail", kwargs={"work_order_id": order.pk}),
        )
        for name in (
            "work_order_transition",
            "work_order_evidence_create",
            "spare_link_create",
        ):
            self.assertNotContains(
                response,
                reverse(f"equipment:{name}", kwargs={"work_order_id": order.pk}),
            )
        self.assertEqual(
            self.client.get(reverse("equipment:usage_create")).status_code, 403
        )
        self.login(self.denied)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.get(self.url, {"format": "xlsx"}).status_code, 403)

    def test_foreign_tenant_order_is_not_in_summary_or_follow_up(self):
        foreign_equipment = Equipment.objects.create(
            organization=self.other_organization,
            code="FOREIGN-EQ",
            name="تجهیز شرکت دیگر",
            category="ماشین‌آلات",
        )
        EquipmentWorkOrder.objects.create(
            organization=self.other_organization,
            equipment=foreign_equipment,
            number="FOREIGN-WO",
            summary="دستورکار شرکت دیگر",
            created_by=self.owner,
        )
        response = self.client.get(self.url)
        self.assertContains(response, "۰ دستورکار نمایش‌داده‌شده")
        self.assertNotContains(response, "FOREIGN-WO")
        self.assertNotContains(response, "دستورکار شرکت دیگر")

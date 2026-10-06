from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import JournalEntry, JournalLine
from apps.audit.models import AuditAction, AuditEvent
from apps.equipment.models import (
    Equipment,
    EquipmentAssignment,
    EquipmentMeterKind,
    WorkOrderStatus,
)
from apps.equipment.p8_models import (
    EquipmentMeter,
    MaintenanceSparePartReference,
    OperatorEquipmentQualification,
)
from apps.equipment.p8_services import (
    add_work_order_evidence,
    create_maintenance_plan,
    create_work_order,
    link_spare_part,
    record_downtime,
    record_fuel,
    record_meter_reading,
    record_operator_qualification,
    record_usage,
    transition_work_order,
)
from apps.equipment.tests import EquipmentTestBase
from apps.fixed_assets.models import FixedAsset
from apps.inventory.models import (
    StockTransaction,
    StockTransactionStatus,
    StockTransactionType,
    Warehouse,
)
from apps.inventory.p8_models import InventoryReservation, InventoryValuationEvent
from apps.materials.models import Material, UnitCategory, UnitOfMeasure
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects.models import ProjectCostFact
from apps.workforce.models import Employee, EmployeeQualification, QualificationKind


class P8EquipmentOperationsTests(EquipmentTestBase, TestCase):
    def setUp(self):
        super().setUp()
        self.equipment = self.make_equipment()
        self.meter = EquipmentMeter.objects.create(
            organization=self.organization,
            equipment=self.equipment,
            kind=EquipmentMeterKind.HOURS,
            name="Engine hours",
            unit="hour",
            created_by=self.owner,
        )

    def _work_order(self, number: str):
        return create_work_order(
            organization=self.organization,
            actor=self.owner,
            equipment=self.equipment,
            number=number,
            summary="Scheduled service",
        )

    def _workforce_qualification(
        self, *, valid_until=None, organization=None, actor=None
    ):
        organization = organization or self.organization
        actor = actor or self.owner
        suffix = str(Employee.objects.filter(organization=organization).count() + 1)
        employee = Employee.objects.create(
            organization=organization,
            employee_number=f"OP-{suffix}",
            first_name="Operator",
            last_name=suffix,
            created_by=actor,
            updated_by=actor,
        )
        qualification = EmployeeQualification.objects.create(
            organization=organization,
            employee=employee,
            kind=QualificationKind.CERTIFICATE,
            title="Equipment operator",
            issued_on=timezone.localdate() - timedelta(days=1),
            valid_until=valid_until,
            recorded_by=actor,
        )
        return employee, qualification

    def _stock_issue(self, *, organization=None, project=None, actor=None, suffix="1"):
        organization = organization or self.organization
        project = project or self.project
        actor = actor or self.owner
        unit = UnitOfMeasure.objects.create(
            organization=organization,
            code=f"EA-{suffix}",
            name=f"Each {suffix}",
            symbol=f"ea{suffix}",
            category=UnitCategory.COUNT,
            created_by=actor,
            updated_by=actor,
        )
        material = Material.objects.create(
            organization=organization,
            code=f"SPARE-{suffix}",
            name=f"Spare {suffix}",
            unit_of_measure=unit,
            created_by=actor,
            updated_by=actor,
        )
        warehouse = Warehouse.objects.create(
            organization=organization,
            code=f"WH-{suffix}",
            name=f"Warehouse {suffix}",
            created_by=actor,
            updated_by=actor,
        )
        issue = StockTransaction.objects.create(
            organization=organization,
            transaction_number=f"ISSUE-{suffix}",
            transaction_type=StockTransactionType.ISSUE,
            source_warehouse=warehouse,
            material=material,
            unit_of_measure=unit,
            project=project,
            quantity=Decimal("2.0000"),
            occurred_at=timezone.now(),
            created_by=actor,
            updated_by=actor,
        )
        return issue, warehouse

    def _post(self, stock_transaction, *, actor=None):
        stock_transaction.status = StockTransactionStatus.POSTED
        stock_transaction.posted_at = timezone.now()
        stock_transaction.posted_by = actor or self.owner
        stock_transaction.updated_by = actor or self.owner
        stock_transaction.save()
        return stock_transaction

    def _activate_client(self, user, organization):
        self.client.force_login(user)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(organization.pk)
        session.save()

    def test_meter_idempotency_and_correction_preserve_history(self):
        occurred_at = timezone.now()
        reading = record_meter_reading(
            organization=self.organization,
            actor=self.owner,
            meter=self.meter,
            value=Decimal(10),
            observed_at=occurred_at,
            source_key="meter-1",
        )
        self.assertEqual(
            reading,
            record_meter_reading(
                organization=self.organization,
                actor=self.owner,
                meter=self.meter,
                value=Decimal(10),
                observed_at=occurred_at,
                source_key="meter-1",
            ),
        )
        correction = record_meter_reading(
            organization=self.organization,
            actor=self.owner,
            meter=self.meter,
            value=Decimal(9),
            observed_at=occurred_at + timedelta(minutes=1),
            source_key="meter-2",
            correction_of=reading,
            correction_reason="reset evidence",
        )
        self.assertEqual(correction.correction_of, reading)
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.EQUIPMENT_OPERATION_CORRECTED,
            ).exists()
        )

    def test_usage_and_downtime_are_operational_and_single_open(self):
        record_usage(
            organization=self.organization,
            actor=self.owner,
            equipment=self.equipment,
            started_at=timezone.now(),
            ended_at=timezone.now() + timedelta(hours=1),
            runtime_hours=Decimal(1),
            source_key="use-1",
        )
        record_downtime(
            organization=self.organization,
            actor=self.owner,
            equipment=self.equipment,
            reason_code="repair",
            started_at=timezone.now(),
        )
        with self.assertRaises(ValueError):
            record_downtime(
                organization=self.organization,
                actor=self.owner,
                equipment=self.equipment,
                reason_code="repair",
                started_at=timezone.now(),
            )

    def test_plan_and_work_order_lifecycle(self):
        plan = create_maintenance_plan(
            organization=self.organization,
            actor=self.owner,
            equipment=self.equipment,
            name="Weekly",
            maintenance_type="preventive",
            interval_days=7,
        )
        order = create_work_order(
            organization=self.organization,
            actor=self.owner,
            equipment=self.equipment,
            number="P8-WO-1",
            summary="Service",
            plan=plan,
        )
        order = transition_work_order(
            organization=self.organization,
            actor=self.owner,
            work_order=order,
            target_status=WorkOrderStatus.SCHEDULED,
        )
        order = transition_work_order(
            organization=self.organization,
            actor=self.owner,
            work_order=order,
            target_status=WorkOrderStatus.IN_PROGRESS,
        )
        order = transition_work_order(
            organization=self.organization,
            actor=self.owner,
            work_order=order,
            target_status=WorkOrderStatus.COMPLETED,
            completion_notes="done",
        )
        self.assertIsNotNone(order.completed_at)

    def test_operations_reject_other_tenant_equipment(self):
        other = self.equipment
        with self.assertRaises(PermissionDenied):
            record_usage(
                organization=self.other_organization,
                actor=self.other_owner,
                equipment=other,
                started_at=timezone.now(),
                ended_at=timezone.now() + timedelta(hours=1),
                runtime_hours=Decimal(1),
                source_key="foreign",
            )

    def test_qualification_uses_workforce_authority_and_fails_closed(self):
        valid_until = timezone.localdate() + timedelta(days=7)
        employee, source = self._workforce_qualification(valid_until=valid_until)
        source_count = EmployeeQualification.objects.filter(
            organization=self.organization
        ).count()

        link = record_operator_qualification(
            organization=self.organization,
            actor=self.owner,
            equipment=self.equipment,
            employee=employee,
            workforce_qualification=source,
            effective_from=timezone.localdate(),
        )
        self.assertEqual(link.workforce_qualification_id, source.pk)
        self.assertEqual(
            EmployeeQualification.objects.filter(
                organization=self.organization
            ).count(),
            source_count,
        )

        _, expired = self._workforce_qualification(
            valid_until=timezone.localdate() - timedelta(days=1)
        )
        with self.assertRaises(ValueError):
            record_operator_qualification(
                organization=self.organization,
                actor=self.owner,
                equipment=self.equipment,
                employee=expired.employee,
                workforce_qualification=expired,
                effective_from=timezone.localdate(),
            )

        foreign_employee, foreign_source = self._workforce_qualification(
            organization=self.other_organization,
            actor=self.other_owner,
        )
        with self.assertRaises(ValidationError):
            record_operator_qualification(
                organization=self.organization,
                actor=self.owner,
                equipment=self.equipment,
                employee=foreign_employee,
                workforce_qualification=foreign_source,
                effective_from=timezone.localdate(),
            )
        self.assertEqual(OperatorEquipmentQualification.objects.count(), 1)

    def test_spare_references_link_posted_issue_and_reversal_without_inventory_mutation(
        self,
    ):
        issue, warehouse = self._stock_issue(suffix="valid")
        self._post(issue)
        reversal = StockTransaction.objects.create(
            organization=self.organization,
            transaction_number="REV-valid",
            transaction_type=StockTransactionType.REVERSAL,
            status=StockTransactionStatus.POSTED,
            destination_warehouse=warehouse,
            material=issue.material,
            unit_of_measure=issue.unit_of_measure,
            project=self.project,
            quantity=issue.quantity,
            occurred_at=timezone.now(),
            reversal_of=issue,
            posted_at=timezone.now(),
            posted_by=self.owner,
            created_by=self.owner,
            updated_by=self.owner,
        )
        inventory_before = {
            "stock": list(
                StockTransaction.objects.order_by("pk").values_list(
                    "pk",
                    "status",
                    "quantity",
                    "source_warehouse_id",
                    "destination_warehouse_id",
                )
            ),
            "reservations": InventoryReservation.objects.count(),
            "valuation": InventoryValuationEvent.objects.count(),
        }

        issue_reference = link_spare_part(
            organization=self.organization,
            actor=self.owner,
            work_order=self._work_order("P8-SPARE-ISSUE"),
            inventory_transaction=issue,
        )
        reversal_reference = link_spare_part(
            organization=self.organization,
            actor=self.owner,
            work_order=self._work_order("P8-SPARE-REVERSAL"),
            inventory_transaction=reversal,
        )

        self.assertEqual(issue_reference.quantity_snapshot, issue.quantity)
        self.assertEqual(reversal_reference.inventory_transaction_id, reversal.pk)
        self.assertEqual(
            list(
                StockTransaction.objects.order_by("pk").values_list(
                    "pk",
                    "status",
                    "quantity",
                    "source_warehouse_id",
                    "destination_warehouse_id",
                )
            ),
            inventory_before["stock"],
        )
        self.assertEqual(
            InventoryReservation.objects.count(), inventory_before["reservations"]
        )
        self.assertEqual(
            InventoryValuationEvent.objects.count(), inventory_before["valuation"]
        )

    def test_spare_references_reject_unposted_foreign_duplicate_and_foreign_work_order(
        self,
    ):
        work_order = self._work_order("P8-SPARE-REJECT")
        draft, _ = self._stock_issue(suffix="draft")
        with self.assertRaises(ValueError):
            link_spare_part(
                organization=self.organization,
                actor=self.owner,
                work_order=work_order,
                inventory_transaction=draft,
            )

        issue, _ = self._stock_issue(suffix="duplicate")
        self._post(issue)
        link_spare_part(
            organization=self.organization,
            actor=self.owner,
            work_order=work_order,
            inventory_transaction=issue,
        )
        with self.assertRaises(ValueError):
            link_spare_part(
                organization=self.organization,
                actor=self.owner,
                work_order=work_order,
                inventory_transaction=issue,
            )

        foreign_issue, _ = self._stock_issue(
            organization=self.other_organization,
            project=self.other_project,
            actor=self.other_owner,
            suffix="foreign",
        )
        self._post(foreign_issue, actor=self.other_owner)
        with self.assertRaises(PermissionDenied):
            link_spare_part(
                organization=self.organization,
                actor=self.owner,
                work_order=work_order,
                inventory_transaction=foreign_issue,
            )

        foreign_equipment = Equipment.objects.create(
            organization=self.other_organization,
            code="OTHER-EXC",
            name="Other excavator",
            category="Plant",
        )
        foreign_order = create_work_order(
            organization=self.other_organization,
            actor=self.other_owner,
            equipment=foreign_equipment,
            number="P8-FOREIGN-WO",
            summary="Foreign service",
        )
        with self.assertRaises(PermissionDenied):
            link_spare_part(
                organization=self.organization,
                actor=self.owner,
                work_order=foreign_order,
                inventory_transaction=issue,
            )
        self.assertEqual(MaintenanceSparePartReference.objects.count(), 1)

    def test_operations_have_no_downstream_financial_or_fixed_asset_effect(self):
        employee, qualification = self._workforce_qualification(
            valid_until=timezone.localdate() + timedelta(days=1)
        )
        before = {
            "journals": JournalEntry.objects.count(),
            "journal_lines": JournalLine.objects.count(),
            "project_costs": ProjectCostFact.objects.count(),
            "valuations": InventoryValuationEvent.objects.count(),
            "fixed_assets": FixedAsset.objects.count(),
        }
        started_at = timezone.now()
        record_usage(
            organization=self.organization,
            actor=self.owner,
            equipment=self.equipment,
            started_at=started_at,
            ended_at=started_at + timedelta(hours=1),
            runtime_hours=Decimal(1),
            source_key="no-financial-usage",
        )
        record_fuel(
            organization=self.organization,
            actor=self.owner,
            equipment=self.equipment,
            occurred_at=started_at,
            quantity=Decimal(10),
            unit="litre",
            source_key="no-financial-fuel",
        )
        record_operator_qualification(
            organization=self.organization,
            actor=self.owner,
            equipment=self.equipment,
            employee=employee,
            workforce_qualification=qualification,
            effective_from=timezone.localdate(),
        )
        plan = create_maintenance_plan(
            organization=self.organization,
            actor=self.owner,
            equipment=self.equipment,
            name="Non-financial plan",
            maintenance_type="preventive",
            interval_days=7,
        )
        order = create_work_order(
            organization=self.organization,
            actor=self.owner,
            equipment=self.equipment,
            number="P8-NO-FINANCIAL",
            summary="Non-financial maintenance",
            plan=plan,
        )
        add_work_order_evidence(
            organization=self.organization,
            actor=self.owner,
            work_order=order,
            reference="dms://p8/no-financial",
        )

        self.assertEqual(JournalEntry.objects.count(), before["journals"])
        self.assertEqual(JournalLine.objects.count(), before["journal_lines"])
        self.assertEqual(ProjectCostFact.objects.count(), before["project_costs"])
        self.assertEqual(InventoryValuationEvent.objects.count(), before["valuations"])
        self.assertEqual(FixedAsset.objects.count(), before["fixed_assets"])

    def test_operations_enforce_permission_tenant_project_and_site_scope(self):
        started_at = timezone.now()
        assignment = EquipmentAssignment.objects.create(
            organization=self.organization,
            equipment=self.equipment,
            project=self.project,
            site=self.site,
            start_date=timezone.localdate(),
            created_by=self.owner,
            updated_by=self.owner,
        )
        usage = record_usage(
            organization=self.organization,
            actor=self.owner,
            equipment=self.equipment,
            deployment=assignment,
            started_at=started_at,
            ended_at=started_at + timedelta(hours=1),
            runtime_hours=Decimal(1),
            source_key="scoped-usage",
        )
        self.assertEqual(usage.deployment_id, assignment.pk)
        with self.assertRaises(PermissionDenied):
            record_usage(
                organization=self.organization,
                actor=self.viewer,
                equipment=self.equipment,
                started_at=started_at,
                ended_at=started_at + timedelta(hours=1),
                runtime_hours=Decimal(1),
                source_key="viewer-denied",
            )

        other_equipment = Equipment.objects.create(
            organization=self.other_organization,
            code="OTHER-SCOPE",
            name="Other equipment",
            category="Plant",
        )
        other_assignment = EquipmentAssignment.objects.create(
            organization=self.other_organization,
            equipment=other_equipment,
            project=self.other_project,
            start_date=timezone.localdate(),
            created_by=self.other_owner,
            updated_by=self.other_owner,
        )
        with self.assertRaises(ValidationError):
            record_usage(
                organization=self.organization,
                actor=self.owner,
                equipment=self.equipment,
                deployment=other_assignment,
                started_at=started_at,
                ended_at=started_at + timedelta(hours=1),
                runtime_hours=Decimal(1),
                source_key="foreign-deployment",
            )

    def test_rtl_operations_workbench_and_mutation_routes_are_navigable(self):
        order = self._work_order("P8-UI-WO")
        self._activate_client(self.owner, self.organization)
        workbench_url = reverse("equipment:operations_workbench")
        response = self.client.get(workbench_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dir="rtl"', html=False)

        routes = [
            reverse("equipment:meter_reading_create"),
            reverse("equipment:usage_create"),
            reverse("equipment:fuel_create"),
            reverse("equipment:operator_qualification_create"),
            reverse("equipment:downtime_create"),
            reverse("equipment:maintenance_plan_create"),
            reverse("equipment:work_order_create"),
            reverse(
                "equipment:work_order_transition", kwargs={"work_order_id": order.pk}
            ),
            reverse(
                "equipment:work_order_evidence_create",
                kwargs={"work_order_id": order.pk},
            ),
            reverse("equipment:spare_link_create", kwargs={"work_order_id": order.pk}),
        ]
        for route in routes:
            self.assertContains(response, route)
            form_response = self.client.get(route)
            self.assertEqual(form_response.status_code, 200)
            self.assertContains(form_response, "csrfmiddlewaretoken")

        self.assertContains(self.client.get(reverse("equipment:list")), workbench_url)
        self._activate_client(self.viewer, self.organization)
        viewer_workbench = self.client.get(workbench_url)
        self.assertEqual(viewer_workbench.status_code, 200)
        self.assertNotContains(viewer_workbench, routes[1])
        self.assertEqual(self.client.get(routes[1]).status_code, 403)

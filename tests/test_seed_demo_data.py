from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command

from apps.accounts.management.commands.seed_demo_data import (
    DEMO_ADMIN_USERNAME,
    DEMO_PASSWORD,
)
from apps.accounts.models import User
from apps.daily_reports.models import DailyReport, DailyReportStatus
from apps.documents.models import Document, DocumentLink, DocumentVersion
from apps.equipment.models import Equipment, EquipmentAssignment, MaintenanceRecord
from apps.inventory.models import StockTransaction, Warehouse
from apps.organizations.models import Organization, OrganizationMembership
from apps.procurement.models import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequest,
    PurchaseRequestItem,
    PurchaseRequestStatus,
)
from apps.projects.models import Project
from apps.quality.models import QualityIssue
from apps.safety.models import SafetyIncident
from apps.workflows.models import (
    WorkflowCondition,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkItem,
    WorkItemStatus,
)
from apps.workforce.models import (
    Department,
    Employee,
    EmployeePositionAssignment,
    EmployeeProjectAssignment,
    Position,
    WorkTeam,
)


@pytest.mark.django_db(transaction=True)
def test_seed_demo_data_creates_four_persian_tenants_and_is_idempotent(
    settings: Any, tmp_path: Path
) -> None:
    settings.MEDIA_ROOT = tmp_path
    settings.DEBUG = True

    call_command("seed_demo_data", stdout=StringIO())

    organizations = Organization.objects.filter(slug__startswith="demo-construction-")
    admin = User.objects.get(username=DEMO_ADMIN_USERNAME)
    assert organizations.count() == 4
    assert User.objects.filter(is_superuser=True).count() == 1
    assert admin.is_staff
    assert admin.check_password(DEMO_PASSWORD)
    assert (
        OrganizationMembership.objects.filter(
            organization__in=organizations,
            status="active",
        ).count()
        == 4
    )
    assert all(
        any("\u0600" <= character <= "\u06ff" for character in value)
        for value in organizations.values_list("name", flat=True)
    )

    assert Project.objects.filter(organization__in=organizations).count() == 16
    assert Department.objects.filter(organization__in=organizations).count() == 8
    assert Position.objects.filter(organization__in=organizations).count() == 8
    assert WorkTeam.objects.filter(organization__in=organizations).count() == 4
    assert Employee.objects.filter(organization__in=organizations).count() == 8
    assert (
        EmployeePositionAssignment.objects.filter(
            organization__in=organizations,
            status="active",
            is_primary=True,
        ).count()
        == 8
    )
    assert (
        EmployeeProjectAssignment.objects.filter(organization__in=organizations).count()
        == 8
    )
    assert PurchaseRequest.objects.filter(organization__in=organizations).count() == 32
    assert (
        PurchaseRequestItem.objects.filter(organization__in=organizations).count() == 48
    )
    assert (
        PurchaseRequest.objects.filter(
            organization__in=organizations,
            status=PurchaseRequestStatus.SUBMITTED,
            request_number__endswith="-WF",
        ).count()
        == 16
    )
    assert (
        DailyReport.objects.filter(
            organization__in=organizations,
            status=DailyReportStatus.SUBMITTED,
            progress_summary__startswith="نمونه باز",
        ).count()
        == 16
    )
    assert PurchaseOrder.objects.filter(organization__in=organizations).count() == 16
    assert (
        PurchaseOrderItem.objects.filter(organization__in=organizations).count() == 32
    )
    assert GoodsReceipt.objects.filter(organization__in=organizations).count() == 16
    assert GoodsReceiptItem.objects.filter(organization__in=organizations).count() == 32
    assert Warehouse.objects.filter(organization__in=organizations).count() == 16
    assert StockTransaction.objects.filter(organization__in=organizations).count() == 36
    assert (
        StockTransaction.objects.filter(
            organization__in=organizations,
            transaction_number__endswith="-WF",
            status="draft",
        ).count()
        == 4
    )
    assert Equipment.objects.filter(organization__in=organizations).count() == 8
    assert (
        EquipmentAssignment.objects.filter(organization__in=organizations).count() == 4
    )
    assert MaintenanceRecord.objects.filter(organization__in=organizations).count() == 4
    assert SafetyIncident.objects.filter(organization__in=organizations).count() == 16
    assert QualityIssue.objects.filter(organization__in=organizations).count() == 16
    assert Document.objects.filter(organization__in=organizations).count() == 32
    assert DocumentVersion.objects.filter(organization__in=organizations).count() == 32
    assert DocumentLink.objects.filter(organization__in=organizations).count() == 64
    assert WorkflowCondition.objects.filter(organization__in=organizations).count() == 4
    assert (
        WorkflowInstance.objects.filter(
            organization__in=organizations,
            status=WorkflowInstanceStatus.ACTIVE,
            subject_type__in=(
                "procurement.purchase_request",
                "daily_reports.daily_report",
            ),
        ).count()
        >= 32
    )
    assert (
        WorkItem.objects.filter(
            organization__in=organizations,
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
            instance__subject_type__in=(
                "procurement.purchase_request",
                "daily_reports.daily_report",
            ),
        ).count()
        >= 32
    )
    assert (
        WorkflowInstance.objects.filter(
            organization__in=organizations,
            status=WorkflowInstanceStatus.ACTIVE,
            definition__workflow_type__code="inventory.stock_transaction_posting",
        ).count()
        == 4
    )
    assert (
        WorkItem.objects.filter(
            organization__in=organizations,
            status__in=(WorkItemStatus.OPEN, WorkItemStatus.CLAIMED),
            instance__definition__workflow_type__code=(
                "inventory.stock_transaction_posting"
            ),
        ).count()
        == 4
    )

    counts_before = {
        model: model.objects.count()
        for model in (
            User,
            Organization,
            Project,
            DailyReport,
            Department,
            Position,
            WorkTeam,
            Employee,
            EmployeePositionAssignment,
            EmployeeProjectAssignment,
            PurchaseRequest,
            PurchaseRequestItem,
            PurchaseOrder,
            PurchaseOrderItem,
            GoodsReceipt,
            GoodsReceiptItem,
            Warehouse,
            StockTransaction,
            Equipment,
            EquipmentAssignment,
            MaintenanceRecord,
            SafetyIncident,
            QualityIssue,
            Document,
            DocumentVersion,
            DocumentLink,
            WorkflowInstance,
            WorkItem,
        )
    }
    call_command("seed_demo_data", stdout=StringIO())

    assert {model: model.objects.count() for model in counts_before} == counts_before
    admin.refresh_from_db()
    assert admin.check_password(DEMO_PASSWORD)

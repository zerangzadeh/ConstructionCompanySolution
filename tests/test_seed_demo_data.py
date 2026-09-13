from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command

from apps.accounts.management.commands.seed_demo_data import DEMO_PASSWORD
from apps.accounts.models import User
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
)
from apps.projects.models import Project
from apps.quality.models import QualityIssue
from apps.safety.models import SafetyIncident
from apps.workforce.models import (
    Department,
    Employee,
    EmployeeProjectAssignment,
    Position,
    WorkTeam,
)


@pytest.mark.django_db(transaction=True)
def test_seed_demo_data_creates_four_persian_tenants_and_is_idempotent(
    settings: Any, tmp_path: Path
) -> None:
    settings.MEDIA_ROOT = tmp_path

    call_command("seed_demo_data", stdout=StringIO())

    organizations = Organization.objects.filter(slug__startswith="demo-construction-")
    users = User.objects.filter(username__startswith="demo.o")
    assert organizations.count() == 4
    assert users.count() == 12
    assert (
        OrganizationMembership.objects.filter(
            organization__in=organizations,
            status="active",
        ).count()
        == 12
    )
    assert all(user.check_password(DEMO_PASSWORD) for user in users)
    assert all(
        any("\u0600" <= character <= "\u06ff" for character in value)
        for value in organizations.values_list("name", flat=True)
    )
    assert all(
        any("\u0600" <= character <= "\u06ff" for character in value)
        for value in users.values_list("first_name", flat=True)
    )

    assert Project.objects.filter(organization__in=organizations).count() == 16
    assert Department.objects.filter(organization__in=organizations).count() == 8
    assert Position.objects.filter(organization__in=organizations).count() == 8
    assert WorkTeam.objects.filter(organization__in=organizations).count() == 4
    assert Employee.objects.filter(organization__in=organizations).count() == 8
    assert (
        EmployeeProjectAssignment.objects.filter(organization__in=organizations).count()
        == 8
    )
    assert PurchaseRequest.objects.filter(organization__in=organizations).count() == 16
    assert (
        PurchaseRequestItem.objects.filter(organization__in=organizations).count() == 32
    )
    assert PurchaseOrder.objects.filter(organization__in=organizations).count() == 16
    assert (
        PurchaseOrderItem.objects.filter(organization__in=organizations).count() == 32
    )
    assert GoodsReceipt.objects.filter(organization__in=organizations).count() == 16
    assert GoodsReceiptItem.objects.filter(organization__in=organizations).count() == 32
    assert Warehouse.objects.filter(organization__in=organizations).count() == 16
    assert StockTransaction.objects.filter(organization__in=organizations).count() == 32
    assert Equipment.objects.filter(organization__in=organizations).count() == 8
    assert (
        EquipmentAssignment.objects.filter(organization__in=organizations).count() == 4
    )
    assert MaintenanceRecord.objects.filter(organization__in=organizations).count() == 4
    assert SafetyIncident.objects.filter(organization__in=organizations).count() == 16
    assert QualityIssue.objects.filter(organization__in=organizations).count() == 16

    counts_before = {
        model: model.objects.count()
        for model in (
            User,
            Organization,
            Project,
            Department,
            Position,
            WorkTeam,
            Employee,
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
        )
    }

    call_command("seed_demo_data", stdout=StringIO())

    assert {model: model.objects.count() for model in counts_before} == counts_before

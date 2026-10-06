"""P8 operational Equipment aggregates and non-posting cost proposals."""
# ruff: noqa: RUF012

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.equipment.models import (
    Equipment,
    EquipmentAssignment,
    EquipmentMeterKind,
    WorkOrderStatus,
)
from core.models import TimeStampedModel, UUIDModel
from core.tenant_validation import validate_related_organizations


class EquipmentMeter(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="equipment_meters",
    )
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name="meters"
    )
    kind = models.CharField(max_length=20, choices=EquipmentMeterKind.choices)
    name = models.CharField(max_length=80)
    unit = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="equipment_meters_created",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["equipment", "kind", "name"],
                name="equipment_meter_unique_kind_name",
            )
        ]
        indexes = [
            models.Index(
                fields=["organization", "equipment", "is_active"],
                name="equip_meter_org_eq_idx",
            )
        ]

    def clean(self):
        validate_related_organizations(self, equipment=self.equipment)
        self.name = self.name.strip()
        self.unit = self.unit.strip()
        if not self.name or not self.unit:
            raise ValidationError("نام و واحد کنتور الزامی است.")


class MeterReading(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="equipment_meter_readings",
    )
    meter = models.ForeignKey(
        EquipmentMeter, on_delete=models.PROTECT, related_name="readings"
    )
    deployment = models.ForeignKey(
        EquipmentAssignment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="meter_readings",
    )
    observed_at = models.DateTimeField()
    value = models.DecimalField(max_digits=18, decimal_places=3)
    source_key = models.CharField(max_length=100)
    evidence_reference = models.CharField(max_length=255, blank=True)
    correction_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="corrections",
    )
    correction_reason = models.TextField(blank=True)
    finalized_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="meter_readings_created",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "source_key"],
                name="meter_reading_org_source_uq",
            ),
            models.CheckConstraint(
                condition=Q(value__gte=0), name="meter_reading_value_nonnegative"
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "meter", "observed_at"],
                name="meter_reading_org_meter_idx",
            )
        ]

    def clean(self):
        validate_related_organizations(
            self, meter=self.meter, deployment=self.deployment
        )
        if (
            self.deployment_id
            and self.deployment.equipment_id != self.meter.equipment_id
        ):
            raise ValidationError("استقرار باید متعلق به تجهیز کنتور باشد.")
        if self.correction_of_id and (
            self.correction_of.meter_id != self.meter_id
            or not self.correction_reason.strip()
        ):
            raise ValidationError("اصلاح باید برای همان کنتور و دارای علت باشد.")

    def delete(self, *args, **kwargs):
        raise ValidationError("قرائت کنتور قابل حذف نیست.")


class OperatorEquipmentQualification(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="operator_equipment_qualifications",
    )
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name="operator_qualifications"
    )
    employee = models.ForeignKey(
        "workforce.Employee",
        on_delete=models.PROTECT,
        related_name="equipment_qualifications",
    )
    workforce_qualification = models.ForeignKey(
        "workforce.EmployeeQualification",
        on_delete=models.PROTECT,
        related_name="equipment_uses",
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="operator_equipment_qualifications_created",
    )

    class Meta:
        indexes = [
            models.Index(
                fields=["organization", "equipment", "employee"],
                name="operator_eq_qual_org_idx",
            )
        ]

    def clean(self):
        validate_related_organizations(
            self,
            equipment=self.equipment,
            employee=self.employee,
            workforce_qualification=self.workforce_qualification,
        )
        if self.workforce_qualification.employee_id != self.employee_id:
            raise ValidationError("صلاحیت نیروی انسانی با اپراتور سازگار نیست.")
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError("پایان اعتبار پیش از شروع است.")


class EquipmentUsageLog(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="equipment_usage_logs",
    )
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name="usage_logs"
    )
    deployment = models.ForeignKey(
        EquipmentAssignment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="usage_logs",
    )
    operator = models.ForeignKey(
        "workforce.Employee",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="equipment_usage_logs",
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    runtime_hours = models.DecimalField(max_digits=12, decimal_places=3)
    source_key = models.CharField(max_length=100)
    evidence_reference = models.CharField(max_length=255, blank=True)
    correction_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="corrections",
    )
    correction_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="equipment_usage_created",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "source_key"], name="equip_usage_org_source_uq"
            ),
            models.CheckConstraint(
                condition=Q(runtime_hours__gt=0), name="equip_usage_runtime_positive"
            ),
        ]

    def clean(self):
        validate_related_organizations(
            self,
            equipment=self.equipment,
            deployment=self.deployment,
            operator=self.operator,
        )
        if self.ended_at <= self.started_at:
            raise ValidationError("پایان کارکرد باید پس از شروع باشد.")
        if self.deployment_id and self.deployment.equipment_id != self.equipment_id:
            raise ValidationError("استقرار با تجهیز سازگار نیست.")


class FuelLog(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="equipment_fuel_logs",
    )
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name="fuel_logs"
    )
    deployment = models.ForeignKey(
        EquipmentAssignment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fuel_logs",
    )
    occurred_at = models.DateTimeField()
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit = models.CharField(max_length=20)
    source_key = models.CharField(max_length=100)
    evidence_reference = models.CharField(max_length=255, blank=True)
    inventory_transaction = models.ForeignKey(
        "inventory.StockTransaction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="equipment_fuel_references",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="equipment_fuel_created",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "source_key"], name="equip_fuel_org_source_uq"
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="equip_fuel_quantity_positive"
            ),
        ]

    def clean(self):
        validate_related_organizations(
            self,
            equipment=self.equipment,
            deployment=self.deployment,
            inventory_transaction=self.inventory_transaction,
        )
        if self.deployment_id and self.deployment.equipment_id != self.equipment_id:
            raise ValidationError("استقرار با تجهیز سازگار نیست.")


class DowntimeEvent(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="equipment_downtime_events",
    )
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name="downtime_events"
    )
    deployment = models.ForeignKey(
        EquipmentAssignment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="downtime_events",
    )
    reason_code = models.CharField(max_length=50)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    evidence_reference = models.CharField(max_length=255, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="equipment_downtime_created",
    )

    class Meta:
        indexes = [
            models.Index(
                fields=["organization", "equipment", "ended_at"],
                name="equip_down_org_eq_idx",
            )
        ]

    def clean(self):
        validate_related_organizations(
            self, equipment=self.equipment, deployment=self.deployment
        )
        if self.ended_at and self.ended_at <= self.started_at:
            raise ValidationError("پایان توقف باید پس از شروع باشد.")


class MaintenancePlan(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="equipment_maintenance_plans",
    )
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name="maintenance_plans"
    )
    name = models.CharField(max_length=255)
    maintenance_type = models.CharField(max_length=20)
    interval_days = models.PositiveIntegerField(null=True, blank=True)
    meter_interval = models.DecimalField(
        max_digits=14, decimal_places=3, null=True, blank=True
    )
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="maintenance_plans_created",
    )

    class Meta:
        indexes = [
            models.Index(
                fields=["organization", "equipment", "active"],
                name="maint_plan_org_eq_idx",
            )
        ]

    def clean(self):
        validate_related_organizations(self, equipment=self.equipment)
        if not self.interval_days and not self.meter_interval:
            raise ValidationError("حداقل یک تناوب زمان یا کنتور الزامی است.")


class EquipmentWorkOrder(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="equipment_work_orders",
    )
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name="work_orders"
    )
    plan = models.ForeignKey(
        MaintenancePlan,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="work_orders",
    )
    deployment = models.ForeignKey(
        EquipmentAssignment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="work_orders",
    )
    number = models.CharField(max_length=50)
    summary = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=WorkOrderStatus.choices, default=WorkOrderStatus.DRAFT
    )
    scheduled_for = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completion_notes = models.TextField(blank=True)
    correction_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="corrective_orders",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="equipment_work_orders_created",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "number"],
                name="equipment_work_order_org_num_uq",
            )
        ]
        indexes = [
            models.Index(
                fields=["organization", "equipment", "status"],
                name="work_order_org_eq_idx",
            )
        ]

    def clean(self):
        validate_related_organizations(
            self, equipment=self.equipment, plan=self.plan, deployment=self.deployment
        )
        if self.plan_id and self.plan.equipment_id != self.equipment_id:
            raise ValidationError("برنامه نگهداری با تجهیز سازگار نیست.")
        if self.deployment_id and self.deployment.equipment_id != self.equipment_id:
            raise ValidationError("استقرار با تجهیز سازگار نیست.")

    def delete(self, *args, **kwargs):
        raise ValidationError("دستورکار قابل حذف نیست.")


class MaintenanceWorkOrderEvidence(UUIDModel, TimeStampedModel):
    """Reference to the authoritative DMS/evidence record; no document bytes live here."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="maintenance_work_order_evidence",
    )
    work_order = models.ForeignKey(
        EquipmentWorkOrder, on_delete=models.PROTECT, related_name="evidence_references"
    )
    reference = models.CharField(max_length=255)
    result_notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="maintenance_work_order_evidence_recorded",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["work_order", "reference"],
                name="work_order_evidence_reference_uq",
            )
        ]

    def clean(self):
        validate_related_organizations(self, work_order=self.work_order)
        self.reference = self.reference.strip()
        if not self.reference:
            raise ValidationError("مرجع مدرک الزامی است.")


class MaintenanceSparePartReference(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="maintenance_spare_part_references",
    )
    work_order = models.ForeignKey(
        EquipmentWorkOrder,
        on_delete=models.PROTECT,
        related_name="spare_part_references",
    )
    inventory_transaction = models.ForeignKey(
        "inventory.StockTransaction",
        on_delete=models.PROTECT,
        related_name="maintenance_work_order_references",
    )
    material = models.ForeignKey(
        "materials.Material",
        on_delete=models.PROTECT,
        related_name="maintenance_spare_part_references",
    )
    quantity_snapshot = models.DecimalField(max_digits=14, decimal_places=4)
    unit_snapshot = models.CharField(max_length=20)
    linked_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="maintenance_spare_references_created",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["work_order", "inventory_transaction"],
                name="maint_spare_work_tx_uq",
            ),
            models.CheckConstraint(
                condition=Q(quantity_snapshot__gt=0),
                name="maint_spare_quantity_positive",
            ),
        ]

    def clean(self):
        validate_related_organizations(
            self,
            work_order=self.work_order,
            inventory_transaction=self.inventory_transaction,
            material=self.material,
        )


class CostPolicyStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    REVIEWED = "reviewed", "بررسی‌شده"
    PUBLISHED = "published", "منتشرشده"
    SUPERSEDED = "superseded", "جایگزین‌شده"
    RETIRED = "retired", "بازنشسته"


class CostAllocationStatus(models.TextChoices):
    DRAFT = "draft", "پیش‌نویس"
    FINALIZED = "finalized", "نهایی"
    REVERSED = "reversed", "برگشت‌شده"


class ProposalStatus(models.TextChoices):
    PREPARED = "prepared", "تهیه‌شده"
    REVIEWED = "reviewed", "بررسی‌شده"
    ACKNOWLEDGED = "acknowledged", "دریافت‌شده"
    REJECTED = "rejected", "ردشده"
    RECONCILED = "reconciled", "تطبیق‌شده"
    SUPERSEDED = "superseded", "جایگزین‌شده"


class EquipmentCostPolicyVersion(UUIDModel, TimeStampedModel):
    """Versioned internal proposal-rate policy; never a financial actual."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="equipment_cost_policies",
    )
    code = models.CharField(max_length=50)
    version = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20, choices=CostPolicyStatus.choices, default=CostPolicyStatus.DRAFT
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    currency_code = models.CharField(max_length=3, default="IRR")
    monetary_policy_code = models.CharField(max_length=80)
    monetary_policy_version = models.CharField(max_length=40)
    decimal_places = models.PositiveSmallIntegerField(default=0)
    idle_policy = models.CharField(max_length=30, default="explicit_exception")
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="equipment_cost_policies_prepared",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="equipment_cost_policies_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="equipment_cost_policies_published",
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code", "version"],
                name="equip_cost_policy_org_code_ver_uq",
            )
        ]

    def clean(self):
        self.code = self.code.strip().upper()
        if (
            self.currency_code != "IRR"
            or not self.monetary_policy_code.strip()
            or not self.monetary_policy_version.strip()
        ):
            raise ValidationError("سیاست هزینه باید دارای مبنا و نسخه پولی IRR باشد.")
        if self.decimal_places > 6:
            raise ValidationError("دقت پولی نامعتبر است.")
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError("پایان اعتبار پیش از شروع است.")

    def delete(self, *args, **kwargs):
        raise ValidationError("نسخه سیاست هزینه قابل حذف نیست.")


class EquipmentCostRate(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="equipment_cost_rates",
    )
    policy = models.ForeignKey(
        EquipmentCostPolicyVersion, on_delete=models.PROTECT, related_name="rates"
    )
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cost_rates",
    )
    equipment_category = models.CharField(max_length=120, blank=True)
    measure_unit = models.CharField(max_length=20, default="hour")
    rate_amount = models.DecimalField(max_digits=20, decimal_places=6)
    component_snapshot = models.JSONField(default=dict)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="equipment_cost_rates_prepared",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(rate_amount__gte=0), name="equip_cost_rate_nonnegative"
            )
        ]

    def clean(self):
        validate_related_organizations(
            self, policy=self.policy, equipment=self.equipment
        )
        if bool(self.equipment_id) == bool(self.equipment_category.strip()):
            raise ValidationError("نرخ باید دقیقاً برای تجهیز یا طبقه تجهیز تعریف شود.")
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError("پایان نرخ پیش از شروع است.")
        component_total = sum(
            (Decimal(str(value)) for value in self.component_snapshot.values()),
            Decimal(0),
        )
        if component_total != self.rate_amount:
            raise ValidationError("جمع مؤلفه‌های نرخ باید با نرخ کل برابر باشد.")

    def delete(self, *args, **kwargs):
        raise ValidationError("نرخ هزینه قابل حذف نیست.")


class EquipmentCostAllocation(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="equipment_cost_allocations",
    )
    usage = models.ForeignKey(
        EquipmentUsageLog, on_delete=models.PROTECT, related_name="cost_allocations"
    )
    rate = models.ForeignKey(
        EquipmentCostRate, on_delete=models.PROTECT, related_name="allocations"
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="equipment_cost_allocations",
    )
    site = models.ForeignKey(
        "projects.ProjectSite",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="equipment_cost_allocations",
    )
    wbs_node = models.ForeignKey(
        "projects.WBSNode",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="equipment_cost_allocations",
    )
    activity = models.ForeignKey(
        "projects.Activity",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="equipment_cost_allocations",
    )
    cost_center = models.ForeignKey(
        "projects.CostCenter",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="equipment_cost_allocations",
    )
    measure = models.DecimalField(max_digits=18, decimal_places=3)
    rate_snapshot = models.DecimalField(max_digits=20, decimal_places=6)
    amount = models.DecimalField(max_digits=24, decimal_places=6)
    currency_code = models.CharField(max_length=3, default="IRR")
    status = models.CharField(
        max_length=20,
        choices=CostAllocationStatus.choices,
        default=CostAllocationStatus.DRAFT,
    )
    source_key = models.CharField(max_length=120)
    correction_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="replacements",
    )
    reason = models.TextField(blank=True)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="equipment_cost_allocations_prepared",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="equipment_cost_allocations_reviewed",
    )
    finalized_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="equipment_cost_allocations_reversed",
    )
    reversed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "source_key"],
                name="equip_cost_alloc_org_source_uq",
            ),
            models.CheckConstraint(
                condition=Q(measure__gt=0), name="equip_cost_alloc_measure_positive"
            ),
        ]

    def clean(self):
        validate_related_organizations(
            self,
            usage=self.usage,
            rate=self.rate,
            project=self.project,
            site=self.site,
            wbs_node=self.wbs_node,
            activity=self.activity,
            cost_center=self.cost_center,
        )
        if self.usage.equipment_id != self.rate.equipment_id and self.rate.equipment_id:
            raise ValidationError("نرخ با تجهیز کارکرد سازگار نیست.")
        if self.site_id and self.site.project_id != self.project_id:
            raise ValidationError("کارگاه باید متعلق به پروژه تخصیص باشد.")
        if self.currency_code != "IRR":
            raise ValidationError("تخصیص هزینه تجهیز فقط با IRR مجاز است.")

    def delete(self, *args, **kwargs):
        raise ValidationError("تخصیص هزینه قابل حذف نیست.")


class EquipmentCostSourceEnvelope(UUIDModel, TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="equipment_cost_envelopes",
    )
    allocation = models.ForeignKey(
        EquipmentCostAllocation,
        on_delete=models.PROTECT,
        related_name="source_envelopes",
    )
    consumer = models.CharField(max_length=30, default="project_cost")
    status = models.CharField(
        max_length=20, choices=ProposalStatus.choices, default=ProposalStatus.PREPARED
    )
    occurrence_key = models.CharField(max_length=140)
    source_amount = models.DecimalField(max_digits=24, decimal_places=6)
    source_version = models.PositiveIntegerField(default=1)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="equipment_cost_envelopes_prepared",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="equipment_cost_envelopes_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    consumer_reference = models.CharField(max_length=120, blank=True)
    reconciliation_note = models.TextField(blank=True)
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="successors",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "consumer", "occurrence_key"],
                name="equip_cost_env_org_cons_occ_uq",
            ),
            models.UniqueConstraint(
                fields=["organization", "consumer", "allocation"],
                name="equip_cost_env_org_cons_source_uq",
            ),
        ]

    def clean(self):
        validate_related_organizations(
            self, allocation=self.allocation, supersedes=self.supersedes
        )
        if self.consumer != "project_cost":
            raise ValidationError("مصرف‌کننده اولیه فقط پیشنهاد هزینه پروژه است.")

    def delete(self, *args, **kwargs):
        raise ValidationError("پیشنهاد هزینه قابل حذف نیست.")

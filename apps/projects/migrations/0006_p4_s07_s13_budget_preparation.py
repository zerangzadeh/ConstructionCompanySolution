import uuid
from decimal import Decimal
from typing import ClassVar

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

IMMUTABILITY_SQL = r"""
CREATE OR REPLACE FUNCTION projects_guard_accepted_budget() RETURNS trigger AS $$
BEGIN
    IF OLD.status = 'accepted' THEN
        RAISE EXCEPTION 'accepted budget versions are immutable';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER projects_budget_accepted_guard
BEFORE UPDATE OR DELETE ON projects_budgetversion
FOR EACH ROW EXECUTE FUNCTION projects_guard_accepted_budget();

CREATE OR REPLACE FUNCTION projects_guard_budget_payload() RETURNS trigger AS $$
DECLARE budget_status varchar;
BEGIN
    IF TG_TABLE_NAME = 'projects_budgetallocation' THEN
        SELECT b.status INTO budget_status
        FROM projects_budgetversion b
        JOIN projects_budgetsourcemanifest m ON m.budget_id = b.id
        JOIN projects_budgetmanifestline l ON l.manifest_id = m.id
        WHERE l.id = COALESCE(NEW.manifest_line_id, OLD.manifest_line_id);
    ELSIF TG_TABLE_NAME = 'projects_budgetmanifestline' THEN
        SELECT b.status INTO budget_status
        FROM projects_budgetversion b
        JOIN projects_budgetsourcemanifest m ON m.budget_id = b.id
        WHERE m.id = COALESCE(NEW.manifest_id, OLD.manifest_id);
    ELSE
        SELECT b.status INTO budget_status
        FROM projects_budgetversion b
        WHERE b.id = COALESCE(NEW.budget_id, OLD.budget_id);
    END IF;
    IF budget_status = 'accepted' THEN
        RAISE EXCEPTION 'accepted budget payloads are immutable';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER projects_budget_manifest_guard
BEFORE UPDATE OR DELETE ON projects_budgetsourcemanifest
FOR EACH ROW EXECUTE FUNCTION projects_guard_budget_payload();
CREATE TRIGGER projects_budget_manifest_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON projects_budgetmanifestline
FOR EACH ROW EXECUTE FUNCTION projects_guard_budget_payload();
CREATE TRIGGER projects_budget_allocation_guard
BEFORE INSERT OR UPDATE OR DELETE ON projects_budgetallocation
FOR EACH ROW EXECUTE FUNCTION projects_guard_budget_payload();

CREATE OR REPLACE FUNCTION projects_guard_locked_structure() RETURNS trigger AS $$
DECLARE structure_status varchar;
BEGIN
    IF TG_TABLE_NAME = 'projects_coststructureversion' THEN
        structure_status := OLD.status;
    ELSE
        SELECT status INTO structure_status FROM projects_coststructureversion
        WHERE id = COALESCE(NEW.structure_version_id, OLD.structure_version_id);
    END IF;
    IF structure_status = 'locked' THEN
        RAISE EXCEPTION 'locked cost structures are immutable';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER projects_cost_structure_guard
BEFORE UPDATE OR DELETE ON projects_coststructureversion
FOR EACH ROW EXECUTE FUNCTION projects_guard_locked_structure();
CREATE TRIGGER projects_cbs_node_guard
BEFORE INSERT OR UPDATE OR DELETE ON projects_cbsnode
FOR EACH ROW EXECUTE FUNCTION projects_guard_locked_structure();
CREATE TRIGGER projects_cost_center_guard
BEFORE INSERT OR UPDATE OR DELETE ON projects_costcenter
FOR EACH ROW EXECUTE FUNCTION projects_guard_locked_structure();
"""

REVERSE_IMMUTABILITY_SQL = r"""
DROP TRIGGER IF EXISTS projects_cost_center_guard ON projects_costcenter;
DROP TRIGGER IF EXISTS projects_cbs_node_guard ON projects_cbsnode;
DROP TRIGGER IF EXISTS projects_cost_structure_guard ON projects_coststructureversion;
DROP FUNCTION IF EXISTS projects_guard_locked_structure();
DROP TRIGGER IF EXISTS projects_budget_allocation_guard ON projects_budgetallocation;
DROP TRIGGER IF EXISTS projects_budget_manifest_line_guard ON projects_budgetmanifestline;
DROP TRIGGER IF EXISTS projects_budget_manifest_guard ON projects_budgetsourcemanifest;
DROP FUNCTION IF EXISTS projects_guard_budget_payload();
DROP TRIGGER IF EXISTS projects_budget_accepted_guard ON projects_budgetversion;
DROP FUNCTION IF EXISTS projects_guard_accepted_budget();
"""


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("estimates", "0005_p4_s01_s06_estimate_depth"),
        ("organizations", "0065_p4_s07_s13_budget_permissions"),
        ("projects", "0005_projectdocumentlink"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.CreateModel(
            name="CostStructureVersion",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="شناسه",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, verbose_name="زمان آخرین به‌روزرسانی"
                    ),
                ),
                ("code", models.CharField(max_length=50)),
                ("version", models.PositiveIntegerField()),
                ("name", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[("draft", "پیش‌نویس"), ("locked", "قفل‌شده")],
                        default="draft",
                        max_length=16,
                    ),
                ),
                ("governance_reference", models.CharField(max_length=255)),
                ("locked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cost_structures_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "locked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cost_structures_locked",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cost_structure_versions",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("organization", "code", "version"),
                        name="cost_structure_org_code_ver_uq",
                    )
                ]
            },
        ),
        migrations.CreateModel(
            name="CBSNode",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="شناسه",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, verbose_name="زمان آخرین به‌روزرسانی"
                    ),
                ),
                ("code", models.CharField(max_length=50)),
                ("name", models.CharField(max_length=255)),
                ("is_leaf", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="organizations.organization",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="projects.cbsnode",
                    ),
                ),
                (
                    "structure_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cbs_nodes",
                        to="projects.coststructureversion",
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order", "code"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("structure_version", "code"),
                        name="cbs_structure_code_uq",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="CostCenter",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="شناسه",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, verbose_name="زمان آخرین به‌روزرسانی"
                    ),
                ),
                ("code", models.CharField(max_length=50)),
                ("name", models.CharField(max_length=255)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="organizations.organization",
                    ),
                ),
                (
                    "structure_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cost_centers",
                        to="projects.coststructureversion",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("structure_version", "code"),
                        name="cost_center_structure_code_uq",
                    )
                ]
            },
        ),
        migrations.CreateModel(
            name="BudgetVersion",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="شناسه",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, verbose_name="زمان آخرین به‌روزرسانی"
                    ),
                ),
                ("version_number", models.PositiveIntegerField()),
                ("handoff_id", models.CharField(max_length=100)),
                ("submission_version", models.PositiveIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "پیش‌نویس"),
                            ("submitted", "ارسال‌شده"),
                            ("accepted", "پذیرفته‌شده"),
                        ],
                        default="draft",
                        max_length=16,
                    ),
                ),
                ("currency", models.CharField(max_length=3)),
                ("rounding_policy_reference", models.CharField(max_length=255)),
                ("governance_reference", models.CharField(max_length=255)),
                ("cost_center_required", models.BooleanField()),
                ("reason", models.TextField()),
                ("payload_hash", models.CharField(blank=True, max_length=64)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "accepted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="budget_versions_accepted",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="budget_versions_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="budget_versions",
                        to="organizations.organization",
                    ),
                ),
                (
                    "predecessor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="successors",
                        to="projects.budgetversion",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="budget_versions",
                        to="projects.project",
                    ),
                ),
                (
                    "structure_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="projects.coststructureversion",
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="budget_versions_submitted",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["organization", "project", "status"],
                        name="budget_org_project_status_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("organization", "project", "version_number"),
                        name="budget_org_project_version_uq",
                    ),
                    models.UniqueConstraint(
                        fields=(
                            "organization",
                            "project",
                            "handoff_id",
                            "submission_version",
                        ),
                        name="budget_handoff_submission_uq",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="BudgetSourceManifest",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="شناسه",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, verbose_name="زمان آخرین به‌روزرسانی"
                    ),
                ),
                ("estimate_revision_number", models.PositiveIntegerField()),
                ("source_reference", models.CharField(max_length=255)),
                (
                    "budget",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="source_manifest",
                        to="projects.budgetversion",
                    ),
                ),
                (
                    "estimate",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="estimates.estimate",
                    ),
                ),
                (
                    "estimate_revision",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="estimates.estimaterevision",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="organizations.organization",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="BudgetManifestLine",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="شناسه",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, verbose_name="زمان آخرین به‌روزرسانی"
                    ),
                ),
                ("source_description", models.CharField(max_length=255)),
                (
                    "source_quantity",
                    models.DecimalField(decimal_places=4, max_digits=18),
                ),
                ("source_unit", models.CharField(max_length=80)),
                (
                    "source_unit_price",
                    models.DecimalField(decimal_places=2, max_digits=18),
                ),
                ("source_amount", models.DecimalField(decimal_places=2, max_digits=20)),
                (
                    "disposition",
                    models.CharField(
                        choices=[
                            ("pending", "در انتظار تعیین تکلیف"),
                            ("included", "منظورشده"),
                            ("excluded", "حذف‌شده"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("exclusion_reason", models.TextField(blank=True)),
                (
                    "estimate_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="estimates.estimateitem",
                    ),
                ),
                (
                    "manifest",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="lines",
                        to="projects.budgetsourcemanifest",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("manifest", "estimate_item"),
                        name="budget_manifest_item_uq",
                    )
                ]
            },
        ),
        migrations.CreateModel(
            name="BudgetAllocation",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="شناسه",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, verbose_name="زمان آخرین به‌روزرسانی"
                    ),
                ),
                ("sequence", models.PositiveIntegerField()),
                ("amount", models.DecimalField(decimal_places=2, max_digits=20)),
                ("allocation_basis_reference", models.CharField(max_length=255)),
                (
                    "cbs_node",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="projects.cbsnode",
                    ),
                ),
                (
                    "cost_center",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="projects.costcenter",
                    ),
                ),
                (
                    "manifest_line",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="allocations",
                        to="projects.budgetmanifestline",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="organizations.organization",
                    ),
                ),
                (
                    "wbs_node",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="projects.wbsnode",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("manifest_line", "sequence"),
                        name="budget_allocation_line_seq_uq",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("amount__gt", Decimal("0.00"))),
                        name="budget_allocation_amount_positive",
                    ),
                ]
            },
        ),
        migrations.CreateModel(
            name="ProjectBudgetControl",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="شناسه",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, verbose_name="زمان آخرین به‌روزرسانی"
                    ),
                ),
                (
                    "governing_budget",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="governing_for",
                        to="projects.budgetversion",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="organizations.organization",
                    ),
                ),
                (
                    "project",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="budget_control",
                        to="projects.project",
                    ),
                ),
            ],
        ),
        migrations.RunSQL(IMMUTABILITY_SQL, REVERSE_IMMUTABILITY_SQL),
    ]

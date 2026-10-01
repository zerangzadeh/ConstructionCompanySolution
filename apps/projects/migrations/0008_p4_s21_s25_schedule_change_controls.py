import uuid
from typing import ClassVar

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

IMMUTABILITY_SQL = r"""
CREATE OR REPLACE FUNCTION projects_guard_schedule_revision() RETURNS trigger AS $$
BEGIN
    IF OLD.status = 'accepted' THEN
        RAISE EXCEPTION 'accepted schedule revisions are immutable';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER projects_schedule_revision_guard
BEFORE UPDATE OR DELETE ON projects_projectschedulerevision
FOR EACH ROW EXECUTE FUNCTION projects_guard_schedule_revision();

CREATE OR REPLACE FUNCTION projects_guard_schedule_payload() RETURNS trigger AS $$
DECLARE schedule_status varchar;
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT status INTO schedule_status
        FROM projects_projectschedulerevision
        WHERE id = NEW.schedule_id;
        IF schedule_status = 'accepted' THEN
            RAISE EXCEPTION 'accepted schedule payload is immutable';
        END IF;
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'schedule payload evidence is append-only';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER projects_schedule_item_guard
BEFORE INSERT OR UPDATE OR DELETE ON projects_projectscheduleitem
FOR EACH ROW EXECUTE FUNCTION projects_guard_schedule_payload();
CREATE TRIGGER projects_schedule_dependency_guard
BEFORE INSERT OR UPDATE OR DELETE ON projects_projectscheduledependency
FOR EACH ROW EXECUTE FUNCTION projects_guard_schedule_payload();

CREATE OR REPLACE FUNCTION projects_guard_project_control_evidence() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'project control evidence is append-only';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER projects_control_item_guard
BEFORE UPDATE OR DELETE ON projects_projectcontrolitem
FOR EACH ROW EXECUTE FUNCTION projects_guard_project_control_evidence();
CREATE TRIGGER projects_control_status_guard
BEFORE UPDATE OR DELETE ON projects_projectcontrolstatusevent
FOR EACH ROW EXECUTE FUNCTION projects_guard_project_control_evidence();
CREATE TRIGGER projects_change_proposal_guard
BEFORE UPDATE OR DELETE ON projects_projectchangeproposal
FOR EACH ROW EXECUTE FUNCTION projects_guard_project_control_evidence();
CREATE TRIGGER projects_rebaseline_proposal_guard
BEFORE UPDATE OR DELETE ON projects_schedulerebaselineproposal
FOR EACH ROW EXECUTE FUNCTION projects_guard_project_control_evidence();
"""

REVERSE_IMMUTABILITY_SQL = r"""
DROP TRIGGER IF EXISTS projects_rebaseline_proposal_guard ON projects_schedulerebaselineproposal;
DROP TRIGGER IF EXISTS projects_change_proposal_guard ON projects_projectchangeproposal;
DROP TRIGGER IF EXISTS projects_control_status_guard ON projects_projectcontrolstatusevent;
DROP TRIGGER IF EXISTS projects_control_item_guard ON projects_projectcontrolitem;
DROP FUNCTION IF EXISTS projects_guard_project_control_evidence();
DROP TRIGGER IF EXISTS projects_schedule_dependency_guard ON projects_projectscheduledependency;
DROP TRIGGER IF EXISTS projects_schedule_item_guard ON projects_projectscheduleitem;
DROP FUNCTION IF EXISTS projects_guard_schedule_payload();
DROP TRIGGER IF EXISTS projects_schedule_revision_guard ON projects_projectschedulerevision;
DROP FUNCTION IF EXISTS projects_guard_schedule_revision();
"""


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0067_p4_s21_s25_project_control_permissions"),
        ("projects", "0007_projectcostsourcecontract_projectcostfact_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.CreateModel(
            name="ProjectChangeProposal",
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
                ("occurrence_id", models.CharField(max_length=100)),
                ("title", models.CharField(max_length=255)),
                ("reason", models.TextField()),
                ("evidence_reference", models.CharField(max_length=255)),
                ("schedule_impact_description", models.TextField()),
                ("cost_impact_description", models.TextField(blank=True)),
                (
                    "contractual_impact_status",
                    models.CharField(
                        default="unassessed", editable=False, max_length=16
                    ),
                ),
                (
                    "financial_effect_status",
                    models.CharField(
                        default="observation_only", editable=False, max_length=20
                    ),
                ),
                ("payload_hash", models.CharField(max_length=64)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="organizations.organization",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="change_proposals",
                        to="projects.project",
                    ),
                ),
                (
                    "proposed_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ProjectControlItem",
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
                    "kind",
                    models.CharField(
                        choices=[
                            ("constraint", "محدودیت"),
                            ("issue", "مسئله"),
                            ("risk", "ریسک"),
                            ("delay", "تأخیر"),
                        ],
                        max_length=16,
                    ),
                ),
                ("occurrence_id", models.CharField(max_length=100)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField()),
                ("identified_on", models.DateField()),
                ("observed_from", models.DateField(blank=True, null=True)),
                ("observed_to", models.DateField(blank=True, null=True)),
                ("owner_reference", models.CharField(max_length=255)),
                ("evidence_reference", models.CharField(max_length=255)),
                ("schedule_impact_description", models.TextField(blank=True)),
                (
                    "responsibility_status",
                    models.CharField(
                        default="undetermined", editable=False, max_length=16
                    ),
                ),
                (
                    "contractual_impact_status",
                    models.CharField(
                        default="unassessed", editable=False, max_length=16
                    ),
                ),
                ("payload_hash", models.CharField(max_length=64)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to=settings.AUTH_USER_MODEL,
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
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="control_register_items",
                        to="projects.project",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ProjectControlStatusEvent",
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
                ("occurrence_id", models.CharField(max_length=100)),
                (
                    "from_status",
                    models.CharField(
                        blank=True,
                        choices=[("open", "باز"), ("closed", "بسته")],
                        max_length=16,
                    ),
                ),
                (
                    "to_status",
                    models.CharField(
                        choices=[("open", "باز"), ("closed", "بسته")], max_length=16
                    ),
                ),
                ("reason", models.TextField()),
                (
                    "actor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="status_events",
                        to="projects.projectcontrolitem",
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
            name="ProjectScheduleItem",
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
                ("is_milestone", models.BooleanField(default=False)),
                ("planned_start", models.DateField()),
                ("planned_finish", models.DateField()),
                ("source_reference", models.CharField(max_length=255)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="organizations.organization",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="projects.project",
                    ),
                ),
                (
                    "wbs_node",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="projects.wbsnode",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="projectcontrolitem",
            name="schedule_item",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="projects.projectscheduleitem",
            ),
        ),
        migrations.CreateModel(
            name="ProjectScheduleRevision",
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
                ("occurrence_id", models.CharField(max_length=100)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "پیش‌نویس"),
                            ("accepted", "مبنای پذیرفته‌شده"),
                        ],
                        default="draft",
                        max_length=16,
                    ),
                ),
                ("data_date", models.DateField()),
                ("planned_start", models.DateField()),
                ("planned_finish", models.DateField()),
                ("calendar_reference", models.CharField(max_length=255)),
                ("assumptions", models.TextField()),
                ("payload_hash", models.CharField(max_length=64)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "accepted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="project_schedule_revisions_accepted",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="project_schedule_revisions_created",
                        to=settings.AUTH_USER_MODEL,
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
                    "predecessor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="projects.projectschedulerevision",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="schedule_revisions",
                        to="projects.project",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="projectscheduleitem",
            name="schedule",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="items",
                to="projects.projectschedulerevision",
            ),
        ),
        migrations.CreateModel(
            name="ProjectScheduleDependency",
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
                    "dependency_type",
                    models.CharField(
                        choices=[
                            ("finish_start", "پایان به شروع"),
                            ("start_start", "شروع به شروع"),
                            ("finish_finish", "پایان به پایان"),
                            ("start_finish", "شروع به پایان"),
                        ],
                        max_length=16,
                    ),
                ),
                ("lag_days", models.IntegerField(default=0)),
                ("rationale", models.CharField(max_length=255)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="organizations.organization",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="projects.project",
                    ),
                ),
                (
                    "predecessor_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="successor_links",
                        to="projects.projectscheduleitem",
                    ),
                ),
                (
                    "successor_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="predecessor_links",
                        to="projects.projectscheduleitem",
                    ),
                ),
                (
                    "schedule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="dependencies",
                        to="projects.projectschedulerevision",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ScheduleRebaselineProposal",
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
                ("occurrence_id", models.CharField(max_length=100)),
                ("reason", models.TextField()),
                ("evidence_reference", models.CharField(max_length=255)),
                ("payload_hash", models.CharField(max_length=64)),
                (
                    "candidate_revision",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rebaseline_candidates",
                        to="projects.projectschedulerevision",
                    ),
                ),
                (
                    "change_proposal",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="projects.projectchangeproposal",
                    ),
                ),
                (
                    "current_baseline",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rebaseline_sources",
                        to="projects.projectschedulerevision",
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
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rebaseline_proposals",
                        to="projects.project",
                    ),
                ),
                (
                    "proposed_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="projectchangeproposal",
            constraint=models.UniqueConstraint(
                fields=("organization", "project", "occurrence_id"),
                name="project_change_occurrence_uq",
            ),
        ),
        migrations.AddConstraint(
            model_name="projectchangeproposal",
            constraint=models.CheckConstraint(
                condition=models.Q(("contractual_impact_status", "unassessed")),
                name="project_change_contract_fail_closed_ck",
            ),
        ),
        migrations.AddConstraint(
            model_name="projectchangeproposal",
            constraint=models.CheckConstraint(
                condition=models.Q(("financial_effect_status", "observation_only")),
                name="project_change_finance_fail_closed_ck",
            ),
        ),
        migrations.AddConstraint(
            model_name="projectcontrolstatusevent",
            constraint=models.UniqueConstraint(
                fields=("item", "sequence"), name="project_control_status_seq_uq"
            ),
        ),
        migrations.AddConstraint(
            model_name="projectcontrolstatusevent",
            constraint=models.UniqueConstraint(
                fields=("item", "occurrence_id"),
                name="project_control_status_occurrence_uq",
            ),
        ),
        migrations.AddConstraint(
            model_name="projectcontrolitem",
            constraint=models.UniqueConstraint(
                fields=("organization", "project", "occurrence_id"),
                name="project_control_item_occurrence_uq",
            ),
        ),
        migrations.AddConstraint(
            model_name="projectcontrolitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("responsibility_status", "undetermined")),
                name="project_control_responsibility_fail_closed_ck",
            ),
        ),
        migrations.AddConstraint(
            model_name="projectcontrolitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("contractual_impact_status", "unassessed")),
                name="project_control_contract_fail_closed_ck",
            ),
        ),
        migrations.AddConstraint(
            model_name="projectschedulerevision",
            constraint=models.UniqueConstraint(
                fields=("project", "version_number"), name="project_schedule_version_uq"
            ),
        ),
        migrations.AddConstraint(
            model_name="projectschedulerevision",
            constraint=models.UniqueConstraint(
                fields=("organization", "occurrence_id"),
                name="project_schedule_occurrence_uq",
            ),
        ),
        migrations.AddConstraint(
            model_name="projectschedulerevision",
            constraint=models.CheckConstraint(
                condition=models.Q(("planned_finish__gte", models.F("planned_start"))),
                name="project_schedule_date_order_ck",
            ),
        ),
        migrations.AddConstraint(
            model_name="projectschedulerevision",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("accepted_at__isnull", True),
                        ("accepted_by__isnull", True),
                        ("status", "draft"),
                    ),
                    models.Q(
                        ("accepted_at__isnull", False),
                        ("accepted_by__isnull", False),
                        ("status", "accepted"),
                    ),
                    _connector="OR",
                ),
                name="project_schedule_acceptance_ck",
            ),
        ),
        migrations.AddConstraint(
            model_name="projectscheduleitem",
            constraint=models.UniqueConstraint(
                fields=("schedule", "code"), name="project_schedule_item_code_uq"
            ),
        ),
        migrations.AddConstraint(
            model_name="projectscheduleitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("planned_finish__gte", models.F("planned_start"))),
                name="project_schedule_item_date_order_ck",
            ),
        ),
        migrations.AddConstraint(
            model_name="projectscheduleitem",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("is_milestone", False),
                    ("planned_finish", models.F("planned_start")),
                    _connector="OR",
                ),
                name="project_schedule_milestone_date_ck",
            ),
        ),
        migrations.AddConstraint(
            model_name="projectscheduledependency",
            constraint=models.UniqueConstraint(
                fields=(
                    "schedule",
                    "predecessor_item",
                    "successor_item",
                    "dependency_type",
                ),
                name="project_schedule_dependency_uq",
            ),
        ),
        migrations.AddConstraint(
            model_name="projectscheduledependency",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("predecessor_item", models.F("successor_item")), _negated=True
                ),
                name="project_schedule_dependency_not_self_ck",
            ),
        ),
        migrations.AddConstraint(
            model_name="schedulerebaselineproposal",
            constraint=models.UniqueConstraint(
                fields=("organization", "project", "occurrence_id"),
                name="project_rebaseline_occurrence_uq",
            ),
        ),
        migrations.AddConstraint(
            model_name="schedulerebaselineproposal",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("current_baseline", models.F("candidate_revision")), _negated=True
                ),
                name="project_rebaseline_distinct_revision_ck",
            ),
        ),
        migrations.RunSQL(IMMUTABILITY_SQL, REVERSE_IMMUTABILITY_SQL),
    ]

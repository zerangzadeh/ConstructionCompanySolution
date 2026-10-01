import uuid
from decimal import Decimal
from typing import ClassVar

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


IMMUTABILITY_SQL = """
CREATE FUNCTION expenses_p4_control_guard() RETURNS trigger AS $$
BEGIN
    IF TG_TABLE_NAME IN ('expenses_expenseallocation', 'expenses_expensebudgetassessment') THEN
        RAISE EXCEPTION 'expense allocation and budget assessment evidence is immutable';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'expense evidence cannot be deleted';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.status IN ('submitted', 'approved', 'recorded', 'void')
       AND (
          NEW.organization_id IS DISTINCT FROM OLD.organization_id OR
          NEW.project_id IS DISTINCT FROM OLD.project_id OR
          NEW.phase_id IS DISTINCT FROM OLD.phase_id OR
          NEW.amount IS DISTINCT FROM OLD.amount OR
          NEW.incurred_on IS DISTINCT FROM OLD.incurred_on OR
          NEW.description IS DISTINCT FROM OLD.description OR
          NEW.source_reference IS DISTINCT FROM OLD.source_reference OR
          NEW.source_fingerprint IS DISTINCT FROM OLD.source_fingerprint OR
          NEW.classification IS DISTINCT FROM OLD.classification
       ) THEN
        RAISE EXCEPTION 'submitted expense source and financial evidence is immutable';
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER expenses_allocation_guard
BEFORE UPDATE OR DELETE ON expenses_expenseallocation
FOR EACH ROW EXECUTE FUNCTION expenses_p4_control_guard();
CREATE TRIGGER expenses_budget_assessment_guard
BEFORE UPDATE OR DELETE ON expenses_expensebudgetassessment
FOR EACH ROW EXECUTE FUNCTION expenses_p4_control_guard();
CREATE TRIGGER expenses_expense_guard
BEFORE UPDATE OR DELETE ON expenses_expense
FOR EACH ROW EXECUTE FUNCTION expenses_p4_control_guard();
"""

REVERSE_IMMUTABILITY_SQL = """
DROP TRIGGER IF EXISTS expenses_expense_guard ON expenses_expense;
DROP TRIGGER IF EXISTS expenses_budget_assessment_guard ON expenses_expensebudgetassessment;
DROP TRIGGER IF EXISTS expenses_allocation_guard ON expenses_expenseallocation;
DROP FUNCTION IF EXISTS expenses_p4_control_guard();
"""


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("expenses", "0004_expensedocumentlink"),
        ("organizations", "0067_p4_s21_s25_project_control_permissions"),
        ("parties", "0004_p1_s17_party_governance"),
        ("projects", "0008_p4_s21_s25_schedule_change_controls"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations: ClassVar[list] = [
        migrations.AddField(model_name="expense", name="approved_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="expense", name="approved_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="expenses_approved", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="expense", name="classification", field=models.CharField(choices=[("direct", "مستقیم"), ("indirect", "غیرمستقیم")], default="direct", max_length=16)),
        migrations.AddField(model_name="expense", name="idempotency_key", field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name="expense", name="recurrence_occurrence_on", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="expense", name="return_reason", field=models.TextField(blank=True)),
        migrations.AddField(model_name="expense", name="returned_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="expense", name="returned_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="expenses_returned", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="expense", name="settlement_status", field=models.CharField(choices=[("unsettled", "تسویه‌نشده"), ("external", "تسویه در مرجع بیرونی")], default="unsettled", max_length=16)),
        migrations.AddField(model_name="expense", name="source_fingerprint", field=models.CharField(blank=True, max_length=64)),
        migrations.AddField(model_name="expense", name="source_reference", field=models.CharField(blank=True, max_length=160)),
        migrations.AddField(model_name="expense", name="submitted_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="expense", name="submitted_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="expenses_submitted", to=settings.AUTH_USER_MODEL)),
        migrations.AlterField(model_name="expense", name="status", field=models.CharField(choices=[("draft", "پیش‌نویس"), ("submitted", "ارسال‌شده"), ("approved", "تأییدشده"), ("returned", "بازگردانده‌شده"), ("recorded", "ثبت‌شده"), ("void", "باطل‌شده")], db_index=True, default="recorded", max_length=20, verbose_name="وضعیت")),
        migrations.CreateModel(
            name="ExpenseAllocation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name="شناسه")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="زمان آخرین به‌روزرسانی")),
                ("sequence", models.PositiveIntegerField()),
                ("amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("allocation_basis_reference", models.CharField(max_length=255)),
                ("activity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="projects.activity")),
                ("cbs_node", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="projects.cbsnode")),
                ("cost_center", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="projects.costcenter")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="expense_allocations_created", to=settings.AUTH_USER_MODEL)),
                ("expense", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="allocations", to="expenses.expense")),
                ("governing_budget", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="projects.budgetversion")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organizations.organization")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="expense_allocations", to="projects.project")),
                ("wbs_node", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="projects.wbsnode")),
            ],
            options={"ordering": ["sequence"]},
        ),
        migrations.CreateModel(
            name="ExpenseBudgetAssessment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name="شناسه")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="زمان آخرین به‌روزرسانی")),
                ("accepted_budget_amount", models.DecimalField(decimal_places=2, max_digits=20)),
                ("prior_approved_expense_amount", models.DecimalField(decimal_places=2, max_digits=20)),
                ("proposed_amount", models.DecimalField(decimal_places=2, max_digits=20)),
                ("remaining_after_proposal", models.DecimalField(decimal_places=2, max_digits=20)),
                ("is_overrun", models.BooleanField()),
                ("control_mode", models.CharField(default="advisory_only", max_length=32)),
                ("assessed_at", models.DateTimeField()),
                ("allocation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="budget_assessments", to="expenses.expenseallocation")),
                ("expense", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="budget_assessments", to="expenses.expense")),
                ("governing_budget", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="projects.budgetversion")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organizations.organization")),
            ],
        ),
        migrations.CreateModel(
            name="RecurringExpenseTemplate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name="شناسه")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="زمان آخرین به‌روزرسانی")),
                ("description", models.CharField(max_length=255)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("classification", models.CharField(choices=[("direct", "مستقیم"), ("indirect", "غیرمستقیم")], max_length=16)),
                ("frequency", models.CharField(choices=[("weekly", "هفتگی"), ("monthly", "ماهانه")], max_length=16)),
                ("starts_on", models.DateField()),
                ("ends_on", models.DateField(blank=True, null=True)),
                ("source_reference_prefix", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organizations.organization")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="projects.project")),
            ],
        ),
        migrations.AddField(model_name="expense", name="recurrence_template", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="proposals", to="expenses.recurringexpensetemplate")),
        migrations.AddConstraint(model_name="expense", constraint=models.UniqueConstraint(condition=~models.Q(idempotency_key=""), fields=("organization", "idempotency_key"), name="expense_org_idempotency_uq")),
        migrations.AddConstraint(model_name="expense", constraint=models.UniqueConstraint(condition=~models.Q(source_fingerprint="") & ~models.Q(status="void"), fields=("organization", "source_fingerprint"), name="expense_org_source_fingerprint_uq")),
        migrations.AddConstraint(model_name="expense", constraint=models.UniqueConstraint(condition=models.Q(recurrence_template__isnull=False), fields=("recurrence_template", "recurrence_occurrence_on"), name="expense_recurrence_occurrence_uq")),
        migrations.AddConstraint(model_name="expenseallocation", constraint=models.UniqueConstraint(fields=("expense", "sequence"), name="expense_allocation_sequence_uq")),
        migrations.AddConstraint(model_name="expenseallocation", constraint=models.CheckConstraint(condition=models.Q(amount__gt=Decimal("0.00")), name="expense_allocation_amount_positive")),
        migrations.AddConstraint(model_name="recurringexpensetemplate", constraint=models.CheckConstraint(condition=models.Q(amount__gt=Decimal("0.00")), name="recurring_expense_amount_positive")),
        migrations.RunSQL(IMMUTABILITY_SQL, REVERSE_IMMUTABILITY_SQL),
    ]

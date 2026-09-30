import uuid
from decimal import Decimal
from typing import ClassVar

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("accounting", "0008_reconciliationreview"),
        ("audit", "0040_p2_statement_adjustment_actions"),
        ("organizations", "0055_p2_reporting_adjustment_permissions"),
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.CreateModel(
            name="FinancialStatementLineSnapshot",
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
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")),
                ("sequence", models.PositiveIntegerField()),
                ("account_code", models.CharField(max_length=50)),
                ("account_name", models.CharField(max_length=255)),
                (
                    "account_type",
                    models.CharField(
                        choices=[
                            ("asset", "دارایی"),
                            ("liability", "بدهی"),
                            ("equity", "حقوق مالکانه"),
                            ("income", "درآمد"),
                            ("expense", "هزینه"),
                        ],
                        max_length=20,
                    ),
                ),
                ("opening_debit", models.DecimalField(decimal_places=6, default=Decimal("0"), max_digits=24)),
                ("opening_credit", models.DecimalField(decimal_places=6, default=Decimal("0"), max_digits=24)),
                ("period_debit", models.DecimalField(decimal_places=6, default=Decimal("0"), max_digits=24)),
                ("period_credit", models.DecimalField(decimal_places=6, default=Decimal("0"), max_digits=24)),
                ("closing_debit", models.DecimalField(decimal_places=6, default=Decimal("0"), max_digits=24)),
                ("closing_credit", models.DecimalField(decimal_places=6, default=Decimal("0"), max_digits=24)),
                ("amount", models.DecimalField(decimal_places=6, default=Decimal("0"), max_digits=24)),
                ("source_line_count", models.PositiveIntegerField(default=0)),
                ("source_line_evidence", models.JSONField(default=list)),
            ],
            options={"ordering": ["run", "sequence"]},
        ),
        migrations.CreateModel(
            name="FinancialStatementRun",
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
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("trial_balance", "تراز آزمایشی"),
                            ("balance_sheet", "ترازنامه"),
                            ("profit_loss", "صورت سود و زیان"),
                        ],
                        max_length=24,
                    ),
                ),
                ("starts_on", models.DateField(blank=True, null=True)),
                ("ends_on", models.DateField()),
                ("currency", models.CharField(default="IRR", max_length=3)),
                ("scope_hash", models.CharField(max_length=64)),
                ("input_hash", models.CharField(max_length=64)),
                ("result_hash", models.CharField(max_length=64)),
                ("source_line_count", models.PositiveIntegerField(default=0)),
                ("debit_total", models.DecimalField(decimal_places=6, default=Decimal("0"), max_digits=24)),
                ("credit_total", models.DecimalField(decimal_places=6, default=Decimal("0"), max_digits=24)),
                ("net_total", models.DecimalField(decimal_places=6, default=Decimal("0"), max_digits=24)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="FiscalPeriodControlEvent",
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
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")),
                ("sequence", models.PositiveIntegerField()),
                ("action", models.CharField(choices=[("close", "بستن دوره"), ("reopen", "بازگشایی دوره")], max_length=12)),
                ("reason", models.TextField()),
                ("evidence_hash", models.CharField(max_length=64)),
            ],
            options={"ordering": ["period", "sequence"]},
        ),
        migrations.AddField(
            model_name="journalentry",
            name="adjustment_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="journalentry",
            name="adjusts",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="controlled_adjustments",
                to="accounting.journalentry",
            ),
        ),
        migrations.AddConstraint(
            model_name="journalentry",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("adjustment_reason__gt", ""),
                        ("adjusts__isnull", False),
                        ("kind", "manual"),
                    ),
                    models.Q(("adjustment_reason", ""), ("adjusts__isnull", True)),
                    _connector="OR",
                ),
                name="journal_controlled_adjustment_consistent",
            ),
        ),
        migrations.AddField(
            model_name="financialstatementlinesnapshot",
            name="account",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="financial_statement_snapshots",
                to="accounting.account",
            ),
        ),
        migrations.AddField(
            model_name="financialstatementlinesnapshot",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="accounting_statement_line_snapshots",
                to="organizations.organization",
            ),
        ),
        migrations.AddField(
            model_name="financialstatementrun",
            name="created_by",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="accounting_statement_runs_created",
                to="organizations.organizationmembership",
            ),
        ),
        migrations.AddField(
            model_name="financialstatementrun",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="accounting_statement_runs",
                to="organizations.organization",
            ),
        ),
        migrations.AddField(
            model_name="financialstatementlinesnapshot",
            name="run",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="lines",
                to="accounting.financialstatementrun",
            ),
        ),
        migrations.AddField(
            model_name="fiscalperiodcontrolevent",
            name="acted_by",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="accounting_period_controls_acted",
                to="organizations.organizationmembership",
            ),
        ),
        migrations.AddField(
            model_name="fiscalperiodcontrolevent",
            name="balance_sheet_run",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="period_balance_sheet_close_events",
                to="accounting.financialstatementrun",
            ),
        ),
        migrations.AddField(
            model_name="fiscalperiodcontrolevent",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="accounting_period_control_events",
                to="organizations.organization",
            ),
        ),
        migrations.AddField(
            model_name="fiscalperiodcontrolevent",
            name="period",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="control_events",
                to="accounting.fiscalperiod",
            ),
        ),
        migrations.AddField(
            model_name="fiscalperiodcontrolevent",
            name="profit_loss_run",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="period_profit_loss_close_events",
                to="accounting.financialstatementrun",
            ),
        ),
        migrations.AddField(
            model_name="fiscalperiodcontrolevent",
            name="reconciliation_run",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="period_close_events",
                to="accounting.reconciliationrun",
            ),
        ),
        migrations.AddField(
            model_name="fiscalperiodcontrolevent",
            name="related_close",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reopen_event",
                to="accounting.fiscalperiodcontrolevent",
            ),
        ),
        migrations.AddField(
            model_name="fiscalperiodcontrolevent",
            name="requested_by",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="accounting_period_controls_requested",
                to="organizations.organizationmembership",
            ),
        ),
        migrations.AddField(
            model_name="fiscalperiodcontrolevent",
            name="trial_balance_run",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="period_trial_balance_close_events",
                to="accounting.financialstatementrun",
            ),
        ),
        migrations.AddConstraint(
            model_name="financialstatementrun",
            constraint=models.UniqueConstraint(
                fields=("organization", "kind", "starts_on", "ends_on", "input_hash"),
                name="statement_run_unique_retained_input",
                nulls_distinct=False,
            ),
        ),
        migrations.AddConstraint(
            model_name="financialstatementrun",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("ends_on__gte", models.F("starts_on")),
                    ("starts_on__isnull", True),
                    _connector="OR",
                ),
                name="statement_run_valid_interval",
            ),
        ),
        migrations.AddConstraint(
            model_name="financialstatementlinesnapshot",
            constraint=models.UniqueConstraint(
                fields=("run", "sequence"), name="statement_line_unique_sequence"
            ),
        ),
        migrations.AddConstraint(
            model_name="financialstatementlinesnapshot",
            constraint=models.UniqueConstraint(
                fields=("run", "account"), name="statement_line_unique_account"
            ),
        ),
        migrations.AddConstraint(
            model_name="fiscalperiodcontrolevent",
            constraint=models.UniqueConstraint(
                fields=("period", "sequence"), name="period_control_unique_sequence"
            ),
        ),
        migrations.AddConstraint(
            model_name="fiscalperiodcontrolevent",
            constraint=models.CheckConstraint(
                condition=models.Q(("sequence__gte", 1)),
                name="period_control_sequence_positive",
            ),
        ),
    ]

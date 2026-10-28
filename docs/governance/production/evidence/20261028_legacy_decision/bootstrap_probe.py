"""Actual empty/populated production-settings qualification in new synthetic DBs."""

import hashlib
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import django

django.setup()

from django.apps import apps as runtime_apps
from django.conf import settings
from django.core.management import call_command
from django.db import connection, models, transaction
from django.db.migrations.executor import MigrationExecutor
from psycopg import sql

OUT = Path("/evidence")
PRE = [
    ("documents", "0011_documentcategory_employee_current_visible_and_more"),
    ("billing", "0017_cep037_variation_billing_eligibility"),
    (
        "treasury",
        "0009_remove_paymentrequest_treasury_request_beneficiary_consistent_and_more",
    ),
    ("payments", "0006_paymentdocumentlink"),
]
LEGACY = {
    "payments_payment",
    "payments_paymentallocation",
    "payments_paymentdocumentlink",
    "billing_claimsettlementallocation",
}


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, default=str) + "\n")


def rows(tables):
    result = {}
    with connection.cursor() as cursor:
        for table in sorted(tables):
            cursor.execute(
                sql.SQL("SELECT row_to_json(t)::text FROM {} t").format(
                    sql.Identifier(table)
                )
            )
            data = sorted(row[0] for row in cursor.fetchall())
            result[table] = {
                "rows": len(data),
                "sha256": hashlib.sha256(json.dumps(data).encode()).hexdigest(),
            }
    return result


def financial_rows():
    tables = connection.introspection.table_names()
    return rows(
        {t for t in tables if t.startswith(("accounting_", "treasury_", "subledgers_"))}
    )


def populate(historical):
    counter = [0]
    cache = {}

    def create(model, **supplied):
        counter[0] += 1
        key = model._meta.label
        # Fixtures create only required historical values/relations; no domain
        # command, recognition, cash, settlement or journal reconstruction.
        values = dict(supplied)
        for field in model._meta.local_fields:
            if (
                field.name in values
                or field.attname in values
                or field.primary_key
                or field.null
                or field.has_default()
                or (
                    field.blank
                    and isinstance(field, (models.CharField, models.TextField))
                )
                or getattr(field, "auto_now", False)
                or getattr(field, "auto_now_add", False)
            ):
                continue
            if field.is_relation:
                related = field.remote_field.model
                if related._meta.label not in cache:
                    cache[related._meta.label] = create(related)
                values[field.name] = cache[related._meta.label]
            elif isinstance(field, models.DecimalField):
                values[field.name] = Decimal("11.00")
            elif isinstance(field, models.DateTimeField):
                from django.utils import timezone

                values[field.name] = timezone.now()
            elif isinstance(field, models.DateField):
                values[field.name] = date(2026, 1, 1)
            elif isinstance(field, models.BooleanField):
                values[field.name] = False
            elif isinstance(field, models.IntegerField):
                values[field.name] = 1
            elif isinstance(field, models.UUIDField):
                values[field.name] = uuid4()
            elif isinstance(field, models.JSONField):
                values[field.name] = {}
            else:
                choices = list(field.flatchoices)
                value = choices[0][0] if choices else f"synthetic-{counter[0]}"
                if field.name in {"currency", "currency_code"}:
                    value = "IRR"
                values[field.name] = (
                    str(value)[: field.max_length] if field.max_length else str(value)
                )
        obj = model.objects.create(**values)
        cache.setdefault(key, obj)
        return obj

    for number in (1, 2):
        cache.clear()
        org = create(
            historical.get_model("organizations", "Organization"),
            name=f"Retired synthetic {number}",
            slug=f"retired-synthetic-{number}",
        )
        cache["organizations.Organization"] = org
        project = create(
            historical.get_model("projects", "Project"),
            organization=org,
            code=f"RET-{number}",
        )
        cache["projects.Project"] = project
        contract = create(
            historical.get_model("contracts", "Contract"),
            organization=org,
            project=project,
            contract_number=f"RET-{number}",
        )
        cache["contracts.Contract"] = contract
        payment = create(
            historical.get_model("payments", "Payment"),
            organization=org,
            project=project,
            contract=contract,
            payment_number=f"HISTORICAL-{number}",
            amount=Decimal("123.45"),
            paid_on=date(2025, 1, 1),
            status="posted" if number == 1 else "void",
        )
        allocation = create(
            historical.get_model("payments", "PaymentAllocation"),
            organization=org,
            payment=payment,
            contract=contract,
            amount=Decimal("11.00"),
        )
        claim = create(
            historical.get_model("billing", "ProgressClaim"),
            organization=org,
            project=project,
            contract=contract,
            claim_number=number,
        )
        create(
            historical.get_model("billing", "ClaimSettlementAllocation"),
            organization=org,
            claim=claim,
            payment_allocation=allocation,
            amount=Decimal("11.00"),
        )
        document = create(
            historical.get_model("documents", "Document"),
            organization=org,
            document_number=f"RET-{number}",
        )
        create(
            historical.get_model("payments", "PaymentDocumentLink"),
            organization=org,
            payment=payment,
            document=document,
        )
        create(
            historical.get_model("documents", "DocumentLink"),
            organization=org,
            payment=payment,
            document=document,
        )
        create(
            historical.get_model("audit", "AuditEvent"),
            organization=org,
            entity_id=str(payment.pk),
            action="historical.synthetic.retired",
            entity_type="payments.Payment",
        )
        # Independent active GL fixture, unrelated to any legacy amounts/IDs.
        # Draft history is hashed before migration; no legacy recognition occurs.
        debit_account = create(
            historical.get_model("accounting", "Account"),
            organization=org,
            code=f"ACTIVE-A-{number}",
            account_type="asset",
            is_posting=True,
        )
        credit_account = create(
            historical.get_model("accounting", "Account"),
            organization=org,
            code=f"ACTIVE-B-{number}",
            account_type="equity",
            is_posting=True,
        )
        journal = create(
            historical.get_model("accounting", "JournalEntry"),
            organization=org,
            number=None,
            status="draft",
        )
        for line_number, account, debit, credit in [
            (1, debit_account, Decimal("987.65"), Decimal(0)),
            (2, credit_account, Decimal(0), Decimal("987.65")),
        ]:
            create(
                historical.get_model("accounting", "JournalLine"),
                organization=org,
                journal=journal,
                account=account,
                line_number=line_number,
                debit=debit,
                credit=credit,
            )


def main():
    assert (
        settings.SETTINGS_MODULE == "config.settings.production" and not settings.DEBUG
    )
    assert settings.DATABASES["default"]["NAME"].startswith("pe_legacy_20261028_")
    assert settings.DATABASES["default"]["HOST"] == "db"
    assert settings.DATABASES["default"]["OPTIONS"]["sslmode"] == "verify-full"
    action, phase = sys.argv[1:3]
    if action == "prepare":
        executor = MigrationExecutor(connection)
        assert not any(
            m.app_label == "documents" and m.name.startswith("0012")
            for m, _ in executor.migration_plan(PRE)
        )
        executor.migrate(PRE)
        save(
            "PREPARED.json",
            {"result": "PASS", "targets": PRE, "production_settings": True},
        )
        return
    executor = MigrationExecutor(connection)
    if phase == "populated":
        with transaction.atomic():
            populate(executor.loader.project_state(PRE).apps)
    before = rows(LEGACY)
    active_before = financial_rows()
    save(phase + "_BEFORE.json", {"retired": before, "active_financial": active_before})
    previous_evidence = None
    if phase == "populated":
        # Explicit synthetic upgrade fixture: one already-accepted snapshot under
        # the older disposition must survive this decision without rewriting.
        partial = [
            ("documents", "0012_legacy_payment_reference_preparation"),
            ("treasury", "0010_legacy_payment_reference_preparation"),
        ]
        MigrationExecutor(connection).migrate(partial)
        historical = MigrationExecutor(connection).loader.project_state(partial).apps
        evidence_model = historical.get_model("documents", "RetiredPaymentEvidence")
        first = evidence_model.objects.order_by("pk").first()
        snapshot = dict(first.source_snapshot, disposition="excluded_demo_test")
        evidence_model.objects.filter(pk=first.pk).update(
            source_snapshot=snapshot,
            source_sha256=hashlib.sha256(
                json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            authority_reference="synthetic-prior-accepted-disposition",
        )
        previous_evidence = evidence_model.objects.values().get(pk=first.pk)
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())
    # Synchronize the code-owned catalogs, then prove no pending graph or drift.
    call_command("migrate", interactive=False, verbosity=0)
    call_command("makemigrations", check=True, dry_run=True, verbosity=0)
    call_command("check", deploy=True, fail_level="WARNING")
    assert before == rows(LEGACY), "Original retired rows changed or removed"
    after = financial_rows()
    assert all(after[t] == value for t, value in active_before.items()), (
        "Active financial records changed"
    )
    assert all(after[t]["rows"] == 0 for t in set(after) - set(active_before)), (
        "Financial targets fabricated"
    )
    assert list(runtime_apps.get_app_config("payments").get_models()) == []
    from apps.documents.models import (
        DocumentLink,
        RetiredPaymentDocumentLink,
        RetiredPaymentEvidence,
    )
    from apps.organizations.models import BusinessPermission

    assert not BusinessPermission.objects.filter(code__startswith="payments.").exists()
    expected = 2 if phase == "populated" else 0
    assert RetiredPaymentEvidence.objects.count() == expected
    evidence_before = list(RetiredPaymentEvidence.objects.order_by("pk").values())
    for evidence in RetiredPaymentEvidence.objects.all():
        assert evidence.source_snapshot["disposition"] in {
            "RETIRED_LEGACY_DATA",
            "excluded_demo_test",
        }
        assert (
            hashlib.sha256(
                json.dumps(
                    evidence.source_snapshot, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
            == evidence.source_sha256
        )
        assert (
            RetiredPaymentDocumentLink.objects.filter(
                payment=evidence, organization=evidence.organization
            ).count()
            == 1
        )
        assert (
            DocumentLink.objects.filter(
                payment=evidence, organization=evidence.organization
            ).count()
            == 1
        )
    if previous_evidence:
        assert previous_evidence == RetiredPaymentEvidence.objects.values().get(
            pk=previous_evidence["id"]
        )
    # Repeat the preservation step through historical models, without rewriting.
    from importlib import import_module

    preservation = import_module(
        "apps.billing.migrations.0018_retire_legacy_claim_settlements"
    )
    historical = (
        MigrationExecutor(connection)
        .loader.project_state(
            [
                ("documents", "0012_legacy_payment_reference_preparation"),
                ("treasury", "0010_legacy_payment_reference_preparation"),
            ]
        )
        .apps
    )
    with connection.schema_editor() as editor:
        preservation.verify_retirement(historical, editor)
    assert evidence_before == list(
        RetiredPaymentEvidence.objects.order_by("pk").values()
    )
    assert before == rows(LEGACY)
    save(
        phase + "_RESULT.json",
        {
            "result": "PASS",
            "settings": settings.SETTINGS_MODULE,
            "debug": settings.DEBUG,
            "phase": phase,
            "database": settings.DATABASES["default"]["NAME"],
            "legacy_rows": sum(v["rows"] for v in before.values()),
            "retired_tables": before,
            "original_rows_preserved_exactly": True,
            "active_financial_records_preserved": True,
            "financial_targets_created": 0,
            "evidence_records": expected,
            "disposition": "RETIRED_LEGACY_DATA",
            "typed_and_generic_links_preserved": expected * 2,
            "idempotent_preservation": True,
            "legacy_orm_and_permissions": "ABSENT",
            "previously_accepted_snapshot_preserved": previous_evidence is not None,
            "migration_nodes": len(MigrationExecutor(connection).loader.graph.nodes),
            "drift_and_deploy_checks": "PASS",
            "production_action": False,
        },
    )


if __name__ == "__main__":
    main()

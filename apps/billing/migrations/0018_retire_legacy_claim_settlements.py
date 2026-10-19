"""Development-only contract; populated databases require exact readiness proof."""

import hashlib
import json
import os
from importlib import import_module
from pathlib import Path

from django.conf import settings
from django.db import migrations


def candidate_digest(root):
    digest = hashlib.sha256()
    for base in ("apps", "core", "config", "templates", "tests"):
        for path in sorted((root / base).rglob("*")):
            if path.is_file() and path.suffix in {".py", ".html"}:
                digest.update(path.relative_to(root).as_posix().encode())
                digest.update(b"\0")
                digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
                digest.update(b"\0")
    return digest.hexdigest()


def verify_retirement(apps, schema_editor):
    connection = schema_editor.connection
    if (
        settings.SETTINGS_MODULE != "config.settings.development"
        or connection.settings_dict["HOST"] not in {"localhost", "127.0.0.1", "::1"}
    ):
        raise RuntimeError("Legacy Payment retirement is local Development only")
    alias = connection.alias
    Payment = apps.get_model("payments", "Payment")
    Evidence = apps.get_model("documents", "RetiredPaymentEvidence")
    if apps.get_model("organizations", "Organization").objects.using(alias).exists():
        name = connection.settings_dict["NAME"]
        rehearsal = (
            name.startswith("bonira_retire_")
            and os.getenv("BONIRA_LEGACY_PAYMENT_REHEARSAL_DB") == name
        )
        if not rehearsal:
            root = Path(settings.BASE_DIR)
            gate = json.loads(
                (
                    root
                    / "docs/governance/cep/evidence/CEP-064_RETIREMENT_READINESS.json"
                ).read_text(encoding="utf-8")
            )
            conditions = gate["conditions"]
            if (
                gate.get("LEGACY_PAYMENT_RETIREMENT_READINESS") != "PASS"
                or len(conditions) != 12
                or {row["number"] for row in conditions} != set(range(1, 13))
                or any(row["status"] != "PASS" for row in conditions)
                or gate.get("candidate_digest") != candidate_digest(root)
            ):
                raise RuntimeError(
                    "Exact twelve-condition candidate readiness proof required"
                )
        for pk in Payment.objects.using(alias).values_list("pk", flat=True):
            if not Evidence.objects.using(alias).filter(pk=pk).exists():
                raise RuntimeError("Source has no approved retained disposition")
    # Immutable historical preparation detects changed source/dependent/audit data.
    preparation = import_module(
        "apps.documents.migrations.0012_legacy_payment_reference_preparation"
    )
    preparation.preserve_excluded_sources(apps, schema_editor)
    SourceLink = apps.get_model("payments", "PaymentDocumentLink")
    RetainedLink = apps.get_model("documents", "RetiredPaymentDocumentLink")
    fields = (
        "organization_id",
        "document_id",
        "payment_id",
        "created_by_id",
        "created_at",
        "legacy_link_id",
    )
    for row in SourceLink.objects.using(alias).all():
        retained = RetainedLink.objects.using(alias).get(pk=row.pk)
        if any(getattr(row, field) != getattr(retained, field) for field in fields):
            raise RuntimeError("Retained document identity mismatch")


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0017_cep037_variation_billing_eligibility"),
        ("documents", "0012_legacy_payment_reference_preparation"),
        ("treasury", "0010_legacy_payment_reference_preparation"),
    ]
    # Recovery is the verified native checkpoint, never an empty schema downgrade.
    operations = [
        migrations.RunPython(verify_retirement),
        migrations.DeleteModel(name="ClaimSettlementAllocation"),
    ]

"""Read-only Development verification of the excluded-source retention boundary."""

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.conf import settings
from django.db import connection
from django.db.migrations.loader import MigrationLoader

from apps.audit.models import AuditEvent
from apps.documents.models import (
    DocumentLink,
    RetiredPaymentDocumentLink,
    RetiredPaymentEvidence,
)


def normalized(value):
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def verify():
    if settings.SETTINGS_MODULE != "config.settings.development":
        raise RuntimeError("Development-only evidence verification")
    retired = "payments_payment" not in connection.introspection.table_names()
    if retired:
        return verify_retired()
    historical = (
        MigrationLoader(connection)
        .project_state(
            [
                ("documents", "0012_legacy_payment_reference_preparation"),
                ("treasury", "0010_legacy_payment_reference_preparation"),
            ]
        )
        .apps
    )
    Payment = historical.get_model("payments", "Payment")
    PaymentAllocation = historical.get_model("payments", "PaymentAllocation")
    PaymentDocumentLink = historical.get_model("payments", "PaymentDocumentLink")
    ClaimSettlementAllocation = historical.get_model(
        "billing", "ClaimSettlementAllocation"
    )
    count = 0
    audit_ids_verified = 0
    for source in Payment.objects.order_by("pk"):
        evidence = RetiredPaymentEvidence.objects.get(
            pk=source.pk, organization_id=source.organization_id
        )
        snapshot = evidence.source_snapshot
        audit_ids = snapshot["audit_ids"]
        if AuditEvent.objects.filter(
            organization_id=source.organization_id, pk__in=audit_ids
        ).count() != len(audit_ids):
            raise RuntimeError("Retained audit identity missing")
        audit_ids_verified += len(audit_ids)
        encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
        if hashlib.sha256(encoded).hexdigest() != evidence.source_sha256:
            raise RuntimeError("Retained snapshot digest mismatch")
        if snapshot["payment"] != normalized(
            Payment.objects.filter(pk=source.pk).values().get()
        ):
            raise RuntimeError("Source changed after archival preparation")
        allocations = PaymentAllocation.objects.filter(payment=source)
        for key, rows in (
            ("allocations", allocations.values()),
            (
                "billing_settlements",
                ClaimSettlementAllocation.objects.filter(
                    payment_allocation__in=allocations
                ).values(),
            ),
            (
                "typed_document_links",
                PaymentDocumentLink.objects.filter(payment=source).values(),
            ),
            (
                "generic_document_links",
                DocumentLink.objects.filter(payment_id=source.pk).values(),
            ),
        ):
            expected = normalized(list(rows))
            if sorted(snapshot[key], key=lambda r: r["id"]) != sorted(
                expected, key=lambda r: r["id"]
            ):
                raise RuntimeError("Dependent retained source changed")
        count += 1
    for source in PaymentDocumentLink.objects.all():
        target = RetiredPaymentDocumentLink.objects.get(pk=source.pk)
        fields = (
            "document_id",
            "payment_id",
            "organization_id",
            "created_by_id",
            "created_at",
            "legacy_link_id",
        )
        if any(getattr(source, f) != getattr(target, f) for f in fields):
            raise RuntimeError("Retained typed document identity changed")
    return {
        "status": "PASS",
        "excluded_sources_verified": count,
        "retained_evidence_count": RetiredPaymentEvidence.objects.count(),
        "typed_document_identities_verified": PaymentDocumentLink.objects.count(),
        "generic_document_references_verified": DocumentLink.objects.filter(
            payment__isnull=False
        ).count(),
        "source_and_dependent_values_unchanged": True,
        "audit_identities_verified": audit_ids_verified,
        "destructive_retirement_executed": False,
    }


def verify_retired():
    """Validate retained evidence and every document/audit identity after removal."""
    audit_ids_verified = 0
    for evidence in RetiredPaymentEvidence.objects.all():
        snapshot = evidence.source_snapshot
        encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
        if hashlib.sha256(encoded).hexdigest() != evidence.source_sha256:
            raise RuntimeError("Retained snapshot digest mismatch")
        if snapshot["payment"]["id"] != str(evidence.pk):
            raise RuntimeError("Retained source identity mismatch")
        ids = snapshot["audit_ids"]
        if AuditEvent.objects.filter(
            organization_id=evidence.organization_id, pk__in=ids
        ).count() != len(ids):
            raise RuntimeError("Retained audit identity missing")
        audit_ids_verified += len(ids)
        for row in snapshot["typed_document_links"]:
            link = RetiredPaymentDocumentLink.objects.get(
                pk=row["id"], organization_id=evidence.organization_id
            )
            if (
                str(link.payment_id) != str(evidence.pk)
                or str(link.document_id) != row["document_id"]
            ):
                raise RuntimeError("Retained typed identity mismatch")
        for row in snapshot["generic_document_links"]:
            link = DocumentLink.objects.get(
                pk=row["id"], organization_id=evidence.organization_id
            )
            if (
                str(link.payment_id) != str(evidence.pk)
                or str(link.document_id) != row["document_id"]
            ):
                raise RuntimeError("Retained generic identity mismatch")
    tables = set(connection.introspection.table_names())
    if tables & {
        "payments_payment",
        "payments_paymentallocation",
        "payments_paymentdocumentlink",
        "billing_claimsettlementallocation",
    }:
        raise RuntimeError("Legacy table remains")
    return {
        "status": "PASS",
        "retained_evidence_count": RetiredPaymentEvidence.objects.count(),
        "typed_document_identities_verified": RetiredPaymentDocumentLink.objects.count(),
        "generic_document_references_verified": DocumentLink.objects.filter(
            payment__isnull=False
        ).count(),
        "audit_identities_verified": audit_ids_verified,
        "destructive_retirement_executed": True,
    }


if __name__ == "__main__":
    result = verify()
    if "--no-write" not in sys.argv:
        (ROOT / "docs/governance/cep/evidence/CEP-064_REFERENCE_RETENTION.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(result))

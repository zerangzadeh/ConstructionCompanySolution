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

from apps.audit.models import AuditEvent
from apps.billing.models import ClaimSettlementAllocation
from apps.documents.models import (
    DocumentLink,
    RetiredPaymentDocumentLink,
    RetiredPaymentEvidence,
)
from apps.payments.models import Payment, PaymentAllocation, PaymentDocumentLink


def normalized(value):
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def verify():
    if settings.SETTINGS_MODULE != "config.settings.development":
        raise RuntimeError("Development-only evidence verification")
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


if __name__ == "__main__":
    result = verify()
    (ROOT / "docs/governance/cep/evidence/CEP-064_REFERENCE_RETENTION.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result))

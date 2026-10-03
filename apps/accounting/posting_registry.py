"""Code-owned posting contracts for the bounded P2 accounting kernel."""

from dataclasses import dataclass

from django.core.exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class PostingContract:
    source_kind: str
    event_kind: str
    rule_code: str
    rule_version: int
    source_owner: str
    source_model: str
    source_line_model: str
    operational_producer: bool = False


_CONTRACTS = {
    ("manual", "manual_entry"): PostingContract(
        source_kind="manual",
        event_kind="manual_entry",
        rule_code="core.manual-journal",
        rule_version=1,
        source_owner="accounting",
        source_model="accounting.JournalEntry",
        source_line_model="accounting.JournalLine",
    ),
    ("opening", "opening_balance"): PostingContract(
        source_kind="opening",
        event_kind="opening_balance",
        rule_code="core.opening-balance",
        rule_version=1,
        source_owner="accounting",
        source_model="accounting.OpeningBalanceImport|accounting.JournalEntry",
        source_line_model="accounting.OpeningBalanceImportLine|accounting.JournalLine",
    ),
    ("accounting", "reversal"): PostingContract(
        source_kind="accounting",
        event_kind="reversal",
        rule_code="core.journal-reversal",
        rule_version=1,
        source_owner="accounting",
        source_model="accounting.JournalEntry",
        source_line_model="accounting.JournalLine",
    ),
    ("accounting", "replacement"): PostingContract(
        source_kind="accounting",
        event_kind="replacement",
        rule_code="core.journal-replacement",
        rule_version=1,
        source_owner="accounting",
        source_model="accounting.JournalEntry",
        source_line_model="accounting.JournalLine",
    ),
    ("treasury", "movement_posted"): PostingContract(
        source_kind="treasury",
        event_kind="movement_posted",
        rule_code="treasury.movement.posted.v1",
        rule_version=1,
        source_owner="treasury",
        source_model="treasury.TreasuryMovement",
        source_line_model="treasury.TreasuryMovementLeg",
        operational_producer=True,
    ),
    ("billing.progress_claim.v1", "claim_approved"): PostingContract(
        source_kind="billing.progress_claim.v1",
        event_kind="claim_approved",
        rule_code="billing.receivable-claim.approved.v1",
        rule_version=1,
        source_owner="billing",
        source_model="billing.ProgressClaim",
        source_line_model="billing.ProgressClaimItem|billing.ClaimAdjustment",
        operational_producer=False,
    ),
    ("billing.payable_certificate.v1", "certificate_approved"): PostingContract(
        source_kind="billing.payable_certificate.v1",
        event_kind="certificate_approved",
        rule_code="billing.payable-certificate.approved.v1",
        rule_version=1,
        source_owner="billing",
        source_model="billing.PayableCertificate",
        source_line_model=(
            "billing.PayableCertificateItem|billing.PayableCertificateAdjustment"
        ),
        operational_producer=False,
    ),
}


def get_posting_contract(*, source_kind: str, event_kind: str) -> PostingContract:
    """Resolve a platform-owned contract; Tenant-authored rules are not accepted."""

    try:
        return _CONTRACTS[(source_kind, event_kind)]
    except KeyError as exc:
        raise ValidationError(
            "منبع یا رویداد ثبت حسابداری در سامانه ثبت نشده است."
        ) from exc


def registered_posting_contracts() -> tuple[PostingContract, ...]:
    """Expose the closed, code-owned registry for lineage/reconciliation checks."""

    return tuple(_CONTRACTS.values())

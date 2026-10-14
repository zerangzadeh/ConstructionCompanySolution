"""Frozen CEP-008 recognition-owner policy resolution.

This registry is deliberately code-owned and has no persistence or posting side
effects. Downstream source-family integrations must resolve a policy here before
they can request an Accounting recognition output.
"""

from dataclasses import dataclass
from uuid import UUID

from django.core.exceptions import ValidationError

UNSPECIFIED_RECOGNITION_POLICY = "UNSPECIFIED RECOGNITION POLICY"


@dataclass(frozen=True, slots=True)
class RecognitionOwnerPolicy:
    source_family: str
    economic_occurrence: str
    source_identity_rule: str
    source_version_rule: str
    recognition_type: str
    recognition_owner: str
    creates_obligation: str
    creates_accounting_entry: str
    settlement_owner: str
    accounting_integration: str
    reversal_owner: str
    correction_owner: str
    reconciliation_requirement: str
    governing_pd: str
    integration_contract: str
    v1_status: str


@dataclass(frozen=True, slots=True)
class RecognitionRequest:
    """A caller-validated request to resolve one canonical occurrence."""

    organization_id: UUID
    source_organization_id: UUID
    source_family: str
    economic_occurrence: str
    source_identity: UUID | None
    source_version: int | None
    recognition_type: str
    recognition_owner: str
    object_scope_authorized: bool


@dataclass(frozen=True, slots=True)
class RecognitionIdentity:
    """The canonical duplicate-recognition identity; it creates no new key."""

    source_family: str
    economic_occurrence: str
    source_identity: UUID
    source_version: int
    recognition_type: str
    recognition_owner: str


@dataclass(frozen=True, slots=True)
class RecognitionResolution:
    policy: RecognitionOwnerPolicy
    identity: RecognitionIdentity

    def audit_metadata(self) -> dict[str, str | int]:
        """Provide source/owner linkage for an Accounting-owned audit event."""

        return {
            "source_family": self.identity.source_family,
            "economic_occurrence": self.identity.economic_occurrence,
            "source_identity": str(self.identity.source_identity),
            "source_version": self.identity.source_version,
            "recognition_type": self.identity.recognition_type,
            "recognition_owner": self.identity.recognition_owner,
            "reversal_owner": self.policy.reversal_owner,
            "correction_owner": self.policy.correction_owner,
            "reconciliation_requirement": self.policy.reconciliation_requirement,
        }


@dataclass(frozen=True, slots=True)
class RecognitionAttempt:
    """The duplicate guard result a downstream owner must honor before output."""

    resolution: RecognitionResolution
    is_replay: bool


_POLICIES = (
    RecognitionOwnerPolicy(
        "Billing Progress Claim",
        "Approved claim recognized as AR obligation",
        "ProgressClaim UUID",
        "Claim revision/version",
        "AR receivable recognition",
        "Subledgers — source-family AR recognition",
        "AR=YES",
        "L2 Accounting draft only when matrix row/mapping active",
        "Treasury via SettlementAllocation",
        "Source-family recognition control under PD-030",
        "Billing/Subledgers controlled reversal",
        "Billing correction + Subledger recognition correction",
        "AR obligation ↔ Accounting control account ↔ Treasury settlement",
        "PD-030; PD-013",
        "EDGE-04 + recognition-control contract",
        "V1",
    ),
    RecognitionOwnerPolicy(
        "Billing Payable Certificate",
        "Approved payable certificate recognized as AP obligation",
        "PayableCertificate UUID",
        "Certificate revision/version",
        "AP liability recognition",
        "Subledgers — source-family AP recognition",
        "AP=YES",
        "L2 Accounting draft only when matrix/mapping active",
        "Treasury via SettlementAllocation",
        "Source-family recognition control under PD-030",
        "Subledgers/source correction lineage",
        "Billing correction + Subledger correction",
        "AP obligation ↔ Accounting control account ↔ Treasury settlement",
        "PD-030; PD-013",
        "EDGE-05 + recognition-control contract",
        "V1",
    ),
    RecognitionOwnerPolicy(
        "Procurement Supplier Invoice Match",
        "Approved supplier invoice/match recognized as AP obligation",
        "Supplier invoice UUID + match identity",
        "Invoice version + match version",
        "AP liability / source recognition",
        "Subledgers — explicit AP source-family recognition",
        "AP=YES",
        "L2 Accounting draft under source-family mapping",
        "Treasury",
        "INT-B01 + source-family recognition",
        "Subledgers/source reversal",
        "Procurement superseding source + Subledger correction",
        "Invoice/match ↔ AP obligation ↔ Accounting control account",
        "PD-008; PD-030",
        "INT-B01",
        "V1",
    ),
    RecognitionOwnerPolicy(
        "Treasury Cash Movement",
        "Posted Treasury movement",
        "TreasuryMovement UUID",
        "Movement version / reversal lineage",
        "Cash / clearing recognition",
        "Treasury",
        "NO",
        "YES — existing contract",
        "Treasury",
        "EDGE-07 / Treasury posting registry",
        "Treasury + Accounting reversal",
        "Treasury correction/replacement + Accounting correction",
        "Treasury movement ↔ Accounting journal ↔ settlement/bank evidence",
        "PD-001; PD-030",
        "EDGE-07 / INT-R01 boundary",
        "V1",
    ),
    RecognitionOwnerPolicy(
        "Inventory",
        "Eligible posted inventory financial-effect event",
        "StockTransaction / valuation evidence ID",
        "Transaction/version + valuation version",
        "Inventory asset/COGS/consumption recognition",
        "Inventory",
        "NO",
        "YES — L2",
        "N/A",
        "INT-A01",
        "Inventory reversal",
        "Inventory correction/revaluation",
        "Inventory valuation ↔ Accounting",
        "PD-011; PD-030",
        "INT-A01",
        "V1",
    ),
    RecognitionOwnerPolicy(
        "Payroll",
        "Finalized payroll expense/liability occurrence",
        "Payroll run + occurrence identity",
        "Payroll run revision/version",
        "Payroll expense/liability recognition",
        "Payroll",
        "AP only by separate authorized liability path",
        "YES — L2",
        "Treasury for payment",
        "INT-A02",
        "Payroll correction/replacement + Accounting reversal",
        "Payroll",
        "Payroll totals ↔ Accounting",
        "PD-009; PD-030",
        "INT-A02",
        "V1",
    ),
    RecognitionOwnerPolicy(
        "Payroll",
        "Payroll payable/disbursement request",
        "Payroll run/payment batch identity",
        "Payroll version + payment batch",
        "Settlement request — not new expense recognition",
        "Payroll for payable evidence; Treasury for cash settlement",
        "NO unless separate approved AP path",
        "NO new GL expense entry",
        "Treasury",
        "INT-A03",
        "Treasury reversal / Payroll replacement reference",
        "Payroll/Treasury correction",
        "Payroll net payable ↔ Treasury requested/paid/reversed",
        "PD-009; PD-001; PD-030",
        "INT-A03",
        "V1",
    ),
    RecognitionOwnerPolicy(
        "Fixed Assets",
        "Capitalization / depreciation / disposal occurrence",
        "Asset transaction or depreciation-run identity",
        "Asset/depreciation version",
        "Fixed asset/depreciation recognition",
        "Fixed Assets",
        "NO",
        "YES — L2",
        "N/A",
        "INT-A04",
        "Fixed Assets + Accounting reversal",
        "Fixed Assets",
        "FA book ↔ Accounting",
        "PD-012; PD-030",
        "INT-A04",
        "V1",
    ),
    RecognitionOwnerPolicy(
        "Direct Expense",
        "Approved explicitly classified direct-expense occurrence",
        "Expense UUID",
        "Expense version",
        "Direct expense recognition",
        "Expenses",
        "NO generic AP",
        "YES — L2",
        "Treasury if separately settled",
        "INT-C01",
        "Expenses / Accounting",
        "Expenses / Accounting",
        "Expense ↔ Accounting ↔ settlement evidence",
        "PD-014; PD-030",
        "INT-C01",
        "V1 SHOULD",
    ),
    RecognitionOwnerPolicy(
        "Employee Reimbursement",
        "Approved reimbursable direct-expense occurrence",
        "Expense/reimbursement identity",
        "Version/correction lineage",
        "Expense recognition",
        "Expenses",
        "NO generic AP",
        "YES only through INT-C01 row",
        "Treasury",
        "INT-C01 + Treasury settlement",
        "Expenses/Treasury",
        "Expenses/Treasury",
        "Expense ↔ Accounting ↔ settlement",
        "PD-014; PD-030",
        "INT-C01",
        "V1 SHOULD",
    ),
    RecognitionOwnerPolicy(
        "AP/AR Write-off",
        "Approved write-off occurrence",
        "Obligation ID + write-off ID",
        "Write-off version",
        "Write-off recognition",
        "Subledgers",
        "AP/AR balance adjusted",
        "YES — L2",
        "N/A",
        "Source-family recognition under PD-030",
        "Subledgers reversal",
        "Subledgers correction",
        "Obligation ↔ write-off ↔ Accounting control account",
        "PD-015; PD-030",
        "Recognition-control contract",
        "V1 SHOULD / NON-BLOCKING",
    ),
    RecognitionOwnerPolicy(
        "AP/AR Write-off",
        "Write-off reversal/correction",
        "Write-off + reversal ID",
        "Reversal version",
        "Write-off reversal recognition",
        "Subledgers",
        "AP/AR balance restored/adjusted",
        "YES — L2 reversal",
        "N/A",
        "Source-family recognition under PD-030",
        "Subledgers",
        "Subledgers",
        "Reversal ↔ obligation ↔ Accounting",
        "PD-015; PD-030",
        "Recognition-control contract",
        "V1 SHOULD / NON-BLOCKING",
    ),
    RecognitionOwnerPolicy(
        "Contract Variation",
        "Variation approval itself",
        "Variation UUID",
        "Variation version",
        "NO ACCOUNTING RECOGNITION",
        "NONE — Billing handoff only",
        "NO",
        "NO",
        "N/A",
        "INT-C02",
        "Contracts/Billing",
        "Contracts/Billing",
        "Variation ↔ Billing eligibility/draft",
        "PD-013; PD-030",
        "INT-C02",
        "V1",
    ),
    RecognitionOwnerPolicy(
        "Project Cost",
        "ProjectCostFact budget/commitment/accrual/actual/forecast",
        "ProjectCostFact source identity",
        "Fact/source version",
        "NO ACCOUNTING RECOGNITION BY PROJECT COST",
        "NONE",
        "NO",
        "NO",
        "N/A",
        "Producer contracts only",
        "Project Controls reversal fact",
        "Project Controls correction",
        "ProjectCostFact ↔ source fact",
        "PD-010; PD-030",
        "Producer contracts",
        "V1",
    ),
    RecognitionOwnerPolicy(
        "Mission — Payroll Route",
        "Mission effect classified as Payroll Component",
        "Mission + effect identity",
        "Mission/effect version",
        "Payroll component recognition",
        "Payroll",
        "NO",
        "YES only through Payroll row",
        "Treasury later",
        "Mission Routing + INT-A02",
        "Payroll",
        "Mission/Payroll correction",
        "Mission effect ↔ Payroll component/run",
        "PD-027; PD-009; PD-030",
        "Mission Routing + INT-A02",
        "V1 SHOULD",
    ),
    RecognitionOwnerPolicy(
        "Mission — Direct Expense Route",
        "Mission effect classified as Direct Expense/Reimbursement",
        "Mission + effect identity",
        "Mission/effect version",
        "Direct expense recognition",
        "Expenses",
        "NO generic AP",
        "YES only through Direct Expense row",
        "Treasury",
        "Mission Routing + INT-C01",
        "Expenses/Treasury",
        "Mission/Expense correction",
        "Mission effect ↔ Expense ↔ Accounting/settlement",
        "PD-027; PD-014; PD-030",
        "Mission Routing + INT-C01",
        "V1 SHOULD",
    ),
    RecognitionOwnerPolicy(
        "Mission — Treasury Advance Route",
        "Mission effect classified as Treasury Advance/Settlement",
        "Mission + effect identity",
        "Mission/effect version",
        "Cash advance/settlement",
        "Treasury",
        "NO",
        "YES only when Treasury movement posts",
        "Treasury",
        "Mission Routing + EDGE-07",
        "Treasury",
        "Mission/Treasury correction",
        "Mission effect ↔ Treasury ↔ Accounting cash effect",
        "PD-027; PD-001; PD-030",
        "Mission Routing + EDGE-07",
        "V1 SHOULD",
    ),
    RecognitionOwnerPolicy(
        "Negative-Net Payroll Excess",
        "Potential Employee Receivable / Carry Forward",
        "Payroll run + employee + excess occurrence",
        "Payroll version",
        "Potential receivable/carry-forward",
        UNSPECIFIED_RECOGNITION_POLICY + " — STOP",
        "UNSPECIFIED",
        "NO until explicit row approved",
        "N/A",
        "None activated",
        "N/A",
        "Payroll correction",
        "Held/review evidence",
        "PD-028; PD-030",
        "NONE — HELD",
        "V1 SAFE FALLBACK",
    ),
)

_POLICIES_BY_OCCURRENCE = {
    (policy.source_family, policy.economic_occurrence): policy for policy in _POLICIES
}


def registered_recognition_owner_policies() -> tuple[RecognitionOwnerPolicy, ...]:
    """Return the complete frozen SPEC-002 policy set."""

    return _POLICIES


def resolve_recognition_owner(*, request: RecognitionRequest) -> RecognitionResolution:
    """Resolve one exact policy row or fail closed without any posting side effect."""

    if request.organization_id != request.source_organization_id:
        raise ValidationError("منبع متعلق به Tenant حسابداری نیست.")
    if not request.object_scope_authorized:
        raise ValidationError("مجوز محدوده شیء منبع تأیید نشده است.")
    if request.source_identity is None:
        raise ValidationError("شناسه منبع الزامی است.")
    if request.source_version is None or request.source_version < 1:
        raise ValidationError("نسخه منبع معتبر الزامی است.")
    if not request.recognition_type.strip():
        raise ValidationError("نوع شناسایی الزامی است.")
    if not request.recognition_owner.strip():
        raise ValidationError("مالک شناسایی الزامی است.")

    policy = _POLICIES_BY_OCCURRENCE.get(
        (request.source_family, request.economic_occurrence)
    )
    if policy is None or policy.recognition_owner.startswith(
        UNSPECIFIED_RECOGNITION_POLICY
    ):
        raise ValidationError(UNSPECIFIED_RECOGNITION_POLICY)
    if request.recognition_type != policy.recognition_type:
        raise ValidationError("نوع شناسایی با سیاست مصوب سازگار نیست.")
    if request.recognition_owner != policy.recognition_owner:
        raise ValidationError("مالک شناسایی با سیاست مصوب سازگار نیست.")

    return RecognitionResolution(
        policy=policy,
        identity=RecognitionIdentity(
            source_family=policy.source_family,
            economic_occurrence=policy.economic_occurrence,
            source_identity=request.source_identity,
            source_version=request.source_version,
            recognition_type=policy.recognition_type,
            recognition_owner=policy.recognition_owner,
        ),
    )


def ensure_no_competing_recognition(
    *,
    resolution: RecognitionResolution,
    existing_recognitions: tuple[RecognitionIdentity, ...],
) -> RecognitionAttempt:
    """Classify a retry or reject another owner for the same occurrence."""

    requested = resolution.identity
    occurrence_key = (
        requested.source_family,
        requested.economic_occurrence,
        requested.source_identity,
        requested.source_version,
        requested.recognition_type,
    )
    for existing in existing_recognitions:
        existing_key = (
            existing.source_family,
            existing.economic_occurrence,
            existing.source_identity,
            existing.source_version,
            existing.recognition_type,
        )
        if existing_key != occurrence_key:
            continue
        if existing.recognition_owner != requested.recognition_owner:
            raise ValidationError("مالک رقیب برای رخداد اقتصادی مجاز نیست.")
        return RecognitionAttempt(resolution=resolution, is_replay=True)
    return RecognitionAttempt(resolution=resolution, is_replay=False)

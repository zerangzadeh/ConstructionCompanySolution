"""Bounded local receivable sample, using existing domain services and policy only.

Dry-run is default. Applying requires explicit approval to reuse the existing
published UAT regulatory configuration on this new sample contract.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from django.conf import settings
from django.db import connection, transaction
from django.test import Client
from django.urls import reverse

from apps.accounting.models import JournalEntry
from apps.accounts.models import User
from apps.billing.models import (
    PayableCertificate,
    ProgressClaim,
)
from apps.billing.services import (
    add_baseline_item,
    approve_progress_claim,
    approve_project_baseline,
    create_progress_claim,
    create_progress_record,
    create_project_baseline,
    request_progress_verification,
    request_project_baseline_approval,
    return_progress_claim,
    submit_progress_claim,
    verify_progress_record,
)
from apps.contracts.models import Contract
from apps.contracts.services import (
    add_contract_item,
    approve_contract_term_version,
    create_contract,
    create_contract_term_version,
    transition_contract_status,
)
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import Organization, PlatformPolicyVersion
from apps.organizations.policy_services import (
    resolve_effective_platform_regulatory_policy,
)
from apps.organizations.policy_specs import RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE
from apps.organizations.services import set_active_organization
from apps.subledgers.models import Obligation
from apps.treasury.models import PaymentRequest, TreasuryMovement

NUMBER = "UAT-REC-02-03"
MARKER = "BONIRA-RECEIVABLE-UAT-02-03-20261101"
POLICY_ID = "c8e9de14-242d-4866-aa67-463f85a892f8"
PERIODS = [
    (24, 25, Decimal("0.10"), "approved"),
    (26, 27, Decimal("0.15"), "submitted"),
    (28, 29, Decimal("0.10"), "returned"),
    (30, 31, Decimal("0.10"), "draft"),
]


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


def finance(org):
    return {
        m.__name__: m.objects.filter(organization=org).count()
        for m in (JournalEntry, Obligation, TreasuryMovement, PaymentRequest)
    }


def protected(org):
    contracts = Contract.objects.filter(
        organization=org, project__code="PRJ-02-03"
    ).exclude(contract_number=NUMBER)
    return {
        "contracts": list(contracts.order_by("pk").values()),
        "claims": list(
            ProgressClaim.objects.filter(contract__in=contracts).order_by("pk").values()
        ),
        "payables": list(
            PayableCertificate.objects.filter(contract__in=contracts)
            .order_by("pk")
            .values()
        ),
        "policy": PlatformPolicyVersion.objects.values().get(pk=POLICY_ID),
    }


def run(apply, authority):
    if not (
        settings.DEBUG
        and settings.SETTINGS_MODULE == "config.settings.development"
        and connection.vendor == "postgresql"
        and connection.settings_dict["HOST"] in ("localhost", "127.0.0.1", "::1", "")
    ):
        raise RuntimeError(
            "Only the verified local development environment is permitted."
        )
    with transaction.atomic():
        org = Organization.objects.select_for_update().get(
            slug="demo-construction-02", status="active", deleted_at__isnull=True
        )
        source = Contract.objects.select_related("project", "party").get(
            organization=org,
            contract_number="CTR-02-03-01",
            direction="receivable",
            project__code="PRJ-02-03",
            deleted_at__isnull=True,
        )
        policy = PlatformPolicyVersion.objects.select_related(
            "insurance_classification"
        ).get(
            pk=POLICY_ID,
            status="published",
            policy__code=RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE,
        )
        actor = User.objects.get(
            username="account.demo-construction-02.owner", is_active=True
        )
        approver = User.objects.get(username="admin", is_active=True)
        for user, codes in (
            (
                actor,
                [
                    P.CONTRACTS_CREATE,
                    P.CONTRACT_ITEMS_ADD,
                    P.CONTRACTS_TRANSITION,
                    P.CONTRACT_TERMS_MANAGE,
                    P.BASELINES_MANAGE,
                    P.PROGRESS_RECORD,
                    P.CLAIMS_CREATE,
                    P.CLAIMS_REVISE,
                    P.CLAIMS_SUBMIT,
                ],
            ),
            (
                approver,
                [
                    P.CONTRACT_TERMS_APPROVE,
                    P.BASELINES_APPROVE,
                    P.PROGRESS_VERIFY,
                    P.CLAIMS_APPROVE,
                    P.WORK_ITEMS_CLAIM,
                    P.WORK_ITEMS_ACT,
                ],
            ),
        ):
            for code in codes:
                require_business_permission(
                    user=user,
                    organization=org,
                    permission=code,
                    project=source.project,
                    message="Missing existing tenant authority for the requested demo operation.",
                )
        if actor.pk == approver.pk or not source.party.identity_snapshots.exists():
            raise RuntimeError(
                "Independent actor and existing party identity evidence are required."
            )
        for start, end, factor, status in PERIODS:
            resolved = resolve_effective_platform_regulatory_policy(
                code=RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE,
                consumer="billing.progress_claim.calculate",
                on_date=date(2026, 10, end),
                insurance_classification=policy.insurance_classification,
            )
            if resolved.pk != policy.pk:
                raise RuntimeError(
                    "Existing pinned policy identity changed; inspect before using it."
                )
        source_items = list(
            source.items.select_related("unit_of_measure").order_by("sort_order", "pk")
        )
        if (
            not source_items
            or sum((i.line_total for i in source_items), Decimal(0))
            != source.contract_value
        ):
            raise RuntimeError(
                "Source line sum no longer matches the sampled contract amount."
            )
        plan = {
            "mode": "apply" if apply else "dry-run",
            "contract_number": NUMBER,
            "tenant": org.slug,
            "project_code": source.project.code,
            "project_name": source.project.name,
            "contract_value": str(source.contract_value),
            "source_contract": source.contract_number,
            "policy_id": POLICY_ID,
            "policy_parameters": policy.parameters,
            "policy_authority_extension_required": "Reuse existing published configuration only on this NEW local demo contract; no legal/statutory/production assertion and no Platform policy change.",
            "planned_claim_states": [p[3] for p in PERIODS],
            "returned_claim_creates_linked_draft_revision": True,
            "periods": [
                {"start": date(2026, 10, p[0]), "end": date(2026, 10, p[1])}
                for p in PERIODS
            ],
        }
        if not apply:
            return plan
        if not authority:
            raise RuntimeError(
                "Explicit bounded Human authority to reuse this policy for the new sample is required."
            )
        before = protected(org)
        financial_before = finance(org)
        existing = Contract.objects.filter(
            organization=org, contract_number=NUMBER
        ).first()
        if existing:
            if MARKER not in existing.notes:
                raise RuntimeError("Identifier collision with unrelated contract.")
            contract = existing
        else:
            contract = create_contract(
                organization=org,
                project=source.project,
                actor=actor,
                contract_number=NUMBER,
                title="قرارداد نمونه دریافتنی با کارفرما — آزمون صورت‌وضعیت",
                counterparty_name=source.counterparty_name,
                party=source.party,
                direction="receivable",
                contract_type="client",
                contract_value=source.contract_value,
                signed_at=date(2026, 10, 24),
                start_date=date(2026, 10, 24),
                end_date=date(2027, 10, 23),
                notes=f"{MARKER}\nصرفاً داده نمونه محلی برای بررسی فرم؛ فاقد اعتبار تجاری یا ادعای قانونی. پیکربندی منتشرشده فقط با تأیید محدود کاربر برای همین نمونه مصرف می‌شود. بدون شناسایی دریافتنی، ثبت حسابداری، وصول یا تسویه.",
            )
            for i in source_items:
                add_contract_item(
                    organization=org,
                    actor=actor,
                    contract=contract,
                    description="نمونه آزمون — " + i.description,
                    quantity=i.quantity,
                    unit_price=i.unit_price,
                    unit=i.unit,
                    unit_of_measure=i.unit_of_measure,
                    wbs_node=i.wbs_node,
                    sort_order=i.sort_order,
                )
            contract = transition_contract_status(
                organization=org, actor=actor, contract=contract, status="active"
            )
            term = create_contract_term_version(
                organization=org,
                actor=actor,
                contract=contract,
                effective_from=date(2026, 10, 24),
                insurance_classification=policy.insurance_classification,
                reason=MARKER
                + " — استفاده صرفاً آزمایشی از طبقه‌بندی و پیکربندی موجود با تأیید کاربر",
            )
            approve_contract_term_version(
                organization=org,
                actor=approver,
                term_version=term,
                reason=MARKER + " — تأیید مستقل شرایط نمونه؛ بدون تغییر سیاست منتشرشده",
            )
            baseline = create_project_baseline(
                organization=org,
                actor=actor,
                project=source.project,
                contract=contract,
                effective_date=date(2026, 10, 24),
            )
            for i in contract.items.order_by("sort_order", "pk"):
                add_baseline_item(
                    organization=org,
                    actor=actor,
                    baseline=baseline,
                    line_key=f"UAT-L{i.sort_order:02}",
                    description=i.description,
                    unit=i.unit,
                    planned_quantity=i.quantity,
                    unit_rate=i.unit_price,
                    contract_item=i,
                    sort_order=i.sort_order,
                )
            request_project_baseline_approval(
                organization=org, actor=actor, baseline=baseline
            )
            baseline = approve_project_baseline(
                organization=org,
                actor=approver,
                baseline=baseline,
                reason=MARKER + " — تأیید مستقل مبنای نمونه",
            )
            cumulative = Decimal(0)
            for start, end, factor, status in PERIODS:
                cumulative += factor
                for i in baseline.items.order_by("sort_order", "pk"):
                    record = create_progress_record(
                        organization=org,
                        actor=actor,
                        baseline=baseline,
                        baseline_item=i,
                        period_start=date(2026, 10, start),
                        period_end=date(2026, 10, end),
                        measured_on=date(2026, 10, start),
                        source_type="demo",
                        source_reference=f"{MARKER}-{start}-{i.line_key}",
                        period_quantity=(i.planned_quantity * factor).quantize(
                            Decimal("0.0001")
                        ),
                        cumulative_quantity=(i.planned_quantity * cumulative).quantize(
                            Decimal("0.0001")
                        ),
                        evidence=MARKER + " — شاهد اندازه‌گیری صرفاً آزمایشی",
                    )
                    request_progress_verification(
                        organization=org, actor=actor, record=record
                    )
                    verify_progress_record(
                        organization=org,
                        actor=approver,
                        record=record,
                        reason=MARKER + " — کنترل مستقل اندازه‌گیری نمونه",
                    )
                claim = create_progress_claim(
                    organization=org,
                    actor=actor,
                    baseline=baseline,
                    period_start=date(2026, 10, start),
                    period_end=date(2026, 10, end),
                    measurement_cutoff=date(2026, 10, end),
                )
                if status != "draft":
                    submit_progress_claim(organization=org, actor=actor, claim=claim)
                if status == "approved":
                    approve_progress_claim(
                        organization=org,
                        actor=approver,
                        claim=claim,
                        reason=MARKER + " — تأیید مستقل نمونه؛ بدون شناسایی دریافتنی",
                    )
                elif status == "returned":
                    return_progress_claim(
                        organization=org,
                        actor=approver,
                        claim=claim,
                        reason=MARKER + " — بازگشت آزمایشی برای اصلاح و بررسی نسخه بعد",
                    )
        claims = list(
            ProgressClaim.objects.filter(organization=org, contract=contract).order_by(
                "claim_number", "revision_number"
            )
        )
        if len(claims) != 5 or {c.status for c in claims} != {
            "approved",
            "submitted",
            "returned",
            "draft",
        }:
            raise RuntimeError(
                "Sample state set is incomplete or has changed; do not overwrite it."
            )
        if before != protected(org) or financial_before != finance(org):
            raise RuntimeError(
                "Protected existing records or downstream finance changed; rollback."
            )
        for claim in claims:
            if (
                claim.regulatory_rule_version_id != policy.pk
                or claim.organization_id != org.pk
                or claim.project_id != source.project_id
            ):
                raise RuntimeError("Claim source/scope mismatch.")
            if claim.gross_amount != sum(
                (i.current_amount for i in claim.items.all()), Decimal(0)
            ):
                raise RuntimeError("Claim does not reconcile to its source items.")
        client = Client(HTTP_HOST="localhost")
        client.force_login(actor)
        session = client.session
        set_active_organization(session, org)
        session.save()
        paths = [reverse("contracts:detail", args=[contract.pk])] + [
            reverse("billing:claim_detail", args=[c.pk]) for c in claims
        ]
        checks = []
        for path in paths:
            response = client.get(path)
            if response.status_code != 200:
                raise RuntimeError(f"Page render failed: {path} {response.status_code}")
            checks.append({"path": path, "status": 200})
        return {
            **plan,
            "contract_id": str(contract.pk),
            "contract_path": paths[0],
            "claims": [
                {
                    "number": c.claim_number,
                    "revision": c.revision_number,
                    "status": c.status,
                    "gross": str(c.gross_amount),
                    "net": str(c.net_amount),
                    "path": reverse("billing:claim_detail", args=[c.pk]),
                }
                for c in claims
            ],
            "render_checks": checks,
            "protected_before": digest(before),
            "protected_after": digest(protected(org)),
            "downstream_finance_before": financial_before,
            "downstream_finance_after": finance(org),
            "policy_unchanged": True,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--authorized-policy-reuse", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.apply, args.authorized_policy_reuse)
    payload = json.dumps(result, ensure_ascii=False, default=str, indent=2)
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, flush=True)

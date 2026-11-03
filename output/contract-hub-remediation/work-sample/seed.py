"""Explicitly requested, bounded local-development work-record review sample.

Dry run is the default. Ordinary services, existing independent members/policy,
one new marked contract only; no schema, grants, policy or financial activation.
"""

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.conf import settings
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client

from apps.accounts.models import User
from apps.accounting.models import JournalEntry
from apps.billing.models import ProgressClaim, ProgressRecord, ProjectBaseline
from apps.billing.services import (
    add_baseline_item,
    approve_progress_claim,
    approve_project_baseline,
    create_progress_claim,
    create_progress_record,
    create_project_baseline,
    reject_progress_record,
    request_progress_verification,
    request_project_baseline_approval,
    return_progress_claim,
    submit_progress_claim,
    verify_progress_record,
)
from apps.contracts.models import Contract, ContractItem, ContractTermVersion
from apps.contracts.services import (
    add_contract_item,
    approve_contract_term_version,
    create_contract,
    create_contract_term_version,
    transition_contract_status,
)
from apps.materials.models import UnitOfMeasure
from apps.organizations.models import Organization, PlatformPolicyVersion
from apps.organizations.policy_services import (
    resolve_effective_platform_regulatory_policy,
)
from apps.organizations.policy_specs import RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE
from apps.organizations.services import set_active_organization
from apps.subledgers.models import Obligation
from apps.treasury.models import PaymentRequest, TreasuryMovement

OUT = Path(__file__).resolve().parent
MARKER = "BONIRA-WORK-REVIEW-20261103"
NUMBER = "UAT-WORK-1405-01"
POLICY_ID = "c8e9de14-242d-4866-aa67-463f85a892f8"
ROWS = [
    (
        "خاک‌برداری و حمل خاک مازاد با ماشین‌آلات",
        "M3",
        "12500.7500",
        "4850000.00",
        [".10", ".25", ".40", ".55", ".70"],
    ),
    (
        "تهیه و اجرای بتن سازه‌ای فونداسیون و سقف‌ها",
        "M3",
        "3850.5000",
        "58750000.00",
        [".08", ".18", ".35", ".50", ".68"],
    ),
    (
        "تهیه، برش، خم و نصب میلگرد سازه",
        "KG",
        "780000.1250",
        "445000.00",
        [".12", ".30", ".46", ".63", ".80"],
    ),
    (
        "قالب‌بندی دیوارها و سقف‌های بتنی با تجهیزات فلزی",
        "M2",
        "24950.7500",
        "9850000.00",
        [".05", ".14", ".29", ".48", ".66"],
    ),
    (
        "تأمین و اجرای شبکه لوله‌کشی تأسیسات مکانیکی",
        "M",
        "9650.2500",
        "18650000.00",
        [".15", ".27", ".42", ".58", ".75"],
    ),
    (
        "تأمین و نصب مجموعه تجهیزات مکانیکی و تابلو کنترل",
        "EA",
        "24.0000",
        "8750000000.00",
        ["2", "5", "9", "13", "18"],
    ),
]
PERIODS = [
    (24, 25, "approved"),
    (26, 27, "approved"),
    (28, 29, "submitted"),
    (30, 30, "returned"),
    (31, 31, "draft"),
]
Q = Decimal(".0001")


def digest(rows):
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, default=str).encode()
    ).hexdigest()


def finance(org):
    return {
        m.__name__: m.objects.filter(organization=org).count()
        for m in (JournalEntry, Obligation, TreasuryMovement, PaymentRequest)
    }


def verify_contract(contract, policy):
    org = contract.organization
    items = list(contract.items.order_by("sort_order", "pk"))
    assert len(items) == 6
    assert contract.contract_value == sum((i.line_total for i in items), Decimal(0))
    baselines = list(
        ProjectBaseline.objects.filter(organization=org, contract=contract)
    )
    assert len(baselines) == 1 and baselines[0].status == "approved"
    baseline = baselines[0]
    assert baseline.effective_ceiling == contract.contract_value
    assert (
        sum((i.planned_value for i in baseline.items.all()), Decimal(0))
        == contract.contract_value
    )
    records = list(
        ProgressRecord.objects.filter(organization=org, baseline=baseline).order_by(
            "measured_on", "baseline_item__sort_order"
        )
    )
    assert Counter(r.status for r in records) == {
        "verified": 30,
        "submitted": 1,
        "rejected": 1,
        "draft": 1,
    }
    for index, item in enumerate(baseline.items.order_by("sort_order", "pk")):
        last = Decimal(0)
        for period, spec in zip(PERIODS, ROWS[index][4], strict=True):
            target = (
                Decimal(spec) if index == 5 else item.planned_quantity * Decimal(spec)
            )
            target = target.quantize(Q)
            r = next(
                r
                for r in records
                if r.baseline_item_id == item.pk
                and r.measured_on == date(2026, 10, period[0])
            )
            assert (
                r.status == "verified"
                and r.cumulative_quantity == target
                and r.period_quantity == target - last
            )
            assert r.verified_by_id != r.created_by_id
            last = target
    claims = list(
        ProgressClaim.objects.filter(organization=org, contract=contract).order_by(
            "claim_number", "revision_number"
        )
    )
    assert Counter(c.status for c in claims) == {
        "approved": 2,
        "submitted": 1,
        "returned": 1,
        "draft": 2,
    }
    for c in claims:
        assert c.regulatory_rule_version_id == policy.pk
        intermediate = sum((i.current_amount for i in c.items.all()), Decimal(0))
        quantum = Decimal(1).scaleb(
            -int(c.calculation_snapshot["currency_decimal_places"])
        )
        assert Decimal(c.calculation_snapshot["gross_intermediate"]) == intermediate
        assert c.gross_amount == intermediate.quantize(quantum, rounding=ROUND_HALF_UP)
        assert c.net_amount == Decimal(
            c.calculation_snapshot["net_intermediate"]
        ).quantize(quantum, rounding=ROUND_HALF_UP)
        assert c.net_amount == c.gross_amount + c.adjustment_amount
        for i in c.items.all():
            assert i.current_amount == (
                i.current_quantity * i.unit_rate_snapshot
            ).quantize(Q, rounding=ROUND_HALF_UP)
            assert (
                i.new_cumulative_quantity - i.previous_cumulative_quantity
                == i.current_quantity
            )
        if c.status == "returned":
            assert (
                c.returned_revision.status == "draft"
                and c.returned_revision.claim_number == c.claim_number
            )
    return {
        "contract": {
            "number": contract.contract_number,
            "title": contract.title,
            "id": str(contract.pk),
            "amount": str(contract.contract_value),
            "project": contract.project.name,
            "path": f"/contracts/{contract.pk}/",
        },
        "items": [
            {
                "description": i.description,
                "unit": i.unit,
                "quantity": str(i.quantity),
                "rate": str(i.unit_price),
                "total": str(i.line_total),
            }
            for i in items
        ],
        "baseline": {
            "id": str(baseline.pk),
            "version": baseline.version,
            "path": f"/contracts/{contract.pk}/?section=quantities&pane=basis",
        },
        "claims": [
            {
                "number": c.claim_number,
                "revision": c.revision_number,
                "status": c.status,
                "gross": str(c.gross_amount),
                "adjustment": str(c.adjustment_amount),
                "net": str(c.net_amount),
                "path": f"/billing/claims/{c.pk}/",
            }
            for c in claims
        ],
        "work_records": [
            {
                "description": r.baseline_item.description,
                "measured_on": r.measured_on.isoformat(),
                "period_quantity": str(r.period_quantity),
                "cumulative_quantity": str(r.cumulative_quantity),
                "unit": r.baseline_item.unit,
                "status": r.status,
                "path": f"/billing/progress/{r.pk}/",
            }
            for r in records
        ],
        "work_statuses": dict(Counter(r.status for r in records)),
        "amounts_and_scopes_reconciled": True,
    }


def run(apply):
    assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
    assert connection.vendor == "postgresql" and connection.settings_dict["HOST"] in (
        "localhost",
        "127.0.0.1",
        "::1",
        "",
    )
    executor = MigrationExecutor(connection)
    pending = [
        (m.app_label, m.name)
        for m, _ in executor.migration_plan(executor.loader.graph.leaf_nodes())
    ]
    assert all(app == "payroll" for app, _ in pending), pending
    with transaction.atomic():
        org = Organization.objects.select_for_update().get(
            slug="demo-construction-02", status="active", deleted_at__isnull=True
        )
        source = Contract.objects.select_related("project", "party").get(
            organization=org,
            contract_number="UAT-AFG-REC-01",
            direction="receivable",
            deleted_at__isnull=True,
        )
        actor = User.objects.get(
            username="account.demo-construction-02.owner", is_active=True
        )
        approver = User.objects.get(username="admin", is_active=True)
        assert actor.pk != approver.pk and source.party_id
        policy = PlatformPolicyVersion.objects.select_related(
            "insurance_classification"
        ).get(pk=POLICY_ID, status="published")
        for start, end, _ in PERIODS:
            resolved = resolve_effective_platform_regulatory_policy(
                code=RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE,
                consumer="billing.progress_claim.calculate",
                on_date=date(2026, 10, end),
                insurance_classification=policy.insurance_classification,
            )
            assert resolved.pk == policy.pk
        policy_before = digest(
            list(PlatformPolicyVersion.objects.order_by("pk").values())
        )
        before_finance = finance(org)
        protected = []
        for model in (
            Contract,
            ContractItem,
            ContractTermVersion,
            ProjectBaseline,
            ProgressRecord,
            ProgressClaim,
        ):
            rows = list(model.objects.filter(organization=org).order_by("pk").values())
            protected.append((model, [r["id"] for r in rows], digest(rows)))
        existing = Contract.objects.filter(
            organization=org, contract_number=NUMBER
        ).first()
        if existing:
            assert MARKER in existing.notes and existing.project_id == source.project_id
            contract = existing
        else:
            units = {
                code: UnitOfMeasure.objects.get(organization=org, code=code)
                for code in {r[1] for r in ROWS}
            }
            total = sum(
                (Decimal(r[2]) * Decimal(r[3]) for r in ROWS), Decimal(0)
            ).quantize(Decimal(".01"))
            contract = create_contract(
                organization=org,
                actor=actor,
                project=source.project,
                contract_number=NUMBER,
                title="نمونه کنترل مقادیر، متره و کارکرد — سازه و تأسیسات باغستان",
                counterparty_name=source.counterparty_name,
                party=source.party,
                direction="receivable",
                contract_type="client",
                contract_value=total,
                signed_at=date(2026, 10, 24),
                start_date=date(2026, 10, 24),
                end_date=date(2027, 10, 23),
                notes=MARKER
                + " — داده ساختگی برای بررسی صفحات؛ فاقد اعتبار تجاری یا قانونی. بدون شناسایی دریافتنی، ثبت حسابداری یا تسویه. مصرف تنظیمات موجود بدون تغییر نرخ یا سیاست.",
            )
            items = []
            for index, (description, code, qty, rate, _) in enumerate(ROWS, 1):
                items.append(
                    add_contract_item(
                        organization=org,
                        actor=actor,
                        contract=contract,
                        description=description,
                        quantity=Decimal(qty),
                        unit_price=Decimal(rate),
                        unit=units[code].symbol,
                        unit_of_measure=units[code],
                        sort_order=index,
                    )
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
                reason=MARKER + " — شرایط پیش‌فرض سرویس برای نمونه ساختگی",
            )
            approve_contract_term_version(
                organization=org,
                actor=approver,
                term_version=term,
                reason=MARKER + " — بررسی مستقل شرایط نمونه",
            )
            baseline = create_project_baseline(
                organization=org,
                actor=actor,
                project=source.project,
                contract=contract,
                effective_date=date(2026, 10, 24),
            )
            basis_items = []
            for index, i in enumerate(items, 1):
                basis_items.append(
                    add_baseline_item(
                        organization=org,
                        actor=actor,
                        baseline=baseline,
                        contract_item=i,
                        line_key=f"WORK-L{index:02}",
                        description=i.description,
                        unit=i.unit,
                        planned_quantity=i.quantity,
                        unit_rate=i.unit_price,
                        sort_order=index,
                    )
                )
            request_project_baseline_approval(
                organization=org, actor=actor, baseline=baseline
            )
            baseline = approve_project_baseline(
                organization=org,
                actor=approver,
                baseline=baseline,
                reason=MARKER + " — بررسی مستقل مبنای نمونه",
            )
            previous = {i.pk: Decimal(0) for i in basis_items}
            for period_index, (start, end, status) in enumerate(PERIODS):
                for row_index, item in enumerate(basis_items):
                    spec = Decimal(ROWS[row_index][4][period_index])
                    cumulative = (
                        spec if row_index == 5 else item.planned_quantity * spec
                    ).quantize(Q)
                    record = create_progress_record(
                        organization=org,
                        actor=actor,
                        baseline=baseline,
                        baseline_item=item,
                        period_start=date(2026, 10, start),
                        period_end=date(2026, 10, end),
                        measured_on=date(2026, 10, start),
                        source_type="demo",
                        source_reference=f"UAT-WORK-{start}-L{row_index + 1:02}",
                        period_quantity=cumulative - previous[item.pk],
                        cumulative_quantity=cumulative,
                        evidence=MARKER
                        + " — گزارش کارکرد ساختگی برای بررسی رابط کاربری",
                    )
                    request_progress_verification(
                        organization=org, actor=actor, record=record
                    )
                    verify_progress_record(
                        organization=org,
                        actor=approver,
                        record=record,
                        reason=MARKER + " — کنترل مستقل کارکرد نمونه",
                    )
                    previous[item.pk] = cumulative
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
                        reason=MARKER + " — تأیید مستقل نمونه بدون شناسایی دریافتنی",
                    )
                elif status == "returned":
                    return_progress_claim(
                        organization=org,
                        actor=approver,
                        claim=claim,
                        reason=MARKER + " — بازگشت نمونه برای بررسی نسخه اصلاحی",
                    )
            item = basis_items[0]
            for day, status, share in (
                (1, "submitted", ".72"),
                (2, "rejected", ".74"),
                (3, "draft", ".76"),
            ):
                cumulative = (item.planned_quantity * Decimal(share)).quantize(Q)
                record = create_progress_record(
                    organization=org,
                    actor=actor,
                    baseline=baseline,
                    baseline_item=item,
                    period_start=date(2026, 11, day),
                    period_end=date(2026, 11, day),
                    measured_on=date(2026, 11, day),
                    source_type="demo",
                    source_reference=f"UAT-WORK-NOV{day:02}",
                    period_quantity=cumulative - previous[item.pk],
                    cumulative_quantity=cumulative,
                    evidence=MARKER
                    + " — ثبت بررسی‌نشده نمونه؛ خارج از تاریخ مبنای صورت‌وضعیت‌های مهر",
                )
                if status != "draft":
                    request_progress_verification(
                        organization=org, actor=actor, record=record
                    )
                if status == "rejected":
                    reject_progress_record(
                        organization=org,
                        actor=approver,
                        record=record,
                        reason=MARKER + " — رد نمونه برای کنترل نمایش دلیل و وضعیت",
                    )
        result = verify_contract(contract, policy)
        for model, ids, original in protected:
            assert (
                digest(list(model.objects.filter(pk__in=ids).order_by("pk").values()))
                == original
            ), model.__name__
        assert (
            digest(list(PlatformPolicyVersion.objects.order_by("pk").values()))
            == policy_before
        )
        assert finance(org) == before_finance
        client = Client(HTTP_HOST="localhost")
        client.force_login(actor)
        session = client.session
        set_active_organization(session, org)
        session.save()
        paths = [
            result["contract"]["path"],
            result["baseline"]["path"],
            f"/contracts/{contract.pk}/?section=quantities",
            f"/billing/progress/?contract={contract.pk}",
            f"/billing/claims/?contract={contract.pk}",
        ]
        paths += [r["path"] for r in result["claims"]] + [
            r["path"] for r in result["work_records"]
        ]
        result.update(
            {
                "applied": apply,
                "tenant": org.slug,
                "policy_reused_unchanged": str(policy.pk),
                "finance_unchanged": before_finance,
                "preexisting_rows_unchanged": True,
                "unrelated_pending_migrations_unchanged": pending,
                "http_checks": [
                    {"path": p, "status": client.get(p).status_code} for p in paths
                ],
            }
        )
        assert all(x["status"] == 200 for x in result["http_checks"])
        if not apply:
            transaction.set_rollback(True)
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run(args.apply)
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Work sample verified; applied:", args.apply)

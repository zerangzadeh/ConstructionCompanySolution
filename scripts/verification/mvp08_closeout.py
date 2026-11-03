"""Read-only qualification and non-destructive seed retries for retained MVP-08."""

import hashlib
import io
import json

from django.apps import apps
from django.core.management import call_command
from mvp08_journey3 import OUT, build
from mvp08_policy_successors import CODES, preflight

from apps.accounts.models import User
from apps.billing.models import ProgressClaim
from apps.daily_reports.models import DailyReport
from apps.inventory.models import StockTransaction
from apps.organizations.models import (
    Organization,
    PlatformPolicyVersion,
    TenantPolicySelection,
)
from apps.procurement import models as m


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


def snapshot():
    organizations = Organization.objects.filter(slug__startswith="mvp08-synthetic-demo")
    values = {}
    for model in apps.get_models():
        if any(field.name == "organization" for field in model._meta.fields):
            rows = list(
                model.objects.filter(organization__in=organizations)
                .order_by("pk")
                .values()
            )
            values[model._meta.label] = {"count": len(rows), "sha256": digest(rows)}
    values["accounts.User"] = {
        "sha256": digest(
            list(
                User.objects.filter(username__startswith="mvp08.")
                .order_by("pk")
                .values()
            )
        )
    }
    return values


def main():
    f = build()
    f.bind_chain()
    before = snapshot()
    results = []
    for index in (1, 2):
        output = io.StringIO()
        call_command(
            "seed_mvp_demo",
            terms_source="a84f9c44-a6d8-428f-a84f-469a9893d06e",
            rfq_duty_personas=True,
            stdout=output,
        )
        result = json.loads(output.getvalue())
        assert result["created"] == 0
        assert snapshot() == before
        results.append(
            {
                "retry": index,
                "created": 0,
                "all_owned_rows_and_credentials_unchanged": True,
            }
        )
    org = f.organization
    assert DailyReport.objects.get(organization=org).status == "approved"
    assert ProgressClaim.objects.get(organization=org).status == "approved"
    assert (
        m.PurchaseRequest.objects.get(
            organization=org, request_number="MVP08-UAT-PR"
        ).status
        == "draft"
    )
    assert (
        m.PurchaseRequest.objects.get(organization=org, request_number="PR-F").status
        == "approved"
    )
    assert f.rfq.status == "closed"
    assert f.scope.scope_type == "line"
    order = m.PurchaseOrder.objects.get(organization=org, order_number="MVP08-PO01")
    assert order.status == "completed" and order.current_version_id
    assert (
        m.GoodsReceipt.objects.filter(
            organization=org,
            receipt_number__in=["MVP08-GRN01", "MVP08-GRN02"],
            status="posted",
        ).count()
        == 2
    )
    assert (
        StockTransaction.objects.get(
            organization=org, transaction_number="MVP08-IN01"
        ).status
        == "posted"
    )
    assert (
        StockTransaction.objects.get(
            organization=org, transaction_number="MVP08-IN02"
        ).status
        == "reversed"
    )
    assert f.balance() == 2
    f.financial_checkpoint("final-demo-and-two-idempotent-retries")
    publication = json.loads((OUT / "policy-successors.json").read_text())
    current = preflight(org)
    old_queries = {
        PlatformPolicyVersion: PlatformPolicyVersion.objects.exclude(
            policy__code__in=CODES, version=2
        ),
        TenantPolicySelection: TenantPolicySelection.objects.exclude(
            organization=org, policy__code__in=CODES, policy_version__version=2
        ),
        m.QuoteAdmissibilityDecision: m.QuoteAdmissibilityDecision.objects.exclude(
            organization=org
        ),
        m.CommercialComparison: m.CommercialComparison.objects.exclude(
            organization=org
        ),
        m.SourcingAward: m.SourcingAward.objects.exclude(organization=org),
    }
    preserved = []
    for model, query in old_queries.items():
        prior = next(
            item
            for item in publication["historical_preservation"]
            if item["model"] == model._meta.label
        )
        rows = list(query.order_by("pk").values())
        assert (
            len(rows) == prior["existing_count"]
            and digest(rows) == prior["sha256_before"]
        )
        preserved.append(
            {"model": model._meta.label, "old_rows_unchanged": True, "count": len(rows)}
        )
    (OUT / "policy-final-preservation.json").write_text(
        json.dumps({"preflight": current, "preservation": preserved}, indent=2),
        encoding="utf8",
    )
    (OUT / "demo-final-idempotency.json").write_text(
        json.dumps(
            {
                "demo_states": "PASS",
                "idempotency": "PASS",
                "retries": results,
                "owned_state": before,
                "human_uat": "NOT_EXECUTED",
                "main_RFQ": f.rfq.rfq_number,
                "main_PO": order.order_number,
            },
            indent=2,
        ),
        encoding="utf8",
    )
    print("DEMO STATES: PASS\nDEMO STATE IDEMPOTENCY: PASS")


if __name__ == "__main__":
    main()

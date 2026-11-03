"""Apply the bounded 2026-11-03 Human RFQ independence decision in the UAT copy."""

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone

from apps.accounts.management.commands.seed_mvp_demo import SLUG, guard_environment
from apps.accounts.models import User
from apps.organizations.authorization import is_platform_admin
from apps.organizations.models import (
    Organization,
    PlatformPolicy,
    PlatformPolicyVersion,
    TenantPolicySelection,
)
from apps.organizations.policy_services import (
    apply_tenant_policy_selection,
    create_platform_policy_version,
    publish_platform_policy_version,
    resolve_active_tenant_policy,
    select_tenant_policy_version,
)
from apps.procurement import models as purchasing

OUT = ROOT / "output/mvp-08/continuation-20261103"
CODES = (
    "rfq-admissibility-self-approval",
    "rfq-comparison-self-finalization",
    "rfq-sourcing-award-self-finalization",
)
REASON = "MVP-08 Human Product Decision 2026-11-03: preserve independent RFQ decisions; allow_self_approval=false until explicitly superseded. Development/UAT only."


def digest(rows):
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, default=str).encode()
    ).hexdigest()


def snapshot():
    """Pin every existing version, selection and historical consuming record."""
    models = [
        PlatformPolicyVersion,
        TenantPolicySelection,
        purchasing.QuoteAdmissibilityDecision,
        purchasing.CommercialComparison,
        purchasing.SourcingAward,
    ]
    return {m._meta.label: (m, list(m.objects.order_by("pk").values())) for m in models}


def preflight(organization):
    resolved = []
    for code in CODES:
        version = resolve_active_tenant_policy(
            organization=organization, policy_code=code
        )
        assert version.parameters == {"allow_self_approval": False}
        assert (
            version.effective_from <= timezone.localdate()
            and version.effective_to is None
        )
        resolved.append(
            {
                "code": code,
                "version": version.version,
                "current": True,
                "allow_self_approval": False,
            }
        )
    return resolved


def main():
    guard_environment()
    if connection.settings_dict["NAME"] != "test_bonira_mvp08_demo_20261103":
        raise RuntimeError(
            "Policy continuation requires the exact retained MVP-08 UAT database"
        )
    organization = Organization.objects.get(slug=SLUG)
    publisher = User.objects.get(username="admin")
    assert is_platform_admin(publisher), (
        "Existing Platform Admin required; do not grant authority"
    )
    tenant_admin = User.objects.get(username="mvp08.admin")
    before = snapshot()
    results = []
    with transaction.atomic():
        for code in CODES:
            policy = PlatformPolicy.objects.select_for_update().get(code=code)
            successor = policy.versions.filter(reason=REASON).first()
            if successor is None:
                predecessor = (
                    policy.versions.exclude(status="draft").order_by("-version").first()
                )
                assert predecessor is not None
                next_version = (
                    policy.versions.aggregate(value=Max("version"))["value"] or 0
                ) + 1
                successor = create_platform_policy_version(
                    actor=publisher,
                    policy=policy,
                    version=next_version,
                    parameters={"allow_self_approval": False},
                    effective_from=timezone.localdate(),
                    effective_to=None,
                    reason=REASON,
                    source_basis="product_defined",
                    supersedes=predecessor,
                )
                successor = publish_platform_policy_version(
                    actor=publisher, policy_version=successor, reason=REASON
                )
            else:
                predecessor = successor.supersedes
                assert successor.status == "published" and successor.parameters == {
                    "allow_self_approval": False
                }
                assert successor.effective_to is None
            selection = TenantPolicySelection.objects.filter(
                organization=organization,
                policy=policy,
                status="active",
                policy_version=successor,
            ).first()
            if selection is None:
                # The retained MVP tenant had no prior selections. Never alter
                # any historical selection to hide an unexpected configuration.
                assert not TenantPolicySelection.objects.filter(
                    organization=organization, policy=policy
                ).exists()
                selection = select_tenant_policy_version(
                    organization=organization,
                    actor=tenant_admin,
                    policy_version=successor,
                    reason=REASON,
                )
                selection = apply_tenant_policy_selection(
                    organization=organization, actor=tenant_admin, selection=selection
                )
            results.append(
                {
                    "policy_code": code,
                    "old_version": predecessor.version,
                    "old_effective_from": str(predecessor.effective_from),
                    "old_effective_to": str(predecessor.effective_to),
                    "new_version": successor.version,
                    "new_effective_from": str(successor.effective_from),
                    "new_effective_to": None,
                    "parameters": successor.parameters,
                    "publisher": publisher.username,
                    "tenant_selection": {
                        "tenant": organization.slug,
                        "version": successor.version,
                        "status": selection.status,
                        "applied_by": tenant_admin.username,
                    },
                    "reason": REASON,
                }
            )
        current = preflight(organization)
        preservation = []
        for label, (model, rows) in before.items():
            ids = [r["id"] for r in rows]
            after = list(model.objects.filter(pk__in=ids).order_by("pk").values())
            assert rows == after, label + " historical mutation"
            preservation.append(
                {
                    "model": label,
                    "existing_count": len(rows),
                    "sha256_before": digest(rows),
                    "sha256_after": digest(after),
                    "unchanged": True,
                }
            )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "policy-successors.json").write_text(
        json.dumps(
            {
                "on_date": str(timezone.localdate()),
                "database": connection.settings_dict["NAME"],
                "policies": results,
                "preflight": current,
                "historical_preservation": preservation,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf8",
    )
    print(
        "RFQ ADMISSIBILITY POLICY: CURRENT\nRFQ COMPARISON POLICY: CURRENT\nRFQ SOURCING AWARD POLICY: CURRENT\nALLOW_SELF_APPROVAL: FALSE"
    )


if __name__ == "__main__":
    main()

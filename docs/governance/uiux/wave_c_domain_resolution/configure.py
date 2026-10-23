"""PD-WC-D01/D05 one-tenant Development configuration; no role/permission changes."""
import json
import os
import sys
from datetime import date
from pathlib import Path

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parents[3]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django
django.setup()

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from apps.accounts.models import User
from apps.accounting.models import Account, ControlAccountMappingVersion
from apps.accounting.services import create_account, create_control_account_mapping_version
from apps.audit.services import record_audit_event
from apps.audit.models import AuditAction
from apps.commercial.models import TenderBidActivation
from apps.organizations.models import Organization, PlatformPolicyVersion, TenantPolicySelection
from apps.organizations.policy_services import (
    create_platform_policy, create_platform_policy_version, publish_platform_policy_version,
    select_tenant_policy_version, apply_tenant_policy_selection,
)
from apps.organizations.policy_specs import initial_accounting_policy_parameters
from apps.subledgers.models import MatchTolerancePolicy
from apps.subledgers.services import prepare_match_tolerance_policy, approve_match_tolerance_policy
from apps.subledgers.supplier_invoice_handoffs import INVOICE_MATCH_SOURCE_KIND
from apps.treasury.models import TreasuryAccount
from apps.treasury.services import create_treasury_account, create_account_mapping_version, transition_treasury_account

LABEL = "UIUX_TEST_ONLY_NON_AUTHORITATIVE"


def save(name, data):
    (OUT / name).write_text(json.dumps(data, default=str, indent=2) + "\n", encoding="utf-8")


def configure():
    assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
    today, expiry = timezone.localdate(), date(2026, 12, 22)
    assert today < expiry
    org = Organization.objects.get(slug="demo-construction-01")
    platform = User.objects.get(username="admin")
    admin = User.objects.get(username="uiux.persona.tenant-admin")
    maker = User.objects.get(username="account.demo-construction-01.accountant")
    checker = User.objects.get(username="account.demo-construction-01.owner")
    owner = User.objects.get(username="account.demo-construction-01.owner")
    future = list(PlatformPolicyVersion.objects.filter(
        policy__code__in=["accounting-money-precision", "accounting-rounding"],
        effective_from=expiry, status="published",
    ).order_by("pk").values())
    assert len(future) == 2
    before = OUT / "FUTURE_POLICIES_BEFORE.json"
    if not before.exists():
        save(before.name, future)
    else:
        assert json.loads(before.read_text(encoding="utf-8")) == json.loads(json.dumps(future, default=str))
    result = {"label": LABEL, "tenant": org.slug, "effective_from": today, "effective_to_exclusive": expiry}
    with transaction.atomic():
        versions = {}
        for code in ["accounting-money-precision", "accounting-rounding", "treasury-self-approval"]:
            policy = create_platform_policy(actor=platform, code=code, reason="PD-WC-D01 " + LABEL)
            version = policy.versions.filter(reason="PD-WC-D01 " + LABEL, status="published").first()
            if version is None:
                predecessor = policy.versions.filter(status="published").order_by("-version").first()
                version = create_platform_policy_version(
                    actor=platform, policy=policy,
                    version=(policy.versions.aggregate(n=Max("version"))["n"] or 0) + 1,
                    parameters={"allow_self_approval": False} if code == "treasury-self-approval" else initial_accounting_policy_parameters(code),
                    effective_from=today, effective_to=expiry, supersedes=predecessor,
                    reason="PD-WC-D01 " + LABEL, source_basis="product_defined",
                )
                version = publish_platform_policy_version(actor=platform, policy_version=version, reason="PD-WC-D01 " + LABEL)
            selected = TenantPolicySelection.objects.filter(organization=org, policy_version=version, status="active").first()
            if selected is None:
                selection = select_tenant_policy_version(organization=org, actor=admin, policy_version=version, reason="PD-WC-D01 " + LABEL)
                apply_tenant_policy_selection(organization=org, actor=admin, selection=selection)
            versions[code] = str(version.pk)
        result["policy_versions"] = versions
        accounts = {}
        for code, kind in [("WCD-AP-CONTROL", "liability"), ("WCD-CASH", "asset"), ("WCD-CLEARING", "liability")]:
            account = Account.objects.filter(organization=org, code=code).first()
            if account is None:
                account = create_account(organization=org, actor=maker, code=code, name=LABEL + " " + code, account_type=kind, is_posting=True)
            accounts[code] = account
        mapping = ControlAccountMappingVersion.objects.filter(organization=org, source_kind=INVOICE_MATCH_SOURCE_KIND, direction="payable").first()
        if mapping is None:
            mapping = create_control_account_mapping_version(
                organization=org, actor=maker, source_kind=INVOICE_MATCH_SOURCE_KIND,
                direction="payable", control_account=accounts["WCD-AP-CONTROL"],
                effective_from=today, effective_to=expiry, reason="PD-WC-D01 " + LABEL,
            )
        tolerance = MatchTolerancePolicy.objects.filter(organization=org, reason="PD-WC-D01 " + LABEL).first()
        if tolerance is None:
            tolerance = prepare_match_tolerance_policy(organization=org, actor=maker, effective_from=today, effective_to=expiry, quantity_tolerance_bps=0, unit_price_tolerance_bps=0, reason="PD-WC-D01 " + LABEL)
            approve_match_tolerance_policy(organization=org, actor=checker, policy=tolerance)
        cash = TreasuryAccount.objects.filter(organization=org, code="WCD-CASH").first()
        if cash is None:
            cash = create_treasury_account(organization=org, actor=maker, code="WCD-CASH", name=LABEL, kind="cash", custodian=org.memberships.get(user=maker))
            create_account_mapping_version(organization=org, actor=checker, account=cash, cash_ledger_account=accounts["WCD-CASH"], clearing_ledger_account=accounts["WCD-CLEARING"], effective_from=today, reason="PD-WC-D01 " + LABEL)
            transition_treasury_account(organization=org, actor=checker, account=cash, to_status="active", reason="PD-WC-D01 " + LABEL)
        activation = TenderBidActivation.objects.filter(organization=org).first()
        if activation is None:
            activation = TenderBidActivation.objects.create(organization=org, is_active=True, policy_reference="PD-WC-D05; CEP-032_COMMERCIAL_TENDER_BID_DECISION; " + LABEL, activated_by=owner)
            record_audit_event(action=AuditAction.ORGANIZATION_SETTINGS_UPDATED, entity_type="commercial.TenderBidActivation", entity_id=activation.pk, organization=org, actor=owner, metadata={"reason": "PD-WC-D05 " + LABEL, "after": {"is_active": True, "policy_reference": activation.policy_reference}})
        result.update(accounts={k: str(v.pk) for k, v in accounts.items()}, control_mapping=str(mapping.pk), tolerance=str(tolerance.pk), treasury_account=str(cash.pk), tender_activation=str(activation.pk))
    after = list(PlatformPolicyVersion.objects.filter(pk__in=[v["id"] for v in future]).order_by("pk").values())
    assert before.read_text(encoding="utf-8") == json.dumps(after, default=str, indent=2) + "\n"
    result["future_policies_unchanged"] = True
    save("CONFIGURATION.json", result)
    print("PD-WC-D01/D05 configuration complete; future policies unchanged")


if __name__ == "__main__":
    configure()

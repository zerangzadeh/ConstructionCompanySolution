"""Prepare labelled synthetic sources using existing financial contracts only."""
import hashlib
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from django.apps import apps
from django.conf import settings
from django.db import connection, transaction

OUT = Path(__file__).parent
assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
assert connection.vendor == "postgresql"
assert settings.DATABASES["default"]["HOST"] in ("127.0.0.1", "localhost")
assert not (OUT / "FINANCIAL_STARTING_STATES.json").exists()


def snapshot():
    result = {}
    for model in apps.get_models():
        pk = model._meta.pk.attname
        result[model._meta.label] = {
            str(row[pk]): hashlib.sha256(json.dumps(row, sort_keys=True, default=str).encode()).hexdigest()
            for row in model.objects.values()
        }
    return result


before = snapshot()
(OUT / "FINANCIAL_DATA_BEFORE.json").write_text(json.dumps(before), encoding="utf-8")
from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationMembership
from apps.accounting.models import JournalEntry
from apps.treasury import services as treasury
from apps.treasury.models import TreasuryAccount

org = Organization.objects.get(slug="demo-construction-01", status="active")
maker = User.objects.get(username="account.demo-construction-01.accountant", is_active=True)
checker = User.objects.get(username="account.demo-construction-01.owner", is_active=True)
member = OrganizationMembership.objects.get(organization=org, user=maker, status="active")
sample_journal = JournalEntry.objects.get(organization=org, source_key="CEP079-PREP-01-JOURNAL")
day = sample_journal.accounting_date
period = sample_journal.period
note = "CEP079-PREP-01 isolated synthetic Development starting state; no UAT or production acceptance."
records = []
outcomes = []


def keep(obj, purpose):
    obj.refresh_from_db()
    records.append({"model": obj._meta.label, "id": str(obj.pk), "status": getattr(obj, "status", None), "purpose": purpose})
    return obj


def movement(key, kind, account, request=None, party=None):
    obj = treasury.create_movement(
        organization=org, actor=maker, kind=kind, movement_date=day,
        amount=Decimal("1"), description=note, idempotency_key=key,
        account=account, origin_request=request, party=party,
    )
    treasury.submit_movement(organization=org, actor=maker, movement=obj, reason=note)
    treasury.approve_and_post_movement(
        organization=org, actor=checker, movement=obj,
        accounting_preparer=member, period=period, reason=note,
    )
    return keep(obj, "New native posted movement; existing approved account mapping/policy, distinct maker/checker")


try:
    with transaction.atomic():
        start = len(records)
        account = TreasuryAccount.objects.filter(organization=org, kind="bank", status="active").first()
        assert account is not None, "No existing active bank account"
        receipt = movement("CEP079-PREP-01-RECEIPT", "receipt", account)
        cheque = keep(treasury.create_cheque(
            organization=org, actor=maker, direction="incoming", controlled_account=account,
            amount=Decimal("1"), due_date=day, serial="CEP079-SYNTHETIC-01", custodian=member,
        ), "New synthetic cheque; no real serial")
        for state in ("received", "deposited", "presented"):
            treasury.transition_cheque(organization=org, actor=maker, cheque=cheque, to_status=state, reason=note)
        treasury.clear_cheque(
            organization=org, actor=checker, cheque=cheque,
            accounting_preparer=member, period=period, clearing_date=day, reason=note,
        )
        cheque.refresh_from_db()
        records[-1]["status"] = cheque.status
        from apps.procurement.models import PurchaseOrder
        supplier = PurchaseOrder.objects.get(organization=org, order_number="CEP079-PREP-01-READY").supplier
        request = treasury.create_payment_request(
            organization=org, actor=maker, kind="vendor_advance", amount=Decimal("1"),
            purpose=note, idempotency_key="CEP079-PREP-01-ADVANCE", party=supplier,
        )
        treasury.submit_payment_request(organization=org, actor=maker, request=request, reason=note)
        treasury.decide_payment_request(organization=org, actor=checker, request=request, approve=True, reason=note)
        disbursement = movement("CEP079-PREP-01-ADVANCE-CASH", "disbursement", account, request, supplier)
        treasury.release_payment_request(organization=org, actor=checker, request=request, movement=disbursement, reason=note)
        keep(request, "New released synthetic vendor-advance request")
        keep(treasury.open_advance(organization=org, actor=checker, request=request), "New open advance for isolated reversal/settlement starting state")
        import jdatetime
        date_text = jdatetime.date.fromgregorian(date=day).strftime("%Y/%m/%d")
        csv_text = "transaction_date,direction,amount,provider_row_id,reference\n" + f"{date_text},in,1,CEP079-SYNTHETIC-ROW-01,CEP079-PREP-01-RECEIPT\n"
        # Transport fixture only; no import, matching, clearing or reconciliation executed.
        (OUT / "SYNTHETIC_BANK_STATEMENT.csv").write_text(csv_text, encoding="utf-8")
        outcomes.append({"group": "Treasury", "result": "PREPARED", "records": records[start:], "statement_account": str(account.pk), "statement_movement": str(receipt.pk), "date_source": str(sample_journal.pk)})
except Exception as exc:
    records = []
    outcomes.append({"group": "Treasury", "result": "ROLLED_BACK", "exception": type(exc).__name__, "message": str(exc)})

try:
    with transaction.atomic():
        from apps.procurement.models import PurchaseOrder, GoodsReceipt
        from apps.subledgers import services as ap
        from apps.subledgers.models import SupplierInvoiceLine

        order = PurchaseOrder.objects.get(organization=org, order_number="CEP079-PREP-01-SEED")
        line = order.current_version.lines.first()
        existing = SupplierInvoiceLine.objects.filter(organization=org).first()
        assert existing is not None, "No retained invoice assertion exemplar"
        invoice = ap.prepare_supplier_invoice(
            organization=org, actor=maker, supplier=order.supplier, project=order.project,
            invoice_number="CEP079-PREP-01-INVOICE", invoice_date=day, due_date=None,
            idempotency_key="CEP079-PREP-01-INVOICE",
            lines=[{"kind": existing.kind, "purchase_order_version_line": line,
                    "quantity": Decimal("1"), "unit_price": line.unit_price,
                    "tax_amount": existing.tax_amount, "freight_amount": existing.freight_amount,
                    "other_charge_amount": existing.other_charge_amount, "description": note}],
        )
        ap.submit_supplier_invoice(organization=org, actor=maker, invoice_version=invoice)
        ap.decide_supplier_invoice(organization=org, actor=checker, invoice_version=invoice, approve=True, reason=note)
        match = ap.run_supplier_invoice_match(organization=org, actor=maker, invoice_version=invoice, idempotency_key="CEP079-PREP-01-MATCH")
        keep(invoice, "New approved synthetic supplier assertion; source exemplar charges copied, no Billing tax rule inferred")
        keep(match, "New match under existing approved policy; no payable or recognition mapping invented")
        outcomes.append({"group": "AP", "result": "PREPARED", "invoice_id": str(invoice.pk), "match_id": str(match.pk)})
except Exception as exc:
    outcomes.append({"group": "AP", "result": "ROLLED_BACK", "exception": type(exc).__name__, "message": str(exc)})

after = snapshot()
(OUT / "FINANCIAL_DATA_AFTER.json").write_text(json.dumps(after), encoding="utf-8")
delta = {label: {"changed_or_missing_existing": [key for key, val in old.items() if after[label].get(key) != val], "new": [key for key in after[label] if key not in old]} for label, old in before.items()}
delta = {label: value for label, value in delta.items() if any(value.values())}
result = {"groups": outcomes, "data_changes": delta, "no_uat_scenarios_executed": True,
          "no_roles_permissions_scope_or_policy_changes": True,
          "new_amounts": "Explicit Decimal(1) fictional Treasury facts; no interest, tax, insurance, FX, tolerance, mapping or statutory value invented",
          "AP_amounts": "Existing invoice assertion amounts copied as synthetic facts, not approved commercial/regulatory Billing parameters"}
(OUT / "FINANCIAL_STARTING_STATES.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(outcomes, ensure_ascii=True))

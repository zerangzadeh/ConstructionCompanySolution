"""Bounded synthetic Development starting states; never UAT execution evidence."""
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
from django.utils import timezone

OUT = Path(__file__).parent


def snapshot():
    result = {}
    for model in apps.get_models():
        result[model._meta.label] = {
            str(row["id"]): hashlib.sha256(
                json.dumps(row, sort_keys=True, default=str).encode()
            ).hexdigest()
            for row in model.objects.values()
            if "id" in row
        }
    return result


assert settings.SETTINGS_MODULE == "config.settings.development"
assert settings.DEBUG and connection.vendor == "postgresql"
assert settings.DATABASES["default"]["HOST"] in ("localhost", "127.0.0.1")
assert not (OUT / "FIXTURES_CREATED.json").exists(), "Do not duplicate preparation"
before = snapshot()
(OUT / "DATA_BEFORE_FINGERPRINTS.json").write_text(json.dumps(before), encoding="utf-8")
created = []


def remember(obj, purpose):
    obj.refresh_from_db()
    created.append({"model": obj._meta.label, "id": str(obj.pk), "purpose": purpose})
    return obj


try:
    with transaction.atomic():
        from apps.accounts.models import User
        from apps.organizations.models import Organization
        from apps.projects.models import Project
        from apps.procurement import services as procurement
        from apps.procurement.models import PurchaseOrderItem
        from apps.inventory import services as inventory
        from apps.accounting import services as accounting
        from apps.accounting.models import JournalEntry, JournalKind

        org = Organization.objects.get(slug="demo-construction-01", status="active")
        actor = User.objects.get(username="cep078.synthetic.operations", is_active=True)
        owner = User.objects.get(username="account.demo-construction-01.owner", is_active=True)
        accountant = User.objects.get(username="account.demo-construction-01.accountant", is_active=True)
        project = Project.objects.get(organization=org, code="PRJ-01-01")
        # Existing accepted master identities/prices are read-only references.
        sample = PurchaseOrderItem.objects.filter(
            organization=org, purchase_order__project=project,
            purchase_order__status="issued", material__is_active=True,
        ).select_related("purchase_order__supplier", "material", "unit_of_measure").first()
        assert sample is not None, "No qualified existing PO/material/supplier reference"
        prefix = "CEP079-PREP-01"
        note = "CEP079 isolated synthetic Development fixture; no production or statutory authority; no UAT result."
        request = remember(procurement.create_purchase_request(
            organization=org, actor=actor, project=project,
            request_number=prefix+"-PR", title=prefix+" synthetic request", notes=note,
        ), "New disposable PR; source for workbench and independent approval preparation")
        remember(procurement.add_purchase_request_item(
            organization=org, actor=actor, purchase_request=request,
            material=sample.material, unit_of_measure=sample.unit_of_measure,
            quantity=Decimal("1"), description=note,
        ), "Synthetic PR line; explicit unit; no accepted source changed")
        procurement.submit_purchase_request(organization=org, actor=actor, purchase_request=request)
        request.refresh_from_db()
        warehouse = remember(inventory.create_warehouse(
            organization=org, actor=actor, project=project, code=prefix+"-WH",
            name=prefix+" synthetic isolated warehouse", location=note,
        ), "Dedicated disposable stock namespace; no existing warehouse balance changed")
        for suffix, quantity in [("READY", "1"), ("SEED", "2")]:
            order = remember(procurement.create_purchase_order(
                organization=org, actor=actor, project=project,
                supplier=sample.purchase_order.supplier, order_number=prefix+"-"+suffix,
                order_date=timezone.localdate(), notes=note,
            ), "Isolated issued PO starting state for receipt actions")
            line = remember(procurement.add_purchase_order_item(
                organization=org, actor=actor, purchase_order=order,
                material=sample.material, unit_of_measure=sample.unit_of_measure,
                quantity=Decimal(quantity), unit_price=sample.unit_price, description=note,
            ), "Synthetic quantity; existing source unit price copied as test fact, no rate/policy invention")
            procurement.issue_purchase_order(organization=org, actor=owner, purchase_order=order)
            if suffix == "SEED":
                for receipt_suffix in ("HANDOFF", "STOCK"):
                    receipt = remember(procurement.create_goods_receipt(
                        organization=org, actor=actor, purchase_order=order,
                        receipt_number=prefix+"-"+receipt_suffix,
                        received_at=timezone.now(), notes=note,
                    ), "New posted GR for isolated handoff/stock starting state")
                    receipt_line = remember(procurement.add_goods_receipt_item(
                        organization=org, actor=actor, goods_receipt=receipt,
                        purchase_order_item=line, quantity=Decimal("1"), notes=note,
                    ), "New receipt line; existing accepted PO/GR not mutated")
                    procurement.post_goods_receipt(organization=org, actor=owner, goods_receipt=receipt)
                    if receipt_suffix == "STOCK":
                        stock = remember(inventory.create_stock_transaction(
                            organization=org, actor=actor, transaction_number=prefix+"-STOCK",
                            transaction_type="receipt", material=sample.material,
                            unit_of_measure=sample.unit_of_measure, quantity=Decimal("1"),
                            occurred_at=timezone.now(), destination_warehouse=warehouse,
                            project=project, goods_receipt_item=receipt_line, reference=prefix,
                            notes=note,
                        ), "Dedicated posted stock starting state; no accepted stock reversed")
                        inventory.post_stock_transaction(organization=org, actor=owner, stock_transaction=stock)
        sample_journal = JournalEntry.objects.filter(
            organization=org, status="posted",
            period__status="open",
        ).select_related("period").first()
        assert sample_journal is not None, "No existing posted example in an open source period"
        journal = remember(accounting.create_journal(
            organization=org, actor=accountant, period=sample_journal.period,
            kind=JournalKind.MANUAL, document_date=sample_journal.document_date,
            accounting_date=sample_journal.accounting_date, description=note,
            source_key=prefix+"-JOURNAL", evidence_reference=prefix,
        ), "New independent-maker/checker posted journal; reversal starting state only")
        for line in sample_journal.lines.select_related("account", "project", "site", "party"):
            remember(accounting.add_journal_line(
                organization=org, actor=accountant, journal=journal, account=line.account,
                line_number=line.line_number, debit=line.debit, credit=line.credit,
                description=note, project=line.project, site=line.site, party=line.party,
            ), "Exact existing manual example amounts copied as synthetic test facts")
        accounting.submit_journal(organization=org, actor=accountant, journal=journal)
        accounting.post_journal(organization=org, actor=owner, journal=journal, reason=note)
    outcome = {"result": "CREATED_CANONICAL_DEVELOPMENT_STARTING_STATES", "created": created,
               "no_uat_scenarios_executed": True, "roles_permissions_scopes_unchanged": True,
               "no_billing_or_statutory_inputs_created": True,
               "retention": "Retain. Future mutation limited to these identified disposable new records; canonical reversal/archive only, no raw deletion."}
except Exception as exc:
    outcome = {"result": "ROLLED_BACK_NO_FIXTURES_COMMITTED", "exception": type(exc).__name__,
               "message": str(exc), "attempted_new_models": sorted({x["model"] for x in created}),
               "no_uat_scenarios_executed": True}
after = snapshot()
changes = {}
for label, old in before.items():
    current = after[label]
    changed = [key for key, value in old.items() if current.get(key) != value]
    new = [key for key in current if key not in old]
    if changed or new:
        changes[label] = {"changed_or_missing_existing": changed, "new": new}
outcome["data_changes"] = changes
(OUT / "FIXTURES_CREATED.json").write_text(json.dumps(outcome, indent=2, ensure_ascii=False), encoding="utf-8")
(OUT / "DATA_AFTER_FINGERPRINTS.json").write_text(json.dumps(after), encoding="utf-8")
print(json.dumps({k: v for k, v in outcome.items() if k not in ("created", "data_changes")}, ensure_ascii=True))
print(json.dumps({label: {k: len(v) for k, v in delta.items()} for label, delta in changes.items()}))

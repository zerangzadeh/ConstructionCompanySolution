"""Resume the retained MVP-08 procurement chain through installed Chrome.

Native domain transitions only. The sole source-processing fixture is explicitly
synthetic, digest-bound and restricted to the exact local UAT database.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.db import connection
from django.test import override_settings
from django.test.testcases import LiveServerThread
from django.urls import reverse
from django.utils import timezone
from mvp08_verify import CurrentJourney, prepare, sourcing_preflight

from apps.accounts.models import User
from apps.documents.models import DocumentProcessingAssessment
from apps.inventory.models import StockTransaction
from apps.inventory.test_mvp04e import InventoryJourneyFixture
from apps.procurement import models as m
from apps.procurement.buyer_ui import action_url
from apps.procurement.test_mvp04f import ConnectedJourneyFixture
from apps.procurement.test_mvp04f_browser import ConnectedBrowserTests
from core.jalali import format_jalali

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output/mvp-08/continuation-20261103"
RFQ_NUMBER = "MVP08-RFQ02"


class Journey(CurrentJourney):
    act = ConnectedBrowserTests.act
    buyer = ConnectedJourneyFixture.buyer
    stock_url = InventoryJourneyFixture.stock_url
    stock_detail = InventoryJourneyFixture.stock_detail
    balance = InventoryJourneyFixture.balance

    def money_snapshot(self):
        from django.apps import apps

        values = ConnectedJourneyFixture.money_snapshot(self)
        for model in apps.get_models():
            if (
                model._meta.app_label
                not in {"accounting", "treasury", "subledgers", "payroll", "valuation"}
                and not model.__name__.startswith("InventoryValuation")
                and not model.__name__.startswith("DownstreamCost")
            ):
                continue
            if not any(field.name == "organization" for field in model._meta.fields):
                continue
            rows = list(
                model.objects.filter(organization=self.organization)
                .order_by("pk")
                .values()
            )
            values[model._meta.label] = {
                "count": len(rows),
                "sha256": hashlib.sha256(
                    json.dumps(rows, sort_keys=True, default=str).encode()
                ).hexdigest(),
            }
        return values

    def financial_checkpoint(self, stage):
        self.assertEqual(self.money_snapshot(), self.financial_before, stage)
        path = OUT / "financial-checkpoints.json"
        checkpoints = json.loads(path.read_text()) if path.exists() else []
        if stage not in [item["stage"] for item in checkpoints]:
            checkpoints.append({"stage": stage, "unchanged": True})
        path.write_text(json.dumps(checkpoints, indent=2), encoding="utf8")

    def negative(self, action, fields, **parents):
        self.act(
            self.owner,
            action_url(self.rfq, action, **parents),
            fields,
            selector="#buyer-action-form",
            name="deny-self-" + action,
            expected=400,
        )

    def decisions(self):
        self.bind_chain()
        self.revision = m.QuoteRevision.objects.get(
            organization=self.organization, rfq_version=self.version
        )
        prep = m.QuoteAdmissibilityPreparation.objects.filter(
            organization=self.organization, quote_revision=self.revision
        ).first()
        if prep is None:
            self.buyer(
                self.owner,
                "prepare_admissibility",
                {
                    "state": "admissible",
                    "reason_code": "requirements_met",
                    "rationale": "انطباق پیشنهاد مصنوعی با اقلام و شرایط استعلام",
                },
                quote_revision=self.revision.pk,
            )
            prep = m.QuoteAdmissibilityPreparation.objects.get(
                organization=self.organization, quote_revision=self.revision
            )
        if not m.QuoteAdmissibilityDecision.objects.filter(preparation=prep).exists():
            self.negative("approve_admissibility", {}, preparation=prep.pk)
            assert not m.QuoteAdmissibilityDecision.objects.filter(
                preparation=prep
            ).exists()
            self.buyer(self.approver, "approve_admissibility", preparation=prep.pk)
        decision = m.QuoteAdmissibilityDecision.objects.get(preparation=prep)
        assert decision.approved_by_id != prep.prepared_by_id
        assert decision.approval_policy_version.parameters == {
            "allow_self_approval": False
        }
        self.financial_checkpoint("independent-admissibility")
        prepared = m.CommercialComparison.objects.filter(
            organization=self.organization,
            commercial_scope=self.scope,
            finalized_at__isnull=True,
        ).first()
        if prepared is None:
            self.buyer(
                self.owner,
                "prepare_comparison",
                {
                    "rows-0-quote_revision_id": str(self.revision.pk),
                    "rows-0-offered_quantity": "10",
                    "rows-0-unit_price": "1250000",
                    "rows-0-currency": "IRR",
                    "rows-0-explicit_discount": "0",
                    "rows-0-source_locator": "صفحه ۱، قلم ۱؛ پیشنهاد مصنوعی",
                },
                scope=self.scope.pk,
            )
            prepared = m.CommercialComparison.objects.get(
                organization=self.organization,
                commercial_scope=self.scope,
                finalized_at__isnull=True,
            )
        if not prepared.evaluator_appointments.exists():
            self.buyer(
                self.owner,
                "appoint_evaluator",
                {
                    "membership": str(
                        self.organization.memberships.get(user=self.evaluator).pk
                    )
                },
                comparison=prepared.pk,
            )
        appointment = prepared.evaluator_appointments.get()
        if not m.CommercialEvaluation.objects.filter(
            evaluator_appointment=appointment
        ).exists():
            self.buyer(
                self.evaluator,
                "evaluate",
                {
                    "input": str(prepared.inputs.get().pk),
                    "recommendation": "بررسی مستند و مستقل؛ پیشنهاد منطبق است",
                    "evidence": "پیشنهاد مصنوعی، صفحه ۱ قلم ۱",
                },
                appointment=appointment.pk,
            )
        finalized = m.CommercialComparison.objects.filter(
            organization=self.organization,
            supersedes=prepared,
            finalized_at__isnull=False,
        ).first()
        if finalized is None:
            self.negative(
                "finalize_comparison",
                {"reason": "آزمون منع نهایی‌سازی تهیه‌کننده"},
                comparison=prepared.pk,
            )
            assert not m.CommercialComparison.objects.filter(
                organization=self.organization,
                commercial_scope=self.scope,
                finalized_at__isnull=False,
            ).exists()
            self.buyer(
                self.approver,
                "finalize_comparison",
                {"reason": "بررسی و نهایی‌سازی مستقل نمونه"},
                comparison=prepared.pk,
            )
            finalized = m.CommercialComparison.objects.get(
                organization=self.organization,
                supersedes=prepared,
                finalized_at__isnull=False,
            )
        self.comparison = finalized
        assert finalized.prepared_by_id != finalized.finalized_by_id
        assert finalized.finalization_policy_version.parameters == {
            "allow_self_approval": False
        }
        self.financial_checkpoint("independent-comparison")
        award_prep = m.SourcingAwardPreparation.objects.filter(
            organization=self.organization, comparison=finalized
        ).first()
        if award_prep is None:
            self.buyer(
                self.owner,
                "prepare_award",
                {
                    "outcome": "awarded",
                    "reason": "انتخاب مستقل بخشی از نیاز کارگاه",
                    "evidence": "پیشنهاد و ارزیابی مصنوعی؛ انتخاب شش از ده مترمکعب و تحویل جزئی",
                    "tie_resolution": False,
                    "rows-0-comparison_input_id": str(finalized.inputs.get().pk),
                    "rows-0-quantity": "6",
                },
                comparison=finalized.pk,
            )
            award_prep = m.SourcingAwardPreparation.objects.get(
                organization=self.organization, comparison=finalized
            )
        if not m.SourcingAward.objects.filter(preparation=award_prep).exists():
            self.negative("finalize_award", {}, preparation=award_prep.pk)
            assert not m.SourcingAward.objects.filter(preparation=award_prep).exists()
            self.buyer(self.approver, "finalize_award", preparation=award_prep.pk)
        self.award_record = m.SourcingAward.objects.get(preparation=award_prep)
        assert self.award_record.finalized_by_id != award_prep.prepared_by_id
        assert self.award_record.finalization_policy_version.parameters == {
            "allow_self_approval": False
        }
        denial_evidence = list(
            (OUT / "browser").glob(f"batch-{RFQ_NUMBER}-*-deny-self-*.json")
        )
        assert len(denial_evidence) == 3
        assert all(
            json.loads(path.read_text(encoding="utf8"))[0]["status"] == 400
            for path in denial_evidence
        )
        (OUT / "independent-decisions.json").write_text(
            json.dumps(
                {
                    "rfq": self.rfq.rfq_number,
                    "denial_evidence": [
                        str(path.relative_to(OUT)) for path in denial_evidence
                    ],
                    "self_admissibility_denied": True,
                    "self_comparison_denied": True,
                    "self_award_denied": True,
                    "no_record_on_denial": True,
                    "preparer": self.owner.username,
                    "independent_reviewer": self.approver.username,
                    "evaluator": self.evaluator.username,
                    "policy_versions": [
                        decision.approval_policy_version.version,
                        finalized.finalization_policy_version.version,
                        self.award_record.finalization_policy_version.version,
                    ],
                },
                indent=2,
            ),
            encoding="utf8",
        )
        self.financial_checkpoint("independent-award")

    def downstream(self):
        self.bind_chain()
        self.award_record = m.SourcingAward.objects.get(
            organization=self.organization, comparison__commercial_scope=self.scope
        )
        order = m.PurchaseOrder.objects.filter(
            organization=self.organization, order_number="MVP08-PO01"
        ).first()
        if order is None:
            self.act(
                self.owner,
                reverse("procurement:order_from_award", args=[self.award_record.pk])
                + f"?supplier={self.supplier.pk}",
                {
                    "allocations": [
                        str(a.pk) for a in self.award_record.allocations.all()
                    ],
                    "order_number": "MVP08-PO01",
                    "order_date": format_jalali(timezone.localdate()),
                },
                selector='form[aria-label="سفارش از انتخاب نهایی"]',
                name="award-to-po",
            )
            order = m.PurchaseOrder.objects.get(
                organization=self.organization, order_number="MVP08-PO01"
            )
        if order.status == "draft":
            self.act(
                self.owner,
                reverse("procurement:order_detail", args=[order.pk]),
                selector='form[action$="/issue/"]',
                name="issue-po",
            )
            order.refresh_from_db()
        assert (
            order.current_version_id and order.source_award_id == self.award_record.pk
        )
        self.financial_checkpoint("PO-issued")
        for index, quantity in [(1, "2"), (2, "4")]:
            receipt = m.GoodsReceipt.objects.filter(
                organization=self.organization, receipt_number=f"MVP08-GRN0{index}"
            ).first()
            if receipt is None:
                self.act(
                    self.owner,
                    reverse("procurement:receipt_create")
                    + f"?purchase_order={order.pk}",
                    {
                        "purchase_order": str(order.pk),
                        "receipt_number": f"MVP08-GRN0{index}",
                        "received_at": format_jalali(
                            timezone.localtime(), include_time=True
                        ),
                    },
                    selector='form[aria-label="رسید کالای جدید"]',
                    name="po-to-grn",
                )
                receipt = m.GoodsReceipt.objects.get(
                    organization=self.organization, receipt_number=f"MVP08-GRN0{index}"
                )
            path = self.detail_url(receipt)
            if not receipt.items.exists():
                self.act(
                    self.owner,
                    path,
                    {
                        "purchase_order_item": str(order.items.get().pk),
                        "quantity": quantity,
                    },
                    selector='form[aria-label="افزودن قلم رسید"]',
                    name="receipt-line",
                )
            if receipt.status == "draft":
                before = StockTransaction.objects.filter(
                    organization=self.organization
                ).count()
                self.act(
                    self.owner,
                    path,
                    selector='form[aria-label="ثبت نهایی رسید"]',
                    name="post-grn",
                )
                assert (
                    StockTransaction.objects.filter(
                        organization=self.organization
                    ).count()
                    == before
                )
            source = receipt.items.get()
            stock = StockTransaction.objects.filter(
                organization=self.organization, transaction_number=f"MVP08-IN0{index}"
            ).first()
            if stock is None:
                self.act(
                    self.owner,
                    self.stock_url(source),
                    {
                        "transaction_number": f"MVP08-IN0{index}",
                        "destination_warehouse": str(self.site.pk),
                        "occurred_at": format_jalali(
                            timezone.localtime(), include_time=True
                        ),
                    },
                    selector='form[aria-label="ورود به انبار از رسید کالا"]',
                    name="grn-to-inventory-draft",
                )
                stock = StockTransaction.objects.get(
                    organization=self.organization,
                    transaction_number=f"MVP08-IN0{index}",
                )
                assert stock.status == "draft"
            if stock.status == "draft":
                self.act(
                    self.owner,
                    self.stock_detail(stock),
                    selector='form[aria-label="ثبت نهایی گردش"]',
                    name="post-inventory",
                )
            self.financial_checkpoint(f"explicit-stock-post-{index}")
        self.order = order

    def reverse_and_prove(self):
        self.downstream()
        receipts = list(
            m.GoodsReceipt.objects.filter(
                organization=self.organization,
                receipt_number__in=["MVP08-GRN01", "MVP08-GRN02"],
            ).order_by("receipt_number")
        )
        records = list(
            StockTransaction.objects.filter(
                organization=self.organization,
                transaction_number__in=["MVP08-IN01", "MVP08-IN02"],
            ).order_by("transaction_number")
        )
        assert len(receipts) == len(records) == 2
        record = records[1]
        if record.status == "posted":
            assert self.balance() == Decimal(6)
            self.act(
                self.owner,
                reverse("inventory:transaction_reverse", args=[record.pk]),
                {
                    "reversal_number": "MVP08-REV02",
                    "reason": "برگشت صریح تحویل دوم نمونه با حفظ اصل و رسید",
                },
                selector='form[aria-label="برگشت گردش انبار"]',
                name="explicit-reversal",
            )
            record.refresh_from_db()
        assert record.status == "reversed" and self.balance() == Decimal(2)
        assert all(receipt.status == "posted" for receipt in receipts)
        assert self.order.source_award_id == self.award_record.pk
        assert self.order.current_version.source_award_id == self.award_record.pk
        assert self.order.purchase_request_id == self.pr.pk
        allocation = self.order.items.get().source_award_allocation
        assert allocation.quote_revision.rfq_version_id == self.version.pk
        assert allocation.quote_revision.envelope.supplier_id == self.order.supplier_id
        assert self.version.lines.get().purchase_request_item_id == self.pr_line.pk
        for receipt, stock in zip(receipts, records, strict=True):
            assert receipt.purchase_order_version_id == self.order.current_version_id
            assert stock.goods_receipt_item.goods_receipt_id == receipt.pk
            assert (
                stock.quantity == receipt.items.get().quantity
                and stock.project_id == receipt.project_id
            )
        values = {
            "requested": self.pr_line.quantity,
            "sourced": self.version.lines.get().quantity,
            "awarded": sum(a.quantity for a in self.award_record.allocations.all()),
            "unawarded": self.award_record.unawarded_quantity,
            "ordered": self.order.items.get().quantity,
            "received": sum(r.items.get().quantity for r in receipts),
            "stock_originals": sum(s.quantity for s in records),
            "balance_after_reversal": self.balance(),
        }
        assert (
            values["requested"]
            == values["sourced"]
            == values["awarded"] + values["unawarded"]
            == Decimal(10)
        )
        assert (
            values["awarded"]
            == values["ordered"]
            == values["received"]
            == values["stock_originals"]
            == Decimal(6)
        )
        self.financial_checkpoint("explicit-reversal-no-receipt-or-financial-mutation")
        (OUT / "J3-lineage-quantity-reversal.json").write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "quantities": values,
                    "references": {
                        "PR": "PR-F",
                        "RFQ": self.rfq.rfq_number,
                        "RFQ_version": self.version.version_number,
                        "PO": self.order.order_number,
                        "GRNs": [r.receipt_number for r in receipts],
                        "Inventory": [s.transaction_number for s in records],
                        "reversal": "MVP08-REV02",
                    },
                    "financial_boundary": "unchanged",
                    "receipt_statuses": [r.status for r in receipts],
                },
                default=str,
                indent=2,
            ),
            encoding="utf8",
        )

    def qualify(self):
        self.bind_chain()
        order = m.PurchaseOrder.objects.get(
            organization=self.organization, order_number="MVP08-PO01"
        )
        receipt = m.GoodsReceipt.objects.get(
            organization=self.organization, receipt_number="MVP08-GRN01"
        )
        stock = StockTransaction.objects.get(
            organization=self.organization, transaction_number="MVP08-IN01"
        )
        paths = {
            "PR": reverse("procurement:request_detail", args=[self.pr.pk]),
            "RFQ": reverse("procurement:rfq_detail", args=[self.rfq.pk]),
            "sourcing": reverse("procurement:rfq_buyer_workspace", args=[self.rfq.pk]),
            "PO": reverse("procurement:order_detail", args=[order.pk]),
            "GRN": self.detail_url(receipt),
            "Inventory": self.stock_detail(stock),
        }
        retained_batch = OUT / "browser" / f"batch-{RFQ_NUMBER}-J3-PR-1440.json"
        if retained_batch.exists():
            qualified = json.loads(retained_batch.read_text(encoding="utf8"))
            assert len(qualified) == 18 and all(
                item["status"] == 200 for item in qualified
            )
        else:
            self.browser(
                self.owner,
                [
                    self.case(
                        f"J3-{name}-{width}", path, width=width, mobile=width == 390
                    )
                    for width in [1440, 1024, 390]
                    for name, path in paths.items()
                ],
            )
        revision = m.QuoteRevision.objects.get(
            organization=self.organization, rfq_version=self.version
        )
        admissibility = m.QuoteAdmissibilityPreparation.objects.get(
            organization=self.organization, quote_revision=revision
        )
        prepared = m.CommercialComparison.objects.get(
            organization=self.organization,
            commercial_scope=self.scope,
            finalized_at=None,
        )
        award_prep = m.SourcingAwardPreparation.objects.get(
            organization=self.organization, comparison__commercial_scope=self.scope
        )
        for actor, action, parents in [
            (self.owner, "prepare_admissibility", {"quote_revision": revision.pk}),
            (self.approver, "approve_admissibility", {"preparation": admissibility.pk}),
            (self.approver, "finalize_comparison", {"comparison": prepared.pk}),
            (self.owner, "prepare_award", {"comparison": award_prep.comparison_id}),
            (self.approver, "finalize_award", {"preparation": award_prep.pk}),
        ]:
            self.browser(
                actor,
                [
                    self.case(
                        "J3-current-form-" + action,
                        action_url(self.rfq, action, **parents),
                    )
                ],
            )
        denials = []
        evidence = m.QuoteRevisionEvidence.objects.get(
            organization=self.organization, quote_revision__rfq_version=self.version
        )
        source_path = reverse(
            "procurement:rfq_buyer_document", args=[self.rfq.pk, evidence.pk]
        )
        self.login(self.owner)
        source_response = self.client.get(source_path)
        assert source_response.status_code == 200
        assert (
            hashlib.sha256(
                b"".join(source_response.streaming_content)
                if source_response.streaming
                else source_response.content
            ).hexdigest()
            == evidence.canonical_sha256
        )
        for actor in [User.objects.get(username="mvp08.restricted"), self.outsider]:
            self.login(actor)
            scenarios = []
            for name, path in paths.items():
                for suffix in (
                    ["", "?format=xlsx", "?format=print"]
                    if name in ["PO", "GRN", "Inventory"]
                    else [""]
                ):
                    target = path + suffix
                    response = self.client.get(target)
                    assert response.status_code in (403, 404), (
                        actor.username,
                        name,
                        suffix,
                        response.status_code,
                    )
                    denied_text = response.content.decode()
                    if actor == self.outsider:
                        assert self.project.name not in denied_text
                    assert not any(
                        reference in denied_text
                        for reference in [
                            RFQ_NUMBER,
                            "MVP08-PO01",
                            "MVP08-GRN01",
                            "MVP08-IN01",
                        ]
                    )
                    denials.append(
                        {
                            "actor": actor.username,
                            "surface": name + suffix,
                            "status": response.status_code,
                        }
                    )
                    if not suffix:
                        scenarios.append(
                            self.case(
                                f"J3-denied-{name}",
                                target,
                                status=response.status_code,
                                noHttpErrors=False,
                                plainBusinessDenial=True,
                            )
                        )
            self.browser(actor, scenarios)
            response = self.client.get(source_path)
            assert response.status_code in (403, 404)
            denials.append(
                {
                    "actor": actor.username,
                    "surface": "protected supplier document",
                    "status": response.status_code,
                }
            )
        (OUT / "tenant-permission-denials.json").write_text(
            json.dumps(denials, indent=2), encoding="utf8"
        )
        self.outputs(paths)

    def outputs(self, paths):
        self.login(self.owner)
        env = os.environ.copy()
        env["MVP07_SESSION"] = self.client.cookies["sessionid"].value
        downloads = [
            {"name": "procurement", "path": reverse("procurement:request_list")},
            {"name": "PO", "path": reverse("procurement:order_list")},
            {"name": "GRN", "path": reverse("procurement:receipt_list")},
            {"name": "Inventory", "path": reverse("inventory:transaction_list")},
        ]
        env["MVP07_SCENARIOS"] = json.dumps(downloads)
        result = subprocess.run(
            [
                "node",
                str(ROOT / "scripts/verification/mvp07_browser.mjs"),
                self.live_server_url,
                str(OUT / "downloads"),
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf8",
            timeout=240,
            check=False,
        )
        assert result.returncode == 0, (result.stderr + result.stdout)[-3000:]
        from openpyxl import load_workbook

        workbooks = []
        for path in (OUT / "downloads").rglob("*.xlsx"):
            wb = load_workbook(path, data_only=True)
            sheets = []
            all_text = ""
            for sheet in wb:
                rows = list(sheet.values)
                all_text += " ".join(
                    str(v) for row in rows for v in row if v is not None
                )
                assert sheet.sheet_view.rightToLeft and sheet.max_row > 1
                sheets.append(
                    {
                        "title": sheet.title,
                        "rows": sheet.max_row,
                        "columns": sheet.max_column,
                    }
                )
            reference = {
                "procurement": "PR-F",
                "PO": "MVP08-PO01",
                "GRN": "MVP08-GRN01",
                "Inventory": "MVP08-IN01",
            }[path.parent.name.split("-", 1)[0]]
            assert reference in all_text, (path, reference)
            import re

            assert not re.search(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-", all_text)
            workbooks.append(
                {
                    "file": str(path.relative_to(OUT)),
                    "source_reference": reference,
                    "sheets": sheets,
                    "reopened": True,
                }
            )
            wb.close()
        assert len({item["source_reference"] for item in workbooks}) == 4
        (OUT / "workbook-integrity.json").write_text(
            json.dumps(workbooks, ensure_ascii=False, indent=2), encoding="utf8"
        )
        env["MVP06_SESSION"] = env["MVP07_SESSION"]
        env["MVP06_SCENARIOS"] = json.dumps(
            [{"name": "PO", "path": paths["PO"]}, {"name": "GRN", "path": paths["GRN"]}]
        )
        result = subprocess.run(
            [
                "node",
                str(ROOT / "scripts/verification/mvp06_browser.mjs"),
                self.live_server_url,
                str(OUT / "print"),
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf8",
            timeout=240,
            check=False,
        )
        assert result.returncode == 0, (result.stderr + result.stdout)[-3000:]
        self.financial_checkpoint("browser-isolation-XLSX-and-print")

    def print_po(self):
        order = m.PurchaseOrder.objects.get(
            organization=self.organization, order_number="MVP08-PO01"
        )
        self.login(self.owner)
        env = os.environ.copy()
        env["MVP06_SESSION"] = self.client.cookies["sessionid"].value
        env["MVP06_SCENARIOS"] = json.dumps(
            [
                {
                    "name": "PO",
                    "path": reverse("procurement:order_detail", args=[order.pk]),
                }
            ]
        )
        result = subprocess.run(
            [
                "node",
                str(ROOT / "scripts/verification/mvp06_browser.mjs"),
                self.live_server_url,
                str(OUT / "print-currency-corrected"),
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf8",
            timeout=240,
            check=False,
        )
        assert result.returncode == 0, (result.stderr + result.stdout)[-3000:]
        self.financial_checkpoint("PO-print-source-currency-label")

    def billing_concurrent(self):
        from apps.billing.models import ProgressClaim

        claim = ProgressClaim.objects.get(organization=self.organization)
        path = reverse("billing:claim_detail", args=[claim.pk])
        self.browser(
            self.member,
            [
                self.case(
                    f"concurrent-billing-{width}",
                    path,
                    width=width,
                    mobile=width == 390,
                    mustText=["صورت‌وضعیت", "ناخالص", "خالص"],
                    steps=[
                        self.inspect(
                            "document.querySelectorAll('[data-xlsx-export]').length===1 && document.querySelectorAll('[data-print-preview]').length===1",
                            "current Billing output controls remain available",
                        )
                    ],
                )
                for width in [1440, 1024, 390]
            ],
        )
        claim.refresh_from_db()
        assert (
            claim.status == "approved"
            and claim.gross_amount == Decimal(50000000)
            and claim.net_amount == Decimal(36700000)
        )
        self.financial_checkpoint("concurrent-Billing-template-read-only-check")

    def case(self, name, path, **kwargs):
        result = super().case(name, path, **kwargs)
        result["steps"].append(
            self.inspect(
                "!/(?:\\b(?:draft|submitted|approved|no_award|awarded|posted|reversed|idempotency|fingerprint|candidacy)\\b|(?:rfqs|purchase_orders|goods_receipts|stock_transactions)\\.|object \\()/i.test(document.querySelector('main')?.innerText||'')",
                "business-language sourcing state and actions",
            )
        )
        result["steps"].append(
            self.inspect(
                "!/(?:^|\\n)\\s*(?:comparison|quote_revision|preparation|opening_request|invitation|scope|appointment):/m.test(document.querySelector('main')?.innerText||'')",
                "sourcing context uses business labels",
            )
        )
        return result

    def browser(self, actor, scenarios):
        # Confirmation is explicit for the intended test submission only; normal
        # confirm/cancel probes and all historic driver callers stay unchanged.
        for scenario in scenarios:
            if not scenario["name"].startswith(RFQ_NUMBER + "-"):
                scenario["name"] = RFQ_NUMBER + "-" + scenario["name"]
            for step in scenario.get("steps", []):
                if step.get("clickSelector") or step.get("submit"):
                    step["confirmIfShown"] = True
        self.login(actor)
        env = os.environ.copy()
        env["MVP02_SESSION"] = self.client.cookies["sessionid"].value
        env["MVP02_SCENARIOS"] = json.dumps(scenarios)
        directory = OUT / "browser"
        directory.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                "node",
                str(ROOT / "scripts/verification/mvp08_browser.mjs"),
                self.live_server_url,
                str(directory),
                actor.username,
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf8",
            timeout=240,
            check=False,
        )
        if result.returncode:
            (directory / f"failed-{scenarios[0]['name']}.txt").write_text(
                result.stdout + result.stderr, encoding="utf8"
            )
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-3000:])
        values = json.loads(result.stdout)
        (directory / f"batch-{scenarios[0]['name']}.json").write_text(
            json.dumps(values, ensure_ascii=False, indent=2), encoding="utf8"
        )

    def detail_url(self, receipt):
        return reverse("procurement:receipt_detail", args=[receipt.pk])

    def uat_start(self):
        request = m.PurchaseRequest.objects.filter(
            organization=self.organization, request_number="MVP08-UAT-PR"
        ).first()
        if request is None:
            self.act(
                self.member,
                reverse("procurement:request_create")
                + f"?project_id={self.project.pk}",
                {
                    "request_number": "MVP08-UAT-PR",
                    "title": "تمرین پذیرش نیاز بتن کارگاه — نمونه",
                },
                selector='form[aria-label="درخواست خرید جدید"]',
                name="uat-draft-request",
            )
            request = m.PurchaseRequest.objects.get(
                organization=self.organization, request_number="MVP08-UAT-PR"
            )
        if not request.items.exists():
            self.browser(
                self.member,
                [
                    self.case(
                        "uat-draft-line",
                        reverse("procurement:request_detail", args=[request.pk]),
                        steps=[
                            {
                                "searchChoice": {
                                    "name": "material",
                                    "query": "بتن",
                                    "value": str(self.material.pk),
                                }
                            },
                            {
                                "formSelector": 'form[aria-label="افزودن قلم"]',
                                "fill": {
                                    "quantity": "10",
                                    "description": "بتن آماده برای تمرین پذیرش",
                                },
                                "clickSelector": 'form[aria-label="افزودن قلم"] button[type="submit"]',
                                "afterPrefix": "/",
                            },
                        ],
                    )
                ],
            )
        assert request.status == "draft" and request.items.get().quantity == Decimal(10)
        self.financial_checkpoint("Human-UAT-draft-start")

    def bind_chain(self):
        self.pr = m.PurchaseRequest.objects.get(
            organization=self.organization, request_number="PR-F"
        )
        self.pr_line = self.pr.items.get()
        self.rfq = m.RequestForQuotation.objects.filter(
            organization=self.organization, rfq_number=RFQ_NUMBER
        ).first()
        if self.rfq and self.rfq.versions.exists():
            self.version = self.rfq.versions.get(
                version_number=self.rfq.current_version_number
            )
            self.scope = self.version.commercial_scopes.get()

    def upstream(self):
        self.bind_chain()
        detail = reverse("procurement:request_detail", args=[self.pr.pk])
        if self.pr.status == "draft":
            self.act(
                self.member,
                detail,
                selector='form[action$="/submit/"]',
                name="submit-retained-pr",
            )
            self.pr.refresh_from_db()
        if self.pr.status == "submitted":
            self.act(
                self.pr_reviewer,
                detail,
                {"approve-reason": "تأیید مستقل نیاز کارگاه"},
                selector='form[action$="/approve/"]',
                name="approve-pr",
            )
            self.pr.refresh_from_db()
        assert self.pr.status == "approved"
        if self.rfq is None:
            # Real current clock, not a patched/future decision timestamp.
            deadline = timezone.localtime().replace(
                second=0, microsecond=0
            ) + timedelta(minutes=10)
            self.act(
                self.owner,
                reverse("procurement:rfq_create") + f"?purchase_request={self.pr.pk}",
                {
                    "rfq_number": RFQ_NUMBER,
                    "title": "استعلام بتن آماده سروستان — نمونه",
                    "closing_at": format_jalali(deadline, include_time=True),
                    "earliest_opening_at": format_jalali(deadline, include_time=True),
                },
                selector='form[aria-label="استعلام جدید"]',
                name="contextual-pr-to-rfq",
            )
            self.bind_chain()
        rfq_detail = reverse("procurement:rfq_detail", args=[self.rfq.pk])
        if not self.rfq.lines.exists():
            self.browser(
                self.owner,
                [
                    self.case(
                        "select-retained-pr-line",
                        rfq_detail,
                        steps=[
                            {
                                "toggleSelector": 'details:has(form[aria-label="افزودن قلم استعلام"]) summary'
                            },
                            {
                                "searchChoice": {
                                    "name": "purchase_request_item_id",
                                    "query": "بتن",
                                    "value": str(self.pr_line.pk),
                                }
                            },
                            {
                                "formSelector": 'form[aria-label="افزودن قلم استعلام"]',
                                "fill": {
                                    "quantity": "10",
                                    "description": "بتن آماده فونداسیون — نمونه",
                                },
                                "clickSelector": 'form[aria-label="افزودن قلم استعلام"] button[type="submit"]',
                                "afterPrefix": "/",
                            },
                        ],
                    )
                ],
            )
        if not self.rfq.scope_definitions.exists():
            self.act(
                self.owner,
                rfq_detail,
                {
                    "quantity_0": "10",
                    "independently_awardable_0": "yes",
                    "allows_split_award_0": "yes",
                    "allows_alternates_0": "no",
                    "operation": "configure_items",
                },
                selector='form[aria-label="تنظیمات انتخاب تأمین‌کننده"]',
                button='button[value="configure_items"]',
                name="define-explicit-scope",
            )
        self.rfq.refresh_from_db()
        if self.rfq.status == "draft":
            self.act(
                self.owner,
                rfq_detail,
                selector='form[action$="/submit/"]',
                name="submit-rfq",
            )
            self.rfq.refresh_from_db()
        if self.rfq.status == "submitted_for_issue":
            self.act(
                self.owner,
                rfq_detail,
                {"supplier_ids": [str(self.supplier.pk)]},
                selector='form[aria-label="صدور استعلام"]',
                name="select-suppliers-and-issue",
            )
        self.bind_chain()
        assert self.rfq.status == "issued"
        self.financial_checkpoint("PR-RFQ-issued")

    def quotes(self):
        self.bind_chain()
        self.invitation = self.version.invitations.get()
        self.revision = (
            m.QuoteRevision.objects.filter(
                organization=self.organization, invitation=self.invitation
            )
            .order_by("-revision_number")
            .first()
        )
        if self.revision is None:
            self.buyer(
                self.owner,
                "capture",
                {"source_channel": "manual_capture"},
                invitation=self.invitation.pk,
            )
            self.revision = m.QuoteRevision.objects.get(
                organization=self.organization, invitation=self.invitation
            )
        if self.revision.status == "captured":
            self.buyer(self.owner, "submit", quote_revision=self.revision.pk)
            self.revision.refresh_from_db()
        assert self.revision.status == "submitted"
        remaining = (self.version.closing_at - timezone.now()).total_seconds()
        while remaining > 0:
            print(
                f"Waiting for actual RFQ deadline: {int(remaining)} seconds", flush=True
            )
            time.sleep(min(30, remaining + 0.1))
            remaining = (self.version.closing_at - timezone.now()).total_seconds()
        self.rfq.refresh_from_db()
        if self.rfq.status == "issued":
            self.act(
                self.custodian,
                reverse("procurement:rfq_detail", args=[self.rfq.pk]),
                selector='form[action$="/close/"]',
                name="close-rfq",
            )
        if not self.revision.evidence_items.exists():
            self.buyer(
                self.custodian,
                "attach_evidence",
                {"evidence_type": "supplier_original"},
                quote_revision=self.revision.pk,
            )
        evidence = self.revision.evidence_items.get()
        if not evidence.document_version.processing_assessments.exists():
            if connection.settings_dict["NAME"] != "test_bonira_mvp08_demo_20261103":
                raise RuntimeError("Synthetic processing fixture is TEST-copy-only")
            expected = hashlib.sha256(self.source_path.read_bytes()).hexdigest()
            assert expected == evidence.canonical_sha256
            # Explicit nonproduction infrastructure fixture, matching accepted
            # MVP-04 convention. No scanner or Platform Operations grant claim.
            DocumentProcessingAssessment.objects.create(
                organization=self.organization,
                version=evidence.document_version,
                sequence=1,
                verdict="clean",
                input_sha256=expected,
                adapter_code="mvp08-known-generated-synthetic-offer-fixture",
                adapter_version="1",
                recorded_by=self.custodian,
            )
            (OUT / "synthetic-processing.json").write_text(
                json.dumps(
                    {
                        "synthetic": True,
                        "source": "synthetic-supplier-offer.pdf",
                        "sha256": expected,
                        "fixture_verdict": "clean",
                        "real_scanner_executed": False,
                        "new_platform_authority": False,
                    },
                    indent=2,
                ),
                encoding="utf8",
            )
        if not m.QuoteOpeningRequest.objects.filter(
            organization=self.organization, quote_revision=self.revision
        ).exists():
            self.buyer(
                self.owner,
                "request_opening",
                {"reason": "گشایش مستقل پیشنهاد مصنوعی پس از مهلت واقعی"},
                quote_revision=self.revision.pk,
            )
        opening = m.QuoteOpeningRequest.objects.get(
            organization=self.organization, quote_revision=self.revision
        )
        if not m.QuoteOpeningEvent.objects.filter(
            quote_revision=self.revision
        ).exists():
            self.buyer(
                self.opening_approver, "approve_opening", opening_request=opening.pk
            )
        for actor in (self.owner, self.approver, self.evaluator):
            membership = self.organization.memberships.get(user=actor)
            if not m.QuoteConfidentialAccessGrant.objects.filter(
                quote_revision=self.revision,
                membership=membership,
                revocation__isnull=True,
            ).exists():
                self.buyer(
                    self.opening_approver,
                    "grant_access",
                    {
                        "membership": str(membership.pk),
                        "reason": "بررسی مجاز و اختصاصی پیشنهاد نمونه",
                    },
                    quote_revision=self.revision.pk,
                )
        self.financial_checkpoint("quote-custody-opening-access")

    def correct_deadline(self):
        self.bind_chain()
        if (
            self.version.closing_at <= timezone.now()
            and not m.QuoteRevision.objects.filter(
                organization=self.organization, rfq_version=self.version
            ).exists()
        ):
            next_number = self.rfq.current_version_number + 1
            if not self.rfq.scope_definitions.filter(
                version_number=next_number
            ).exists():
                self.act(
                    self.owner,
                    reverse("procurement:rfq_scope_define", args=[self.rfq.pk]),
                    {
                        "scope_code": "بتن آماده فونداسیون",
                        "required_quantity": "10",
                        "unit_of_measure": str(self.unit.pk),
                        "select_0": True,
                        "member_0": "10",
                        "independently_awardable": "yes",
                        "allows_split_award": "yes",
                        "allows_alternates": "no",
                    },
                    selector='form[aria-label="تنظیم گروه خرید"]',
                    button='button[value="append"]',
                    name="prepare-addendum-scope",
                )
            deadline = timezone.localtime().replace(
                second=0, microsecond=0
            ) + timedelta(minutes=5)
            self.act(
                self.owner,
                reverse("procurement:rfq_addendum", args=[self.rfq.pk]),
                {
                    "closing_at": format_jalali(deadline, include_time=True),
                    "earliest_opening_at": format_jalali(deadline, include_time=True),
                    "terms": "اصلاح مهلت دریافت نمونه آموزشی با حفظ نسخه قبلی",
                },
                selector='form[aria-label="صدور الحاقیه"]',
                name="correct-local-deadline-addendum",
            )
            self.bind_chain()
            (OUT / "deadline-correction.json").write_text(
                json.dumps(
                    {
                        "reason": "Harness supplied UTC to a local-time form; original issued version preserved. Native explicit scope and addendum used before any quote capture.",
                        "current_version": self.version.version_number,
                        "closing_at": self.version.closing_at.isoformat(),
                        "actual_clock": timezone.now().isoformat(),
                    },
                    indent=2,
                ),
                encoding="utf8",
            )


def build():
    base = prepare()
    f = Journey()
    f.__dict__.update(base.__dict__)
    f.pr_reviewer = base.approver
    for attr, suffix in [
        ("owner", "rfq-preparer"),
        ("approver", "rfq-reviewer"),
        ("evaluator", "rfq-evaluator"),
        ("custodian", "rfq-custodian"),
        ("opening_approver", "rfq-opening-approver"),
    ]:
        setattr(f, attr, User.objects.get(username="mvp08." + suffix))
    f.source_path = OUT / "synthetic-supplier-offer.pdf"
    f.sequence = 0
    baseline_path = OUT / "financial-baseline-v3.json"
    actual = f.money_snapshot()
    if not baseline_path.exists():
        original = OUT / "financial-baseline.json"
        baseline = json.loads(original.read_text()) if original.exists() else actual
        # The first harness classifier matched 'valuation' inside 'Evaluation'.
        # Preserve its original evidence; commercial evaluations are explicitly
        # procurement operational evidence, not inventory valuation authority.
        assert set(actual) <= set(baseline), (
            "A required financial source lacks an initial baseline"
        )
        baseline = {key: baseline[key] for key in actual}
        baseline_path.write_text(json.dumps(baseline, indent=2), encoding="utf8")
    f.financial_before = json.loads(baseline_path.read_text())
    f.financial_checkpoints = []
    f.assertEqual(
        actual, f.financial_before, "retained continuation financial baseline"
    )
    return f


def main():
    f = build()
    sourcing_preflight(f)
    server = LiveServerThread(
        "localhost", StaticFilesHandler, connections_override={}, port=0
    )
    with override_settings(
        DEBUG=False,
        PRODUCT_SURFACE_PROFILE="MVP",
        ALLOWED_HOSTS=["localhost", "127.0.0.1", "testserver"],
        DOCUMENT_PROTECTED_ROOT=OUT / "protected-source",
    ):
        server.start()
        server.is_ready.wait(30)
        if server.error:
            raise server.error
        Journey.server_thread = server
        try:
            phase = sys.argv[1] if len(sys.argv) > 1 else "upstream"
            if phase == "upstream":
                f.upstream()
            elif phase == "source-and-open":
                f.upstream()
                f.quotes()
            elif phase == "deadline-and-quotes":
                f.correct_deadline()
                f.quotes()
            elif phase == "quotes":
                f.quotes()
            elif phase == "decisions":
                f.decisions()
            elif phase == "downstream":
                f.downstream()
            elif phase == "reverse-and-prove":
                f.reverse_and_prove()
            elif phase == "qualify":
                f.qualify()
            elif phase == "print-po":
                f.print_po()
            elif phase == "billing-concurrent":
                f.billing_concurrent()
            elif phase == "outputs":
                order = m.PurchaseOrder.objects.get(
                    organization=f.organization, order_number="MVP08-PO01"
                )
                receipt = m.GoodsReceipt.objects.get(
                    organization=f.organization, receipt_number="MVP08-GRN01"
                )
                f.outputs(
                    {
                        "PO": reverse("procurement:order_detail", args=[order.pk]),
                        "GRN": f.detail_url(receipt),
                    }
                )
            elif phase == "uat-start":
                f.uat_start()
            else:
                raise ValueError(phase)
        finally:
            server.terminate()
            server.join(30)
    print("MVP-08 Journey 3 phase:", phase, "PASS")


if __name__ == "__main__":
    main()

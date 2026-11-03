"""Connected MVP-04 verification, starting with master data only.

Only clock, explicit test-policy selection and synthetic file-processing evidence
are fixture controls. Every business transition uses the real customer endpoint.
"""

import hashlib
import json
import re
import tempfile
from datetime import timedelta
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.documents.models import (
    DocumentProcessingAssessment,
    DocumentProcessingVerdict,
)
from apps.inventory.models import StockTransaction
from apps.inventory.test_mvp04e import InventoryJourneyFixture
from apps.organizations.models import (
    BusinessPermission,
    MembershipRoleAssignment,
    OrganizationRole,
)
from apps.parties.models import BusinessParty, PartyRole
from apps.procurement import models as m
from apps.procurement.buyer_ui import action_url
from apps.procurement.test_p5_s10_admissibility import AdmissibilityFixtureMixin
from apps.procurement.test_p5_s11_comparison_award import P5S11FixtureMixin
from core.jalali import format_jalali


class RenderedForms(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.forms = []
        self.current = None
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.current = {"attrs": attrs, "hidden": {}}
            self.forms.append(self.current)
        elif (
            tag == "input"
            and self.current is not None
            and attrs.get("type") == "hidden"
            and attrs.get("name")
        ):
            self.current["hidden"][attrs["name"]] = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None

    def select(self, selector):
        for form in self.forms:
            attrs = form["attrs"]
            if selector.startswith("#") and attrs.get("id") == selector[1:]:
                return form
            label = re.search(r'aria-label="([^"]+)"', selector)
            if label and attrs.get("aria-label") == label[1]:
                return form
            action = re.search(r'action\$="([^"]+)"', selector)
            if action and attrs.get("action", "").endswith(action[1]):
                return form
        raise AssertionError(f"Rendered business form missing: {selector}")


class ConnectedJourneyFixture(InventoryJourneyFixture):
    evidence_root = (
        Path(__file__).resolve().parents[2] / "output/mvp-04b-ux/connected-journey"
    )

    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        setting = override_settings(DOCUMENT_PROTECTED_ROOT=temporary.name)
        setting.enable()
        self.addCleanup(temporary.cleanup)
        self.addCleanup(setting.disable)
        self.approver = self.new_actor("f-independent-reviewer")
        self.evaluator = self.new_actor("f-commercial-evaluator")
        for user in (self.owner, self.member, self.approver, self.evaluator):
            membership = self.organization.memberships.get(user=user)
            role = OrganizationRole.objects.create(
                code=f"mvp04f-{user.pk}", name="Explicit synthetic journey authority"
            )
            role.permissions.set(BusinessPermission.objects.filter(is_active=True))
            MembershipRoleAssignment.objects.create(
                organization=self.organization,
                membership=membership,
                role=role,
                reason="MVP-04F isolated fixture",
                source="test_fixture",
            )
        self.second_supplier = BusinessParty.objects.create(
            organization=self.organization,
            display_name="تأمین مصالح دوم",
            party_kind="company",
        )
        PartyRole.objects.create(
            organization=self.organization, party=self.second_supplier, role="supplier"
        )
        self.organization.name = "شرکت ساختمانی نمونه"
        self.organization.save(update_fields=["name"])
        self.site.name = "انبار پروژه سازه"
        self.site.save(update_fields=["name"])
        self.source_path = self.evidence_root / "synthetic-offer.pdf"
        self.source_path.parent.mkdir(parents=True, exist_ok=True)
        self.source_path.write_bytes(
            b"%PDF-1.7\nSynthetic MVP-04F source offer fixture\n%%EOF\n"
        )
        self.sequence = 0
        self.financial_before = self.money_snapshot()
        self.financial_checkpoints = []
        self.assertFalse(m.PurchaseRequest.objects.exists())
        self.assertFalse(m.RequestForQuotation.objects.exists())
        self.assertFalse(m.QuoteRevision.objects.exists())
        self.assertFalse(StockTransaction.objects.exists())

    def new_actor(self, name):
        actor = User.objects.create_user(username=name)
        membership = self.organization.memberships.create(
            user=actor, role="company_owner", status="active"
        )
        self.establish_test_membership_authority(membership)
        return actor

    def money_snapshot(self):
        """Hash existing financial rows too, so an update cannot hide behind counts."""
        from apps.accounting.models import JournalEntry
        from apps.documents.models import RetiredPaymentEvidence
        from apps.projects.models import ProjectCostFact
        from apps.subledgers.models import Obligation, SupplierInvoice
        from apps.treasury.models import PaymentRequest, TreasuryMovement

        snapshot = {}
        for model in (
            SupplierInvoice,
            Obligation,
            JournalEntry,
            TreasuryMovement,
            PaymentRequest,
            RetiredPaymentEvidence,
            ProjectCostFact,
        ):
            rows = list(
                model.objects.filter(organization=self.organization)
                .order_by("pk")
                .values()
            )
            snapshot[model._meta.label] = {
                "count": len(rows),
                "sha256": hashlib.sha256(
                    json.dumps(rows, sort_keys=True, default=str).encode()
                ).hexdigest(),
            }
        # Legacy Payment has no runtime model. Inspect any retained payment tables
        # on this isolated DB without reintroducing the retired financial app.
        with connection.cursor() as cursor:
            for table in sorted(connection.introspection.table_names(cursor)):
                if "payment" not in table:
                    continue
                columns = {
                    c.name
                    for c in connection.introspection.get_table_description(
                        cursor, table
                    )
                }
                if "organization_id" not in columns:
                    continue
                cursor.execute(
                    f"SELECT * FROM {connection.ops.quote_name(table)} WHERE organization_id = %s",
                    [self.organization.pk],
                )
                rows = sorted((list(row) for row in cursor.fetchall()), key=str)
                snapshot[table] = {
                    "count": len(rows),
                    "sha256": hashlib.sha256(
                        json.dumps(rows, sort_keys=True, default=str).encode()
                    ).hexdigest(),
                }
        return snapshot

    def financial_checkpoint(self, stage):
        actual = self.money_snapshot()
        self.assertEqual(actual, self.financial_before, stage)
        self.financial_checkpoints.append({"stage": stage, "unchanged": True})

    def act(
        self,
        actor,
        path,
        fields=None,
        *,
        selector=None,
        button=None,
        upload=False,
        name=None,
        expected=302,
    ):
        """Use each real form's internally managed hidden values, not invented keys."""
        self.login(actor)
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        form = RenderedForms(response.content.decode()).select(selector)
        data = dict(form["hidden"])
        data.update(fields or {})
        if any(k.startswith("rows-1-") for k in data):
            data["rows-TOTAL_FORMS"] = max(int(data.get("rows-TOTAL_FORMS", 0)), 2)
        if upload:
            field = "upload" if "attach_evidence" in path else "source_file"
            data[field] = SimpleUploadedFile(
                "offer.pdf",
                self.source_path.read_bytes(),
                content_type="application/pdf",
            )
        target = form["attrs"].get("action") or path
        result = self.client.post(target, data)
        self.assertEqual(
            result.status_code,
            expected,
            (
                target,
                result.context["form"].errors
                if result.context and result.context.get("form")
                else result.content[-1200:],
            ),
        )
        return result

    def buyer(self, actor, action, fields=None, **parents):
        return self.act(
            actor,
            action_url(self.rfq, action, **parents),
            fields,
            selector="#buyer-action-form",
            upload=action in ("capture", "attach_evidence"),
            name=action,
        )

    def begin(self, *, suppliers=1):
        now = timezone.now().replace(second=0, microsecond=0)
        self.act(
            self.member,
            reverse("procurement:request_create") + f"?project_id={self.project.pk}",
            {"request_number": "PR-F", "title": "خرید مصالح فونداسیون"},
            selector='form[aria-label="درخواست خرید جدید"]',
            name="create-pr",
        )
        self.pr = m.PurchaseRequest.objects.get(request_number="PR-F")
        detail = reverse("procurement:request_detail", args=[self.pr.pk])
        self.act(
            self.member,
            detail,
            {
                "material": str(self.material.pk),
                "quantity": "10",
                "description": "سیمان فونداسیون",
            },
            selector='form[aria-label="افزودن قلم"]',
            name="add-pr-material",
        )
        self.pr_line = self.pr.items.get()
        self.act(
            self.member, detail, selector='form[action$="/submit/"]', name="submit-pr"
        )
        self.act(
            self.owner,
            detail,
            {"approve-reason": "تأیید نیاز پروژه"},
            selector='form[action$="/approve/"]',
            name="approve-pr",
        )
        self.pr.refresh_from_db()
        self.assertEqual(self.pr.status, "approved")
        rfq_create = (
            reverse("procurement:rfq_create") + f"?purchase_request={self.pr.pk}"
        )
        self.act(
            self.owner,
            rfq_create,
            {
                "rfq_number": "RFQ-F",
                "title": "استعلام سیمان پروژه",
                "closing_at": format_jalali(now + timedelta(days=1), include_time=True),
                "earliest_opening_at": format_jalali(
                    now + timedelta(days=1), include_time=True
                ),
            },
            selector='form[aria-label="استعلام جدید"]',
            name="contextual-pr-to-rfq",
        )
        self.rfq = m.RequestForQuotation.objects.get(rfq_number="RFQ-F")
        rfq_detail = reverse("procurement:rfq_detail", args=[self.rfq.pk])
        self.act(
            self.owner,
            rfq_detail,
            {
                "purchase_request_item_id": str(self.pr_line.pk),
                "quantity": "10",
                "description": "سیمان فونداسیون",
            },
            selector='form[aria-label="افزودن قلم استعلام"]',
            name="select-pr-line",
        )
        self.act(
            self.owner,
            rfq_detail,
            {
                "quantity_0": "10",
                "independently_awardable_0": "yes",
                "allows_split_award_0": "yes" if suppliers == 2 else "no",
                "allows_alternates_0": "no",
                "operation": "configure_items",
            },
            selector='form[aria-label="تنظیمات انتخاب تأمین‌کننده"]',
            button='button[value="configure_items"]',
            name="define-explicit-scope",
        )
        self.act(
            self.owner,
            rfq_detail,
            selector='form[action$="/submit/"]',
            name="submit-rfq",
        )
        supplier_ids = [str(self.supplier.pk)] + (
            [str(self.second_supplier.pk)] if suppliers == 2 else []
        )
        self.act(
            self.owner,
            rfq_detail,
            {"supplier_ids": supplier_ids},
            selector='form[aria-label="صدور استعلام"]',
            name="select-suppliers-and-issue",
        )
        self.rfq.refresh_from_db()
        self.version = self.rfq.versions.get()
        self.scope = self.version.commercial_scopes.get()
        self.financial_checkpoint("PR-RFQ-scope-issue")

    def open_quotes_and_compare(self, *, revise=False):
        self.revisions = []
        for invitation in self.version.invitations.select_related("supplier").order_by(
            "created_at"
        ):
            self.buyer(
                self.owner,
                "capture",
                {"source_channel": "manual_capture"},
                invitation=invitation.pk,
            )
            revision = m.QuoteRevision.objects.filter(invitation=invitation).latest(
                "created_at"
            )
            self.buyer(self.owner, "submit", quote_revision=revision.pk)
            if revise:
                original = revision
                self.buyer(
                    self.owner,
                    "capture",
                    {"source_channel": "manual_capture"},
                    invitation=invitation.pk,
                )
                revision = m.QuoteRevision.objects.filter(invitation=invitation).latest(
                    "created_at"
                )
                self.buyer(self.owner, "submit", quote_revision=revision.pk)
                original.refresh_from_db()
                self.assertEqual(original.status, "superseded")
            self.revisions.append(revision)
        detail = reverse("procurement:rfq_detail", args=[self.rfq.pk])
        with patch(
            "apps.procurement.rfq_services.timezone.now",
            return_value=self.version.closing_at + timedelta(seconds=2),
        ):
            self.act(
                self.owner, detail, selector='form[action$="/close/"]', name="close-rfq"
            )
        for revision in self.revisions:
            self.buyer(
                self.owner,
                "attach_evidence",
                {"evidence_type": "supplier_original"},
                quote_revision=revision.pk,
            )
            evidence = revision.evidence_items.get()
            # Explicit synthetic scanner outcome; never a deployed scanner claim.
            DocumentProcessingAssessment.objects.create(
                organization=self.organization,
                version=evidence.document_version,
                sequence=1,
                verdict=DocumentProcessingVerdict.CLEAN,
                input_sha256=evidence.canonical_sha256,
                adapter_code="mvp04f-synthetic-processing-fixture",
                adapter_version="1",
                recorded_by=self.owner,
            )
            with patch(
                "apps.procurement.opening_services.timezone.now",
                return_value=self.version.earliest_opening_at + timedelta(seconds=2),
            ):
                self.buyer(
                    self.owner,
                    "request_opening",
                    {"reason": "گشایش رسمی پس از مهلت"},
                    quote_revision=revision.pk,
                )
                opening = m.QuoteOpeningRequest.objects.get(quote_revision=revision)
                self.buyer(self.approver, "approve_opening", opening_request=opening.pk)
            for actor, grantor in (
                (self.owner, self.approver),
                (self.approver, self.owner),
                (self.evaluator, self.owner),
            ):
                self.buyer(
                    grantor,
                    "grant_access",
                    {
                        "membership": str(
                            self.organization.memberships.get(user=actor).pk
                        ),
                        "reason": "بررسی مستند پیشنهاد",
                    },
                    quote_revision=revision.pk,
                )
        self.revision = self.revisions[0]
        AdmissibilityFixtureMixin._activate_self_approval_policy(self, allow=False)
        for code in (
            "rfq-comparison-self-finalization",
            "rfq-commercial-exception-self-approval",
            "rfq-sourcing-award-self-finalization",
        ):
            P5S11FixtureMixin._activate_policy(self, code, allow=False)
        for revision in self.revisions:
            self.buyer(
                self.owner,
                "prepare_admissibility",
                {
                    "state": "admissible",
                    "reason_code": "requirements_met",
                    "rationale": "انطباق با شرایط مصوب استعلام",
                },
                quote_revision=revision.pk,
            )
            prep = m.QuoteAdmissibilityPreparation.objects.get(quote_revision=revision)
            self.buyer(self.approver, "approve_admissibility", preparation=prep.pk)
        fields = {}
        for index, revision in enumerate(self.revisions):
            fields.update(
                {
                    f"rows-{index}-quote_revision_id": str(revision.pk),
                    f"rows-{index}-offered_quantity": "10",
                    f"rows-{index}-unit_price": "12.50",
                    f"rows-{index}-currency": "IRR",
                    f"rows-{index}-explicit_discount": "0",
                    f"rows-{index}-source_locator": "صفحه یک، قلم سیمان",
                }
            )
        self.buyer(self.owner, "prepare_comparison", fields, scope=self.scope.pk)
        prepared = m.CommercialComparison.objects.get(finalized_at__isnull=True)
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
        for item in prepared.inputs.all():
            self.buyer(
                self.evaluator,
                "evaluate",
                {
                    "input": str(item.pk),
                    "recommendation": "بررسی کامل پیشنهاد",
                    "evidence": "برگه ارزیابی مستند",
                },
                appointment=appointment.pk,
            )
        self.buyer(
            self.approver,
            "finalize_comparison",
            {"reason": "ارزیابی کامل و مستقل"},
            comparison=prepared.pk,
        )
        self.comparison = m.CommercialComparison.objects.get(finalized_at__isnull=False)
        self.financial_checkpoint("quote-custody-opening-admissibility-comparison")

    def award(self, quantities=None, *, no_award=False):
        fields = {
            "outcome": "no_award" if no_award else "awarded",
            "reason": "تصمیم مستند کمیته خرید",
            "evidence": "صورت‌جلسه خرید",
            "tie_resolution": len(self.revisions) > 1,
        }
        if not no_award:
            for index, item in enumerate(
                self.comparison.inputs.order_by(
                    "quote_revision__envelope__supplier__display_name"
                )
            ):
                fields.update(
                    {
                        f"rows-{index}-comparison_input_id": str(item.pk),
                        f"rows-{index}-quantity": (quantities or ["6"])[index],
                    }
                )
        self.buyer(self.owner, "prepare_award", fields, comparison=self.comparison.pk)
        prep = m.SourcingAwardPreparation.objects.get()
        self.buyer(self.approver, "finalize_award", preparation=prep.pk)
        result = m.SourcingAward.objects.get()
        self.financial_checkpoint("award")
        return result

    def order_from(self, award, supplier, number="PO-F"):
        path = (
            reverse("procurement:order_from_award", args=[award.pk])
            + f"?supplier={supplier.pk}"
        )
        self.act(
            self.owner,
            path,
            {
                "allocations": [
                    str(a.pk)
                    for a in award.allocations.filter(
                        quote_revision__envelope__supplier=supplier
                    )
                ],
                "order_number": number,
                "order_date": format_jalali(timezone.localdate()),
            },
            selector='form[aria-label="سفارش از انتخاب نهایی"]',
            name="award-to-po",
        )
        order = m.PurchaseOrder.objects.get(order_number=number)
        self.act(
            self.owner,
            reverse("procurement:order_detail", args=[order.pk]),
            selector='form[action$="/issue/"]',
            name="issue-po",
        )
        order.refresh_from_db()
        return order

    def receive_into_stock(self, order, quantity, index):
        self.act(
            self.owner,
            reverse("procurement:receipt_create") + f"?purchase_order={order.pk}",
            {
                "purchase_order": str(order.pk),
                "receipt_number": f"GRN-F-{index}",
                "received_at": format_jalali(
                    timezone.localtime(self.received_at), include_time=True
                ),
            },
            selector='form[aria-label="رسید کالای جدید"]',
            name="po-to-grn",
        )
        receipt = m.GoodsReceipt.objects.get(receipt_number=f"GRN-F-{index}")
        path = self.detail_url(receipt)
        self.act(
            self.owner,
            path,
            {"purchase_order_item": str(order.items.get().pk), "quantity": quantity},
            selector='form[aria-label="افزودن قلم رسید"]',
            name="receipt-line",
        )
        self.act(
            self.owner,
            path,
            selector='form[aria-label="ثبت نهایی رسید"]',
            name="post-grn",
        )
        self.assertFalse(
            StockTransaction.objects.filter(
                goods_receipt_item__goods_receipt=receipt
            ).exists()
        )
        source = receipt.items.get()
        self.act(
            self.owner,
            self.stock_url(source),
            {
                "transaction_number": f"IN-F-{index}",
                "destination_warehouse": str(self.site.pk),
                "occurred_at": format_jalali(
                    timezone.localtime(self.received_at), include_time=True
                ),
            },
            selector='form[aria-label="ورود به انبار از رسید کالا"]',
            name="grn-to-inventory-draft",
        )
        record = StockTransaction.objects.get(transaction_number=f"IN-F-{index}")
        self.assertEqual(record.status, "draft")
        self.act(
            self.owner,
            self.stock_detail(record),
            selector='form[aria-label="ثبت نهایی گردش"]',
            name="post-inventory",
        )
        self.financial_checkpoint(f"receipt-stock-{index}")
        return receipt, record

    def prove_lineage(self, award, orders, receipts, stock_records, name):
        for order in orders:
            self.assertEqual(order.source_award_id, award.pk)
            self.assertEqual(order.purchase_request_id, self.pr.pk)
            self.assertEqual(order.project_id, self.project.pk)
            allocation = order.items.get().source_award_allocation
            self.assertEqual(
                order.supplier_id, allocation.quote_revision.envelope.supplier_id
            )
            self.assertEqual(allocation.quote_revision.rfq_version_id, self.version.pk)
            self.assertEqual(order.current_version.source_award_id, award.pk)
        self.assertEqual(award.comparison.commercial_scope_id, self.scope.pk)
        self.assertEqual(
            self.scope.rfq_version_line.purchase_request_item_id, self.pr_line.pk
        )
        for receipt, record in zip(receipts, stock_records, strict=True):
            self.assertEqual(record.goods_receipt_item.goods_receipt_id, receipt.pk)
            self.assertEqual(
                receipt.purchase_order_version_id,
                receipt.purchase_order.current_version_id,
            )
            self.assertEqual(record.project_id, receipt.project_id)
            self.assertEqual(record.quantity, receipt.items.get().quantity)
            self.assertEqual(record.material_id, self.material.pk)
        values = {
            "requested": str(self.pr_line.quantity),
            "sourced": str(self.version.lines.get().quantity),
            "awarded": str(
                sum((a.quantity for a in award.allocations.all()), Decimal(0))
            ),
            "unawarded": str(award.unawarded_quantity),
            "ordered": str(sum((o.items.get().quantity for o in orders), Decimal(0))),
            "received": str(
                sum((r.items.get().quantity for r in receipts), Decimal(0))
            ),
            "stock_posted": str(sum((s.quantity for s in stock_records), Decimal(0))),
        }
        self.assertEqual(
            Decimal(values["awarded"]) + Decimal(values["unawarded"]),
            Decimal(values["sourced"]),
        )
        self.assertEqual(Decimal(values["awarded"]), Decimal(values["ordered"]))
        self.assertEqual(Decimal(values["ordered"]), Decimal(values["received"]))
        self.assertEqual(Decimal(values["received"]), Decimal(values["stock_posted"]))
        (self.evidence_root / f"{name}-lineage.json").write_text(
            json.dumps(
                {
                    "quantities": values,
                    "chain": {
                        "pr": str(self.pr.pk),
                        "rfq": str(self.rfq.pk),
                        "rfq_version": str(self.version.pk),
                        "quote_revisions": [str(r.pk) for r in self.revisions],
                        "comparison": str(self.comparison.pk),
                        "award": str(award.pk),
                        "orders": [str(o.pk) for o in orders],
                        "receipts": [str(r.pk) for r in receipts],
                        "stock_transactions": [str(s.pk) for s in stock_records],
                    },
                    "financial_baseline": self.financial_before,
                    "financial_checkpoints": self.financial_checkpoints,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


class ConnectedJourneyTests(ConnectedJourneyFixture, TestCase):
    def test_split_award_separate_supplier_orders_receipts_and_exact_lineage(self):
        self.begin(suppliers=2)
        self.open_quotes_and_compare()
        award = self.award(["4", "6"])
        orders, receipts, records = [], [], []
        for index, allocation in enumerate(award.allocations.all(), 1):
            supplier = allocation.quote_revision.envelope.supplier
            order = self.order_from(award, supplier, f"PO-F-{index}")
            receipt, record = self.receive_into_stock(
                order, str(allocation.quantity), index
            )
            orders.append(order)
            receipts.append(receipt)
            records.append(record)
        self.assertEqual(self.balance(), Decimal(10))
        self.prove_lineage(award, orders, receipts, records, "split")
        self.login(self.owner)
        self.assertContains(
            self.client.get(reverse("procurement:request_detail", args=[self.pr.pk])),
            "data-pr-existing-rfq",
        )
        self.assertContains(
            self.client.get(
                reverse("procurement:rfq_buyer_workspace", args=[self.rfq.pk])
            ),
            "data-award-existing-po",
        )
        for order in orders:
            self.assertContains(
                self.client.get(reverse("procurement:order_detail", args=[order.pk])),
                "data-po-existing-grn",
            )
        # Read access to the parent does not imply access to downstream records.
        reader = self.new_actor("f-limited-history-reader")
        member = self.organization.memberships.get(user=reader)
        MembershipRoleAssignment.objects.filter(membership=member).update(
            revoked_at=timezone.now()
        )
        role = OrganizationRole.objects.create(
            code="f-history-only", name="Synthetic parent-only reader"
        )
        role.permissions.set(
            BusinessPermission.objects.filter(
                code__in=["purchase_requests.view", "purchase_orders.view"]
            )
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=member,
            role=role,
            reason="Read-only lineage denial fixture",
            source="test_fixture",
        )
        self.login(reader)
        self.assertNotContains(
            self.client.get(reverse("procurement:request_detail", args=[self.pr.pk])),
            "data-pr-existing-rfq",
        )
        self.assertNotContains(
            self.client.get(reverse("procurement:order_detail", args=[orders[0].pk])),
            "data-po-existing-grn",
        )

    def test_no_award_has_history_and_no_downstream_continuation(self):
        self.begin()
        self.open_quotes_and_compare()
        award = self.award(no_award=True)
        self.assertEqual(award.outcome, "no_award")
        self.assertFalse(award.allocations.exists())
        self.login(self.owner)
        page = self.client.get(
            reverse("procurement:rfq_buyer_workspace", args=[self.rfq.pk])
        )
        self.assertNotContains(page, "data-award-po")
        self.assertFalse(m.PurchaseOrder.objects.exists())
        self.assertFalse(m.GoodsReceipt.objects.exists())
        self.assertFalse(StockTransaction.objects.exists())
        self.financial_checkpoint("no-award-no-downstream")
        (self.evidence_root / "no-award.json").write_text(
            json.dumps(
                {
                    "outcome": award.outcome,
                    "history_retained": True,
                    "downstream_counts": [0, 0, 0],
                    "financial_checkpoints": self.financial_checkpoints,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

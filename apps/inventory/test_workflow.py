from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.inventory.models import (
    StockTransaction,
    StockTransactionStatus,
    StockTransactionType,
)
from apps.inventory.services import (
    create_stock_transaction,
    post_stock_transaction,
    reverse_stock_transaction,
)
from apps.inventory.tests import InventoryFixtureMixin
from apps.inventory.workflow import (
    POSTING_WORKFLOW_TYPE,
    backfill_open_stock_transaction_workflows,
    request_stock_transaction_posting,
    request_stock_transaction_reversal,
    stock_transaction_shadow_comparison,
)
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.organizations.services import set_active_organization
from apps.workflows.models import (
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkItemStatus,
)


class StockTransactionWorkflowTests(InventoryFixtureMixin, TestCase):
    def _draft(self, number: str = "W56-DRAFT") -> StockTransaction:
        return create_stock_transaction(
            organization=self.organization,
            actor=self.member,
            transaction_number=number,
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            destination_warehouse=self.central,
            material=self.material,
            unit_of_measure=self.unit,
            quantity=Decimal("3.0000"),
            occurred_at=timezone.now(),
        )

    def test_explicit_posting_request_uses_workbench_and_keeps_direct_legacy_path(
        self,
    ) -> None:
        direct = self._draft("W56-DIRECT")
        direct = post_stock_transaction(
            organization=self.organization, actor=self.member, stock_transaction=direct
        )
        self.assertEqual(direct.status, StockTransactionStatus.POSTED)
        self.assertFalse(WorkflowInstance.objects.filter(subject_id=direct.pk).exists())

        draft = self._draft("W56-REQUEST")
        instance = request_stock_transaction_posting(
            organization=self.organization, actor=self.owner, stock_transaction=draft
        )
        item = instance.work_items.get()
        self.assertEqual(item.status, WorkItemStatus.OPEN)
        self.assertFalse(
            stock_transaction_shadow_comparison(
                organization=self.organization,
                stock_transaction=draft,
                workflow_type=POSTING_WORKFLOW_TYPE,
            )["mismatch"]
        )
        self.client.force_login(self.owner)
        set_active_organization(self.client.session, self.organization)
        self.client.session.save()
        self.assertContains(
            self.client.get(reverse("workflows:workbench")), draft.transaction_number
        )

        posted = post_stock_transaction(
            organization=self.organization, actor=self.owner, stock_transaction=draft
        )
        self.assertEqual(posted.status, StockTransactionStatus.POSTED)
        self.assertEqual(
            WorkflowInstance.objects.get(pk=instance.pk).status,
            WorkflowInstanceStatus.COMPLETED,
        )

    def test_drafts_are_not_backfilled_and_candidacy_and_tenant_scope_are_rechecked(
        self,
    ) -> None:
        draft = self._draft("W56-NO-BACKFILL")
        report = backfill_open_stock_transaction_workflows(
            organization=self.organization
        )
        self.assertEqual((report.scanned, report.created, report.existing), (0, 0, 0))
        self.assertFalse(WorkflowInstance.objects.filter(subject_id=draft.pk).exists())

        instance = request_stock_transaction_posting(
            organization=self.organization, actor=self.owner, stock_transaction=draft
        )
        instance.work_items.get().candidates.filter(membership__user=self.owner).update(
            is_active=False
        )
        with self.assertRaises(PermissionDenied):
            post_stock_transaction(
                organization=self.organization,
                actor=self.owner,
                stock_transaction=draft,
            )
        with self.assertRaises(PermissionDenied):
            request_stock_transaction_posting(
                organization=self.organization,
                actor=self.owner,
                stock_transaction=StockTransaction.objects.create(
                    organization=self.other_organization,
                    transaction_number="W56-OTHER",
                    transaction_type=StockTransactionType.ADJUSTMENT_IN,
                    destination_warehouse=self.other_warehouse,
                    project=self.other_project,
                    material=self.other_material,
                    unit_of_measure=self.other_unit,
                    quantity=Decimal("1.0000"),
                    occurred_at=timezone.now(),
                ),
            )
        self.assertEqual(
            backfill_open_stock_transaction_workflows(
                organization=self.organization
            ).existing,
            1,
        )

    def test_reversal_workflow_preserves_immutable_equal_and_opposite_reversal(
        self,
    ) -> None:
        original = self.create_and_post(
            number="W56-REV-ORIGINAL",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal("4.0000"),
            destination=self.central,
        )
        instance = request_stock_transaction_reversal(
            organization=self.organization, actor=self.owner, stock_transaction=original
        )
        reversal = reverse_stock_transaction(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=original,
            reversal_number="W56-REVERSAL",
            reason="Workflow correction",
        )
        original.refresh_from_db()
        self.assertEqual(original.status, StockTransactionStatus.REVERSED)
        self.assertEqual(reversal.reversal_of_id, original.pk)
        self.assertEqual(reversal.status, StockTransactionStatus.POSTED)
        self.assertEqual(
            WorkflowInstance.objects.get(pk=instance.pk).status,
            WorkflowInstanceStatus.COMPLETED,
        )

    def test_goods_receipt_stock_movement_is_outside_w56_assignment_scope(self) -> None:
        receipt, item = self.create_posted_goods_receipt()
        draft = create_stock_transaction(
            organization=self.organization,
            actor=self.member,
            transaction_number="W56-RECEIPT",
            transaction_type=StockTransactionType.RECEIPT,
            destination_warehouse=self.site,
            project=self.project,
            goods_receipt_item=item,
            material=self.material,
            unit_of_measure=self.unit,
            quantity=item.quantity,
            occurred_at=timezone.now(),
        )
        with self.assertRaises(ValueError):
            request_stock_transaction_posting(
                organization=self.organization,
                actor=self.owner,
                stock_transaction=draft,
            )
        posted = post_stock_transaction(
            organization=self.organization, actor=self.member, stock_transaction=draft
        )
        self.assertEqual(posted.status, StockTransactionStatus.POSTED)
        self.assertEqual(receipt.status, "posted")


class StockTransactionWorkflowConcurrencyTests(TransactionTestCase):
    serialized_rollback = True

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        for alias in cls._databases_names(include_mirrors=False):
            db_connection = connections[alias]
            serialized = getattr(db_connection, "_test_serialized_contents", None)
            if serialized:
                db_connection.creation.deserialize_db_from_string(serialized)

    def test_competing_assigned_posting_commits_once(self) -> None:
        owner = User.objects.create_user(username="w56-owner")
        manager = User.objects.create_user(username="w56-manager")
        organization = Organization.objects.create(name="W56", slug="w56")
        for user, role in (
            (owner, MembershipRole.COMPANY_OWNER),
            (manager, MembershipRole.COMPANY_MANAGER),
        ):
            organization.memberships.create(
                user=user, role=role, status=MembershipStatus.ACTIVE
            )
        from apps.inventory.services import create_warehouse
        from apps.materials.models import Material, UnitCategory, UnitOfMeasure

        unit = UnitOfMeasure.objects.create(
            organization=organization,
            code="W56-KG",
            name="W56 kilogram",
            symbol="kg",
            category=UnitCategory.WEIGHT,
            decimal_places=4,
        )
        material = Material.objects.create(
            organization=organization,
            code="W56-MAT",
            name="W56 material",
            unit_of_measure=unit,
        )
        warehouse = create_warehouse(
            organization=organization, actor=owner, code="W56", name="W56 warehouse"
        )
        draft = create_stock_transaction(
            organization=organization,
            actor=owner,
            transaction_number="W56-RACE",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            destination_warehouse=warehouse,
            material=material,
            unit_of_measure=unit,
            quantity=Decimal("1.0000"),
            occurred_at=timezone.now(),
        )
        request_stock_transaction_posting(
            organization=organization, actor=owner, stock_transaction=draft
        )
        barrier = Barrier(2)

        def post(actor: User) -> str:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                post_stock_transaction(
                    organization=Organization.objects.get(pk=organization.pk),
                    actor=User.objects.get(pk=actor.pk),
                    stock_transaction=StockTransaction.objects.get(pk=draft.pk),
                )
                return "posted"
            except (PermissionDenied, ValidationError, ValueError):
                return "rejected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(post, (owner, manager)))
        self.assertEqual(outcomes.count("posted"), 1)
        self.assertEqual(
            StockTransaction.objects.get(pk=draft.pk).status,
            StockTransactionStatus.POSTED,
        )

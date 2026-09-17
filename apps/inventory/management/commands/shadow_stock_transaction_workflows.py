from argparse import ArgumentParser

from django.core.management.base import BaseCommand

from apps.inventory.models import StockTransaction, StockTransactionStatus
from apps.inventory.workflow import (
    POSTING_WORKFLOW_TYPE,
    REVERSAL_WORKFLOW_TYPE,
    stock_transaction_shadow_comparison,
)
from apps.workflows.models import WorkflowInstance, WorkflowInstanceStatus


class Command(BaseCommand):
    help = "Compare active W5.6 inventory workflow candidates with legacy permissions."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--organization", help="Limit to one organization UUID.")

    def handle(self, *args: object, **options: object) -> None:
        del args
        instances = WorkflowInstance.objects.filter(
            subject_type="inventory.stock_transaction",
            status=WorkflowInstanceStatus.ACTIVE,
            definition__workflow_type__code__in=(
                POSTING_WORKFLOW_TYPE,
                REVERSAL_WORKFLOW_TYPE,
            ),
        )
        if options["organization"]:
            instances = instances.filter(organization_id=options["organization"])
        scanned = mismatches = 0
        for instance in instances.select_related(
            "organization", "definition__workflow_type"
        ).iterator():
            expected_status = (
                StockTransactionStatus.DRAFT
                if instance.definition.workflow_type.code == POSTING_WORKFLOW_TYPE
                else StockTransactionStatus.POSTED
            )
            transaction_record = StockTransaction.objects.filter(
                pk=instance.subject_id,
                organization=instance.organization,
                status=expected_status,
            ).first()
            if transaction_record is None:
                continue
            scanned += 1
            result = stock_transaction_shadow_comparison(
                organization=instance.organization,
                stock_transaction=transaction_record,
                workflow_type=instance.definition.workflow_type.code,
            )
            mismatches += int(result["mismatch"])
        self.stdout.write(f"scanned={scanned} mismatches={mismatches}")

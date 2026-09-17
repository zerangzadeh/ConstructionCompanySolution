from argparse import ArgumentParser

from django.core.management.base import BaseCommand

from apps.contracts.models import ContractAmendment
from apps.contracts.workflow import contract_amendment_shadow_comparison
from apps.workflows.models import WorkflowInstance, WorkflowInstanceStatus


class Command(BaseCommand):
    help = "Compare active contract-amendment candidates with legacy approvers."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--organization", help="Limit to one organization UUID.")

    def handle(self, *args: object, **options: object) -> None:
        del args
        instances = WorkflowInstance.objects.filter(
            subject_type="contracts.contract_amendment",
            status=WorkflowInstanceStatus.ACTIVE,
        )
        if options["organization"]:
            instances = instances.filter(organization_id=options["organization"])
        scanned = mismatches = 0
        for instance in instances.select_related("organization").iterator():
            amendment = ContractAmendment.objects.filter(
                pk=instance.subject_id, organization=instance.organization
            ).first()
            if amendment is None:
                continue
            scanned += 1
            result = contract_amendment_shadow_comparison(
                organization=instance.organization, amendment=amendment
            )
            mismatches += int(result["mismatch"])
        self.stdout.write(f"scanned={scanned} mismatches={mismatches}")

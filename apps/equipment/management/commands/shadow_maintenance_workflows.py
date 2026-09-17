from argparse import ArgumentParser

from django.core.management.base import BaseCommand

from apps.equipment.models import MaintenanceRecord, MaintenanceStatus
from apps.equipment.workflow import maintenance_shadow_comparison
from apps.workflows.models import WorkflowInstance, WorkflowInstanceStatus


class Command(BaseCommand):
    help = "Compare open W5.7 maintenance candidates with legacy permissions."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--organization", help="Limit to one organization UUID.")

    def handle(self, *args: object, **options: object) -> None:
        del args
        instances = WorkflowInstance.objects.filter(
            subject_type="equipment.maintenance_record",
            status=WorkflowInstanceStatus.ACTIVE,
            definition__workflow_type__code="equipment.maintenance_record_lifecycle",
        )
        if options["organization"]:
            instances = instances.filter(organization_id=options["organization"])
        scanned = mismatches = 0
        for instance in instances.select_related("organization").iterator():
            record = MaintenanceRecord.objects.filter(
                pk=instance.subject_id,
                organization=instance.organization,
                status__in=(MaintenanceStatus.SCHEDULED, MaintenanceStatus.IN_PROGRESS),
            ).first()
            if record is None:
                continue
            scanned += 1
            mismatches += int(
                maintenance_shadow_comparison(
                    organization=instance.organization, record=record
                )["mismatch"]
            )
        self.stdout.write(f"scanned={scanned} mismatches={mismatches}")

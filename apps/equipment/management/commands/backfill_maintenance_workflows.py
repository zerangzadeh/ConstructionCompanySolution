from argparse import ArgumentParser

from django.core.management.base import BaseCommand

from apps.equipment.workflow import backfill_open_maintenance_workflows
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = "Backfill only open W5.7 equipment maintenance workflows."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--organization", help="Limit to one organization UUID.")

    def handle(self, *args: object, **options: object) -> None:
        del args
        organization = (
            Organization.objects.get(pk=options["organization"])
            if options["organization"]
            else None
        )
        report = backfill_open_maintenance_workflows(organization=organization)
        self.stdout.write(
            self.style.SUCCESS(
                f"scanned={report.scanned} created={report.created} "
                f"existing={report.existing} skipped={report.skipped}"
            )
        )

from argparse import ArgumentParser

from django.core.management.base import BaseCommand

from apps.organizations.models import Organization
from apps.safety.workflow import backfill_open_safety_incidents


class Command(BaseCommand):
    help = "Backfill open safety incidents into the shared workflow runtime."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--organization", help="Limit to one organization UUID.")

    def handle(self, *args: object, **options: object) -> None:
        del args
        organization = None
        if options["organization"]:
            organization = Organization.objects.get(pk=options["organization"])
        report = backfill_open_safety_incidents(organization=organization)
        self.stdout.write(
            f"scanned={report.scanned} created={report.created} "
            f"existing={report.existing} skipped={report.skipped}"
        )

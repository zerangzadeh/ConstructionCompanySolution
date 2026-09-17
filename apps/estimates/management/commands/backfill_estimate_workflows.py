from argparse import ArgumentParser

from django.core.management.base import BaseCommand

from apps.estimates.workflow import backfill_open_estimate_approvals
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = "Reconcile explicitly pending estimate approvals in the shared workflow runtime."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--organization", help="Limit to one organization UUID.")

    def handle(self, *args: object, **options: object) -> None:
        del args
        organization = (
            Organization.objects.get(pk=options["organization"])
            if options["organization"]
            else None
        )
        report = backfill_open_estimate_approvals(organization=organization)
        self.stdout.write(
            f"scanned={report.scanned} created={report.created} existing={report.existing} skipped={report.skipped}"
        )

from django.core.management.base import BaseCommand

from apps.procurement.workflow import backfill_submitted_purchase_requests


class Command(BaseCommand):
    help = "Idempotently backfill workflow runtime for submitted purchase requests."

    def handle(self, *args: object, **options: object) -> None:
        del args, options
        report = backfill_submitted_purchase_requests()
        self.stdout.write(
            self.style.SUCCESS(
                f"scanned={report.scanned} created={report.created} "
                f"existing={report.existing} skipped={report.skipped}"
            )
        )

import json

from django.core.management.base import BaseCommand, CommandError

from apps.procurement.models import PurchaseRequest
from apps.procurement.workflow import purchase_request_shadow_comparison


class Command(BaseCommand):
    help = (
        "Report legacy/workflow candidate mismatches for submitted purchase requests."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--organization", required=True)

    def handle(self, *args: object, **options: object) -> None:
        del args
        requests = PurchaseRequest.objects.filter(
            organization_id=options["organization"], status="submitted"
        ).select_related("organization")
        if not requests.exists():
            raise CommandError(
                "No submitted purchase requests found for the organization."
            )
        mismatches = 0
        for purchase_request in requests.iterator():
            result = purchase_request_shadow_comparison(
                organization=purchase_request.organization,
                purchase_request=purchase_request,
            )
            mismatches += int(result["mismatch"])
            self.stdout.write(json.dumps(result, sort_keys=True))
        self.stdout.write(f"mismatches={mismatches} scanned={requests.count()}")

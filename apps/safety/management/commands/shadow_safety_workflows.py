from argparse import ArgumentParser

from django.core.management.base import BaseCommand

from apps.safety.models import SafetyIncident, SafetyIncidentStatus
from apps.safety.workflow import safety_shadow_comparison


class Command(BaseCommand):
    help = "Compare legacy safety eligibility with workflow candidates."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--organization", help="Limit to one organization UUID.")

    def handle(self, *args: object, **options: object) -> None:
        del args
        incidents = SafetyIncident.objects.exclude(status=SafetyIncidentStatus.CLOSED)
        if options["organization"]:
            incidents = incidents.filter(organization_id=options["organization"])
        scanned = mismatches = 0
        for incident in incidents.select_related("organization").iterator():
            scanned += 1
            result = safety_shadow_comparison(
                organization=incident.organization, incident=incident
            )
            mismatches += int(result["mismatch"])
            if result["mismatch"]:
                self.stdout.write(
                    f"organization={incident.organization_id} incident={incident.pk} "
                    f"missing={len(result['missing_membership_ids'])} "
                    f"unexpected={len(result['unexpected_membership_ids'])} "
                    "blocked_runtime_permissions="
                    f"{len(result['blocked_runtime_permission_membership_ids'])}"
                )
        self.stdout.write(f"scanned={scanned} mismatches={mismatches}")

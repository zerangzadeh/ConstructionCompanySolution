from argparse import ArgumentParser

from django.core.management.base import BaseCommand

from apps.quality.models import QualityIssue, QualityIssueStatus
from apps.quality.workflow import quality_shadow_comparison


class Command(BaseCommand):
    help = "Compare legacy quality eligibility with workflow candidates."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--organization", help="Limit to one organization UUID.")

    def handle(self, *args: object, **options: object) -> None:
        del args
        issues = QualityIssue.objects.exclude(status=QualityIssueStatus.CLOSED)
        if options["organization"]:
            issues = issues.filter(organization_id=options["organization"])
        scanned = mismatches = 0
        for issue in issues.select_related("organization").iterator():
            scanned += 1
            result = quality_shadow_comparison(
                organization=issue.organization, issue=issue
            )
            mismatches += int(result["mismatch"])
            if result["mismatch"]:
                self.stdout.write(
                    f"organization={issue.organization_id} issue={issue.pk} "
                    f"missing={len(result['missing_membership_ids'])} "
                    f"unexpected={len(result['unexpected_membership_ids'])} "
                    "blocked_runtime_permissions="
                    f"{len(result['blocked_runtime_permission_membership_ids'])}"
                )
        self.stdout.write(f"scanned={scanned} mismatches={mismatches}")

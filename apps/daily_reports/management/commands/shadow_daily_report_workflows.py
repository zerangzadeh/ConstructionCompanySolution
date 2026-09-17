from argparse import ArgumentParser

from django.core.management.base import BaseCommand
from django.db.models import F

from apps.daily_reports.models import DailyReport, DailyReportStatus
from apps.daily_reports.workflow import daily_report_shadow_comparison


class Command(BaseCommand):
    help = "Compare legacy approval eligibility with daily-report workflow candidates."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--organization", help="Limit to one organization UUID.")

    def handle(self, *args: object, **options: object) -> None:
        del args
        scanned = mismatches = 0
        reports = DailyReport.objects.filter(
            status=DailyReportStatus.SUBMITTED,
            project__deleted_at__isnull=True,
            site__is_active=True,
            project__organization_id=F("organization_id"),
            site__organization_id=F("organization_id"),
            site__project_id=F("project_id"),
        )
        if options["organization"]:
            reports = reports.filter(organization_id=options["organization"])
        for report in reports.select_related("organization").iterator():
            scanned += 1
            result = daily_report_shadow_comparison(
                organization=report.organization, report=report
            )
            mismatches += int(result["mismatch"])
            if result["mismatch"]:
                self.stdout.write(
                    f"organization={report.organization_id} report={report.pk} "
                    f"missing={len(result['missing_membership_ids'])} "
                    f"unexpected={len(result['unexpected_membership_ids'])} "
                    "blocked_runtime_permissions="
                    f"{len(result['blocked_runtime_permission_membership_ids'])}"
                )
        self.stdout.write(f"scanned={scanned} mismatches={mismatches}")

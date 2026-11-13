"""Publish the Return-capable version for an existing compatibility definition."""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.daily_reports.return_workflow import publish_return_workflow
from apps.organizations.models import Organization
from apps.workflows.models import WorkflowVersion
from apps.workflows.runtime import WorkflowConflict


class Command(BaseCommand):
    help = "Supersede one tenant's legacy Daily Report workflow under existing publication authority."

    def add_arguments(self, parser):
        parser.add_argument("--organization", required=True)
        parser.add_argument("--actor", required=True)
        parser.add_argument("--reason", required=True)

    def handle(self, *args, **options):
        user_model = get_user_model()
        try:
            organization = Organization.objects.get(slug=options["organization"])
            actor = user_model.objects.get(username=options["actor"])
            version = publish_return_workflow(organization=organization, actor=actor, reason=options["reason"])
        except (Organization.DoesNotExist, user_model.DoesNotExist, WorkflowVersion.DoesNotExist,
                PermissionDenied, ValidationError, WorkflowConflict) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Published Daily Report workflow version {version.version_number}."))

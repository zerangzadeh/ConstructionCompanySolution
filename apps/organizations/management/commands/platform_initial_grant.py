"""Trusted operator entry point; all authority checks remain in the service."""

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationRole
from apps.organizations.platform_grants import platform_initial_grant
from apps.projects.models import Project, ProjectSite


class Command(BaseCommand):
    help = (
        "Perform one audited Platform Initial Grant using an existing Platform Admin."
    )

    def add_arguments(self, parser):
        for name in ("actor", "organization", "membership", "role", "scope", "reason"):
            parser.add_argument(f"--{name}", required=True)
        parser.add_argument("--project")
        parser.add_argument("--site")

    def handle(self, *args, **options):
        try:
            assignment, scope = platform_initial_grant(
                actor=User.objects.get(username=options["actor"]),
                organization=Organization.objects.get(pk=options["organization"]),
                membership_id=options["membership"],
                role=OrganizationRole.objects.get(pk=options["role"]),
                scope_type=options["scope"],
                reason=options["reason"],
                project=Project.objects.get(pk=options["project"])
                if options["project"]
                else None,
                site=ProjectSite.objects.get(pk=options["site"])
                if options["site"]
                else None,
            )
        except (
            ObjectDoesNotExist,
            PermissionDenied,
            ValidationError,
            ValueError,
        ) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Initial Grant: assignment={assignment.pk} scope={scope.pk}")

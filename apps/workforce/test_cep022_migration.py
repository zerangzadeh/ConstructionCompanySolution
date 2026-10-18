from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.organizations.models import BusinessPermission, OrganizationRole
from apps.timekeeping.models import RosterSlot, RosterVersion

from . import test_cep022 as fixtures
from .models import (
    EmploymentRecord,
    OffboardingCase,
    OffboardingReview,
    Person,
    WorkRelationship,
)


class EmploymentMigrationTests(TransactionTestCase):
    serialized_rollback = True

    def test_expand_rollback_reapply_preserves_identity_documents_and_grants(self):
        fixture = fixtures.EmploymentTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        sources = [
            Person,
            WorkRelationship,
            fixture.document.__class__,
            fixture.document.current_version.__class__,
        ]
        before = {
            m._meta.label: list(m.objects.order_by("pk").values()) for m in sources
        }
        codes = [
            "employment_records.manage",
            "employment_records.view_own",
            "offboarding.start",
            "offboarding.view",
            "offboarding.review",
            "rosters.manage",
            "rosters.view",
        ]
        OrganizationRole.permissions.through.objects.filter(
            businesspermission__code__in=codes
        ).delete()
        grants_before = list(
            OrganizationRole.permissions.through.objects.order_by("pk").values()
        )
        previous = [
            ("workforce", "0012_cep056_certificate_framework"),
            ("timekeeping", "0002_attendancecorrectionrequest"),
            ("organizations", "0114_cep036_indexation_permissions"),
        ]
        current = [
            ("workforce", "0013_cep022_employment_lifecycle"),
            ("timekeeping", "0003_cep022_employment_lifecycle"),
            ("organizations", "0115_cep022_employment_permissions"),
        ]
        try:
            MigrationExecutor(connection).migrate(previous)
            self.assertFalse(
                BusinessPermission.objects.filter(
                    code__in=codes, is_active=True
                ).exists()
            )
            self.assertEqual(
                {
                    m._meta.label: list(m.objects.order_by("pk").values())
                    for m in sources
                },
                before,
            )
            MigrationExecutor(connection).migrate(current)
            self.assertEqual(
                {
                    m._meta.label: list(m.objects.order_by("pk").values())
                    for m in sources
                },
                before,
            )
            self.assertEqual(
                list(
                    OrganizationRole.permissions.through.objects.order_by("pk").values()
                ),
                grants_before,
            )
            self.assertEqual(
                BusinessPermission.objects.filter(
                    code__in=codes, is_active=True
                ).count(),
                len(codes),
            )
            for model in (
                EmploymentRecord,
                OffboardingCase,
                OffboardingReview,
                RosterVersion,
                RosterSlot,
            ):
                self.assertEqual(model.objects.count(), 0)
        finally:
            MigrationExecutor(connection).migrate(current)

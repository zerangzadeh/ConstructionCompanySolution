from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db import models
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import (
    BusinessPermission,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import create_organization_with_owner
from apps.projects.models import Project, ProjectSite
from apps.quality import workflow as quality_workflow
from apps.quality.models import QualityIssue
from apps.quality.services import create_quality_issue, review_quality_issue
from apps.quality.workflow import load_quality_subject
from apps.safety import workflow as safety_workflow
from apps.safety.models import SafetyIncident
from apps.safety.services import create_safety_incident, review_safety_incident
from apps.safety.workflow import load_safety_subject
from apps.workflows.models import WorkflowInstance, WorkflowTemplate, WorkflowType


class HseWorkflowScopeTests(TestCase):
    def setUp(self):
        # Retained test databases may have been flushed after historical data
        # migrations. Restore only the exact code-owned compatibility templates.
        for module in (safety_workflow, quality_workflow):
            WorkflowTemplate.objects.get_or_create(
                workflow_type=WorkflowType.objects.get(code=module.WORKFLOW_TYPE_CODE),
                code=module.TEMPLATE_CODE,
                defaults={
                    "name": module.TEMPLATE_CODE,
                    "configuration": module.COMPATIBILITY_CONFIGURATION,
                },
            )
        owner = User.objects.create_user(username="hse-scope-owner")
        self.org = create_organization_with_owner(
            owner=owner, name="HSE", slug="hse-scope"
        )
        other = User.objects.create_user(username="hse-other-owner")
        self.foreign = create_organization_with_owner(
            owner=other, name="Other", slug="hse-other"
        )
        self.user = User.objects.create_user(username="hse-scoped-maker")
        self.role = OrganizationRole.objects.create(
            organization=self.org, code="hse", name="HSE"
        )
        self.role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=[
                    "safety_incidents.create",
                    "safety_incidents.view",
                    "quality_issues.create",
                    "quality_issues.view",
                ]
            )
        )
        self.membership = OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            status="active",
            role_definition=self.role,
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=self.org,
            membership=self.membership,
            role=self.role,
            reason="Explicit test role",
        )
        self.project = Project.objects.create(organization=self.org, code="A", name="A")
        self.denied = Project.objects.create(organization=self.org, code="B", name="B")
        self.other = Project.objects.create(
            organization=self.foreign, code="C", name="C"
        )
        self.site = ProjectSite.objects.create(
            organization=self.org, project=self.project, code="A", name="A"
        )
        self.sibling = ProjectSite.objects.create(
            organization=self.org, project=self.project, code="S", name="S"
        )
        self.grant = MembershipScopeGrant.objects.create(
            organization=self.org,
            membership=self.membership,
            scope_type="project",
            project=self.project,
            reason="Only A",
        )
        self.when = timezone.now() - timedelta(days=1)

    def sources(self, project=None, site=None):
        project = project or self.project
        maker = (
            self.user
            if project.organization_id == self.org.pk
            else project.organization.created_by
        )
        common = {
            "organization": project.organization,
            "project": project,
            "site": site,
            "description": "Synthetic",
            "created_by": maker,
            "updated_by": maker,
        }
        return [
            (
                load_safety_subject,
                SafetyIncident.objects.create(
                    **common,
                    incident_number=f"SAF-{project.code}",
                    occurred_at=self.when,
                    incident_type="near_miss",
                    severity="low",
                ),
            ),
            (
                load_quality_subject,
                QualityIssue.objects.create(
                    **common,
                    issue_number=f"QUA-{project.code}",
                    identified_at=self.when,
                    issue_type="other",
                    severity="minor",
                ),
            ),
        ]

    def load(self, loader, source):
        return loader(
            organization=self.org,
            actor=self.user,
            subject_id=source.pk,
            for_update=False,
        )

    def test_granted_project_subjects_load(self):
        for loader, source in self.sources(site=self.site):
            with self.subTest(model=source._meta.label):
                self.assertEqual(self.load(loader, source).subject.pk, source.pk)

    def test_scoped_public_creation_starts_atomic_workflow(self):
        common = {
            "organization": self.org,
            "actor": self.user,
            "project": self.project,
            "site": self.site,
            "description": "Synthetic",
        }
        for create, fields in [
            (
                create_safety_incident,
                {
                    "incident_number": "NEW-SAF",
                    "occurred_at": self.when,
                    "incident_type": "near_miss",
                    "severity": "low",
                },
            ),
            (
                create_quality_issue,
                {
                    "issue_number": "NEW-QUA",
                    "identified_at": self.when,
                    "issue_type": "other",
                    "severity": "minor",
                },
            ),
        ]:
            with self.subTest(service=create.__name__):
                source = create(**common, **fields)
                self.assertEqual(
                    WorkflowInstance.objects.filter(
                        organization=self.org, subject_id=source.pk
                    ).count(),
                    1,
                )

    def test_scoped_public_lifecycle_action(self):
        self.role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=[
                    "safety_incidents.review",
                    "quality_issues.review",
                    "work_items.view",
                    "work_items.claim",
                    "work_items.act",
                ]
            )
        )
        for create, review, fields, key in [
            (
                create_safety_incident,
                review_safety_incident,
                {
                    "incident_number": "ACTION-SAF",
                    "occurred_at": self.when,
                    "incident_type": "near_miss",
                    "severity": "low",
                },
                "incident_id",
            ),
            (
                create_quality_issue,
                review_quality_issue,
                {
                    "issue_number": "ACTION-QUA",
                    "identified_at": self.when,
                    "issue_type": "other",
                    "severity": "minor",
                },
                "issue_id",
            ),
        ]:
            with self.subTest(service=review.__name__):
                source = create(
                    organization=self.org,
                    actor=self.user,
                    project=self.project,
                    site=self.site,
                    description="Synthetic",
                    **fields,
                )
                source = review(
                    organization=self.org, actor=self.user, **{key: source.pk}
                )
                self.assertEqual(source.status, "under_review")

    def test_ungranted_and_foreign_subjects_denied(self):
        for project in (self.denied, self.other):
            for loader, source in self.sources(project=project):
                with (
                    self.subTest(model=source._meta.label, project=project.code),
                    self.assertRaises(PermissionDenied),
                ):
                    self.load(loader, source)

    def test_missing_permission_and_inactive_membership_denied(self):
        sources = self.sources(site=self.site)
        self.role.permissions.clear()
        for loader, source in sources:
            with self.assertRaises(PermissionDenied):
                self.load(loader, source)
        self.role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=[
                    "safety_incidents.view",
                    "quality_issues.view",
                ]
            )
        )
        self.membership.status = "suspended"
        self.membership.save(update_fields=["status"])
        for loader, source in sources:
            with self.assertRaises(PermissionDenied):
                self.load(loader, source)

    def test_inconsistent_project_site_context_denied(self):
        bad_site = ProjectSite.objects.create(
            organization=self.org, project=self.denied, code="BAD", name="Bad"
        )
        for loader, source in self.sources(site=self.site):
            # Intentional test-only database corruption exercises loader fail-closed checks.
            models.QuerySet.update(
                type(source).objects.filter(pk=source.pk), site=bad_site
            )
            with self.assertRaises(PermissionDenied):
                self.load(loader, source)

    def test_site_scope_does_not_expand_to_sibling(self):
        self.grant.revoked_at = timezone.now()
        self.grant.save(update_fields=["revoked_at"])
        MembershipScopeGrant.objects.create(
            organization=self.org,
            membership=self.membership,
            scope_type="site",
            project=self.project,
            site=self.site,
            reason="Exact site",
        )
        for loader, source in self.sources(site=self.site):
            with self.subTest(model=source._meta.label):
                self.assertEqual(self.load(loader, source).subject.pk, source.pk)
                models.QuerySet.update(
                    type(source).objects.filter(pk=source.pk), site=self.sibling
                )
                with self.assertRaises(PermissionDenied):
                    self.load(loader, source)

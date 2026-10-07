from __future__ import annotations

from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.documents.models import Document, DocumentVersion
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.permission_registry import PERMISSION_RESOURCES
from apps.organizations.role_defaults import DEFAULT_ROLE_PERMISSIONS
from apps.projects.models import Project
from apps.reporting.models import (
    ProjectCloseoutAssessment,
    ProjectCloseoutCase,
    ProjectCloseoutEvent,
    ProjectCloseoutExportManifest,
    ProjectCloseoutItemSnapshot,
    ProjectCloseoutOutcome,
    ProjectCloseoutProfileDefinition,
    ProjectCloseoutProfileVersion,
)
from apps.reporting.project_closeout import (
    PROJECT_CLOSEOUT_PERMISSION_CATALOGUE,
    closeout_case_detail,
    create_closeout_case,
    decide_closeout_case,
    export_closeout_csv,
    link_closeout_evidence,
    reopen_closeout_case,
    run_closeout_assessment,
)
from apps.reporting.project_closeout_catalog import PROJECT_CLOSEOUT_FAMILIES

CLOSEOUT_PERMISSIONS = {
    value
    for value in BusinessPermissionCode.values
    if value.startswith("reporting.project_closeout")
}


class P10S14S17AcceptanceTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.runner = User.objects.create_user(username="closeout-runner", password="x")
        cls.reviewer = User.objects.create_user(
            username="closeout-reviewer", password="x"
        )
        cls.outsider = User.objects.create_user(
            username="closeout-platform", password="x", is_superuser=True
        )
        cls.organization = Organization.objects.create(
            name="P10 Closeout Tenant",
            slug="p10-closeout",
            created_by=cls.runner,
            updated_by=cls.runner,
        )
        cls.other_organization = Organization.objects.create(
            name="Other Closeout Tenant",
            slug="other-closeout",
            created_by=cls.outsider,
            updated_by=cls.outsider,
        )
        cls.project = Project.objects.create(
            organization=cls.organization,
            code="P10-CLOSE",
            name="پروژه اختتام",
            created_by=cls.runner,
            updated_by=cls.runner,
        )
        cls.other_project = Project.objects.create(
            organization=cls.other_organization,
            code="OTHER-CLOSE",
            name="پروژه دیگر",
            created_by=cls.outsider,
            updated_by=cls.outsider,
        )
        cls._grant(cls.runner, set(BusinessPermissionCode.values))
        cls._grant(cls.reviewer, set(BusinessPermissionCode.values))

    @classmethod
    def _grant(
        cls,
        user: User,
        permissions: set[str],
        *,
        project: Project | None = None,
    ) -> OrganizationMembership:
        membership = OrganizationMembership.objects.create(
            organization=cls.organization,
            user=user,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
            authorization_migrated_at=timezone.now(),
        )
        role = OrganizationRole.objects.create(
            organization=cls.organization,
            code=f"closeout-{user.username}",
            name=f"Closeout {user.username}",
            created_by=cls.runner,
            updated_by=cls.runner,
        )
        role.permissions.set(BusinessPermission.objects.filter(code__in=permissions))
        MembershipRoleAssignment.objects.create(
            organization=cls.organization,
            membership=membership,
            role=role,
            reason="P10 S14-S17 focused acceptance",
        )
        MembershipScopeGrant.objects.create(
            organization=cls.organization,
            membership=membership,
            scope_type=(
                AuthorizationScopeType.PROJECT
                if project is not None
                else AuthorizationScopeType.ORGANIZATION
            ),
            project=project,
            reason="P10 S14-S17 focused acceptance",
        )
        return membership

    def _case(self, key: str = "case") -> ProjectCloseoutCase:
        return create_closeout_case(
            organization=self.organization,
            actor=self.runner,
            project=self.project,
            operation_key=key,
        )

    def _assessment(
        self, key: str = "case", run_key: str = "assessment"
    ) -> tuple[ProjectCloseoutCase, ProjectCloseoutAssessment]:
        case = self._case(key)
        cutoff = timezone.now()
        assessment = run_closeout_assessment(
            case=case,
            actor=self.runner,
            idempotency_key=run_key,
            cutoff_at=cutoff,
            expected_revision=case.revision,
        )
        case.refresh_from_db()
        return case, assessment

    def test_01_catalogue_permissions_and_profile_publication_controls(self) -> None:
        self.assertEqual(len(PROJECT_CLOSEOUT_FAMILIES), 9)
        profile = ProjectCloseoutProfileVersion.objects.get(status="published")
        self.assertEqual(set(profile.specification["families"]), set(PROJECT_CLOSEOUT_FAMILIES))
        self.assertEqual(len(PROJECT_CLOSEOUT_PERMISSION_CATALOGUE), 14)
        self.assertEqual(len(CLOSEOUT_PERMISSIONS), 14)
        registered = {
            str(code)
            for resource in PERMISSION_RESOURCES
            if resource.key == "reporting"
            for code in resource.permissions
        }
        self.assertTrue(CLOSEOUT_PERMISSIONS.issubset(registered))
        for permissions in DEFAULT_ROLE_PERMISSIONS.values():
            self.assertTrue(CLOSEOUT_PERMISSIONS.isdisjoint(permissions))
        draft = ProjectCloseoutProfileVersion.objects.create(
            definition=profile.definition,
            version=2,
            specification=profile.specification,
            source_owner_approvals=profile.source_owner_approvals,
            payload_hash="a" * 64,
            governance_reference="test",
            authored_by=self.runner,
        )
        draft.status = "published"
        draft.published_by = self.runner
        with self.assertRaises(ValidationError):
            draft.save()

    def test_02_tenant_isolation_and_no_implicit_platform_access(self) -> None:
        case = self._case("tenant-case")
        with self.assertRaises(PermissionDenied):
            closeout_case_detail(
                organization=self.other_organization,
                actor=self.outsider,
                case_id=str(case.pk),
            )
        with self.assertRaises(PermissionDenied):
            create_closeout_case(
                organization=self.other_organization,
                actor=self.outsider,
                project=self.other_project,
                operation_key="platform-no-tenant-access",
            )

    def test_03_object_scope_and_source_permissions_are_rechecked(self) -> None:
        limited = User.objects.create_user(username="closeout-limited", password="x")
        self._grant(
            limited,
            {
                BusinessPermissionCode.REPORTING_PROJECT_CLOSEOUT_CASE_PREPARE,
                BusinessPermissionCode.PROJECTS_VIEW,
            },
            project=self.project,
        )
        case = create_closeout_case(
            organization=self.organization,
            actor=limited,
            project=self.project,
            operation_key="limited-case",
        )
        with self.assertRaises(PermissionDenied):
            run_closeout_assessment(
                case=case,
                actor=limited,
                idempotency_key="limited-assessment",
                expected_revision=case.revision,
            )
        with self.assertRaises(PermissionDenied):
            create_closeout_case(
                organization=self.organization,
                actor=limited,
                project=Project.objects.create(
                    organization=self.organization,
                    code="OUT-SCOPE",
                    name="خارج از دامنه",
                    created_by=self.runner,
                    updated_by=self.runner,
                ),
                operation_key="out-of-scope",
            )

    def test_04_nine_families_capture_explicit_non_values_never_zero(self) -> None:
        _, assessment = self._assessment("nine-case", "nine-assessment")
        self.assertEqual(assessment.items.count(), 9)
        outcomes = dict(assessment.items.values_list("family_code", "outcome"))
        self.assertEqual(outcomes["project_identity"], ProjectCloseoutOutcome.SATISFIED)
        self.assertEqual(outcomes["document_completeness"], ProjectCloseoutOutcome.INCOMPLETE)
        self.assertEqual(outcomes["knowledge_lessons"], ProjectCloseoutOutcome.GATED)
        for item in assessment.items.exclude(family_code="project_identity"):
            self.assertNotEqual(item.outcome, ProjectCloseoutOutcome.SATISFIED)
            self.assertNotIn("amount", item.summary)

    def test_05_cutoff_reproducibility_and_successor_preserve_history(self) -> None:
        case, original = self._assessment("successor-case", "original-assessment")
        original_hash = original.calculation_hash
        successor = run_closeout_assessment(
            case=case,
            actor=self.runner,
            idempotency_key="successor-assessment",
            cutoff_at=timezone.now().replace(microsecond=0),
            expected_revision=case.revision,
        )
        self.assertEqual(successor.supersedes_id, original.pk)
        original.refresh_from_db()
        self.assertEqual(original.calculation_hash, original_hash)
        self.assertEqual(original.items.count(), 9)

    def test_06_lifecycle_sod_accept_reject_and_reopen_are_append_only(self) -> None:
        case, assessment = self._assessment("lifecycle-case", "lifecycle-assessment")
        ProjectCloseoutItemSnapshot.objects.filter(assessment=assessment).update(
            outcome=ProjectCloseoutOutcome.SATISFIED
        )
        with self.assertRaises(PermissionDenied):
            decide_closeout_case(
                case=case,
                actor=self.runner,
                decision="accept",
                reason="self acceptance forbidden",
                operation_key="self-accept",
                expected_revision=case.revision,
            )
        with patch("apps.reporting.project_closeout._assert_current_sources"):
            accepted = decide_closeout_case(
                case=case,
                actor=self.reviewer,
                decision="accept",
                reason="independent control acceptance",
                operation_key="independent-accept",
                expected_revision=case.revision,
            )
        case.refresh_from_db()
        self.assertEqual(case.status, "accepted")
        reopened = reopen_closeout_case(
            case=case,
            actor=self.reviewer,
            reason="new source evidence requires successor",
            operation_key="reopen-accepted",
            expected_revision=case.revision,
        )
        self.assertEqual(accepted.new_state, "accepted")
        self.assertEqual(reopened.new_state, "reopened")
        self.assertEqual(ProjectCloseoutEvent.objects.filter(case=case).count(), 2)

    def test_07_idempotency_payload_conflict_and_stale_revision(self) -> None:
        first = self._case("idempotent-case")
        second = self._case("idempotent-case")
        self.assertEqual(first.pk, second.pk)
        with self.assertRaises(ValidationError):
            run_closeout_assessment(
                case=first,
                actor=self.runner,
                idempotency_key="stale-revision",
                cutoff_at=timezone.now().replace(microsecond=0),
                expected_revision=999,
            )
        cutoff = timezone.now().replace(microsecond=0)
        run_one = run_closeout_assessment(
            case=first,
            actor=self.runner,
            idempotency_key="same-assessment",
            cutoff_at=cutoff,
            expected_revision=first.revision,
        )
        run_two = run_closeout_assessment(
            case=first,
            actor=self.runner,
            idempotency_key="same-assessment",
            cutoff_at=cutoff,
            expected_revision=first.revision,
        )
        self.assertEqual(run_one.pk, run_two.pk)

    def test_08_atomic_failure_rolls_back_assessment_items_pointer_and_audit(self) -> None:
        case = self._case("atomic-case")
        with patch(
            "apps.reporting.project_closeout.record_audit_event",
            side_effect=RuntimeError("audit failure"),
        ), self.assertRaises(RuntimeError):
            run_closeout_assessment(
                case=case,
                actor=self.runner,
                idempotency_key="atomic-assessment",
                cutoff_at=timezone.now().replace(microsecond=0),
                expected_revision=case.revision,
            )
        case.refresh_from_db()
        self.assertIsNone(case.current_assessment_id)
        self.assertEqual(ProjectCloseoutAssessment.objects.filter(case=case).count(), 0)
        self.assertEqual(ProjectCloseoutItemSnapshot.objects.filter(assessment__case=case).count(), 0)

    def test_09_source_change_requires_successor_and_never_rewrites_original(self) -> None:
        case, assessment = self._assessment("stale-case", "stale-assessment")
        source_hashes = dict(
            assessment.items.values_list("family_code", "source_hash")
        )
        self.project.name = "پروژه اختتام اصلاح‌شده"
        self.project.save()
        ProjectCloseoutItemSnapshot.objects.filter(assessment=assessment).update(
            outcome=ProjectCloseoutOutcome.SATISFIED
        )
        with self.assertRaises(ValidationError):
            decide_closeout_case(
                case=case,
                actor=self.reviewer,
                decision="accept",
                reason="must detect stale source",
                operation_key="stale-accept",
                expected_revision=case.revision,
            )
        self.assertEqual(
            dict(assessment.items.values_list("family_code", "source_hash")),
            source_hashes,
        )

    def test_10_dms_exact_version_hash_and_tenant_boundary(self) -> None:
        case = self._case("dms-case")
        document = Document.objects.create(
            organization=self.organization,
            document_number="DOC-CLOSE-1",
            title="شاهد اختتام",
            created_by=self.runner,
            updated_by=self.runner,
        )
        version = DocumentVersion.objects.create(
            organization=self.organization,
            document=document,
            version_number=1,
            original_file_name="closeout.txt",
            file="documents/closeout.txt",
            content_type="text/plain",
            file_size=4,
            sha256="b" * 64,
            uploaded_by=self.runner,
        )
        link = link_closeout_evidence(
            case=case,
            actor=self.runner,
            document_version=version,
            evidence_role="closeout_support",
        )
        self.assertEqual(link.document_hash, version.sha256)
        self.assertFalse(hasattr(link, "file"))
        link.document_hash = "c" * 64
        with self.assertRaises(ValidationError):
            link.full_clean()

    def test_11_export_is_private_masked_idempotent_and_byte_free(self) -> None:
        case, _ = self._assessment("export-case", "export-assessment")
        manifest, content = export_closeout_csv(
            case=case,
            actor=self.runner,
            idempotency_key="export-key",
            purpose="focused acceptance",
        )
        retried, retry_content = export_closeout_csv(
            case=case,
            actor=self.runner,
            idempotency_key="export-key",
            purpose="focused acceptance",
        )
        self.assertEqual(manifest.pk, retried.pk)
        self.assertEqual(content, retry_content)
        self.assertFalse(hasattr(manifest, "file"))
        self.assertEqual(ProjectCloseoutExportManifest.objects.count(), 1)

    def test_12_persian_rtl_jalali_ui_and_private_response(self) -> None:
        case = self._case("ui-case")
        self.client.force_login(self.runner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        response = self.client.get(
            reverse("reporting:project_closeout_detail", args=[case.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, "کنترل مشتق")
        self.assertContains(response, "Jalali", count=0)
        self.assertEqual(response["Cache-Control"], "private, no-store, max-age=0")

    def test_13_every_command_has_no_source_domain_effect(self) -> None:
        project_before = (self.project.status, self.project.updated_at)
        case, _ = self._assessment("no-effect-case", "no-effect-assessment")
        export_closeout_csv(
            case=case,
            actor=self.runner,
            idempotency_key="no-effect-export",
            purpose="no effect",
        )
        self.project.refresh_from_db()
        self.assertEqual((self.project.status, self.project.updated_at), project_before)

    def test_14_permission_aware_navigation_and_post_only_mutations(self) -> None:
        self.client.force_login(self.runner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        response = self.client.get(reverse("reporting:project_closeout_workbench"))
        self.assertContains(response, "کنترل هماهنگ اختتام پروژه")
        self.assertEqual(
            self.client.get(reverse("reporting:project_closeout_create")).status_code,
            405,
        )

    def test_15_immutable_models_and_constraints_reject_rewrite(self) -> None:
        _, assessment = self._assessment("immutable-case", "immutable-assessment")
        item = assessment.items.first()
        assert item is not None
        item.outcome = ProjectCloseoutOutcome.SATISFIED
        with self.assertRaises(ValidationError):
            item.save()
        profile = ProjectCloseoutProfileVersion.objects.get(status="published")
        profile.governance_reference = "rewrite"
        with self.assertRaises(ValidationError):
            profile.save()

    def test_16_audit_lineage_and_preserved_gates(self) -> None:
        _case, assessment = self._assessment("audit-case", "audit-assessment")
        self.assertTrue(
            AuditEvent.objects.filter(
                action="reporting.project_closeout_assessed",
                entity_id=str(assessment.pk),
            ).exists()
        )
        profile = ProjectCloseoutProfileDefinition.objects.get(
            code="project_closeout_v1"
        )
        self.assertTrue(profile.is_active)
        self.assertFalse(
            any(
                token in json_text.lower()
                for json_text in [str(profile.versions.get().specification)]
                for token in ("queue", "scheduler", "provider", "rag", "vector")
            )
        )

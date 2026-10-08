from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.compliance.models import (
    CapaStatus,
    CapaType,
    ComplianceLifecycleEvent,
    ControlProfile,
    FindingStatus,
    InspectionStatus,
    NcrStatus,
    PermitStatus,
)
from apps.compliance.models import (
    TestStatus as ComplianceTestStatus,
)
from apps.compliance.services import (
    create_capa,
    create_downstream_proposal,
    create_finding,
    create_inspection,
    create_permit,
    create_template,
    create_test,
    enter_test_result,
    link_evidence,
    promote_finding_to_ncr,
    publish_template_version,
    transition_record,
)
from apps.documents.link_registry import typed_links_for_document
from apps.documents.models import DocumentType
from apps.documents.services import create_document, get_document_version_for_download
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationSettings,
)
from apps.organizations.services import set_active_organization
from apps.projects.models import Project, ProjectSite


class ComplianceP9S06S11Tests(TestCase):
    def setUp(self) -> None:
        self.storage_directory = TemporaryDirectory()
        self.storage_override = override_settings(
            DOCUMENT_PROTECTED_ROOT=self.storage_directory.name
        )
        self.storage_override.enable()
        self.addCleanup(self.storage_override.disable)
        self.addCleanup(self.storage_directory.cleanup)
        self.owner = User.objects.create_user(
            username="p9-compliance-owner", password="test-password"
        )
        self.reviewer = User.objects.create_user(
            username="p9-compliance-reviewer", password="test-password"
        )
        self.other = User.objects.create_user(
            username="p9-compliance-other", password="test-password"
        )
        self.organization = Organization.objects.create(
            name="P9 Compliance",
            slug="p9-compliance",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.other_organization = Organization.objects.create(
            name="Other P9 Compliance",
            slug="other-p9-compliance",
            created_by=self.other,
            updated_by=self.other,
        )
        OrganizationSettings.objects.create(organization=self.organization)
        OrganizationSettings.objects.create(organization=self.other_organization)
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.organization.memberships.create(
            user=self.reviewer,
            role=MembershipRole.COMPANY_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_organization.memberships.create(
            user=self.other,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = Project.objects.create(
            organization=self.organization, code="P9-C", name="Compliance project"
        )
        self.site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="MAIN",
            name="Main site",
        )
        self.other_project = Project.objects.create(
            organization=self.other_organization, code="P9-O", name="Other project"
        )
        self.hse_template = create_template(
            organization=self.organization,
            actor=self.owner,
            profile=ControlProfile.HSE,
            code="HSE-CHK",
            title="بازرسی ایمنی",
        )
        self.hse_version = publish_template_version(
            organization=self.organization,
            actor=self.owner,
            template_id=str(self.hse_template.pk),
            checklist=[{"id": "ppe", "required": True, "type": "pass_fail"}],
            required_evidence=[{"purpose": "execution", "minimum": 1}],
            outcome_rules={"failed_item": "failed"},
            source_references=[
                {"source": "tenant-approved-hse-policy", "version": "1"}
            ],
        )
        self.qa_template = create_template(
            organization=self.organization,
            actor=self.owner,
            profile=ControlProfile.QA_QC,
            code="QA-CHK",
            title="بازرسی کیفیت",
        )
        self.qa_version = publish_template_version(
            organization=self.organization,
            actor=self.owner,
            template_id=str(self.qa_template.pk),
            checklist=[{"id": "dimension", "required": True, "type": "pass_fail"}],
            required_evidence=[],
            outcome_rules={"failed_item": "failed"},
            source_references=[{"source": "approved-specification", "version": "A"}],
        )

    def _inspection(self, *, profile=ControlProfile.HSE, number="I-001"):
        version = self.hse_version if profile == ControlProfile.HSE else self.qa_version
        return create_inspection(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            site=self.site,
            profile=profile,
            number=number,
            template_version=version,
            title="Site inspection",
            inspector=self.owner,
            operation_key=uuid4(),
        )

    def _transition(
        self, record, to_status, actor=None, reason="approved", updates=None
    ):
        return transition_record(
            organization=self.organization,
            actor=actor or self.owner,
            model=type(record),
            record_id=str(record.pk),
            to_status=to_status,
            expected_status=record.status,
            reason=reason,
            updates=updates or {},
            operation_key=uuid4(),
        )

    def test_template_version_is_pinned_and_profiles_cannot_cross(self):
        inspection = self._inspection()
        first_hash = inspection.template_snapshot_hash
        second = publish_template_version(
            organization=self.organization,
            actor=self.owner,
            template_id=str(self.hse_template.pk),
            checklist=[{"id": "ppe-v2", "required": True}],
            required_evidence=[],
            outcome_rules={"failed_item": "failed"},
            source_references=[
                {"source": "tenant-approved-hse-policy", "version": "2"}
            ],
        )
        inspection.refresh_from_db()
        self.assertEqual(inspection.template_version_id, self.hse_version.pk)
        self.assertEqual(inspection.template_snapshot_hash, first_hash)
        self.assertNotEqual(first_hash, second.canonical_hash)
        with self.assertRaises(ValidationError):
            create_inspection(
                organization=self.organization,
                actor=self.owner,
                project=self.project,
                site=self.site,
                profile=ControlProfile.HSE,
                number="I-X",
                template_version=self.qa_version,
                title="Wrong profile",
                inspector=self.owner,
            )

    def test_tenant_scope_and_transition_retry_stale_protection(self):
        with self.assertRaises((PermissionDenied, ValidationError)):
            create_inspection(
                organization=self.organization,
                actor=self.owner,
                project=self.other_project,
                site=None,
                profile=ControlProfile.HSE,
                number="CROSS",
                template_version=self.hse_version,
                title="Cross tenant",
                inspector=self.owner,
            )
        inspection = self._inspection()
        key = uuid4()
        first = transition_record(
            organization=self.organization,
            actor=self.owner,
            model=type(inspection),
            record_id=str(inspection.pk),
            to_status=InspectionStatus.IN_PROGRESS,
            expected_status=InspectionStatus.DRAFT,
            reason="start",
            updates={},
            operation_key=key,
        )
        replay = transition_record(
            organization=self.organization,
            actor=self.owner,
            model=type(inspection),
            record_id=str(inspection.pk),
            to_status=InspectionStatus.IN_PROGRESS,
            expected_status=InspectionStatus.DRAFT,
            reason="start",
            updates={},
            operation_key=key,
        )
        self.assertEqual(first.pk, replay.pk)
        with self.assertRaises(ValueError):
            transition_record(
                organization=self.organization,
                actor=self.owner,
                model=type(inspection),
                record_id=str(inspection.pk),
                to_status=InspectionStatus.SUBMITTED,
                expected_status=InspectionStatus.DRAFT,
                reason="stale",
                updates={},
                operation_key=uuid4(),
            )

    def test_inspection_submission_review_and_reinspection_lineage(self):
        inspection = self._inspection()
        inspection = self._transition(
            inspection,
            InspectionStatus.IN_PROGRESS,
            updates={"responses": {"ppe": "fail"}},
        )
        inspection = self._transition(inspection, InspectionStatus.SUBMITTED)
        self.assertTrue(inspection.canonical_hash)
        inspection.title = "silent rewrite"
        with self.assertRaises(ValidationError):
            inspection.save()
        inspection.refresh_from_db()
        inspection = self._transition(
            inspection, InspectionStatus.UNDER_REVIEW, actor=self.reviewer
        )
        inspection = self._transition(
            inspection,
            InspectionStatus.FAILED,
            actor=self.reviewer,
            reason="PPE failed",
        )
        reinspection = create_inspection(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            site=self.site,
            profile=ControlProfile.HSE,
            number="I-002",
            template_version=self.hse_version,
            title="Reinspection",
            inspector=self.owner,
            replaces=inspection,
        )
        self.assertEqual(reinspection.replaces_id, inspection.pk)

    def test_permit_fails_closed_and_preserves_replacement(self):
        permit = create_permit(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            site=self.site,
            number="PTW-1",
            permit_type="Configured hot work",
            rule_source="",
            rule_version="",
            issuer_name="",
            scope_description="Area A",
            valid_from=None,
            valid_until=None,
        )
        permit = self._transition(permit, PermitStatus.SUBMITTED)
        permit = self._transition(
            permit, PermitStatus.UNDER_REVIEW, actor=self.reviewer
        )
        with self.assertRaises(ValidationError):
            self._transition(permit, PermitStatus.ISSUED, actor=self.reviewer)
        permit = self._transition(
            permit,
            PermitStatus.ISSUED,
            actor=self.reviewer,
            updates={
                "rule_source": "Approved tenant permit policy",
                "rule_version": "1",
                "issuer_name": "HSE manager",
                "valid_from": timezone.now(),
                "valid_until": timezone.now() + timedelta(hours=8),
            },
        )
        self.assertTrue(permit.is_currently_valid)
        permit = self._transition(
            permit,
            PermitStatus.SUSPENDED,
            actor=self.reviewer,
            reason="Unsafe condition",
        )
        self.assertEqual(permit.status, PermitStatus.SUSPENDED)

    def test_test_result_lineage_and_no_invented_criteria(self):
        test = create_test(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            site=self.site,
            number="T-1",
            title="Concrete specimen",
            method_reference="Approved method",
            method_version="2026-A",
            acceptance_criteria={"strength_mpa_min": "30"},
            specimen_id="S-1",
        )
        test = self._transition(test, ComplianceTestStatus.REQUESTED)
        test = self._transition(test, ComplianceTestStatus.IN_EXECUTION)
        result = enter_test_result(
            organization=self.organization,
            actor=self.owner,
            test_id=str(test.pk),
            values={"strength_mpa": "32.5"},
            units={"strength_mpa": "MPa"},
        )
        test.refresh_from_db()
        test = self._transition(test, ComplianceTestStatus.UNDER_REVIEW)
        test = self._transition(
            test, ComplianceTestStatus.ACCEPTED, actor=self.reviewer
        )
        result.refresh_from_db()
        self.assertEqual(result.reviewed_by, self.reviewer)
        self.assertEqual(result.review_decision, ComplianceTestStatus.ACCEPTED)
        self.assertEqual(result.criteria_snapshot, {"strength_mpa_min": "30"})
        result.values = {"strength_mpa": "99"}
        with self.assertRaises(ValidationError):
            result.save()

    def test_finding_ncr_boundary_and_capa_person_separation(self):
        inspection = self._inspection(profile=ControlProfile.QA_QC, number="QI-1")
        finding = create_finding(
            organization=self.organization,
            actor=self.owner,
            inspection=inspection,
            source_test=None,
            number="F-1",
            title="Dimensional deviation",
            description="Out of configured tolerance",
        )
        self.assertFalse(finding.nonconformities.exists())
        finding = self._transition(
            finding,
            FindingStatus.TRIAGED,
            updates={"classification": "major", "severity": "major"},
        )
        ncr = promote_finding_to_ncr(
            organization=self.organization,
            actor=self.owner,
            finding_id=str(finding.pk),
            number="NCR-1",
            description="Formal nonconformance",
        )
        self.assertEqual(ncr.status, NcrStatus.DRAFT)
        capa = create_capa(
            organization=self.organization,
            actor=self.owner,
            source=ncr,
            number="CAPA-1",
            action_type=CapaType.CORRECTIVE,
            problem_or_risk="Recurring deviation",
            cause_or_rationale="Root cause evidence",
            implementation_plan="Revise method",
            verification_criteria="Method deployed",
            effectiveness_criteria="No recurrence",
            target_date=timezone.localdate() + timedelta(days=10),
            distinct_closer_required=True,
        )
        capa = self._transition(capa, CapaStatus.APPROVED)
        capa = self._transition(
            capa, CapaStatus.ASSIGNED, updates={"responsible_user_id": self.owner.pk}
        )
        capa = self._transition(capa, CapaStatus.IN_PROGRESS)
        capa = self._transition(capa, CapaStatus.PENDING_VERIFICATION)
        with self.assertRaises(PermissionDenied):
            self._transition(capa, CapaStatus.VERIFIED, actor=self.owner)
        capa = self._transition(capa, CapaStatus.VERIFIED, actor=self.reviewer)
        capa = self._transition(
            capa, CapaStatus.EFFECTIVENESS_PENDING, actor=self.reviewer
        )
        capa = self._transition(capa, CapaStatus.INEFFECTIVE, actor=self.reviewer)
        capa = self._transition(
            capa, CapaStatus.IN_PROGRESS, actor=self.reviewer, reason="reopen"
        )
        self.assertEqual(capa.status, CapaStatus.IN_PROGRESS)
        capa = self._transition(
            capa, CapaStatus.PENDING_VERIFICATION, actor=self.reviewer
        )
        capa = self._transition(capa, CapaStatus.VERIFIED, actor=self.owner)
        capa = self._transition(
            capa, CapaStatus.EFFECTIVENESS_PENDING, actor=self.owner
        )
        capa = self._transition(capa, CapaStatus.EFFECTIVE, actor=self.owner)
        with self.assertRaises(PermissionDenied):
            self._transition(capa, CapaStatus.CLOSED, actor=self.owner)
        capa = self._transition(capa, CapaStatus.CLOSED, actor=self.reviewer)
        self.assertEqual(capa.closed_by, self.reviewer)

    def test_dms_version_is_pinned_and_proposal_has_no_downstream_effect(self):
        inspection = self._inspection()
        upload = SimpleUploadedFile(
            "inspection.pdf",
            b"%PDF-1.7\ninspection evidence",
            content_type="application/pdf",
        )
        document = create_document(
            organization=self.organization,
            actor=self.owner,
            document_type=DocumentType.GENERAL,
            title="Inspection evidence",
            upload=upload,
            target=self.project,
        )
        link = link_evidence(
            organization=self.organization,
            actor=self.owner,
            document_version=document.current_version,
            purpose="execution",
            operation_key=uuid4(),
            inspection=inspection,
        )
        self.assertEqual(link.sha256, document.current_version.sha256)
        self.assertEqual(link.document_id, document.pk)
        self.assertEqual(typed_links_for_document(document)[-1].target, inspection)
        with self.assertRaises(PermissionDenied):
            get_document_version_for_download(
                document=document,
                version_id=str(document.current_version_id),
                actor=self.reviewer,
            )

        direct_document = create_document(
            organization=self.organization,
            actor=self.owner,
            document_type=DocumentType.GENERAL,
            title="Direct inspection evidence",
            upload=SimpleUploadedFile(
                "direct.pdf",
                b"%PDF-1.7\ndirect evidence",
                content_type="application/pdf",
            ),
            target=inspection,
        )
        direct_links = typed_links_for_document(direct_document)
        self.assertEqual(len(direct_links), 1)
        self.assertEqual(direct_links[0].target, inspection)
        project_name = self.project.name
        proposal = create_downstream_proposal(
            organization=self.organization,
            actor=self.owner,
            source=inspection,
            target_domain="project_cost",
            proposal_payload={"action": "review only"},
            operation_key=uuid4(),
        )
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, project_name)
        self.assertEqual(proposal.status, "draft")

    def test_persian_rtl_workbench_and_navigation_are_reachable(self):
        self.client.force_login(self.owner)
        set_active_organization(self.client.session, self.organization)
        response = self.client.get(reverse("compliance:workbench"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, "بازرسی‌های HSE")
        self.assertContains(response, "بازرسی‌های QA/QC")
        self.assertContains(response, "عدم انطباق‌های رسمی")
        self.assertContains(response, "خروجی کنترل‌شده")
        self.assertContains(response, "ممیزی و تطبیق")
        export_response = self.client.get(reverse("compliance:export"))
        self.assertEqual(export_response.status_code, 200)
        self.assertEqual(export_response["Content-Type"], "text/csv; charset=utf-8")
        assurance_response = self.client.get(reverse("compliance:assurance"))
        self.assertEqual(assurance_response.status_code, 200)
        self.assertContains(assurance_response, "ممیزی و تطبیق HSE/QA")


class ComplianceConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="p9-race-owner")
        self.reviewer = User.objects.create_user(username="p9-race-reviewer")
        self.organization = Organization.objects.create(
            name="P9 Race", slug="p9-race", created_by=self.owner, updated_by=self.owner
        )
        OrganizationSettings.objects.create(organization=self.organization)
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.organization.memberships.create(
            user=self.reviewer,
            role=MembershipRole.COMPANY_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = Project.objects.create(
            organization=self.organization, code="RACE", name="Race project"
        )
        template = create_template(
            organization=self.organization,
            actor=self.owner,
            profile=ControlProfile.HSE,
            code="RACE-HSE",
            title="Concurrent inspection",
        )
        version = publish_template_version(
            organization=self.organization,
            actor=self.owner,
            template_id=str(template.pk),
            checklist=[{"id": "one", "required": True}],
            required_evidence=[],
            outcome_rules={"failed_item": "failed"},
            source_references=[{"source": "approved", "version": "1"}],
        )
        self.inspection = create_inspection(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            site=None,
            profile=ControlProfile.HSE,
            number="RACE-1",
            template_version=version,
            title="Race",
            inspector=self.owner,
        )

    def _start(self, actor_id) -> str:
        close_old_connections()
        try:
            transition_record(
                organization=Organization.objects.get(pk=self.organization.pk),
                actor=User.objects.get(pk=actor_id),
                model=type(self.inspection),
                record_id=str(self.inspection.pk),
                to_status=InspectionStatus.IN_PROGRESS,
                expected_status=InspectionStatus.DRAFT,
                reason="concurrent start",
                operation_key=uuid4(),
                updates={"responses": {}},
            )
        except ValueError:
            return "stale"
        finally:
            close_old_connections()
        return "started"

    def test_concurrent_transition_has_one_winner_and_one_stale_loser(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self._start, [self.owner.pk, self.reviewer.pk]))
        self.assertCountEqual(results, ["started", "stale"])
        self.inspection.refresh_from_db()
        self.assertEqual(self.inspection.status, InspectionStatus.IN_PROGRESS)
        self.assertEqual(
            ComplianceLifecycleEvent.objects.filter(
                organization=self.organization,
                entity_type="compliance.inspection",
                entity_id=self.inspection.pk,
            ).count(),
            1,
        )


class ComplianceMigrationRoundTripTests(TestCase):
    def test_compliance_initial_migration_rolls_back_and_reapplies(self):
        executor = MigrationExecutor(connection)
        migration = executor.loader.get_migration("compliance", "0001_initial")
        self.assertTrue(all(operation.reversible for operation in migration.operations))
        self.assertIn(
            ("compliance", "0001_initial"), executor.loader.applied_migrations
        )
        self.assertIn("compliance_inspection", connection.introspection.table_names())

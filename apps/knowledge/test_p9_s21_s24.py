from datetime import date
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.apps import apps as django_apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.compliance.models import (
    ControlProfile,
    Inspection,
    InspectionStatus,
    InspectionTemplate,
    InspectionTemplateVersion,
)
from apps.daily_reports.field_models import FieldObservation
from apps.documents.models import (
    Document,
    DocumentConfidentiality,
    DocumentType,
    DocumentVersion,
)
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipScopeGrant,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
    PlatformRoleAssignment,
    PlatformRoleCode,
)
from apps.organizations.services import set_active_organization
from apps.parties.models import BusinessParty, PartyKind
from apps.partner_qualification.models import PartnerEvaluation, PartnerProfile
from apps.projects.models import Project
from apps.support.models import SupportCase

from .models import (
    CandidateStatus,
    KnowledgeCandidate,
    KnowledgePromotion,
    KnowledgePublicationEvent,
    KnowledgePublicationVersion,
    KnowledgeRecurrenceEvidence,
    PromotionStatus,
    PublicationStatus,
    RecurrenceStatus,
    ReuseStatus,
)
from .services import (
    approve_candidate,
    approve_platform_promotion,
    correct_recurrence,
    correct_reuse,
    create_candidate,
    create_publication_correction,
    get_publication_history,
    publish_candidate,
    publish_platform_promotion,
    record_recurrence,
    record_reuse,
    request_platform_promotion,
    review_candidate,
    review_platform_promotion,
    submit_candidate,
    withdraw_publication,
)

KNOWLEDGE_CODES = tuple(
    code for code in BusinessPermissionCode.values if code.startswith("knowledge.")
)


class KnowledgeP9S21S24Tests(TestCase):
    def setUp(self):
        self.storage_directory = TemporaryDirectory()
        self.storage_override = override_settings(
            DOCUMENT_PROTECTED_ROOT=self.storage_directory.name
        )
        self.storage_override.enable()
        self.addCleanup(self.storage_override.disable)
        self.addCleanup(self.storage_directory.cleanup)
        self.author = User.objects.create_user(username="knowledge-author")
        self.reviewer = User.objects.create_user(username="knowledge-reviewer")
        self.other = User.objects.create_user(username="knowledge-other")
        self.organization = Organization.objects.create(
            name="Knowledge", slug="knowledge", created_by=self.author
        )
        self.other_organization = Organization.objects.create(
            name="Other Knowledge", slug="other-knowledge", created_by=self.other
        )
        OrganizationSettings.objects.create(organization=self.organization)
        OrganizationSettings.objects.create(organization=self.other_organization)
        self.role = OrganizationRole.objects.create(code="p9_knowledge", name="دانش P9")
        self.role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=(
                    *KNOWLEDGE_CODES,
                    BusinessPermissionCode.COMPLIANCE_VIEW,
                    BusinessPermissionCode.DOCUMENTS_VIEW,
                    BusinessPermissionCode.FIELD_OBSERVATIONS_VIEW,
                    BusinessPermissionCode.PARTNER_VIEW,
                    BusinessPermissionCode.SUPPORT_CASE_VIEW,
                )
            )
        )
        for user in (self.author, self.reviewer):
            membership = OrganizationMembership.objects.create(
                organization=self.organization,
                user=user,
                role_definition=self.role,
                status=MembershipStatus.ACTIVE,
            )
            MembershipScopeGrant.objects.create(
                organization=self.organization,
                membership=membership,
                scope_type=AuthorizationScopeType.ORGANIZATION,
                reason="Explicit Knowledge regression fixture scope",
            )
        other_membership = OrganizationMembership.objects.create(
            organization=self.other_organization,
            user=self.other,
            role_definition=self.role,
            status=MembershipStatus.ACTIVE,
        )
        MembershipScopeGrant.objects.create(
            organization=self.other_organization,
            membership=other_membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Explicit foreign-tenant Knowledge regression fixture scope",
        )

    def _source(self, *, organization=None, user=None):
        return SupportCase.objects.create(
            organization=organization or self.organization,
            requester=user or self.author,
            category="general",
            summary="source",
            status="resolved",
        )

    def _candidate(self):
        return create_candidate(
            organization=self.organization,
            actor=self.author,
            title="درس آموخته",
            body="متن راهنما",
            knowledge_type="lesson_learned",
            authority_classification="advisory",
            audience="کاربران مجاز",
            category_code="quality",
        )

    def _project(self):
        return Project.objects.create(
            organization=self.organization,
            code=f"KN-{uuid4().hex[:8]}",
            name="Knowledge source project",
            created_by=self.author,
        )

    def _document_version(self, *, confidentiality=DocumentConfidentiality.INTERNAL):
        document = Document.objects.create(
            organization=self.organization,
            document_type=DocumentType.REPORT,
            document_number=f"KN-{uuid4().hex[:12]}",
            confidentiality=confidentiality,
            title="Knowledge evidence",
            created_by=self.author,
            updated_by=self.author,
        )
        first = DocumentVersion.objects.create(
            organization=self.organization,
            document=document,
            version_number=1,
            original_file_name="evidence-v1.pdf",
            file=SimpleUploadedFile(
                "evidence-v1.pdf", b"%PDF-1.7\nfirst", content_type="application/pdf"
            ),
            content_type="application/pdf",
            file_size=14,
            sha256="1" * 64,
            uploaded_by=self.author,
        )
        second = DocumentVersion.objects.create(
            organization=self.organization,
            document=document,
            version_number=2,
            original_file_name="evidence-v2.pdf",
            file=SimpleUploadedFile(
                "evidence-v2.pdf", b"%PDF-1.7\nsecond", content_type="application/pdf"
            ),
            content_type="application/pdf",
            file_size=15,
            sha256="2" * 64,
            uploaded_by=self.author,
        )
        document.current_version = second
        document.save(update_fields=["current_version", "updated_at"])
        return document, first, second

    def _published(self):
        candidate = self._candidate()
        source = self._source()
        submit_candidate(
            organization=self.organization,
            actor=self.author,
            candidate_id=candidate.pk,
            expected_status=CandidateStatus.DRAFT,
            sources=[
                {
                    "source_type": "support_case",
                    "source_id": source.pk,
                    "citation_purpose": "source",
                }
            ],
        )
        review_candidate(
            organization=self.organization,
            actor=self.reviewer,
            candidate_id=candidate.pk,
            expected_status=CandidateStatus.SUBMITTED,
            outcome="recommended",
        )
        approve_candidate(
            organization=self.organization,
            actor=self.reviewer,
            candidate_id=candidate.pk,
            expected_status=CandidateStatus.RECOMMENDED,
        )
        return publish_candidate(
            organization=self.organization,
            actor=self.reviewer,
            candidate_id=candidate.pk,
            expected_status=CandidateStatus.APPROVED,
        )

    def _make_platform_admin(self, username):
        user = User.objects.create_user(username=username)
        PlatformRoleAssignment.objects.create(
            user=user,
            role=PlatformRoleCode.PLATFORM_ADMIN,
            assigned_by=user,
            approved_by=user,
            reason="P9 focused validation",
        )
        return user

    def test_lifecycle_pins_source_and_prevents_author_self_approval(self):
        candidate = self._candidate()
        source = self._source()
        submit_candidate(
            organization=self.organization,
            actor=self.author,
            candidate_id=candidate.pk,
            expected_status="draft",
            sources=[
                {
                    "source_type": "support_case",
                    "source_id": source.pk,
                    "citation_purpose": "source",
                }
            ],
        )
        with self.assertRaises(PermissionDenied):
            review_candidate(
                organization=self.organization,
                actor=self.author,
                candidate_id=candidate.pk,
                expected_status="submitted",
                outcome="recommended",
            )
        review_candidate(
            organization=self.organization,
            actor=self.reviewer,
            candidate_id=candidate.pk,
            expected_status="submitted",
            outcome="recommended",
        )
        approve_candidate(
            organization=self.organization,
            actor=self.reviewer,
            candidate_id=candidate.pk,
            expected_status="recommended",
        )
        version = publish_candidate(
            organization=self.organization,
            actor=self.reviewer,
            candidate_id=candidate.pk,
            expected_status="approved_for_publication",
        )
        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.candidate_revision.source_pins.count(), 1)

    def test_tenant_source_and_recurrence_are_isolated_and_distinct(self):
        candidate = self._candidate()
        foreign = self._source(organization=self.other_organization, user=self.other)
        with self.assertRaises(PermissionDenied):
            submit_candidate(
                organization=self.organization,
                actor=self.author,
                candidate_id=candidate.pk,
                expected_status="draft",
                sources=[
                    {
                        "source_type": "support_case",
                        "source_id": foreign.pk,
                        "citation_purpose": "foreign",
                    }
                ],
            )
        source = self._source()
        with self.assertRaises(ValidationError):
            record_recurrence(
                organization=self.organization,
                actor=self.author,
                recurrence_key="same",
                scope_description="Tenant",
                period_start="2026-01-01",
                period_end="2026-01-31",
                sources=[{"source_type": "support_case", "source_id": source.pk}],
            )

    def test_reuse_deduplicates_and_withdrawal_preserves_history(self):
        version = self._published()
        consumer = self._source()
        event = record_reuse(
            organization=self.organization,
            actor=self.author,
            publication_version_id=version.pk,
            reuse_type="referenced",
            consumer_type="support_case",
            consumer_id=consumer.pk,
            consumer_version=str(consumer.created_at),
            purpose="test",
            operation_key=uuid4(),
        )
        self.assertEqual(event.publication_version_id, version.pk)
        withdrawn = withdraw_publication(
            organization=self.organization,
            actor=self.reviewer,
            version_id=version.pk,
            expected_status=PublicationStatus.CURRENT,
            reason="obsolete",
        )
        self.assertEqual(withdrawn.status, PublicationStatus.WITHDRAWN)
        self.assertTrue(
            KnowledgePublicationVersion.objects.filter(pk=version.pk).exists()
        )

    def test_published_version_is_immutable_and_history_is_reproducible(self):
        version = self._published()
        original = (version.title, version.body, version.manifest_hash)
        version.body = "mutated"
        with self.assertRaises(ValidationError):
            version.save()
        with self.assertRaises(ValidationError):
            KnowledgePublicationVersion.objects.filter(pk=version.pk).update(
                body="mutated"
            )
        historical = get_publication_history(
            organization=self.organization,
            actor=self.reviewer,
            version_id=version.pk,
        )
        self.assertEqual(
            (historical.title, historical.body, historical.manifest_hash), original
        )

    def test_linked_correction_requires_normal_lifecycle_and_supersedes_once(self):
        previous = self._published()
        correction = create_publication_correction(
            organization=self.organization,
            actor=self.author,
            version_id=previous.pk,
            title="نسخه اصلاحی",
            body="متن اصلاحی",
            reason="رفع خطای مستند",
        )
        self.assertEqual(correction.corrects_version_id, previous.pk)
        with self.assertRaises(ValidationError):
            publish_candidate(
                organization=self.organization,
                actor=self.reviewer,
                candidate_id=correction.pk,
                expected_status=CandidateStatus.DRAFT,
                supersedes_id=previous.pk,
            )
        source = self._source()
        submit_candidate(
            organization=self.organization,
            actor=self.author,
            candidate_id=correction.pk,
            expected_status=CandidateStatus.DRAFT,
            sources=[{"source_type": "support_case", "source_id": source.pk}],
        )
        review_candidate(
            organization=self.organization,
            actor=self.reviewer,
            candidate_id=correction.pk,
            expected_status=CandidateStatus.SUBMITTED,
            outcome="recommended",
        )
        approve_candidate(
            organization=self.organization,
            actor=self.reviewer,
            candidate_id=correction.pk,
            expected_status=CandidateStatus.RECOMMENDED,
        )
        successor = publish_candidate(
            organization=self.organization,
            actor=self.reviewer,
            candidate_id=correction.pk,
            expected_status=CandidateStatus.APPROVED,
            supersedes_id=previous.pk,
        )
        previous.refresh_from_db()
        self.assertEqual(previous.status, PublicationStatus.SUPERSEDED)
        self.assertEqual(successor.supersedes_id, previous.pk)
        self.assertEqual(successor.publication.current_version_id, successor.pk)
        replay = publish_candidate(
            organization=self.organization,
            actor=self.reviewer,
            candidate_id=correction.pk,
            expected_status=CandidateStatus.APPROVED,
            supersedes_id=previous.pk,
        )
        self.assertEqual(replay.pk, successor.pk)
        competing = KnowledgeCandidate.objects.create(
            organization=self.organization,
            scope="tenant",
            title="رقیب",
            body="رقیب",
            knowledge_type="lesson_learned",
            authority_classification="advisory",
            sensitivity="internal",
            audience="tenant",
            category_code="quality",
            content_hash="a" * 64,
            created_by=self.author,
            corrects_version=previous,
            correction_reason="رقیب",
        )
        self.assertEqual(competing.corrects_version_id, previous.pk)
        self.assertEqual(previous.successors.count(), 1)

    def test_withdrawal_requires_reason_preserves_history_and_is_idempotent(self):
        version = self._published()
        with self.assertRaises(ValidationError):
            withdraw_publication(
                organization=self.organization,
                actor=self.reviewer,
                version_id=version.pk,
                expected_status=PublicationStatus.CURRENT,
                reason="",
            )
        withdrawn = withdraw_publication(
            organization=self.organization,
            actor=self.reviewer,
            version_id=version.pk,
            expected_status=PublicationStatus.CURRENT,
            reason="منسوخ",
        )
        replay = withdraw_publication(
            organization=self.organization,
            actor=self.reviewer,
            version_id=version.pk,
            expected_status=PublicationStatus.CURRENT,
            reason="منسوخ",
        )
        self.assertEqual(replay.pk, withdrawn.pk)
        self.assertIsNone(withdrawn.publication.current_version_id)
        self.assertEqual(withdrawn.body, "متن راهنما")
        self.assertTrue(
            KnowledgePublicationEvent.objects.filter(
                publication_version=version, event_type="withdrawn"
            ).exists()
        )

    def test_recurrence_and_reuse_corrections_preserve_lineage(self):
        first, second = self._source(), self._source()
        key = uuid4()
        recurrence = record_recurrence(
            organization=self.organization,
            actor=self.author,
            recurrence_key="support-repeat",
            scope_description="Tenant",
            period_start="2026-01-01",
            period_end="2026-01-31",
            sources=[
                {"source_type": "support_case", "source_id": first.pk},
                {"source_type": "support_case", "source_id": second.pk},
            ],
            operation_key=key,
        )
        replay = record_recurrence(
            organization=self.organization,
            actor=self.author,
            recurrence_key="support-repeat",
            scope_description="Tenant",
            period_start="2026-01-01",
            period_end="2026-01-31",
            sources=[
                {"source_type": "support_case", "source_id": first.pk},
                {"source_type": "support_case", "source_id": second.pk},
            ],
            operation_key=key,
        )
        self.assertEqual(replay.pk, recurrence.pk)
        invalidation = correct_recurrence(
            organization=self.organization,
            actor=self.author,
            recurrence_id=recurrence.pk,
            disposition="invalidate",
            reason="duplicate lineage discovered",
        )
        self.assertEqual(invalidation.replaces_id, recurrence.pk)
        self.assertEqual(invalidation.status, RecurrenceStatus.INVALIDATED)
        self.assertTrue(KnowledgeRecurrenceEvidence.objects.filter(pk=recurrence.pk).exists())
        with self.assertRaises(ValidationError):
            correct_recurrence(
                organization=self.organization,
                actor=self.author,
                recurrence_id=recurrence.pk,
                disposition="invalidate",
                reason="another correction",
            )

        version = self._published()
        consumer = self._source()
        reuse = record_reuse(
            organization=self.organization,
            actor=self.author,
            publication_version_id=version.pk,
            reuse_type="cited_in_decision",
            consumer_type="support_case",
            consumer_id=consumer.pk,
            consumer_version=str(consumer.created_at),
            purpose="decision citation",
        )
        replacement = correct_reuse(
            organization=self.organization,
            actor=self.author,
            reuse_id=reuse.pk,
            disposition="replace",
            reason="purpose correction",
            purpose="corrected citation",
        )
        self.assertEqual(replacement.reverses_id, reuse.pk)
        self.assertEqual(replacement.status, ReuseStatus.REPLACEMENT)
        consumer.refresh_from_db()
        self.assertEqual(consumer.summary, "source")

    def test_representative_source_adapters_pin_exact_facts_without_mutation(self):
        project = self._project()
        field = FieldObservation.objects.create(
            organization=self.organization,
            project=project,
            kind="general",
            title="Accepted observation",
            status="accepted",
            revision=3,
            create_operation_key=uuid4(),
            create_payload_hash="f" * 64,
            created_by=self.author,
        )
        template = InspectionTemplate.objects.create(
            organization=self.organization,
            profile=ControlProfile.HSE,
            code=f"KN-{uuid4().hex[:8]}",
            title="Knowledge inspection template",
            created_by=self.author,
        )
        template_version = InspectionTemplateVersion.objects.create(
            organization=self.organization,
            template=template,
            version_number=1,
            checklist=[],
            outcome_rules={},
            source_references=[],
            canonical_hash="c" * 64,
            published_by=self.author,
        )
        inspection = Inspection.objects.create(
            organization=self.organization,
            project=project,
            profile=ControlProfile.HSE,
            number=f"KN-{uuid4().hex[:8]}",
            template_version=template_version,
            title="Passed inspection",
            status=InspectionStatus.PASSED,
            template_snapshot_hash=template_version.canonical_hash,
            created_by=self.author,
            inspector=self.author,
        )
        party = BusinessParty.objects.create(
            organization=self.organization,
            party_kind=PartyKind.COMPANY,
            display_name="Knowledge partner",
        )
        profile = PartnerProfile.objects.create(
            organization=self.organization,
            party=party,
            created_by=self.author,
        )
        evaluation = PartnerEvaluation.objects.create(
            organization=self.organization,
            profile=profile,
            project=project,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            criteria_snapshot=[{"code": "quality", "weight": 100}],
            scores={"quality": 90},
            status="published",
            authored_by=self.author,
            published_by=self.reviewer,
        )
        support = self._source()
        originals = {
            "field": (field.status, field.revision),
            "inspection": (inspection.status, inspection.updated_at),
            "evaluation": (evaluation.status, evaluation.updated_at),
            "support": (support.status, support.summary),
        }
        candidate = self._candidate()
        submit_candidate(
            organization=self.organization,
            actor=self.author,
            candidate_id=candidate.pk,
            expected_status=CandidateStatus.DRAFT,
            sources=[
                {"source_type": "field_observation", "source_id": field.pk},
                {"source_type": "inspection", "source_id": inspection.pk},
                {"source_type": "partner_evaluation", "source_id": evaluation.pk},
                {"source_type": "support_case", "source_id": support.pk},
            ],
        )
        pins = {
            pin.source_type: (str(pin.source_id), pin.source_version, pin.source_status)
            for pin in candidate.revisions.get(revision=1).source_pins.all()
        }
        self.assertEqual(set(pins), {
            "field_observation",
            "inspection",
            "partner_evaluation",
            "support_case",
        })
        field.refresh_from_db()
        inspection.refresh_from_db()
        evaluation.refresh_from_db()
        support.refresh_from_db()
        self.assertEqual((field.status, field.revision), originals["field"])
        self.assertEqual((inspection.status, inspection.updated_at), originals["inspection"])
        self.assertEqual((evaluation.status, evaluation.updated_at), originals["evaluation"])
        self.assertEqual((support.status, support.summary), originals["support"])

        denied = User.objects.create_user(username="source-adapter-denied")
        denied_role = OrganizationRole.objects.create(
            code="knowledge_without_source_view", name="Knowledge without source view"
        )
        denied_role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=(
                    BusinessPermissionCode.KNOWLEDGE_CANDIDATES_CREATE,
                    BusinessPermissionCode.KNOWLEDGE_CANDIDATES_SUBMIT,
                )
            )
        )
        denied_membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=denied,
            role_definition=denied_role,
            status=MembershipStatus.ACTIVE,
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=denied_membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Reach the intended missing-source-permission denial",
        )
        denied_candidate = create_candidate(
            organization=self.organization,
            actor=denied,
            title="Denied source",
            body="Denied",
            knowledge_type="lesson_learned",
            authority_classification="advisory",
            audience="tenant",
            category_code="quality",
        )
        with self.assertRaises(PermissionDenied):
            submit_candidate(
                organization=self.organization,
                actor=denied,
                candidate_id=denied_candidate.pk,
                expected_status=CandidateStatus.DRAFT,
                sources=[{"source_type": "field_observation", "source_id": field.pk}],
            )

    def test_dms_pin_is_exact_stable_and_sensitive_history_is_restricted(self):
        document, first, second = self._document_version(
            confidentiality=DocumentConfidentiality.CONFIDENTIAL
        )
        source = self._source()
        candidate = self._candidate()
        submit_candidate(
            organization=self.organization,
            actor=self.author,
            candidate_id=candidate.pk,
            expected_status=CandidateStatus.DRAFT,
            sources=[
                {
                    "source_type": "support_case",
                    "source_id": source.pk,
                    "document_version": first,
                }
            ],
        )
        review_candidate(
            organization=self.organization,
            actor=self.reviewer,
            candidate_id=candidate.pk,
            expected_status=CandidateStatus.SUBMITTED,
            outcome="recommended",
        )
        approve_candidate(
            organization=self.organization,
            actor=self.reviewer,
            candidate_id=candidate.pk,
            expected_status=CandidateStatus.RECOMMENDED,
        )
        version = publish_candidate(
            organization=self.organization,
            actor=self.reviewer,
            candidate_id=candidate.pk,
            expected_status=CandidateStatus.APPROVED,
        )
        pin = version.candidate_revision.source_pins.get()
        self.assertEqual(pin.document_id, document.pk)
        self.assertEqual(pin.document_version_id, first.pk)
        self.assertEqual(pin.sha256, "1" * 64)
        self.assertNotEqual(pin.document_version_id, second.pk)
        self.assertFalse(any(field.name == "file" for field in type(pin)._meta.fields))

        restricted = User.objects.create_user(username="restricted-provenance")
        restricted_role = OrganizationRole.objects.create(
            code="knowledge_restricted_provenance", name="Restricted provenance"
        )
        restricted_role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=(
                    BusinessPermissionCode.DOCUMENTS_VIEW,
                    BusinessPermissionCode.KNOWLEDGE_HISTORY_VIEW,
                    BusinessPermissionCode.SUPPORT_CASE_VIEW,
                )
            )
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=restricted,
            role_definition=restricted_role,
            status=MembershipStatus.ACTIVE,
        )
        with self.assertRaises(PermissionDenied):
            get_publication_history(
                organization=self.organization,
                actor=restricted,
                version_id=version.pk,
            )
        self.assertFalse(
            AuditEvent.objects.filter(
                actor=restricted,
                action=AuditAction.KNOWLEDGE_SENSITIVE_PROVENANCE_VIEWED,
            ).exists()
        )
        history = get_publication_history(
            organization=self.organization,
            actor=self.reviewer,
            version_id=version.pk,
        )
        self.assertEqual(history.candidate_revision.source_pins.get().sha256, "1" * 64)
        self.assertTrue(
            AuditEvent.objects.filter(
                actor=self.reviewer,
                action=AuditAction.KNOWLEDGE_SENSITIVE_PROVENANCE_VIEWED,
            ).exists()
        )

    def test_platform_promotion_is_independent_and_does_not_expose_tenant_source(self):
        source_version = self._published()
        platform_reviewer = self._make_platform_admin("platform-reviewer")
        platform_approver = self._make_platform_admin("platform-approver")
        promotion = request_platform_promotion(
            organization=self.organization,
            actor=self.reviewer,
            version_id=source_version.pk,
            title="راهنمای عمومی",
            body="مشتق پالایش‌شده",
            audience="platform",
            category_code="quality",
            anonymization_statement="هویت و جزئیات Tenant حذف شد",
        )
        frozen_hash = promotion.snapshot_hash
        with self.assertRaises(PermissionDenied):
            approve_platform_promotion(
                promotion_id=promotion.pk, actor=platform_approver
            )
        review_platform_promotion(
            promotion_id=promotion.pk,
            actor=platform_reviewer,
            outcome="recommend",
            reason="sanitized",
        )
        approve_platform_promotion(
            promotion_id=promotion.pk, actor=platform_approver
        )
        platform_version = publish_platform_promotion(
            promotion_id=promotion.pk, actor=platform_approver
        )
        promotion.refresh_from_db()
        source_version.refresh_from_db()
        self.assertEqual(promotion.status, PromotionStatus.PUBLISHED)
        self.assertEqual(promotion.snapshot_hash, frozen_hash)
        self.assertIsNone(platform_version.publication.organization_id)
        self.assertEqual(platform_version.publication.scope, "platform")
        self.assertEqual(source_version.publication.organization_id, self.organization.pk)
        self.assertEqual(platform_version.candidate_revision.source_pins.count(), 0)
        self.assertFalse(
            KnowledgePromotion.objects.filter(
                platform_candidate__organization=self.other_organization
            ).exists()
        )

    def test_default_denial_role_name_and_cross_tenant_routes(self):
        denied_user = User.objects.create_user(username="knowledge-manager-name-only")
        empty_role = OrganizationRole.objects.create(
            code="knowledge_manager_name_only", name="Knowledge Manager"
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=denied_user,
            role_definition=empty_role,
            status=MembershipStatus.ACTIVE,
        )
        with self.assertRaises(PermissionDenied):
            create_candidate(
                organization=self.organization,
                actor=denied_user,
                title="denied",
                body="denied",
                knowledge_type="lesson_learned",
                authority_classification="advisory",
                audience="tenant",
                category_code="quality",
            )
        version = self._published()
        self.client.force_login(self.author)
        set_active_organization(self.client.session, self.organization)
        response = self.client.get(reverse("knowledge:catalogue"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dir="rtl"')
        self.assertEqual(
            self.client.get(reverse("knowledge:candidates")).status_code, 200
        )
        self.assertEqual(
            self.client.get(
                reverse("knowledge:candidate_detail", args=[version.candidate_revision.candidate_id])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("knowledge:publication_history", args=[version.pk])
            ).status_code,
            200,
        )
        self.assertEqual(self.client.get(reverse("knowledge:recurrence")).status_code, 200)
        self.assertEqual(self.client.get(reverse("knowledge:reuse")).status_code, 200)
        self.assertEqual(
            self.client.get(
                reverse("knowledge:publication_withdraw", args=[version.pk])
            ).status_code,
            405,
        )
        self.client.force_login(self.other)
        set_active_organization(self.client.session, self.other_organization)
        self.assertEqual(
            self.client.get(
                reverse("knowledge:publication_detail", args=[version.pk])
            ).status_code,
            404,
        )

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.author)
        set_active_organization(csrf_client.session, self.organization)
        self.assertEqual(
            csrf_client.post(reverse("knowledge:candidate_create"), {}).status_code,
            403,
        )

    def test_knowledge_actions_have_no_automatic_downstream_effects(self):
        source = self._source()
        downstream_apps = (
            "accounting",
            "billing",
            "compliance",
            "contracts",
            "equipment",
            "financials",
            "fixed_assets",
            "inventory",
            "partner_qualification",
            "payroll",
            "procurement",
            "projects",
            "subledgers",
            "support",
            "treasury",
        )

        def counts():
            return {
                model._meta.label_lower: model._default_manager.count()
                for label in downstream_apps
                for model in django_apps.get_app_config(label).get_models()
            }

        before = counts()
        candidate = self._candidate()
        submit_candidate(
            organization=self.organization,
            actor=self.author,
            candidate_id=candidate.pk,
            expected_status=CandidateStatus.DRAFT,
            sources=[{"source_type": "support_case", "source_id": source.pk}],
        )
        review_candidate(
            organization=self.organization,
            actor=self.reviewer,
            candidate_id=candidate.pk,
            expected_status=CandidateStatus.SUBMITTED,
            outcome="recommended",
        )
        approve_candidate(
            organization=self.organization,
            actor=self.reviewer,
            candidate_id=candidate.pk,
            expected_status=CandidateStatus.RECOMMENDED,
        )
        version = publish_candidate(
            organization=self.organization,
            actor=self.reviewer,
            candidate_id=candidate.pk,
            expected_status=CandidateStatus.APPROVED,
        )
        record_reuse(
            organization=self.organization,
            actor=self.author,
            publication_version_id=version.pk,
            reuse_type="referenced",
            consumer_type="support_case",
            consumer_id=source.pk,
            consumer_version=str(source.created_at),
            purpose="no downstream mutation",
        )
        self.assertEqual(counts(), before)

    def test_audit_actions_cover_consequential_lifecycle(self):
        version = self._published()
        withdraw_publication(
            organization=self.organization,
            actor=self.reviewer,
            version_id=version.pk,
            expected_status=PublicationStatus.CURRENT,
            reason="audit validation",
        )
        actions = set(
            AuditEvent.objects.filter(organization=self.organization).values_list(
                "action", flat=True
            )
        )
        self.assertTrue(
            {
                AuditAction.KNOWLEDGE_CANDIDATE_CREATED,
                AuditAction.KNOWLEDGE_CANDIDATE_SUBMITTED,
                AuditAction.KNOWLEDGE_CANDIDATE_REVIEWED,
                AuditAction.KNOWLEDGE_CANDIDATE_APPROVED,
                AuditAction.KNOWLEDGE_PUBLICATION_PUBLISHED,
                AuditAction.KNOWLEDGE_PUBLICATION_WITHDRAWN,
            }.issubset(actions)
        )

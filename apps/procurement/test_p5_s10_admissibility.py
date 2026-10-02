from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.documents.models import (
    DocumentProcessingAssessment,
    DocumentProcessingVerdict,
)
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipStatus,
    PlatformPolicy,
    PlatformPolicyVersion,
    PolicySourceBasis,
    PolicyVersionStatus,
    TenantPolicySelection,
    TenantPolicySelectionStatus,
)
from apps.organizations.policy_specs import (
    RFQ_ADMISSIBILITY_SELF_APPROVAL_POLICY_CODE,
    get_platform_policy_spec,
)
from apps.procurement.admissibility_services import (
    approve_quote_admissibility,
    prepare_quote_admissibility,
    withdraw_quote_admissibility_preparation,
)
from apps.procurement.models import (
    QuoteAdmissibilityDecision,
    QuoteAdmissibilityReasonCode,
    QuoteAdmissibilityWithdrawal,
    QuoteEligibilityState,
)
from apps.procurement.opening_services import (
    approve_quote_opening,
    grant_quote_confidential_access,
    request_quote_opening,
    revoke_quote_confidential_access,
)
from apps.procurement.test_p5_s08_sealed_custody import SealedCustodyFixtureMixin


class AdmissibilityFixtureMixin(SealedCustodyFixtureMixin):
    def setUp(self) -> None:
        super().setUp()
        self.revision, self.manifest = self._closed_revision()
        self._grant(BusinessPermissionCode.RFQS_CUSTODY_SEALED_EVIDENCE)
        self.evidence = self._accept_original(self.revision)
        self.preparer = self._make_actor("admissibility-preparer")
        self.approver = self._make_actor("admissibility-approver")
        self._grant(BusinessPermissionCode.RFQ_QUOTES_OPEN)
        self._grant(BusinessPermissionCode.RFQ_QUOTES_APPROVE_OPEN, self.approver)
        self._grant(
            BusinessPermissionCode.RFQ_QUOTES_MANAGE_CONFIDENTIAL_ACCESS,
        )
        self._mark_clean()
        at_opening = self.revision.rfq_version.earliest_opening_at + timedelta(
            seconds=1
        )
        with patch(
            "apps.procurement.opening_services.timezone.now", return_value=at_opening
        ):
            opening_request = request_quote_opening(
                organization=self.organization,
                actor=self.owner,
                quote_revision=self.revision,
                reason="scheduled opening",
                idempotency_key="s10-open",
            )
            self.opening = approve_quote_opening(
                organization=self.organization,
                actor=self.approver,
                opening_request=opening_request,
            )
        for user in (self.preparer, self.approver):
            self._grant(BusinessPermissionCode.RFQ_QUOTES_VIEW_CONFIDENTIAL, user)
            grant_quote_confidential_access(
                organization=self.organization,
                actor=self.owner,
                quote_revision=self.revision,
                membership=self.organization.memberships.get(user=user),
                reason="S10 controlled review",
                idempotency_key=f"s10-grant-{user.username}",
            )
        self._grant(
            BusinessPermissionCode.RFQ_QUOTES_PREPARE_ADMISSIBILITY, self.preparer
        )
        self._grant(
            BusinessPermissionCode.RFQ_QUOTES_APPROVE_ADMISSIBILITY, self.approver
        )

    def _make_actor(self, username: str) -> User:
        user = User.objects.create_user(username=username, password="x")
        self.organization.memberships.create(
            user=user,
            role=MembershipRole.TENANT_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        return user

    def _mark_clean(self) -> None:
        for item in self.revision.evidence_items.select_related("document_version"):
            DocumentProcessingAssessment.objects.create(
                organization=self.organization,
                version=item.document_version,
                sequence=1,
                verdict=DocumentProcessingVerdict.CLEAN,
                input_sha256=item.canonical_sha256,
                adapter_code="p5-s10-test-scanner",
                adapter_version="1",
                recorded_by=self.owner,
            )

    def _grant(self, code, user=None) -> None:
        membership = self.organization.memberships.get(user=user or self.owner)
        membership.role_definition.permissions.add(
            BusinessPermission.objects.get(code=code)
        )

    def _activate_self_approval_policy(self, *, allow: bool) -> None:
        spec = get_platform_policy_spec(RFQ_ADMISSIBILITY_SELF_APPROVAL_POLICY_CODE)
        policy = PlatformPolicy.objects.create(
            code=spec.code,
            name=spec.name,
            category=spec.category,
            sensitivity=spec.sensitivity,
            tenant_selectable=True,
            requires_source_provenance=False,
            created_by=self.owner,
            updated_by=self.owner,
        )
        now = timezone.now()
        version = PlatformPolicyVersion.objects.create(
            policy=policy,
            version=1,
            parameters={"allow_self_approval": allow},
            effective_from=timezone.localdate(),
            status=PolicyVersionStatus.PUBLISHED,
            source_basis=PolicySourceBasis.PRODUCT_DEFINED,
            created_by=self.owner,
            published_by=self.owner,
            published_at=now,
            reason="P5-S10 test policy",
        )
        owner_membership = self.organization.memberships.get(user=self.owner)
        TenantPolicySelection.objects.create(
            organization=self.organization,
            policy=policy,
            policy_version=version,
            status=TenantPolicySelectionStatus.ACTIVE,
            approved_by=owner_membership,
            approved_at=now,
            applied_by=owner_membership,
            applied_at=now,
            reason="P5-S10 test activation",
        )

    def _prepare(self, *, key="prepare-1", state=QuoteEligibilityState.ADMISSIBLE):
        reason = (
            QuoteAdmissibilityReasonCode.REQUIREMENTS_MET
            if state == QuoteEligibilityState.ADMISSIBLE
            else QuoteAdmissibilityReasonCode.EXCEPTION_REVIEW_REQUIRED
        )
        return prepare_quote_admissibility(
            organization=self.organization,
            actor=self.preparer,
            quote_revision=self.revision,
            state=state,
            reason_code=reason,
            rationale="controlled commercial basis",
            idempotency_key=key,
        )


class QuoteAdmissibilityTests(AdmissibilityFixtureMixin, TestCase):
    def test_prepare_requires_open_confidential_scope_and_retains_exact_evidence(self):
        preparation = self._prepare()
        retry = self._prepare()
        self.assertEqual(preparation.pk, retry.pk)
        self.assertEqual(preparation.opening_event_id, self.opening.pk)
        self.assertEqual(preparation.close_manifest_id, self.manifest.pk)
        self.assertEqual(
            preparation.package_fingerprint, self.opening.package_fingerprint
        )
        with self.assertRaises(ValueError):
            prepare_quote_admissibility(
                organization=self.organization,
                actor=self.preparer,
                quote_revision=self.revision,
                state=QuoteEligibilityState.ADMISSIBLE,
                reason_code=QuoteAdmissibilityReasonCode.REQUIREMENTS_MET,
                rationale="changed basis",
                idempotency_key="prepare-1",
            )
        preparation.rationale = "rewrite"
        with self.assertRaises(ValidationError):
            preparation.save()

    def test_reason_catalog_and_access_fail_closed(self):
        with self.assertRaises(ValueError):
            self._prepare(state=QuoteEligibilityState.INADMISSIBLE)
        self._grant(BusinessPermissionCode.RFQ_QUOTES_PREPARE_ADMISSIBILITY, self.owner)
        with self.assertRaises(PermissionDenied):
            prepare_quote_admissibility(
                organization=self.organization,
                actor=self.owner,
                quote_revision=self.revision,
                state=QuoteEligibilityState.ADMISSIBLE,
                reason_code=QuoteAdmissibilityReasonCode.REQUIREMENTS_MET,
                rationale="owner lacks a revision grant",
                idempotency_key="owner-no-grant",
            )

    def test_revoked_confidential_access_blocks_preparation(self):
        grant = self.revision.confidential_access_grants.get(
            membership=self.organization.memberships.get(user=self.preparer)
        )
        revoke_quote_confidential_access(
            organization=self.organization,
            actor=self.owner,
            grant=grant,
            reason="reviewer access revoked",
        )
        with self.assertRaises(PermissionDenied):
            self._prepare(key="revoked-preparer")

    def test_approve_requires_policy_independent_permission_and_keeps_approved_immutable(
        self,
    ):
        preparation = self._prepare()
        with self.assertRaises(ValidationError):
            approve_quote_admissibility(
                organization=self.organization,
                actor=self.approver,
                preparation=preparation,
            )
        self._activate_self_approval_policy(allow=False)
        decision = approve_quote_admissibility(
            organization=self.organization, actor=self.approver, preparation=preparation
        )
        self.assertEqual(decision.state, QuoteEligibilityState.ADMISSIBLE)
        self.assertEqual(
            decision.approval_policy_version.policy.code,
            RFQ_ADMISSIBILITY_SELF_APPROVAL_POLICY_CODE,
        )
        self.assertEqual(
            approve_quote_admissibility(
                organization=self.organization,
                actor=self.approver,
                preparation=preparation,
            ).pk,
            decision.pk,
        )
        decision.state = QuoteEligibilityState.INADMISSIBLE
        with self.assertRaises(ValidationError):
            decision.save()
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.RFQ_ADMISSIBILITY_APPROVED
            ).exists()
        )

    def test_policy_controls_self_approval_and_withdrawal_blocks_approval(self):
        self._grant(
            BusinessPermissionCode.RFQ_QUOTES_APPROVE_ADMISSIBILITY, self.preparer
        )
        preparation = self._prepare()
        self._activate_self_approval_policy(allow=False)
        with self.assertRaises(PermissionDenied):
            approve_quote_admissibility(
                organization=self.organization,
                actor=self.preparer,
                preparation=preparation,
            )
        withdrawal = withdraw_quote_admissibility_preparation(
            organization=self.organization,
            actor=self.preparer,
            preparation=preparation,
            reason="basis withdrawn",
        )
        self.assertEqual(QuoteAdmissibilityWithdrawal.objects.get().pk, withdrawal.pk)
        with self.assertRaises(ValueError):
            approve_quote_admissibility(
                organization=self.organization,
                actor=self.approver,
                preparation=preparation,
            )

    def test_policy_can_explicitly_allow_self_approval(self):
        self._grant(
            BusinessPermissionCode.RFQ_QUOTES_APPROVE_ADMISSIBILITY, self.preparer
        )
        self._activate_self_approval_policy(allow=True)
        decision = approve_quote_admissibility(
            organization=self.organization,
            actor=self.preparer,
            preparation=self._prepare(),
        )
        self.assertEqual(decision.approved_by_id, self.preparer.pk)

    def test_correction_supersedes_without_mutating_decision(self):
        self._activate_self_approval_policy(allow=False)
        initial = approve_quote_admissibility(
            organization=self.organization,
            actor=self.approver,
            preparation=self._prepare(),
        )
        correction = self._prepare(
            key="prepare-correction", state=QuoteEligibilityState.REVIEW_REQUIRED
        )
        with self.assertRaises(ValueError):
            approve_quote_admissibility(
                organization=self.organization,
                actor=self.approver,
                preparation=correction,
            )
        corrected = approve_quote_admissibility(
            organization=self.organization,
            actor=self.approver,
            preparation=correction,
            supersedes=initial,
        )
        self.assertEqual(corrected.supersedes_id, initial.pk)
        self.assertEqual(QuoteAdmissibilityDecision.objects.count(), 2)

    def test_cross_tenant_and_missing_prerequisite_fail_closed(self):
        outsider = User.objects.create_user(username="s10-outsider", password="x")
        with self.assertRaises(PermissionDenied):
            prepare_quote_admissibility(
                organization=self.other_organization,
                actor=outsider,
                quote_revision=self.revision,
                state=QuoteEligibilityState.ADMISSIBLE,
                reason_code=QuoteAdmissibilityReasonCode.REQUIREMENTS_MET,
                rationale="cross tenant",
                idempotency_key="cross",
            )


class QuoteAdmissibilityConcurrencyTests(
    AdmissibilityFixtureMixin, TransactionTestCase
):
    reset_sequences = True

    def test_concurrent_approval_creates_one_decision(self):
        self._activate_self_approval_policy(allow=False)
        preparation = self._prepare()
        barrier = Barrier(2)

        def approve_once():
            close_old_connections()
            try:
                barrier.wait()
                return approve_quote_admissibility(
                    organization=self.organization,
                    actor=self.approver,
                    preparation=preparation,
                ).pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: approve_once(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(QuoteAdmissibilityDecision.objects.count(), 1)

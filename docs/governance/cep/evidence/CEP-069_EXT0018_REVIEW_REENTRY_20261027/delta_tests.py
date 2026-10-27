"""Synthetic conditional-review safety; these cases assert no statutory choice."""

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import PolicyReviewDisposition, PolicyVersionStatus
from apps.organizations.policy_services import publish_platform_policy_version
from apps.payroll.source_package_services import activate_statutory_source_package
from apps.payroll.statutory_services import _round, _tax_employee
from apps.payroll.test_cep052 import SourcePackageTests


class ConditionalReviewTests(SourcePackageTests):
    """Reuse synthetic fixtures; runner selects only the three new delta cases."""

    def test_conditional_review_cannot_import(self):
        _, policy, payload = self._draft()
        # Adversarial fixture only, never a mutation of retained Human evidence.
        policy.review_evidence.update(
            disposition=PolicyReviewDisposition.ACCEPTED_WITH_CONDITIONS,
            conditions="Synthetic unresolved conditions; activation rejected",
        )
        with self.assertRaises(ValidationError):
            self._import(policy, payload)
        self.assertFalse(hasattr(policy, "payroll_source_package"))
        policy.refresh_from_db()
        self.assertEqual(policy.status, PolicyVersionStatus.DRAFT)

    def test_conditional_review_cannot_bypass_through_publication(self):
        _, policy, _ = self._draft()
        policy.review_evidence.update(
            disposition=PolicyReviewDisposition.ACCEPTED_WITH_CONDITIONS,
            conditions="Synthetic unresolved conditions; activation rejected",
        )
        with self.assertRaises(ValidationError):
            publish_platform_policy_version(
                actor=self.platform, policy_version=policy, reason="Synthetic bypass"
            )
        policy.refresh_from_db()
        self.assertEqual(policy.status, PolicyVersionStatus.DRAFT)

    def test_changed_to_conditional_evidence_blocks_existing_package_activation(self):
        previous, policy, payload = self._draft()
        package = self._import(policy, payload)
        old_digest = previous.payroll_source_package.content_digest
        # Simulate evidence drift/corruption in the isolated fixture only.
        policy.review_evidence.update(
            disposition=PolicyReviewDisposition.ACCEPTED_WITH_CONDITIONS,
            conditions="Synthetic unresolved conditions; activation rejected",
        )
        with self.assertRaises(ValidationError):
            activate_statutory_source_package(
                actor=self.platform, package=package, reason="Synthetic delta"
            )
        with self.assertRaises(ValidationError):
            self._import(policy, payload)
        policy.refresh_from_db()
        previous.payroll_source_package.refresh_from_db()
        self.assertEqual(policy.status, PolicyVersionStatus.DRAFT)
        self.assertEqual(previous.payroll_source_package.content_digest, old_digest)
        self.assertFalse(
            AuditEvent.objects.filter(
                action=AuditAction.PLATFORM_POLICY_VERSION_PUBLISHED,
                entity_id=str(policy.pk),
            ).exists()
        )


class UnselectedSemanticsTests(SimpleTestCase):
    def test_unsupported_cumulative_calculation_remains_fail_closed(self):
        with self.assertRaises(ValidationError):
            _tax_employee(None, {"calculation_basis": "cumulative"})

    def test_missing_rounding_is_not_replaced_by_a_default(self):
        from decimal import Decimal

        for config in (None, {}, {"method": "", "scale": 0, "stage": "line"}):
            with self.subTest(config=config), self.assertRaises(ValidationError):
                _round(Decimal("1.5"), config)

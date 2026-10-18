from copy import deepcopy
from datetime import date
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.access_services import assign_platform_admin
from apps.organizations.models import (
    PlatformPolicyVersion,
    PlatformPolicyVersionSource,
    PolicyReviewDisposition,
    PolicyReviewEvidence,
    PolicyVersionStatus,
)
from apps.organizations.policy_specs import PAYROLL_TAX_REGULATORY_POLICY_CODE

from . import test_p7_s23_s28_statutory_payroll as baseline
from .models import (
    StatutoryCalculation,
    StatutoryCalculationKind,
    StatutorySourcePackage,
)
from .source_package_services import (
    activate_statutory_source_package,
    import_statutory_source_package,
    resolve_statutory_source_package,
)
from .statutory_services import calculate_statutory


class SourcePackageTests(baseline.StatutoryPayrollTests):
    # Six inherited cases retain the existing statutory calculation/output boundary.
    def setUp(self):
        super().setUp()
        root = User.objects.create_superuser(username="source-root", password="x")
        approver = User.objects.create_superuser(
            username="source-approver", password="x"
        )
        self.platform = User.objects.create_user(username="source-platform")
        assign_platform_admin(
            actor=root,
            approver=approver,
            target=self.platform,
            reason="Synthetic fixture",
        )

    def _draft(self):
        previous = self._published_policy(
            PAYROLL_TAX_REGULATORY_POLICY_CODE, self._tax_parameters()
        )
        policy = PlatformPolicyVersion.objects.create(
            policy=previous.policy,
            version=2,
            effective_from=date(2027, 1, 1),
            parameters=deepcopy(previous.parameters),
            source_basis=previous.source_basis,
            supersedes=previous,
            created_by=self.platform,
            reason="Synthetic successor",
        )
        source = previous.sources.get()
        PlatformPolicyVersionSource.objects.create(
            policy_version=policy,
            source=source,
            linked_by=self.platform,
            reason="Synthetic source lineage",
        )
        PolicyReviewEvidence.objects.create(
            policy_version=policy,
            reviewer_identity="Synthetic qualified reviewer",
            qualification_summary="Fixture only",
            independence_statement="Fixture only",
            evidence_reference="REVIEW-PACKAGE-2",
            reviewed_on=date(2026, 10, 18),
            review_scope="Synthetic source package",
            disposition=PolicyReviewDisposition.ACCEPTED,
            created_by=self.platform,
        )
        payload = {
            "schema_version": 1,
            "ytd_treatment": {
                "source_reference": source.source_identifier,
                "description": "Synthetic period treatment; no statutory cumulative formula",
            },
            "retroactivity": {
                "source_reference": "REVIEW-PACKAGE-2",
                "description": "Synthetic successor-only handling",
            },
            "evidence_references": [source.source_identifier, "REVIEW-PACKAGE-2"],
        }
        return previous, policy, payload

    def _import(self, policy, payload):
        return import_statutory_source_package(
            actor=self.platform,
            policy_version=policy,
            payload=payload,
            reason="Synthetic source package import",
        )

    def _resolve(self, on_date=date(2027, 1, 1)):
        return resolve_statutory_source_package(
            code=PAYROLL_TAX_REGULATORY_POLICY_CODE,
            consumer="payroll.statutory_tax.calculate",
            on_date=on_date,
        )

    def test_import_publication_effective_date_history_and_audit(self):
        previous, policy, payload = self._draft()
        package = self._import(policy, payload)
        self.assertEqual(package.supersedes_id, previous.payroll_source_package.pk)
        self.assertEqual(self._import(policy, payload).pk, package.pk)
        self.assertEqual(self._resolve()[0].pk, previous.pk)  # draft is inactive
        activate_statutory_source_package(
            actor=self.platform,
            package=package,
            reason="Synthetic framework validation",
        )
        selected, retained = self._resolve()
        self.assertEqual(selected.pk, policy.pk)
        self.assertEqual(retained.pk, package.pk)
        self.assertEqual(self._resolve(date(2026, 12, 31))[0].pk, previous.pk)
        self.assertEqual(
            previous.payroll_source_package.content["policy"]["version"], 1
        )
        event = AuditEvent.objects.get(
            action=AuditAction.PLATFORM_POLICY_VERSION_PUBLISHED,
            entity_id=str(policy.pk),
        )
        self.assertEqual(event.actor_id, self.platform.pk)
        self.assertEqual(retained.imported_by_id, self.platform.pk)
        with self.assertRaises(ValidationError):
            activate_statutory_source_package(
                actor=self.platform, package=package, reason="Again"
            )

    def test_missing_metadata_unknown_schema_and_untraced_evidence_fail_closed(self):
        _, policy, payload = self._draft()
        variants = []
        for key, value in (
            ("schema_version", 2),
            ("schema_version", True),
            ("ytd_treatment", {}),
            ("retroactivity", {}),
            ("evidence_references", []),
            ("evidence_references", ["INVENTED"]),
            ("unexpected", "value"),
        ):
            variant = deepcopy(payload)
            variant[key] = value
            variants.append(variant)
        for variant in variants:
            with self.subTest(payload=variant), self.assertRaises(ValidationError):
                self._import(policy, variant)
        self.assertFalse(
            StatutorySourcePackage.objects.filter(policy_version=policy).exists()
        )

    def test_missing_external_source_or_review_rejects_import(self):
        _, policy, payload = self._draft()
        policy.review_evidence.all().delete()
        with self.assertRaises(ValidationError):
            self._import(policy, payload)
        policy.sources.clear()
        with self.assertRaises(ValidationError):
            self._import(policy, payload)

    def test_append_only_model_and_unique_policy_version(self):
        _, policy, payload = self._draft()
        package = self._import(policy, payload)
        with self.assertRaises(ValidationError):
            package.save()
        with self.assertRaises(ValidationError):
            package.delete()
        with self.assertRaises(ValidationError):
            StatutorySourcePackage.objects.filter(pk=package.pk).update(
                reason="Changed"
            )
        with self.assertRaises(ValidationError):
            StatutorySourcePackage.objects.filter(pk=package.pk).delete()
        with self.assertRaises(IntegrityError), transaction.atomic():
            StatutorySourcePackage.objects.bulk_create(
                [
                    StatutorySourcePackage(
                        policy_version=policy,
                        schema_version=1,
                        content=package.content,
                        content_digest=package.content_digest,
                        imported_by=self.platform,
                        reason="Duplicate",
                    )
                ]
            )

    def test_policy_drift_and_conflicting_reimport_do_not_activate(self):
        _, policy, payload = self._draft()
        package = self._import(policy, payload)
        changed = deepcopy(payload)
        changed["ytd_treatment"]["description"] = "Changed"
        with self.assertRaises(ValidationError):
            self._import(policy, changed)
        policy.parameters["brackets"][0]["rate"] = "11"  # synthetic input only
        policy.save()
        with self.assertRaises(ValidationError):
            activate_statutory_source_package(
                actor=self.platform, package=package, reason="Drift"
            )
        policy.refresh_from_db()
        self.assertEqual(policy.status, PolicyVersionStatus.DRAFT)

    def test_content_digest_is_validated_at_the_model_boundary(self):
        _, policy, payload = self._draft()
        package = self._import(policy, payload)
        package.content_digest = "0" * 64
        with self.assertRaises(ValidationError):
            package.full_clean()

    def test_activation_rolls_back_policy_publication_when_audit_fails(self):
        _, policy, payload = self._draft()
        package = self._import(policy, payload)
        with (
            patch(
                "apps.organizations.policy_services.record_audit_event",
                side_effect=RuntimeError("Synthetic audit failure"),
            ),
            self.assertRaises(RuntimeError),
        ):
            activate_statutory_source_package(
                actor=self.platform, package=package, reason="Atomic fixture"
            )
        policy.refresh_from_db()
        self.assertEqual(policy.status, PolicyVersionStatus.DRAFT)
        self.assertIsNone(policy.published_at)

    def test_platform_authority_is_required(self):
        _, policy, payload = self._draft()
        with self.assertRaises(PermissionDenied):
            import_statutory_source_package(
                actor=self.owner,
                policy_version=policy,
                payload=payload,
                reason="Denied",
            )
        package = self._import(policy, payload)
        with self.assertRaises(PermissionDenied):
            activate_statutory_source_package(
                actor=self.owner, package=package, reason="Denied"
            )

    def test_published_policy_without_package_cannot_be_consumed(self):
        _, policy, _ = self._draft()
        policy.effective_from = date(2026, 10, 1)
        policy.save()
        PlatformPolicyVersion.objects.filter(pk=policy.pk).update(
            status=PolicyVersionStatus.PUBLISHED,
            published_by=self.platform,
            published_at=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            self._resolve()
        with self.assertRaises(ValidationError):
            calculate_statutory(
                organization=self.organization,
                actor=self.actor,
                run=self.run,
                kind=StatutoryCalculationKind.PAYROLL_TAX,
                reason="No package",
            )
        # New source packages cannot be attached silently to already-published history.
        with self.assertRaises(ValidationError):
            self._import(policy, self._draft_payload_for(policy))
        self.assertEqual(StatutoryCalculation.objects.count(), 0)

    def _draft_payload_for(self, policy):
        ref = policy.sources.get().source_identifier
        return {
            "schema_version": 1,
            "ytd_treatment": {"source_reference": ref, "description": "Fixture"},
            "retroactivity": {"source_reference": ref, "description": "Fixture"},
            "evidence_references": [ref],
        }

    def test_calculation_pins_schema_rounding_and_source_hooks(self):
        policy = self._published_policy(
            PAYROLL_TAX_REGULATORY_POLICY_CODE, self._tax_parameters()
        )
        result = calculate_statutory(
            organization=self.organization,
            actor=self.actor,
            run=self.run,
            kind=StatutoryCalculationKind.PAYROLL_TAX,
            reason="Synthetic pinned package",
        )
        package = policy.payroll_source_package
        self.assertEqual(result.policy_snapshot["source_package_id"], str(package.pk))
        self.assertEqual(
            result.policy_snapshot["source_package_digest"], package.content_digest
        )
        self.assertEqual(result.policy_snapshot["source_package_schema_version"], 1)
        self.assertEqual(
            result.policy_snapshot["ytd_treatment"], package.content["ytd_treatment"]
        )
        self.assertEqual(
            result.policy_snapshot["parameters"]["rounding"],
            policy.parameters["rounding"],
        )

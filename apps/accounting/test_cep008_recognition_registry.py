import uuid

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.accounting.recognition_registry import (
    UNSPECIFIED_RECOGNITION_POLICY,
    RecognitionIdentity,
    RecognitionRequest,
    ensure_no_competing_recognition,
    registered_recognition_owner_policies,
    resolve_recognition_owner,
)


class RecognitionOwnerRegistryTests(SimpleTestCase):
    organization_id = uuid.uuid4()
    source_identity = uuid.uuid4()

    def _request(self, **overrides: object) -> RecognitionRequest:
        values: dict[str, object] = {
            "organization_id": self.organization_id,
            "source_organization_id": self.organization_id,
            "source_family": "Billing Progress Claim",
            "economic_occurrence": "Approved claim recognized as AR obligation",
            "source_identity": self.source_identity,
            "source_version": 2,
            "recognition_type": "AR receivable recognition",
            "recognition_owner": "Subledgers — source-family AR recognition",
            "object_scope_authorized": True,
        }
        values.update(overrides)
        return RecognitionRequest(**values)  # type: ignore[arg-type]

    def test_registry_contains_the_complete_frozen_matrix(self) -> None:
        policies = registered_recognition_owner_policies()

        self.assertEqual(len(policies), 18)
        self.assertEqual(
            {
                (policy.source_family, policy.economic_occurrence)
                for policy in policies
            }.__len__(),
            18,
        )
        for policy in policies:
            with self.subTest(policy=policy.source_family):
                self.assertTrue(policy.source_identity_rule)
                self.assertTrue(policy.source_version_rule)
                self.assertTrue(policy.recognition_type)
                self.assertTrue(policy.recognition_owner)
                self.assertTrue(policy.creates_obligation)
                self.assertTrue(policy.creates_accounting_entry)
                self.assertTrue(policy.settlement_owner)
                self.assertTrue(policy.reversal_owner)
                self.assertTrue(policy.correction_owner)
                self.assertTrue(policy.reconciliation_requirement)
                self.assertIn("PD-", policy.governing_pd)
                self.assertTrue(policy.integration_contract)
                self.assertTrue(policy.v1_status)

    def test_exact_approved_row_resolves_with_auditable_source_lineage(self) -> None:
        resolution = resolve_recognition_owner(request=self._request())

        self.assertEqual(
            resolution.identity.recognition_owner,
            "Subledgers — source-family AR recognition",
        )
        self.assertEqual(resolution.identity.source_identity, self.source_identity)
        self.assertEqual(resolution.identity.source_version, 2)
        self.assertEqual(
            resolution.audit_metadata()["reconciliation_requirement"],
            "AR obligation ↔ Accounting control account ↔ Treasury settlement",
        )

    def test_unknown_family_or_occurrence_fails_closed(self) -> None:
        for request in (
            self._request(source_family="Unknown"),
            self._request(economic_occurrence="Unknown"),
        ):
            with (
                self.subTest(request=request),
                self.assertRaisesMessage(
                    ValidationError, UNSPECIFIED_RECOGNITION_POLICY
                ),
            ):
                resolve_recognition_owner(request=request)

    def test_unspecified_matrix_row_fails_closed(self) -> None:
        with self.assertRaisesMessage(ValidationError, UNSPECIFIED_RECOGNITION_POLICY):
            resolve_recognition_owner(
                request=self._request(
                    source_family="Negative-Net Payroll Excess",
                    economic_occurrence="Potential Employee Receivable / Carry Forward",
                    recognition_type="Potential receivable/carry-forward",
                    recognition_owner=UNSPECIFIED_RECOGNITION_POLICY + " — STOP",
                )
            )

    def test_wrong_owner_or_type_is_rejected(self) -> None:
        for request in (
            self._request(recognition_owner="Treasury"),
            self._request(recognition_type="Cash / clearing recognition"),
        ):
            with self.subTest(request=request), self.assertRaises(ValidationError):
                resolve_recognition_owner(request=request)

    def test_missing_identity_version_or_type_is_rejected(self) -> None:
        for request in (
            self._request(source_identity=None),
            self._request(source_version=None),
            self._request(source_version=0),
            self._request(recognition_type=""),
        ):
            with self.subTest(request=request), self.assertRaises(ValidationError):
                resolve_recognition_owner(request=request)

    def test_cross_tenant_or_unscoped_source_is_rejected(self) -> None:
        for request in (
            self._request(source_organization_id=uuid.uuid4()),
            self._request(object_scope_authorized=False),
        ):
            with self.subTest(request=request), self.assertRaises(ValidationError):
                resolve_recognition_owner(request=request)

    def test_equivalent_retry_is_idempotent_and_competing_owner_is_rejected(
        self,
    ) -> None:
        resolution = resolve_recognition_owner(request=self._request())

        retry = ensure_no_competing_recognition(
            resolution=resolution,
            existing_recognitions=(resolution.identity,),
        )
        self.assertEqual(retry.resolution, resolution)
        self.assertTrue(retry.is_replay)
        self.assertFalse(
            ensure_no_competing_recognition(
                resolution=resolution,
                existing_recognitions=(),
            ).is_replay
        )
        competing = RecognitionIdentity(
            source_family=resolution.identity.source_family,
            economic_occurrence=resolution.identity.economic_occurrence,
            source_identity=resolution.identity.source_identity,
            source_version=resolution.identity.source_version,
            recognition_type=resolution.identity.recognition_type,
            recognition_owner="Treasury",
        )
        with self.assertRaises(ValidationError):
            ensure_no_competing_recognition(
                resolution=resolution,
                existing_recognitions=(competing,),
            )

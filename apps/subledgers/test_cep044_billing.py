"""Real Billing workflow -> AP/AR -> source-family Accounting L2 evidence."""

from datetime import date
from importlib import import_module
from unittest.mock import patch

from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.accounting.models import Account, ControlAccountMappingVersion
from apps.accounting.recognition_services import (
    prepare_source_recognition,
    reconcile_source_recognition,
)
from apps.accounting.services import create_fiscal_period, create_fiscal_year
from apps.accounting.test_cep042_regression import explicit_fixture_authority
from apps.billing import test_payable_certificates as certificate_scenarios
from apps.billing import tests as claim_scenarios
from apps.organizations.models import (
    BusinessPermission,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
)
from apps.organizations.policy_specs import SUBLEDGER_WRITEOFF_SELF_APPROVAL_POLICY_CODE

from . import tests as foundation
from .services import recognize_obligation
from .test_cep044_writeoffs import CEP044Fixture


class BillingRecognitionFixture:
    accounting_mapping = CEP044Fixture.accounting_mapping
    proposal = CEP044Fixture.proposal
    approve = CEP044Fixture.approve
    correct = CEP044Fixture.correct
    _activate_policy = foundation.SubledgerFoundationTests._activate_policy

    def set_up_native(self, native):
        # Historical Billing scenarios predate explicit membership-role cutover.
        # Supply their authority at fixture creation, never weaken production checks.
        original_save = OrganizationMembership.save
        # TransactionTestCase flush does not replay historical data migrations.
        # Restore only the exact approved Billing templates needed by this fixture.
        for module, callback in (
            (
                "0018_project_baseline_compatibility_catalog",
                "seed_project_baseline_catalog",
            ),
            (
                "0019_progress_verification_compatibility_catalog",
                "seed_progress_catalog",
            ),
            (
                "0020_progress_claim_approval_compatibility_catalog",
                "seed_progress_claim_catalog",
            ),
        ):
            getattr(import_module(f"apps.workflows.migrations.{module}"), callback)(
                apps, None
            )

        def save_with_explicit_authority(membership, *args, **kwargs):
            adding = membership._state.adding
            original_save(membership, *args, **kwargs)
            if adding and membership.status == "active":
                role = OrganizationRole.objects.create(
                    organization=membership.organization,
                    code=f"cep044-native-{membership.pk}",
                    name="Explicit native fixture authority",
                )
                role.permissions.set(BusinessPermission.objects.filter(is_active=True))
                explicit_fixture_authority(membership, role)

        with patch.object(OrganizationMembership, "save", save_with_explicit_authority):
            native.setUp()

    def configure(self, native, source_kind, direction):
        self.organization, self.owner, self.approver = (
            native.organization,
            native.owner,
            native.manager,
        )
        for actor in (self.owner, self.approver):
            membership = self.organization.memberships.get(user=actor)
            role = OrganizationRole.objects.create(
                code=f"cep044-billing-{actor.pk}", name="Explicit fixture authority"
            )
            role.permissions.set(BusinessPermission.objects.filter(is_active=True))
            explicit_fixture_authority(membership, role)
        self.owner_membership = self.organization.memberships.get(user=self.owner)
        OrganizationSettings.objects.get_or_create(
            organization=self.organization,
            defaults={"timezone": "UTC", "currency": "IRR"},
        )
        self.control = Account.objects.create(
            organization=self.organization,
            code="BILL044",
            name="Explicit control",
            account_type="asset" if direction == "receivable" else "liability",
            is_posting=True,
            created_by=self.owner,
        )
        ControlAccountMappingVersion.objects.create(
            organization=self.organization,
            source_kind=source_kind,
            direction=direction,
            version=1,
            control_account=self.control,
            effective_from=date(2026, 1, 1),
            reason="Explicit test mapping",
            created_by=self.owner_membership,
        )
        self.counterpart = Account.objects.create(
            organization=self.organization,
            code="BILL044C",
            name="Explicit counterpart",
            account_type="expense",
            is_posting=True,
            created_by=self.owner,
        )
        year = create_fiscal_year(
            organization=self.organization,
            actor=self.owner,
            code="BILL044",
            name="Year",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            calendar_version=1,
        )
        create_fiscal_period(
            organization=self.organization,
            actor=self.owner,
            fiscal_year=year,
            number=1,
            name="Period",
            starts_on=year.starts_on,
            ends_on=year.ends_on,
        )
        self._activate_policy(
            SUBLEDGER_WRITEOFF_SELF_APPROVAL_POLICY_CODE, {"allow_self_approval": False}
        )

    def handoff(self, native, kind, source_kind, family, direction):
        self.target = recognize_obligation(
            organization=self.organization,
            actor=self.owner,
            source_kind=source_kind,
            source_uuid=native.pk,
            source_version=native.revision_number,
            idempotency_key=f"{kind}:{native.pk}",
        )
        self.day = self.target.recognized_on
        debit, credit = (
            (self.control, self.counterpart)
            if direction == "receivable"
            else (self.counterpart, self.control)
        )
        self.accounting_mapping(
            family,
            "receivable_recognized"
            if direction == "receivable"
            else "payable_recognized",
            debit,
            credit,
        )
        self.accounting_mapping(
            "AP/AR Write-off", f"{direction}_written_off", credit, debit
        )
        effect = prepare_source_recognition(
            organization=self.organization,
            actor=self.approver,
            source_kind=kind,
            source_id=native.pk,
        )
        self.assertEqual(
            effect.pk,
            prepare_source_recognition(
                organization=self.organization,
                actor=self.approver,
                source_kind=kind,
                source_id=native.pk,
            ).pk,
        )
        self.assertEqual(effect.source_uuid, native.pk)
        self.assertIn(str(native.revision_number), effect.source_version_reference)
        self.assertEqual(
            reconcile_source_recognition(
                organization=self.organization, actor=self.approver, effect=effect
            )["status"],
            "matched",
        )
        original = self.approve()
        correction = self.correct(original)
        for identity in correction.accounting_evidence.values():
            if identity:
                from apps.accounting.recognition_models import SourceRecognitionDraft

                target = SourceRecognitionDraft.objects.get(pk=identity)
                self.assertEqual(
                    reconcile_source_recognition(
                        organization=self.organization,
                        actor=self.approver,
                        effect=target,
                    )["status"],
                    "matched",
                )


class BillingARRecognitionTests(BillingRecognitionFixture, TestCase):
    def test_approved_native_claim_and_ar_writeoff_reversal(self):
        native = claim_scenarios.ProgressClaimApprovalWorkflowTests(
            methodName="runTest"
        )
        self.set_up_native(native)
        self.configure(native, "billing.progress_claim.v1", "receivable")
        native._configure_reporting_line()
        draft = native._claim_for_approval()
        with self.assertRaises(ValidationError):
            recognize_obligation(
                organization=self.organization,
                actor=self.owner,
                source_kind="billing.progress_claim.v1",
                source_uuid=draft.pk,
                source_version=draft.revision_number,
                idempotency_key="unapproved",
            )
        with self.assertRaises(PermissionDenied):
            prepare_source_recognition(
                organization=self.organization,
                actor=self.approver,
                source_kind="ar_claim",
                source_id=draft.pk,
            )
        claim = native._approve_claim(draft)
        self.handoff(
            claim,
            "ar_claim",
            "billing.progress_claim.v1",
            "Billing Progress Claim",
            "receivable",
        )


class BillingAPRecognitionTests(BillingRecognitionFixture, TestCase):
    def test_approved_native_certificate_and_ap_writeoff_reversal(self):
        native = certificate_scenarios.PayableCertificateTests(methodName="runTest")
        self.set_up_native(native)
        self.configure(native, "billing.payable_certificate.v1", "payable")
        native._measurement()
        draft = native._certificate()
        with self.assertRaises(ValidationError):
            recognize_obligation(
                organization=self.organization,
                actor=self.owner,
                source_kind="billing.payable_certificate.v1",
                source_uuid=draft.pk,
                source_version=draft.revision_number,
                idempotency_key="unapproved",
            )
        certificate = native._approve(draft)
        self.handoff(
            certificate,
            "ap_certificate",
            "billing.payable_certificate.v1",
            "Billing Payable Certificate",
            "payable",
        )

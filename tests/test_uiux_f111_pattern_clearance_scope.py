"""BATCH-02 clearance reader integration; all fixtures are disposable test data."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.billing.commercial_services import (
    create_retention_release,
    get_compliance_evidence,
)
from apps.billing.forms import RetentionReleaseCorrectionForm, RetentionReleaseForm
from apps.billing.models import (
    ComplianceEvidenceKind,
    ComplianceEvidenceStatus,
    ContractComplianceEvidence,
    EvidenceExpiryKind,
    PayableCertificate,
    PayableCertificateAdjustment,
    RetentionRelease,
)
from apps.contracts.models import ContractTermVersion, RetentionReleaseRequirement
from apps.organizations.authorization import get_active_membership
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermissionCode,
    MembershipRole,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationStatus,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from tests import test_uiux_f111_pattern_commercial_scope as batch01


class ClearanceCreateScopeTests(TestCase):
    # Reuse established disposable identity/Contract/DMS builders, not its tests.
    make_membership = batch01.CommercialCreateScopeTests.__dict__["make_membership"]
    make_document = batch01.CommercialCreateScopeTests.__dict__["make_document"]
    make_version = batch01.CommercialCreateScopeTests.__dict__["make_version"]

    @classmethod
    def setUpTestData(cls):
        batch01.CommercialCreateScopeTests.setUpTestData.__func__(cls)
        cls.clearances = {}
        for key in "ABCDX":
            cls.clearances[key] = cls.make_clearance(key)
        cls.clearances["DRAFT"] = cls.make_clearance("DRAFT", status="draft")
        cls.clearances["INSURANCE"] = cls.make_clearance(
            "INSURANCE", evidence_kind="insurance"
        )
        for key in "AB":
            contract = cls.contracts[key]
            term = ContractTermVersion.objects.create(
                organization=cls.org,
                contract=contract,
                version=1,
                effective_from=date(2026, 1, 1),
                retention_rate=Decimal(10),
                retention_cap=Decimal(100),
                retention_release_requirement=RetentionReleaseRequirement.APPROVED_CLEARANCE,
                retention_release_cap=Decimal(100),
                reason="Disposable explicit approved release terms",
                created_by=cls.owner,
            )
            ContractTermVersion.objects.filter(pk=term.pk).update(
                status="approved",
                approved_by=cls.user,
                approved_at=timezone.now(),
                approval_reason="Disposable approved snapshot",
            )
            certificate = PayableCertificate.objects.create(
                organization=cls.org,
                project=contract.project,
                contract=contract,
                contract_term_version=term,
                party_identity_snapshot=contract.party.identity_snapshots.first(),
                certificate_number=1,
                period_start=date(2026, 2, 1),
                period_end=date(2026, 2, 28),
                measurement_cutoff=date(2026, 2, 28),
                currency_code="IRR",
                due_date=date(2026, 3, 28),
                gross_amount=Decimal(1000),
                adjustment_amount=Decimal(-100),
                net_amount=Decimal(900),
                created_by=cls.owner,
                updated_by=cls.owner,
            )
            PayableCertificateAdjustment.objects.create(
                certificate=certificate,
                adjustment_type="retention",
                description="Disposable retained amount",
                amount=Decimal(-100),
            )
            PayableCertificate.objects.filter(pk=certificate.pk).update(
                status="approved",
                approved_by=cls.owner,
                approved_at=timezone.now(),
                approval_reason="Disposable retained certificate snapshot",
            )

    @classmethod
    def make_clearance(cls, key, **overrides):
        contract = cls.contracts[key if key in "ABCDX" else "A"]
        values = {
            "organization": contract.organization,
            "project": contract.project,
            "contract": contract,
            "party_identity_snapshot": contract.party.identity_snapshots.first(),
            "evidence_kind": ComplianceEvidenceKind.CLEARANCE,
            "reference": f"B02-CLEARANCE-{key}",
            "revision_reason": "Disposable original clearance evidence",
            "issuing_authority": "Disposable test authority",
            "effective_from": date(2026, 1, 1),
            "expiry_kind": EvidenceExpiryKind.OPEN_ENDED,
            "document_version": cls.versions[key if key in "ABCDX" else "A"],
            "status": ComplianceEvidenceStatus.APPROVED,
            "approved_by": cls.user,
            "approved_at": timezone.now(),
            "decision_reason": "Disposable approved snapshot",
            "created_by": cls.owner,
            "updated_by": cls.owner,
        }
        values.update(overrides)
        return ContractComplianceEvidence.objects.create(**values)

    def setUp(self):
        self.login(self.user)

    def login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.org.pk)
        session.save()

    def form(self, data=None, actor=None, **overrides):
        actor = actor or self.user
        context = {
            "organization": self.org,
            "actor": actor,
            "membership": get_active_membership(user=actor, organization=self.org),
        }
        context.update(overrides)
        return RetentionReleaseForm(data=data, **context)

    def payload(self, key="B", clearance="B"):
        return {
            "contract": str(self.contracts[key].pk),
            "evidence_document_version": str(self.versions[key].pk),
            "release_date": "2026-10-22",
            "amount": "1",
            "clearance_evidence": str(self.clearances[clearance].pk),
        }

    def state(self):
        return (
            list(RetentionRelease.objects.values()),
            list(ContractComplianceEvidence.objects.values()),
            list(AuditEvent.objects.values()),
        )

    def assert_hidden(self, response, keys="ABCDX"):
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        for key in keys:
            evidence = self.clearances[key]
            for token in (str(evidence.pk), str(evidence), evidence.reference):
                self.assertNotIn(token, body)

    def test_limited_actor_with_view_capability_has_no_clearances_in_form_or_get(self):
        with self.assertRaises(PermissionDenied):
            get_compliance_evidence(actor=self.user, organization=self.org)
        self.assertFalse(self.form().fields["clearance_evidence"].queryset.exists())
        self.assert_hidden(self.client.get(reverse("billing:retention_release_create")))

    def test_organization_view_positive_preserves_kind_approval_and_tenant_filters(
        self,
    ):
        expected = {self.clearances[key].pk for key in "ABCD"}
        field = self.form(actor=self.owner).fields["clearance_evidence"]
        self.assertSetEqual(set(field.queryset.values_list("pk", flat=True)), expected)
        canonical = get_compliance_evidence(actor=self.owner, organization=self.org)
        self.assertSetEqual(
            set(
                canonical.filter(
                    evidence_kind="clearance", status="approved"
                ).values_list("pk", flat=True)
            ),
            expected,
        )
        self.login(self.owner)
        response = self.client.get(reverse("billing:retention_release_create"))
        for key in "ABCD":
            self.assertContains(response, str(self.clearances[key].pk))
            self.assertContains(response, str(self.clearances[key]))
        self.assert_hidden(response, ("X", "DRAFT", "INSURANCE"))
        self.assertTrue(self.form(self.payload(), actor=self.owner).is_valid())

    def test_organization_without_view_permission_has_empty_choices(self):
        role = OrganizationRole.objects.get(code=MembershipRole.COMPANY_OWNER)
        role.permissions.remove(
            role.permissions.get(code=BusinessPermissionCode.COMPLIANCE_EVIDENCE_VIEW)
        )
        self.assertFalse(
            self.form(actor=self.owner).fields["clearance_evidence"].queryset.exists()
        )
        self.login(self.owner)
        self.assert_hidden(self.client.get(reverse("billing:retention_release_create")))

    def test_missing_wrong_tenant_and_mismatched_contexts_fail_closed(self):
        for context in (
            {"membership": None},
            {"membership": self.other_member},
            {"actor": None, "membership": self.owner_member},
            {"actor": self.owner, "membership": self.member},
        ):
            with self.subTest(context=context):
                arguments = {
                    "organization": self.org,
                    "actor": self.owner,
                    "membership": self.owner_member,
                } | context
                form = RetentionReleaseForm(**arguments)
                self.assertFalse(form.fields["clearance_evidence"].queryset.exists())

    def test_absent_revoked_expired_future_and_site_only_scope_fail_closed(self):
        grants = MembershipScopeGrant.objects.filter(membership=self.owner_member)
        for state in ("revoked", "expired", "future", "absent", "site-only"):
            with self.subTest(state=state):
                grants.update(
                    revoked_at=None,
                    starts_at=timezone.now() - timedelta(days=2),
                    ends_at=None,
                )
                if state == "revoked":
                    grants.update(revoked_at=timezone.now())
                elif state == "expired":
                    grants.update(ends_at=timezone.now() - timedelta(days=1))
                elif state == "future":
                    grants.update(starts_at=timezone.now() + timedelta(days=1))
                else:
                    grants.update(revoked_at=timezone.now())
                    if state == "site-only":
                        MembershipScopeGrant.objects.create(
                            organization=self.org,
                            membership=self.owner_member,
                            scope_type=AuthorizationScopeType.SITE,
                            project=self.projects["A"],
                            site=self.site,
                            reason="Disposable site scope",
                        )
                self.assertFalse(
                    self.form(actor=self.owner)
                    .fields["clearance_evidence"]
                    .queryset.exists()
                )

    def test_inactive_context_and_capability_absence_deny_http(self):
        self.login(self.owner)
        for model, pk, field, value, restore in (
            (
                OrganizationMembership,
                self.owner_member.pk,
                "status",
                MembershipStatus.SUSPENDED,
                MembershipStatus.ACTIVE,
            ),
            (User, self.owner.pk, "is_active", False, True),
            (
                Organization,
                self.org.pk,
                "status",
                OrganizationStatus.SUSPENDED,
                OrganizationStatus.ACTIVE,
            ),
        ):
            with self.subTest(context=model.__name__):
                model.objects.filter(pk=pk).update(**{field: value})
                actor = User.objects.get(pk=self.owner.pk)
                org = Organization.objects.get(pk=self.org.pk)
                form = RetentionReleaseForm(
                    organization=org, actor=actor, membership=self.owner_member
                )
                self.assertFalse(form.fields["clearance_evidence"].queryset.exists())
                self.assertIn(
                    self.client.get(
                        reverse("billing:retention_release_create")
                    ).status_code,
                    (302, 403),
                )
                model.objects.filter(pk=pk).update(**{field: restore})
                self.login(self.owner)
        role = OrganizationRole.objects.get(code=MembershipRole.COMPANY_OWNER)
        role.permissions.remove(
            role.permissions.get(code=BusinessPermissionCode.RETENTION_RELEASES_CREATE)
        )
        self.assertEqual(
            self.client.get(reverse("billing:retention_release_create")).status_code,
            403,
        )
        MembershipRoleAssignment.objects.filter(membership=self.owner_member).update(
            revoked_at=timezone.now()
        )
        self.assertFalse(
            self.form(actor=self.owner).fields["clearance_evidence"].queryset.exists()
        )

    def test_forced_same_tenant_and_cross_tenant_post_rejected_without_leak_or_write(
        self,
    ):
        base = self.payload() | {"clearance_evidence": ""}
        self.assertTrue(self.form(base).is_valid())
        for key in "ABCDX":
            with self.subTest(clearance=key):
                data = base | {"clearance_evidence": str(self.clearances[key].pk)}
                form = self.form(data)
                self.assertFalse(form.is_valid())
                self.assertEqual(set(form.errors), {"clearance_evidence"})
                before = self.state()
                response = self.client.post(
                    reverse("billing:retention_release_create"), data
                )
                self.assert_hidden(response)
                self.assertFormError(
                    response.context["form"],
                    "clearance_evidence",
                    form.errors["clearance_evidence"],
                )
                self.assertEqual(before, self.state())

    def test_missing_required_field_and_service_rejection_redisplay_stay_scoped(self):
        data = self.payload() | {"clearance_evidence": ""}
        data.pop("amount")
        self.assert_hidden(
            self.client.post(reverse("billing:retention_release_create"), data)
        )
        before = self.state()
        # Existing approved-clearance term denies blank clearance in the actual service.
        response = self.client.post(
            reverse("billing:retention_release_create"),
            self.payload() | {"clearance_evidence": ""},
        )
        self.assert_hidden(response)
        self.assertTrue(response.context["form"].is_valid())
        self.assertTrue(list(response.context["messages"]))
        self.assertEqual(before, self.state())

    def test_organization_http_success_uses_approved_terms_and_retained_capacity(self):
        self.login(self.owner)
        response = self.client.post(
            reverse("billing:retention_release_create"), self.payload()
        )
        self.assertEqual(response.status_code, 302)
        release = RetentionRelease.objects.get()
        self.assertEqual(release.clearance_evidence_id, self.clearances["B"].pk)
        self.assertEqual(release.available_amount_snapshot, Decimal(100))

    def service(self, **overrides):
        return create_retention_release(
            **(
                {
                    "organization": self.org,
                    "actor": self.owner,
                    "contract": self.contracts["B"],
                    "release_date": date(2026, 10, 22),
                    "amount": Decimal(1),
                    "evidence_document_version": self.versions["B"],
                    "clearance_evidence": self.clearances["B"],
                }
                | overrides
            )
        )

    def test_existing_clearance_contract_date_kind_and_approval_validation(self):
        for key in ("A", "X", "DRAFT", "INSURANCE"):
            with self.subTest(clearance=key), self.assertRaises(ValidationError):
                self.service(clearance_evidence=self.clearances[key])
        for attrs in (
            {"effective_from": date(2027, 1, 1)},
            {"expiry_kind": "dated", "expires_on": date(2026, 10, 21)},
            {"status": "draft", "approved_by_id": None, "approved_at": None},
            {"evidence_kind": "insurance"},
        ):
            with self.subTest(invalid=attrs):
                original = {key: getattr(self.clearances["B"], key) for key in attrs}
                ContractComplianceEvidence.objects.filter(
                    pk=self.clearances["B"].pk
                ).update(**attrs)
                with self.assertRaises(ValidationError):
                    self.service()
                ContractComplianceEvidence.objects.filter(
                    pk=self.clearances["B"].pk
                ).update(**original)
        self.assertFalse(RetentionRelease.objects.exists())

    def test_existing_term_amount_and_contract_service_gates(self):
        term = ContractTermVersion.objects.get(contract=self.contracts["B"])
        for attrs in (
            {"status": "draft", "approved_by_id": None, "approved_at": None},
            {"effective_from": date(2027, 1, 1)},
            {"retention_release_requirement": "unconfigured"},
            {"retention_release_cap": Decimal(0)},
        ):
            with self.subTest(term=attrs):
                original = {key: getattr(term, key) for key in attrs}
                ContractTermVersion.objects.filter(pk=term.pk).update(**attrs)
                with self.assertRaises(ValidationError):
                    self.service()
                ContractTermVersion.objects.filter(pk=term.pk).update(**original)
        with self.assertRaises(ValidationError):
            self.service(amount=Decimal(101))
        for key in "CDX":
            with self.subTest(contract=key), self.assertRaises(PermissionDenied):
                self.service(actor=self.user, contract=self.contracts[key])
        role = OrganizationRole.objects.get(code=MembershipRole.COMPANY_OWNER)
        role.permissions.remove(
            role.permissions.get(code=BusinessPermissionCode.RETENTION_RELEASES_CREATE)
        )
        with self.assertRaises(PermissionDenied):
            self.service()

    def test_writer_reader_separation_and_correction_behavior_unchanged(self):
        # Writer checks project create authority and clearance validity, not enumeration.
        with self.assertRaises(PermissionDenied):
            get_compliance_evidence(actor=self.user, organization=self.org)
        release = self.service(actor=self.user)
        self.assertEqual(release.clearance_evidence_id, self.clearances["B"].pk)
        correction = RetentionReleaseCorrectionForm(organization=self.org)
        self.assertIn(
            self.clearances["C"], correction.fields["clearance_evidence"].queryset
        )
        with patch(
            "apps.billing.forms.get_compliance_evidence", side_effect=PermissionDenied
        ):
            self.assertFalse(
                self.form(actor=self.owner)
                .fields["clearance_evidence"]
                .queryset.exists()
            )

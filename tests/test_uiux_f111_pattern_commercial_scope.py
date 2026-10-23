"""BATCH-01 integration controls; synthetic records live only in the test DB."""

from datetime import date, timedelta
from decimal import Decimal
from typing import ClassVar
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.billing.commercial_services import (
    create_compliance_evidence,
    create_guarantee,
    create_retention_release,
)
from apps.billing.forms import (
    ComplianceEvidenceForm,
    ComplianceEvidenceRevisionForm,
    GuaranteeForm,
    GuaranteeRevisionForm,
    RetentionReleaseCorrectionForm,
    RetentionReleaseForm,
)
from apps.billing.models import (
    ContractComplianceEvidence,
    ContractGuarantee,
    RetentionRelease,
)
from apps.contracts.models import (
    Contract,
    ContractDirection,
    ContractStatus,
    ContractType,
)
from apps.documents.link_registry import create_typed_link
from apps.documents.models import (
    Document,
    DocumentLink,
    DocumentProcessingAssessment,
    DocumentProcessingVerdict,
    DocumentRetentionClassification,
    DocumentVersion,
)
from apps.documents.services import (
    get_organization_document,
    get_organization_documents,
)
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
from apps.parties.models import BusinessParty, PartyIdentitySnapshot, PartyKind
from apps.projects.models import Project, ProjectSite


class CommercialCreateScopeTests(TestCase):
    surfaces: ClassVar[dict] = {
        "guarantee": (
            GuaranteeForm,
            "billing:guarantee_create",
            "evidence_document_version",
        ),
        "compliance": (
            ComplianceEvidenceForm,
            "billing:compliance_evidence_create",
            "document_version",
        ),
        "retention": (
            RetentionReleaseForm,
            "billing:retention_release_create",
            "evidence_document_version",
        ),
    }

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Batch01 A", slug="batch01-a")
        cls.other_org = Organization.objects.create(name="Batch01 X", slug="batch01-x")
        cls.user = User.objects.create_user(username="batch01-scoped")
        cls.owner = User.objects.create_user(username="batch01-organization")
        cls.other_user = User.objects.create_user(username="batch01-other")
        cls.member = cls.make_membership(cls.user, cls.org)
        cls.owner_member = cls.make_membership(cls.owner, cls.org)
        cls.other_member = cls.make_membership(cls.other_user, cls.other_org)
        MembershipScopeGrant.objects.create(
            organization=cls.org,
            membership=cls.owner_member,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Disposable test scope",
        )
        cls.projects, cls.contracts, cls.documents, cls.versions = {}, {}, {}, {}
        for key in "ABCDX":
            org = cls.other_org if key == "X" else cls.org
            cls.projects[key] = Project.objects.create(
                organization=org,
                code=f"B01-P-{key}",
                name=f"Batch01 Project {key}",
            )
            party = BusinessParty.objects.create(
                organization=org,
                party_kind=PartyKind.COMPANY,
                display_name=f"Batch01 Party {key}",
            )
            PartyIdentitySnapshot.objects.create(
                organization=org,
                party=party,
                sequence=1,
                party_kind=party.party_kind,
                display_name=party.display_name,
                normalized_display_name=party.display_name,
                reason="Disposable identity evidence",
                recorded_by=cls.owner,
            )
            cls.contracts[key] = Contract.objects.create(
                organization=org,
                project=cls.projects[key],
                party=party,
                contract_number=f"B01-CON-{key}",
                title=f"Batch01 Contract {key}",
                counterparty_name=party.display_name,
                direction=ContractDirection.PAYABLE,
                contract_type=ContractType.SUBCONTRACT,
                status=ContractStatus.ACTIVE,
            )
            cls.documents[key], cls.versions[key] = cls.make_document(
                f"B01-DOC-{key}",
                org,
                [cls.projects[key]],
            )
            if key in "AB":
                MembershipScopeGrant.objects.create(
                    organization=cls.org,
                    membership=cls.member,
                    scope_type=AuthorizationScopeType.PROJECT,
                    project=cls.projects[key],
                    reason="Disposable explicit A/B grant",
                )
        cls.documents["MIX"], cls.versions["MIX"] = cls.make_document(
            "B01-MIXED-CONTEXT",
            cls.org,
            [cls.projects["A"], cls.projects["C"]],
        )
        for key in ("SEALED", "EXPIRED", "UNLINKED", "BROKEN"):
            cls.documents[key], cls.versions[key] = cls.make_document(
                f"B01-{key}",
                cls.org,
                [] if key == "UNLINKED" else [cls.projects["A"]],
                broken=key == "BROKEN",
            )
        Document.objects.filter(pk=cls.documents["SEALED"].pk).update(
            retention_classification=DocumentRetentionClassification.SEALED_SUPPLIER_QUOTE_EVIDENCE,
        )
        Document.objects.filter(pk=cls.documents["EXPIRED"].pk).update(
            access_expires_at=timezone.now() - timedelta(days=1),
        )
        cls.historical = cls.versions["A"]
        cls.current = cls.make_version(cls.documents["A"], 2)
        Document.objects.filter(pk=cls.documents["A"].pk).update(
            current_version=cls.current
        )
        cls.site = ProjectSite.objects.create(
            organization=cls.org,
            project=cls.projects["A"],
            code="B01-SITE",
            name="Batch01 site",
        )

    @classmethod
    def make_membership(cls, user, org):
        # Existing migration-seeded role and permission catalogue; no new roles.
        member = OrganizationMembership.objects.create(
            organization=org,
            user=user,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=org,
            membership=member,
            role=OrganizationRole.objects.get(code=MembershipRole.COMPANY_OWNER),
            reason="Disposable explicit test assignment",
        )
        return member

    @classmethod
    def make_document(cls, label, org, projects, *, broken=False):
        document = Document.objects.create(
            organization=org,
            document_number=label,
            title=f"{label} unique title",
        )
        version = cls.make_version(document, 1)
        Document.objects.filter(pk=document.pk).update(current_version=version)
        for project in projects:
            legacy = DocumentLink.objects.create(
                organization=org, document=document, project=project
            )
            if not broken:
                create_typed_link(
                    target_type="project", target=project, legacy_link=legacy
                )
        return document, version

    @classmethod
    def make_version(cls, document, number):
        # File metadata only: never write PDFs into the checkout or Development.
        version = DocumentVersion.objects.create(
            organization=document.organization,
            document=document,
            version_number=number,
            original_file_name=f"test-{number}.pdf",
            file=f"disposable/test-{number}.pdf",
            content_type="application/pdf",
            file_size=11,
            sha256="a" * 64,
        )
        DocumentProcessingAssessment.objects.create(
            organization=document.organization,
            version=version,
            sequence=1,
            verdict=DocumentProcessingVerdict.CLEAN,
            input_sha256=version.sha256,
            adapter_code="test-scanner",
            recorded_by=cls.owner,
        )
        return version

    def setUp(self):
        self.client.force_login(self.user)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.org.pk)
        session.save()

    def form(self, surface, data=None, **overrides):
        options = {
            "organization": self.org,
            "actor": self.user,
            "membership": get_active_membership(user=self.user, organization=self.org),
        }
        options.update(overrides)
        return self.surfaces[surface][0](data=data, **options)

    def payload(self, surface, contract="A", version="A"):
        data = {
            "contract": str(self.contracts[contract].pk),
            self.surfaces[surface][2]: str(self.versions[version].pk),
        }
        if surface == "guarantee":
            return data | {
                "guarantee_type": "performance",
                "exposure_side": "received",
                "instrument_reference": "B01-G",
                "issuer_name": "Test issuer",
                "amount": "10",
                "issued_on": "2026-10-01",
                "effective_from": "2026-10-01",
                "expiry_kind": "dated",
                "expires_on": "2027-10-01",
                "reason": "Test evidence",
            }
        if surface == "compliance":
            return data | {
                "evidence_kind": "clearance",
                "reference": "B01-E",
                "issuing_authority": "Test authority",
                "effective_from": "2026-10-01",
                "expiry_kind": "dated",
                "expires_on": "2027-10-01",
                "reason": "Test evidence",
            }
        return data | {"release_date": "2026-10-22", "amount": "1"}

    def state(self):
        return tuple(
            m.objects.count()
            for m in (
                ContractGuarantee,
                ContractComplianceEvidence,
                RetentionRelease,
                AuditEvent,
            )
        )

    def assert_no_metadata(self, response):
        body = response.content.decode()
        for key in "CDX":
            for value in (
                str(self.contracts[key].pk),
                self.contracts[key].contract_number,
                self.contracts[key].title,
            ):
                self.assertNotIn(value, body)
        for key in ("C", "D", "X", "MIX", "SEALED", "EXPIRED", "UNLINKED", "BROKEN"):
            self.assertNotIn(str(self.versions[key].pk), body)
            self.assertNotIn(self.documents[key].title, body)

    def test_all_three_initial_forms_and_http_include_only_authorized_metadata(self):
        for surface, (_, route, field) in self.surfaces.items():
            with self.subTest(surface=surface):
                form = self.form(surface)
                self.assertSetEqual(
                    set(form.fields["contract"].queryset),
                    {self.contracts[k] for k in "AB"},
                )
                self.assertSetEqual(
                    set(form.fields[field].queryset),
                    {self.historical, self.current, self.versions["B"]},
                )
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, str(self.contracts["A"].pk))
                self.assertContains(response, str(self.current.pk))
                self.assert_no_metadata(response)

    def test_authorized_b_bound_payload_valid_for_every_form(self):
        for surface in self.surfaces:
            with self.subTest(surface=surface):
                form = self.form(surface, self.payload(surface, "B", "B"))
                self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_forbidden_contract_posts_rejected_without_mutation_or_redisplay_leak(self):
        for surface, (_, route, _) in self.surfaces.items():
            for key in "CDX":
                with self.subTest(surface=surface, key=key):
                    before = self.state()
                    response = self.client.post(
                        reverse(route), self.payload(surface, key)
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertIn("contract", response.context["form"].errors)
                    self.assertEqual(self.state(), before)
                    self.assert_no_metadata(response)

    def test_forbidden_versions_with_authorized_contract_rejected_on_every_route(self):
        for surface, (_, route, field) in self.surfaces.items():
            for key in (
                "C",
                "D",
                "X",
                "MIX",
                "SEALED",
                "EXPIRED",
                "UNLINKED",
                "BROKEN",
            ):
                with self.subTest(surface=surface, version=key):
                    before = self.state()
                    response = self.client.post(
                        reverse(route), self.payload(surface, version=key)
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(field, response.context["form"].errors)
                    self.assertEqual(self.state(), before)
                    self.assert_no_metadata(response)

    def test_missing_required_field_redisplay_remains_scoped(self):
        for surface, (_, route, _) in self.surfaces.items():
            data = self.payload(surface)
            data.pop("reason" if surface != "retention" else "amount")
            response = self.client.post(reverse(route), data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
            self.assert_no_metadata(response)

    def test_missing_wrong_tenant_or_mismatched_actor_context_fails_closed(self):
        for surface, (_, _, field) in self.surfaces.items():
            for context in (
                {"membership": None},
                {"membership": self.other_member},
                {"actor": None},
                {"actor": self.owner},
            ):
                with self.subTest(surface=surface, context=list(context)):
                    form = self.form(surface, **context)
                    self.assertFalse(form.fields["contract"].queryset.exists())
                    self.assertFalse(form.fields[field].queryset.exists())

    def test_no_scope_revoked_expired_and_future_grants_fail_closed(self):
        grants = MembershipScopeGrant.objects.filter(membership=self.member)
        for state in ("revoked", "expired", "future", "absent"):
            with self.subTest(state=state), self.captureOnCommitCallbacks():
                context = {}
                if state == "revoked":
                    grants.update(revoked_at=timezone.now())
                elif state == "expired":
                    grants.update(
                        revoked_at=None,
                        starts_at=timezone.now() - timedelta(days=2),
                        ends_at=timezone.now() - timedelta(days=1),
                    )
                elif state == "future":
                    grants.update(
                        revoked_at=None,
                        starts_at=timezone.now() + timedelta(days=1),
                        ends_at=None,
                    )
                else:
                    actor = User.objects.create_user(username="batch01-no-grants")
                    context = {
                        "actor": actor,
                        "membership": self.make_membership(actor, self.org),
                    }
                for surface, (_, _, field) in self.surfaces.items():
                    form = self.form(surface, **context)
                    self.assertFalse(form.fields["contract"].queryset.exists())
                    self.assertFalse(form.fields[field].queryset.exists())

    def test_inactive_membership_user_and_tenant_deny_http(self):
        for attr, value in (
            ("membership", MembershipStatus.SUSPENDED),
            ("user", False),
            ("organization", OrganizationStatus.SUSPENDED),
        ):
            with self.subTest(context=attr):
                if attr == "membership":
                    OrganizationMembership.objects.filter(pk=self.member.pk).update(
                        status=value
                    )
                elif attr == "user":
                    User.objects.filter(pk=self.user.pk).update(is_active=value)
                else:
                    Organization.objects.filter(pk=self.org.pk).update(status=value)
                for _, route, _ in self.surfaces.values():
                    response = self.client.get(reverse(route))
                    self.assertIn(response.status_code, (302, 403))
                fresh_actor = User.objects.get(pk=self.user.pk)
                fresh_org = Organization.objects.get(pk=self.org.pk)
                for form_class, _, field in self.surfaces.values():
                    form = form_class(
                        organization=fresh_org,
                        actor=fresh_actor,
                        membership=OrganizationMembership.objects.select_related(
                            "user", "organization"
                        ).get(pk=self.member.pk),
                    )
                    self.assertFalse(form.fields["contract"].queryset.exists())
                    self.assertFalse(form.fields[field].queryset.exists())
                OrganizationMembership.objects.filter(pk=self.member.pk).update(
                    status=MembershipStatus.ACTIVE
                )
                User.objects.filter(pk=self.user.pk).update(is_active=True)
                Organization.objects.filter(pk=self.org.pk).update(
                    status=OrganizationStatus.ACTIVE
                )

    def test_revoked_role_denies_all_http_entry_and_dms_choices(self):
        MembershipRoleAssignment.objects.filter(membership=self.member).update(
            revoked_at=timezone.now()
        )
        for surface, (_, route, field) in self.surfaces.items():
            self.assertEqual(self.client.get(reverse(route)).status_code, 403)
            self.assertFalse(self.form(surface).fields[field].queryset.exists())

    def test_missing_dms_view_permission_clears_versions_but_not_contract_choices(self):
        # Temporarily remove an existing test-DB role permission; never create a permission.
        role = OrganizationRole.objects.get(code=MembershipRole.COMPANY_OWNER)
        role.permissions.remove(
            role.permissions.get(code=BusinessPermissionCode.DOCUMENTS_VIEW)
        )
        for surface, (_, _, field) in self.surfaces.items():
            form = self.form(surface)
            self.assertFalse(form.fields[field].queryset.exists())
            self.assertTrue(form.fields["contract"].queryset.exists())

    def test_site_only_grant_does_not_promote_contract_project_authority(self):
        MembershipScopeGrant.objects.filter(membership=self.member).update(
            revoked_at=timezone.now()
        )
        MembershipScopeGrant.objects.create(
            organization=self.org,
            membership=self.member,
            scope_type=AuthorizationScopeType.SITE,
            project=self.projects["A"],
            site=self.site,
            reason="Disposable site-only negative",
        )
        for surface in self.surfaces:
            self.assertFalse(self.form(surface).fields["contract"].queryset.exists())

    def test_dms_canonical_all_link_and_detail_reader_contracts(self):
        readable = set(
            get_organization_documents(user=self.user, organization=self.org)
        )
        self.assertIn(self.documents["A"], readable)
        self.assertNotIn(self.documents["MIX"], readable)
        # Broken legacy/typed linkage can pass list enumeration; detail reader must deny it.
        for key in ("MIX", "SEALED", "EXPIRED", "UNLINKED", "BROKEN", "X"):
            with self.subTest(key=key), self.assertRaises(PermissionDenied):
                get_organization_document(
                    user=self.user,
                    organization=self.org,
                    document_id=str(self.documents[key].pk),
                )

    def test_organization_actor_retains_all_eligible_tenant_choices(self):
        for surface, (_, _, field) in self.surfaces.items():
            form = self.form(surface, actor=self.owner, membership=self.owner_member)
            self.assertSetEqual(
                set(form.fields["contract"].queryset),
                {self.contracts[k] for k in "ABCD"},
            )
            self.assertIn(self.versions["MIX"], form.fields[field].queryset)
            self.assertNotIn(self.versions["X"], form.fields[field].queryset)

    def test_revision_forms_keep_existing_organization_gated_configuration(self):
        for form_class, field in (
            (GuaranteeRevisionForm, "evidence_document_version"),
            (ComplianceEvidenceRevisionForm, "document_version"),
            (RetentionReleaseCorrectionForm, "evidence_document_version"),
        ):
            form = form_class(organization=self.org)
            self.assertIn(self.versions["C"], form.fields[field].queryset)
            self.assertNotIn(self.versions["X"], form.fields[field].queryset)
        for route in (
            "billing:guarantee_detail",
            "billing:compliance_evidence_detail",
            "billing:retention_release_detail",
        ):
            key = {
                "billing:guarantee_detail": "guarantee_id",
                "billing:compliance_evidence_detail": "evidence_id",
                "billing:retention_release_detail": "release_id",
            }[route]
            response = self.client.get(
                reverse(route, kwargs={key: self.contracts["A"].pk})
            )
            self.assertEqual(response.status_code, 404)

    def test_retention_subcontract_predicate_and_other_lifecycle_filters_remain(self):
        Contract.objects.filter(pk=self.contracts["B"].pk).update(
            contract_type=ContractType.SUPPLIER
        )
        self.assertNotIn(
            self.contracts["B"], self.form("retention").fields["contract"].queryset
        )
        self.assertIn(
            self.contracts["B"], self.form("guarantee").fields["contract"].queryset
        )
        Contract.objects.filter(pk=self.contracts["A"].pk).update(
            status=ContractStatus.DRAFT
        )
        for surface in self.surfaces:
            self.assertNotIn(
                self.contracts["A"], self.form(surface).fields["contract"].queryset
            )

    def test_existing_service_contract_scope_denials_preserved(self):
        for key in "CDX":
            with self.subTest(key=key):
                for surface, service in (
                    ("guarantee", create_guarantee),
                    ("compliance", create_compliance_evidence),
                ):
                    data = self.form(surface, self.payload(surface)).data.copy()
                    form = self.form(surface, data)
                    self.assertTrue(form.is_valid(), form.errors)
                    args = form.cleaned_data | {"contract": self.contracts[key]}
                    before = self.state()
                    with self.assertRaises(PermissionDenied):
                        service(organization=self.org, actor=self.user, **args)
                    self.assertEqual(self.state(), before)
                with self.assertRaises(PermissionDenied):
                    create_retention_release(
                        organization=self.org,
                        actor=self.user,
                        contract=self.contracts[key],
                        release_date=date(2026, 10, 22),
                        amount=Decimal(1),
                        evidence_document_version=self.versions["A"],
                    )

    def test_authorized_guarantee_and_compliance_http_success_preserved(self):
        for surface, model in (
            ("guarantee", ContractGuarantee),
            ("compliance", ContractComplianceEvidence),
        ):
            before = model.objects.count()
            response = self.client.post(
                reverse(self.surfaces[surface][1]), self.payload(surface)
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(model.objects.count(), before + 1)

    def test_existing_service_error_redisplay_stays_scoped(self):
        for surface, service in (
            ("guarantee", "create_guarantee"),
            ("compliance", "create_compliance_evidence"),
            ("retention", "create_retention_release"),
        ):
            with patch(
                f"apps.billing.views.{service}",
                side_effect=PermissionDenied("Existing rejection"),
            ):
                response = self.client.post(
                    reverse(self.surfaces[surface][1]), self.payload(surface)
                )
            self.assertEqual(response.status_code, 200)
            self.assert_no_metadata(response)

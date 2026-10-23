"""BATCH-03 payable source boundaries; fixtures exist only in disposable tests."""

from datetime import date, timedelta
from decimal import Decimal
from typing import ClassVar
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.billing.forms import PayableCertificateForm, PayableMeasurementForm
from apps.billing.models import PayableCertificate, PayableMeasurement
from apps.billing.payable_services import (
    create_payable_certificate,
    create_payable_measurement,
    get_payable_certificates,
)
from apps.contracts.models import Contract, ContractItem, ContractTermVersion
from apps.organizations.models import (
    AuthorizationScopeType,
    MembershipRole,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.parties.models import BusinessParty, PartyIdentitySnapshot
from apps.projects.models import Project, ProjectSite


class PayableSourceScopeTests(TestCase):
    surfaces: ClassVar[dict] = {
        "measurement": (PayableMeasurementForm, "contract_item"),
        "certificate": (PayableCertificateForm, "contract"),
    }

    @classmethod
    def membership(cls, actor, organization):
        member = OrganizationMembership.objects.create(
            organization=organization,
            user=actor,
            role=MembershipRole.COMPANY_OWNER,
            status="active",
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=organization,
            membership=member,
            role=OrganizationRole.objects.get(code=MembershipRole.COMPANY_OWNER),
            reason="Disposable explicit existing role assignment",
        )
        return member

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="B03 tenant", slug="b03")
        cls.other_org = Organization.objects.create(name="B03 X", slug="b03-x")
        cls.user = User.objects.create_user(username="b03-limited")
        cls.owner = User.objects.create_user(username="b03-org")
        cls.foreign = User.objects.create_user(username="b03-x")
        cls.member = cls.membership(cls.user, cls.org)
        cls.owner_member = cls.membership(cls.owner, cls.org)
        cls.foreign_member = cls.membership(cls.foreign, cls.other_org)
        MembershipScopeGrant.objects.create(
            organization=cls.other_org,
            membership=cls.foreign_member,
            scope_type="organization",
            reason="Disposable foreign source qualification",
        )
        MembershipScopeGrant.objects.create(
            organization=cls.org,
            membership=cls.owner_member,
            scope_type="organization",
            reason="Disposable organization control",
        )
        cls.projects, cls.contracts, cls.items = {}, {}, {}
        for key in "ABCDX":
            org = cls.other_org if key == "X" else cls.org
            cls.projects[key] = Project.objects.create(
                organization=org, code=f"B03-P-{key}", name=f"B03 Project {key}"
            )
            party = BusinessParty.objects.create(
                organization=org, party_kind="company", display_name=f"B03 Party {key}"
            )
            PartyIdentitySnapshot.objects.create(
                organization=org,
                party=party,
                sequence=1,
                party_kind="company",
                display_name=party.display_name,
                normalized_display_name=party.display_name,
                reason="Disposable identity",
                recorded_by=cls.owner,
            )
            contract = Contract.objects.create(
                organization=org,
                project=cls.projects[key],
                party=party,
                contract_number=f"B03-CON-{key}",
                title=f"B03 distinctive contract {key}",
                counterparty_name=party.display_name,
                direction="payable",
                contract_type="subcontract",
                status="active",
                contract_value=Decimal(1000),
            )
            cls.contracts[key] = contract
            cls.items[key] = ContractItem.objects.create(
                organization=org,
                contract=contract,
                description=f"B03 distinctive item {key}",
                quantity=Decimal(10),
                unit_price=Decimal(100),
                sort_order=1,
            )
            term = ContractTermVersion.objects.create(
                organization=org,
                contract=contract,
                version=1,
                effective_from=date(2026, 1, 1),
                payment_due_days=10,
                reason="Disposable explicit terms",
                created_by=cls.owner,
            )
            ContractTermVersion.objects.filter(pk=term.pk).update(
                status="approved",
                approved_by=cls.user,
                approved_at=timezone.now(),
                approval_reason="Disposable approved snapshot",
            )
            if key in "AB":
                MembershipScopeGrant.objects.create(
                    organization=org,
                    membership=cls.member,
                    scope_type="project",
                    project=cls.projects[key],
                    reason="Disposable A/B",
                )
        cls.site = ProjectSite.objects.create(
            organization=cls.org,
            project=cls.projects["A"],
            code="B03-SITE",
            name="B03 site",
        )

    def setUp(self):
        self.login(self.user)

    def login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.org.pk)
        session.save()

    def form(self, surface, data=None, **context):
        return self.surfaces[surface][0](
            data=data,
            organization=context.pop("organization", self.org),
            membership=context.pop("membership", self.member),
            **context,
        )

    def route(self, surface):
        return reverse(f"billing:payable_{surface}_create")

    def payload(self, surface, key="B"):
        if surface == "measurement":
            return {
                "contract_item": str(self.items[key].pk),
                "measured_on": "2026-02-15",
                "period_quantity": "1",
                "cumulative_quantity": "1",
                "evidence_reference": "B03 disposable observation",
            }
        return {
            "contract": str(self.contracts[key].pk),
            "period_start": "2026-02-01",
            "period_end": "2026-02-28",
            "measurement_cutoff": "2026-02-28",
        }

    def objects(self, surface, keys):
        sources = self.items if surface == "measurement" else self.contracts
        return [sources[key] for key in keys]

    def assert_scoped_response(self, response, surface):
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        field = self.surfaces[surface][1]
        self.assertEqual(list(form.fields[field].queryset), self.objects(surface, "AB"))
        for key in "CDX":
            for source in (self.contracts[key], self.items[key]):
                self.assertNotContains(response, str(source.pk))
                self.assertNotContains(response, str(source))
            self.assertNotContains(response, self.contracts[key].title)
            self.assertNotContains(response, self.contracts[key].contract_number)
            self.assertNotContains(response, self.items[key].description)
        for source in self.objects(surface, "AB"):
            self.assertContains(response, str(source.pk))
            self.assertContains(response, str(source))

    def counts(self):
        return (
            PayableMeasurement.objects.count(),
            PayableCertificate.objects.count(),
            AuditEvent.objects.count(),
        )

    def test_get_and_authorized_b_bound_choices(self):
        for surface in self.surfaces:
            with self.subTest(surface=surface):
                self.assert_scoped_response(
                    self.client.get(self.route(surface)), surface
                )
                form = self.form(surface, self.payload(surface))
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(
                    form.cleaned_data[self.surfaces[surface][1]],
                    self.objects(surface, "B")[0],
                )

    def test_source_lifecycle_predicates_and_order_remain(self):
        for field, value in (
            ("direction", "receivable"),
            ("contract_type", "client"),
            ("status", "draft"),
            ("deleted_at", timezone.now()),
        ):
            contract = self.contracts["A"]
            old = getattr(contract, field)
            Contract.objects.filter(pk=contract.pk).update(**{field: value})
            for surface in self.surfaces:
                with self.subTest(field=field, surface=surface):
                    choices = (
                        self.form(surface).fields[self.surfaces[surface][1]].queryset
                    )
                    self.assertEqual(list(choices), self.objects(surface, "B"))
            Contract.objects.filter(pk=contract.pk).update(**{field: old})

    def test_missing_invalid_and_wrong_tenant_membership_fail_closed(self):
        for member in (None, object(), self.foreign_member):
            for surface in self.surfaces:
                with self.subTest(surface=surface, member=str(type(member))):
                    form = self.form(surface, membership=member)
                    self.assertFalse(
                        form.fields[self.surfaces[surface][1]].queryset.exists()
                    )

    def test_absent_revoked_expired_future_scope_fails_closed(self):
        grants = MembershipScopeGrant.objects.filter(membership=self.member)
        for state in ("revoked", "expired", "future", "absent"):
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
                    starts_at=timezone.now() + timedelta(days=1), ends_at=None
                )
            else:
                grants.delete()
            for surface in self.surfaces:
                with self.subTest(state=state, surface=surface):
                    self.assertFalse(
                        self.form(surface)
                        .fields[self.surfaces[surface][1]]
                        .queryset.exists()
                    )
                    self.assertEqual(
                        self.client.get(self.route(surface)).status_code, 403
                    )

    def test_inactive_membership_user_tenant_fail_closed(self):
        for model, pk, attr, inactive, active in (
            (OrganizationMembership, self.member.pk, "status", "suspended", "active"),
            (User, self.user.pk, "is_active", False, True),
            (Organization, self.org.pk, "status", "suspended", "active"),
        ):
            model.objects.filter(pk=pk).update(**{attr: inactive})
            member = OrganizationMembership.objects.select_related(
                "user", "organization"
            ).get(pk=self.member.pk)
            for surface in self.surfaces:
                with self.subTest(model=model.__name__, surface=surface):
                    self.assertFalse(
                        self.form(surface, membership=member)
                        .fields[self.surfaces[surface][1]]
                        .queryset.exists()
                    )
                    self.assertIn(
                        self.client.get(self.route(surface)).status_code, (302, 403)
                    )
            model.objects.filter(pk=pk).update(**{attr: active})

    def test_site_only_grant_never_promotes_project_sources(self):
        MembershipScopeGrant.objects.filter(membership=self.member).delete()
        MembershipScopeGrant.objects.create(
            organization=self.org,
            membership=self.member,
            scope_type=AuthorizationScopeType.SITE,
            project=self.projects["A"],
            site=self.site,
            reason="Disposable site only",
        )
        for surface in self.surfaces:
            response = self.client.get(self.route(surface))
            self.assertEqual(response.status_code, 200)
            self.assertFalse(
                response.context["form"]
                .fields[self.surfaces[surface][1]]
                .queryset.exists()
            )
            before = self.counts()
            response = self.client.post(self.route(surface), self.payload(surface, "A"))
            self.assertIn(self.surfaces[surface][1], response.context["form"].errors)
            self.assertEqual(self.counts(), before)

    def test_role_and_capability_are_independent_entry_gates(self):
        role = OrganizationRole.objects.get(code=MembershipRole.COMPANY_OWNER)
        for surface, code in (
            ("measurement", "payable_measurements.record"),
            ("certificate", "payable_certificates.create"),
        ):
            permission = role.permissions.get(code=code)
            role.permissions.remove(permission)
            self.assertEqual(self.client.get(self.route(surface)).status_code, 403)
            role.permissions.add(permission)
        MembershipRoleAssignment.objects.filter(membership=self.member).update(
            revoked_at=timezone.now()
        )
        for surface in self.surfaces:
            self.assertEqual(self.client.get(self.route(surface)).status_code, 403)

    def test_manipulated_c_d_x_posts_no_mutation_or_metadata(self):
        for surface in self.surfaces:
            for key in "CDX":
                with self.subTest(surface=surface, key=key):
                    before = self.counts()
                    response = self.client.post(
                        self.route(surface), self.payload(surface, key)
                    )
                    self.assert_scoped_response(response, surface)
                    self.assertEqual(
                        set(response.context["form"].errors),
                        {self.surfaces[surface][1]},
                    )
                    self.assertEqual(self.counts(), before)

    def test_missing_required_redisplay_and_service_error_remain_scoped(self):
        for surface in self.surfaces:
            data = self.payload(surface)
            del data["measured_on" if surface == "measurement" else "period_start"]
            self.assert_scoped_response(
                self.client.post(self.route(surface), data), surface
            )
            for exc in (PermissionDenied("B03 denied"), ValidationError("B03 invalid")):
                with patch(
                    f"apps.billing.views.create_payable_{surface}", side_effect=exc
                ):
                    before = self.counts()
                    response = self.client.post(
                        self.route(surface), self.payload(surface)
                    )
                    self.assert_scoped_response(response, surface)
                    self.assertContains(response, "B03")
                    self.assertEqual(self.counts(), before)

    def invoke(self, surface, key, actor=None, **updates):
        form = self.form(
            surface,
            self.payload(surface, key),
            membership=self.owner_member if key != "X" else self.foreign_member,
            organization=self.other_org if key == "X" else self.org,
        )
        self.assertTrue(form.is_valid(), form.errors)
        data = dict(form.cleaned_data)
        data.update(updates)
        service = (
            create_payable_measurement
            if surface == "measurement"
            else create_payable_certificate
        )
        return service(organization=self.org, actor=actor or self.user, **data)

    def test_existing_direct_services_deny_scope_tenant_capability_and_site(self):
        for surface in self.surfaces:
            for key in "CDX":
                with self.subTest(surface=surface, key=key):
                    before = self.counts()
                    with self.assertRaises(PermissionDenied):
                        self.invoke(surface, key)
                    self.assertEqual(self.counts(), before)
        role = OrganizationRole.objects.get(code=MembershipRole.COMPANY_OWNER)
        for surface, code in (
            ("measurement", "payable_measurements.record"),
            ("certificate", "payable_certificates.create"),
        ):
            permission = role.permissions.get(code=code)
            role.permissions.remove(permission)
            with self.assertRaises(PermissionDenied):
                self.invoke(surface, "B")
            role.permissions.add(permission)
        MembershipScopeGrant.objects.filter(membership=self.member).delete()
        MembershipScopeGrant.objects.create(
            organization=self.org,
            membership=self.member,
            scope_type="site",
            project=self.projects["A"],
            site=self.site,
            reason="Disposable site denial",
        )
        for surface in self.surfaces:
            with self.assertRaises(PermissionDenied):
                self.invoke(surface, "A")

    def test_authorized_limited_and_organization_success_and_reader_gate(self):
        for surface in self.surfaces:
            response = self.client.post(self.route(surface), self.payload(surface))
            self.assertEqual(response.status_code, 302)
            created = (
                PayableMeasurement if surface == "measurement" else PayableCertificate
            ).objects.get()
            self.assertEqual(created.project_id, self.projects["B"].pk)
            self.assertEqual(created.status, "draft")
            org_form = self.form(surface, membership=self.owner_member)
            self.assertEqual(
                list(org_form.fields[self.surfaces[surface][1]].queryset),
                self.objects(surface, "ABCD"),
            )
            self.invoke(surface, "C", actor=self.owner)
        with self.assertRaises(PermissionDenied):
            get_payable_certificates(organization=self.org, actor=self.user)

    def test_existing_period_overlap_cutoff_and_terms_validation(self):
        certificate = self.invoke("certificate", "B")
        self.assertEqual(certificate.contract_term_version.version, 1)
        self.assertEqual(certificate.currency_code, "IRR")
        for updates in (
            {},
            {"period_end": date(2026, 1, 1)},
            {"measurement_cutoff": date(2026, 3, 1)},
        ):
            before = self.counts()
            with self.assertRaises(ValidationError):
                self.invoke("certificate", "B", **updates)
            self.assertEqual(self.counts(), before)
        ContractTermVersion.objects.filter(contract=self.contracts["A"]).update(
            effective_from=date(2026, 3, 1)
        )
        with self.assertRaises(ValidationError):
            self.invoke("certificate", "A")

    def test_existing_measurement_quantity_guard(self):
        before = self.counts()
        with self.assertRaises(ValidationError):
            self.invoke("measurement", "B", cumulative_quantity=Decimal(11))
        self.assertEqual(self.counts(), before)

"""BATCH-08: independent project-only form/view/service acceptance matrices."""

import re
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
from apps.contracts.forms import ContractForm
from apps.contracts.models import Contract
from apps.contracts.services import create_contract
from apps.inventory.forms import WarehouseForm
from apps.inventory.models import Warehouse
from apps.inventory.services import create_warehouse
from apps.organizations.models import (
    MembershipRoleAssignment,
    MembershipScopeGrant,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.parties.models import BusinessParty
from apps.procurement.forms import PurchaseRequestForm
from apps.procurement.models import PurchaseRequest
from apps.procurement.services import create_purchase_request
from apps.projects.models import Project, ProjectSite
from apps.workforce.forms import TrainingRequirementForm
from apps.workforce.models import Competency, Position, TrainingRequirement
from apps.workforce.services import create_training_requirement


class ProjectScopeMatrix:
    """Each concrete class executes every acceptance case for its own route."""

    @classmethod
    def member(cls, user, organization, role="project_manager", scope=False):
        member = OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=role,
            status="active",
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=organization,
            membership=member,
            role=OrganizationRole.objects.get(code=role),
            reason="Disposable B08 matrix",
        )
        if scope:
            MembershipScopeGrant.objects.create(
                organization=organization,
                membership=member,
                scope_type="organization",
                reason="Disposable B08 organization control",
            )
        return member

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="B08 tenant", slug="b08")
        cls.other = Organization.objects.create(name="B08 foreign", slug="b08-x")
        for org in (cls.org, cls.other):
            OrganizationSettings.objects.create(organization=org, currency="IRR")
        cls.user = User.objects.create_user(username="b08-limited")
        cls.owner = User.objects.create_user(username="b08-owner")
        cls.foreign = User.objects.create_user(username="b08-foreign")
        cls.site_user = User.objects.create_user(username="b08-site")
        cls.viewer = User.objects.create_user(username="b08-viewer")
        cls.limited = cls.member(cls.user, cls.org)
        cls.owner_member = cls.member(cls.owner, cls.org, "company_owner", True)
        cls.foreign_member = cls.member(cls.foreign, cls.other, "company_owner", True)
        cls.site_member = cls.member(cls.site_user, cls.org, "operations_manager")
        cls.viewer_member = cls.member(cls.viewer, cls.org, "viewer", True)
        cls.projects = {}
        for key in "ABCDX":
            project = Project.objects.create(
                organization=cls.other if key == "X" else cls.org,
                code=f"B08-P-{key}",
                name=f"B08 distinctive Project {key}",
            )
            cls.projects[key] = project
            if key in "AB":
                MembershipScopeGrant.objects.create(
                    organization=cls.org,
                    membership=cls.limited,
                    scope_type="project",
                    project=project,
                    reason="Disposable B08 A/B",
                )
        site = ProjectSite.objects.create(
            organization=cls.org,
            project=cls.projects["A"],
            code="B08-SITE",
            name="B08 distinctive site",
        )
        MembershipScopeGrant.objects.create(
            organization=cls.org,
            membership=cls.site_member,
            scope_type="site",
            project=cls.projects["A"],
            site=site,
            reason="Disposable B08 site only",
        )
        for org in (cls.org, cls.other):
            BusinessParty.objects.create(
                organization=org,
                display_name=f"B08 party {org.slug}",
                party_kind="company",
            )
            Competency.objects.create(organization=org, code="B08-C", name="B08 master")
            Position.objects.create(organization=org, code="B08-P", title="B08 master")

    def setUp(self):
        self.login()

    def login(self, user=None):
        self.client.force_login(user or self.user)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.org.pk)
        session.save()

    def form(self, data=None, **kwargs):
        return self.form_class(
            data, organization=self.org, **({"membership": self.limited} | kwargs)
        )

    def payload(self, key="B"):
        return {"project": str(self.projects[key].pk)} | self.fields_payload

    def snapshot(self):
        return tuple(
            list(model.objects.order_by("pk").values())
            for model in (
                PurchaseRequest,
                Contract,
                Warehouse,
                TrainingRequirement,
                AuditEvent,
            )
        )

    def assert_choices(self, form, allowed="AB"):
        self.assertSetEqual(
            set(form.fields["project"].queryset), {self.projects[k] for k in allowed}
        )

    def assert_safe(self, response, allowed="AB"):
        self.assertEqual(response.status_code, 200)
        self.assert_choices(response.context["form"], allowed)
        body = re.sub(r'<input[^>]*name="next"[^>]*>', "", response.content.decode())
        body = re.sub(r'href="[^"]*[?&](?:amp;)?next=[^"]*"', "", body)
        for key in "ABCDX":
            for token in (str(self.projects[key].pk), self.projects[key].name):
                if key in allowed:
                    self.assertIn(token, body)
                elif not (not allowed and key == "A"):
                    # Shared navigation retains legitimate Site A parent context.
                    self.assertNotIn(token, body)
        return response.context["form"]

    def test_get_and_untrusted_query_do_not_expand_choices(self):
        self.assert_safe(self.client.get(reverse(self.route)))
        for key in "CDX":
            with self.subTest(key=key):
                self.assert_safe(
                    self.client.get(
                        reverse(self.route), {"project": self.projects[key].pk}
                    )
                )

    def test_organization_scope_sees_a_to_d_only(self):
        self.login(self.owner)
        self.assert_safe(self.client.get(reverse(self.route)), "ABCD")

    def test_site_only_never_promotes_parent_and_rejects_all_projects(self):
        self.login(self.site_user)
        self.assert_safe(self.client.get(reverse(self.route)), "")
        before = self.snapshot()
        for key in "ABCDX":
            with self.subTest(key=key):
                form = self.assert_safe(
                    self.client.post(reverse(self.route), self.payload(key)), ""
                )
                self.assertIn("project", form.errors)
                self.assertEqual(self.snapshot(), before)

    def test_manipulated_and_malformed_post_rejected_without_mutation_or_audit(self):
        before = self.snapshot()
        for key in "CDX":
            with self.subTest(key=key):
                form = self.assert_safe(
                    self.client.post(reverse(self.route), self.payload(key))
                )
                self.assertIn("project", form.errors)
                self.assertEqual(self.snapshot(), before)
        form = self.assert_safe(
            self.client.post(
                reverse(self.route), self.payload() | {"project": "invalid-uuid"}
            )
        )
        self.assertIn("project", form.errors)
        self.assertEqual(self.snapshot(), before)

    def test_all_required_field_redisplays_retain_authorized_b(self):
        before = self.snapshot()
        for field, definition in self.form().fields.items():
            if not definition.required:
                continue
            with self.subTest(field=field):
                data = self.payload()
                data.pop(field, None)
                form = self.assert_safe(self.client.post(reverse(self.route), data))
                self.assertIn(field, form.errors)
                if field != "project":
                    self.assertEqual(
                        form.cleaned_data.get("project"), self.projects["B"]
                    )
                self.assertEqual(self.snapshot(), before)

    def test_service_error_redisplay_keeps_scoped_choices(self):
        with patch(
            self.service_patch, side_effect=PermissionDenied("B08 service control")
        ) as service:
            before = self.snapshot()
            form = self.assert_safe(
                self.client.post(reverse(self.route), self.payload())
            )
            self.assertIn("B08 service control", str(form.non_field_errors()))
            self.assertEqual(service.call_args.kwargs["project"], self.projects["B"])
            self.assertEqual(self.snapshot(), before)

    def test_missing_wrong_tenant_invalid_membership_fail_closed(self):
        for membership in (None, object(), self.foreign_member):
            with self.subTest(membership=str(membership)):
                for data in (None, self.payload()):
                    self.assert_choices(self.form(data, membership=membership), "")

    def test_absent_grants_fail_closed_and_http_denies(self):
        self.limited.scope_grants.update(revoked_at=timezone.now())
        self.assert_choices(self.form(), "")
        self.assertEqual(self.client.get(reverse(self.route)).status_code, 403)

    def assert_only_b(self):
        self.assert_choices(self.form(), "B")
        self.assert_safe(self.client.get(reverse(self.route)), "B")

    def test_revoked_grant(self):
        self.limited.scope_grants.filter(project=self.projects["A"]).update(
            revoked_at=timezone.now()
        )
        self.assert_only_b()

    def test_expired_grant(self):
        now = timezone.now()
        self.limited.scope_grants.filter(project=self.projects["A"]).update(
            starts_at=now - timedelta(days=2), ends_at=now - timedelta(days=1)
        )
        self.assert_only_b()

    def test_future_grant(self):
        self.limited.scope_grants.filter(project=self.projects["A"]).update(
            starts_at=timezone.now() + timedelta(days=1)
        )
        self.assert_only_b()

    def test_inactive_membership(self):
        self.limited.status = "inactive"
        self.limited.save(update_fields=["status"])
        self.assert_choices(self.form(), "")
        self.assertIn(self.client.get(reverse(self.route)).status_code, (302, 403))

    def test_inactive_user(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assert_choices(self.form(), "")
        self.assertIn(self.client.get(reverse(self.route)).status_code, (302, 403))

    def test_suspended_tenant(self):
        self.org.status = "suspended"
        self.org.save(update_fields=["status"])
        self.assert_choices(self.form(), "")
        self.assertIn(self.client.get(reverse(self.route)).status_code, (302, 403))

    def test_missing_role_denies_entry_and_direct_service(self):
        self.limited.role_assignments.update(revoked_at=timezone.now())
        self.assertEqual(self.client.get(reverse(self.route)).status_code, 403)
        with self.assertRaises(PermissionDenied):
            self.create(self.user, self.projects["B"])

    def test_capability_absence_cannot_be_supplied_by_scope(self):
        self.login(self.viewer)
        self.assertEqual(self.client.get(reverse(self.route)).status_code, 403)
        with self.assertRaises(PermissionDenied):
            self.create(self.viewer, self.projects["B"])

    def test_non_deleted_filter_and_ordering_preserved(self):
        self.projects["A"].deleted_at = timezone.now()
        self.projects["A"].save(update_fields=["deleted_at"])
        self.assert_only_b()
        query = self.form().fields["project"].queryset
        self.assertEqual(query.query.order_by, self.original_ordering)

    def test_direct_services_reject_same_tenant_cross_tenant_and_site_only(self):
        before = self.snapshot()
        for actor, keys in ((self.user, "CDX"), (self.site_user, "ABCDX")):
            for key in keys:
                with self.subTest(actor=actor.username, key=key):
                    with self.assertRaises(PermissionDenied):
                        self.create(actor, self.projects[key])
                    self.assertEqual(self.snapshot(), before)

    def test_authorized_creation_and_domain_gate(self):
        before = self.model.objects.count()
        response = self.client.post(reverse(self.route), self.payload())
        if self.model is TrainingRequirement:
            self.assert_safe(response)
            self.assertTrue(response.context["form"].non_field_errors())
            self.assertEqual(self.model.objects.count(), before)
        else:
            self.assertEqual(response.status_code, 302)
            record = self.model.objects.latest("created_at")
            self.assertEqual(record.project, self.projects["B"])
            self.assertEqual(self.model.objects.count(), before + 1)
        self.login(self.owner)
        data = {
            k: v.replace("new", "owner").replace("NEW", "OWNER")
            for k, v in self.payload("C").items()
        }
        response = self.client.post(reverse(self.route), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.model.objects.latest("created_at").project, self.projects["C"]
        )

    def test_optional_or_required_blank_project_domain_semantics(self):
        self.assertEqual(
            self.form().fields["project"].required,
            self.model in (PurchaseRequest, Contract),
        )
        data = self.payload() | {"project": ""}
        before = self.snapshot()
        form = self.assert_safe(self.client.post(reverse(self.route), data))
        self.assertEqual(self.snapshot(), before)
        if self.model in (PurchaseRequest, Contract):
            self.assertIn("project", form.errors)
        else:
            self.assertNotIn("project", form.errors)
            self.assertTrue(form.non_field_errors())
            self.login(self.owner)
            response = self.client.post(reverse(self.route), data)
            self.assertEqual(response.status_code, 302)
            self.assertIsNone(self.model.objects.latest("created_at").project)

    def test_tenant_masters_are_preserved_even_without_membership(self):
        for field, model in self.masters.items():
            with self.subTest(field=field):
                for member in (self.limited, None):
                    self.assertSetEqual(
                        set(self.form(membership=member).fields[field].queryset),
                        set(model.objects.filter(organization=self.org)),
                    )

    def create(self, actor, project):
        kwargs = dict(self.fields_payload)
        kwargs.pop("project", None)
        if self.model is Contract:
            kwargs["contract_value"] = Decimal("10.00")
        return self.service(
            organization=self.org, actor=actor, project=project, **kwargs
        )


class PurchaseRequestProjectScopeTests(ProjectScopeMatrix, TestCase):
    form_class = PurchaseRequestForm
    route = "procurement:request_create"
    model = PurchaseRequest
    service = staticmethod(create_purchase_request)
    service_patch = "apps.procurement.views.create_purchase_request"
    fields_payload: ClassVar[dict] = {
        "request_number": "B08-NEW",
        "title": "B08 valid request",
    }
    original_ordering = ("name",)
    masters: ClassVar[dict] = {}


class ContractProjectScopeTests(ProjectScopeMatrix, TestCase):
    form_class = ContractForm
    route = "contracts:create"
    model = Contract
    service = staticmethod(create_contract)
    service_patch = "apps.contracts.views.create_contract"
    fields_payload: ClassVar[dict] = {
        "contract_number": "b08-new",
        "title": "B08 valid contract",
        "counterparty_name": "B08 synthetic counterparty",
        "status": "draft",
        "contract_value": "10.00",
    }
    original_ordering = ("name",)
    masters: ClassVar[dict] = {"party": BusinessParty}

    def test_contract_number_dates_status_and_value_validation_preserved(self):
        data = self.payload() | {"start_date": "1405/07/30", "end_date": "1405/07/29"}
        form = self.form(data)
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())
        self.assertEqual(form.cleaned_data["contract_number"], "B08-NEW")
        self.assertIsInstance(form.cleaned_data["start_date"], date)
        self.assertFalse(self.form(self.payload() | {"status": "invalid"}).is_valid())
        before = self.snapshot()
        response = self.client.post(
            reverse(self.route), self.payload() | {"contract_value": "-1"}
        )
        form = self.assert_safe(response)
        self.assertTrue(form.non_field_errors())
        self.assertEqual(self.snapshot(), before)


class WarehouseProjectScopeTests(ProjectScopeMatrix, TestCase):
    form_class = WarehouseForm
    route = "inventory:warehouse_create"
    model = Warehouse
    service = staticmethod(create_warehouse)
    service_patch = "apps.inventory.views.create_warehouse"
    fields_payload: ClassVar[dict] = {"code": "B08-NEW", "name": "B08 valid warehouse"}
    original_ordering = ("name",)
    masters: ClassVar[dict] = {}


class TrainingRequirementProjectScopeTests(ProjectScopeMatrix, TestCase):
    form_class = TrainingRequirementForm
    route = "workforce:training_requirement_create"
    model = TrainingRequirement
    service = staticmethod(create_training_requirement)
    service_patch = "apps.workforce.views.create_training_requirement"
    fields_payload: ClassVar[dict] = {
        "code": "B08-NEW",
        "name": "B08 valid training requirement",
    }
    original_ordering = ()
    masters: ClassVar[dict] = {"competency": Competency, "position": Position}

    def test_training_related_master_tenant_validation_remains_intact(self):
        before = self.snapshot()
        for field, model in self.masters.items():
            with self.subTest(field=field):
                foreign = model.objects.get(organization=self.other)
                form = self.assert_safe(
                    self.client.post(
                        reverse(self.route), self.payload() | {field: str(foreign.pk)}
                    )
                )
                self.assertIn(field, form.errors)
                with self.assertRaises(PermissionDenied):
                    create_training_requirement(
                        organization=self.org,
                        actor=self.owner,
                        project=self.projects["B"],
                        code="B08-X-MASTER",
                        name="B08 rejected master",
                        **{field: foreign},
                    )
                self.assertEqual(self.snapshot(), before)

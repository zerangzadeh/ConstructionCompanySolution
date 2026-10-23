"""BATCH-04 issued order disclosure and inherited Project authorization."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.materials.models import Material, UnitOfMeasure
from apps.organizations.models import (
    MembershipRoleAssignment,
    MembershipScopeGrant,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.parties.models import BusinessParty, PartyRole
from apps.procurement.forms import GoodsReceiptForm
from apps.procurement.models import GoodsReceipt, PurchaseOrder
from apps.procurement.services import (
    add_purchase_order_item,
    create_goods_receipt,
    create_purchase_order,
    issue_purchase_order,
)
from apps.projects.models import Project, ProjectSite


class ReceiptSourceScopeTests(TestCase):
    @classmethod
    def membership(cls, actor, org, role="company_owner", scope=False):
        member = OrganizationMembership.objects.create(
            organization=org,
            user=actor,
            role=role,
            status="active",
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=org,
            membership=member,
            role=OrganizationRole.objects.get(code=role),
            reason="Disposable B04 role",
        )
        if scope:
            MembershipScopeGrant.objects.create(
                organization=org,
                membership=member,
                scope_type="organization",
                reason="Disposable B04 organization control",
            )
        return member

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="B04 tenant", slug="b04")
        cls.other_org = Organization.objects.create(name="B04 X", slug="b04-x")
        cls.user = User.objects.create_user(username="b04-limited")
        cls.owner = User.objects.create_user(username="b04-owner")
        cls.foreign = User.objects.create_user(username="b04-x")
        cls.member = cls.membership(cls.user, cls.org, role="project_manager")
        cls.owner_member = cls.membership(cls.owner, cls.org, scope=True)
        cls.foreign_member = cls.membership(cls.foreign, cls.other_org, scope=True)
        cls.projects, cls.orders = {}, {}
        for org, actor in ((cls.org, cls.owner), (cls.other_org, cls.foreign)):
            unit = UnitOfMeasure.objects.create(
                organization=org, code="EA", name="Each", symbol="ea", category="count"
            )
            material = Material.objects.create(
                organization=org,
                code="B04-M",
                name="B04 material",
                unit_of_measure=unit,
            )
            supplier = BusinessParty.objects.create(
                organization=org,
                party_kind="company",
                display_name="B04 synthetic supplier",
            )
            PartyRole.objects.create(organization=org, party=supplier, role="supplier")
            for key in "X" if org == cls.other_org else "ABCD":
                project = Project.objects.create(
                    organization=org, code=f"B04-P-{key}", name=f"B04 Project {key}"
                )
                cls.projects[key] = project
                order = create_purchase_order(
                    organization=org,
                    actor=actor,
                    project=project,
                    supplier=supplier,
                    order_number=f"B04-PO-{key}",
                    order_date=date(2026, 10, 22),
                )
                add_purchase_order_item(
                    organization=org,
                    actor=actor,
                    purchase_order=order,
                    material=material,
                    quantity=Decimal(2),
                    unit_price=Decimal(1),
                )
                cls.orders[key] = issue_purchase_order(
                    organization=org, actor=actor, purchase_order=order
                )
                if key in "AB":
                    MembershipScopeGrant.objects.create(
                        organization=org,
                        membership=cls.member,
                        scope_type="project",
                        project=project,
                        reason="Disposable A/B",
                    )
        cls.site = ProjectSite.objects.create(
            organization=cls.org,
            project=cls.projects["A"],
            code="B04-S",
            name="B04 site",
        )

    def setUp(self):
        self.login(self.user)

    def login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.org.pk)
        session.save()

    def form(self, data=None, membership="default"):
        return GoodsReceiptForm(
            data=data,
            organization=self.org,
            membership=self.member if membership == "default" else membership,
        )

    def payload(self, key="B"):
        return {
            "purchase_order": str(self.orders[key].pk),
            "receipt_number": "B04-GR",
            "received_at": "2026-10-22T10:00",
            "notes": "Disposable B04",
        }

    def counts(self):
        return GoodsReceipt.objects.count(), AuditEvent.objects.count()

    def assert_response(self, response, keys="AB"):
        self.assertEqual(response.status_code, 200)
        expected = {self.orders[k].pk for k in keys}
        self.assertEqual(
            set(
                response.context["form"]
                .fields["purchase_order"]
                .queryset.values_list("pk", flat=True)
            ),
            expected,
        )
        for key in "ABCDX":
            for token in (
                str(self.orders[key].pk),
                str(self.orders[key]),
                self.orders[key].order_number,
            ):
                if key in keys:
                    self.assertContains(response, token)
                else:
                    self.assertNotContains(response, token)

    def test_qualifying_issued_versioned_sources_get_and_bound_b(self):
        self.assertTrue(
            all(
                o.status == "issued" and o.current_version_id
                for o in self.orders.values()
            )
        )
        self.assert_response(self.client.get(reverse("procurement:receipt_create")))
        form = self.form(self.payload())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["purchase_order"], self.orders["B"])

    def test_missing_invalid_wrong_tenant_membership_fail_closed(self):
        for member in (None, object(), self.foreign_member):
            with self.subTest(member=type(member).__name__):
                self.assertFalse(
                    self.form(membership=member)
                    .fields["purchase_order"]
                    .queryset.exists()
                )

    def test_absent_revoked_expired_future_grants_fail_closed(self):
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
            with self.subTest(state=state):
                self.assertFalse(self.form().fields["purchase_order"].queryset.exists())
                self.assertEqual(
                    self.client.get(reverse("procurement:receipt_create")).status_code,
                    403,
                )

    def test_inactive_membership_user_tenant_fail_closed(self):
        for model, pk, field, inactive, active in (
            (OrganizationMembership, self.member.pk, "status", "suspended", "active"),
            (User, self.user.pk, "is_active", False, True),
            (Organization, self.org.pk, "status", "suspended", "active"),
        ):
            model.objects.filter(pk=pk).update(**{field: inactive})
            member = OrganizationMembership.objects.select_related(
                "user", "organization"
            ).get(pk=self.member.pk)
            with self.subTest(model=model.__name__):
                self.assertFalse(
                    self.form(membership=member)
                    .fields["purchase_order"]
                    .queryset.exists()
                )
                self.assertIn(
                    self.client.get(reverse("procurement:receipt_create")).status_code,
                    (302, 403),
                )
            model.objects.filter(pk=pk).update(**{field: active})

    def site_only(self):
        MembershipScopeGrant.objects.filter(membership=self.member).delete()
        MembershipScopeGrant.objects.create(
            organization=self.org,
            membership=self.member,
            scope_type="site",
            project=self.projects["A"],
            site=self.site,
            reason="Disposable site only",
        )

    def test_site_only_excludes_parent_sources_and_denies_post_and_service(self):
        self.site_only()
        self.assert_response(
            self.client.get(reverse("procurement:receipt_create")), keys=""
        )
        before = self.counts()
        self.assert_response(
            self.client.post(reverse("procurement:receipt_create"), self.payload("A")),
            keys="",
        )
        with self.assertRaises(PermissionDenied):
            self.invoke("A")
        self.assertEqual(self.counts(), before)

    def test_manipulated_c_d_x_posts_and_direct_services_no_mutation(self):
        for key in "CDX":
            with self.subTest(key=key):
                before = self.counts()
                response = self.client.post(
                    reverse("procurement:receipt_create"), self.payload(key)
                )
                self.assert_response(response)
                self.assertEqual(
                    set(response.context["form"].errors), {"purchase_order"}
                )
                with self.assertRaises(PermissionDenied):
                    self.invoke(key)
                self.assertEqual(self.counts(), before)

    def test_invalid_required_and_service_error_redisplays_remain_scoped(self):
        data = self.payload()
        del data["receipt_number"]
        self.assert_response(
            self.client.post(reverse("procurement:receipt_create"), data)
        )
        for error in (PermissionDenied("B04 denial"), ValueError("B04 invalid")):
            with patch(
                "apps.procurement.views.create_goods_receipt", side_effect=error
            ):
                before = self.counts()
                self.assert_response(
                    self.client.post(
                        reverse("procurement:receipt_create"), self.payload()
                    )
                )
                self.assertEqual(self.counts(), before)

    def test_role_and_capability_entry_and_direct_service_denials(self):
        role = OrganizationRole.objects.get(code="project_manager")
        permission = role.permissions.get(code="goods_receipts.create")
        role.permissions.remove(permission)
        before = self.counts()
        self.assertEqual(
            self.client.get(reverse("procurement:receipt_create")).status_code, 403
        )
        with self.assertRaises(PermissionDenied):
            self.invoke("B")
        self.assertEqual(self.counts(), before)
        role.permissions.add(permission)
        MembershipRoleAssignment.objects.filter(membership=self.member).update(
            revoked_at=timezone.now()
        )
        self.assertEqual(
            self.client.get(reverse("procurement:receipt_create")).status_code, 403
        )

    def invoke(self, key, actor=None):
        return create_goods_receipt(
            organization=self.org,
            actor=actor or self.user,
            purchase_order=self.orders[key],
            receipt_number=f"B04-DIRECT-{key}",
            received_at=timezone.now(),
        )

    def test_valid_limited_and_organization_flows_preserve_version_and_audit(self):
        response = self.client.post(
            reverse("procurement:receipt_create"), self.payload()
        )
        self.assertEqual(response.status_code, 302)
        receipt = GoodsReceipt.objects.get()
        self.assertEqual(receipt.project, self.projects["B"])
        self.assertEqual(
            receipt.purchase_order_version_id, self.orders["B"].current_version_id
        )
        self.assertEqual(receipt.status, "draft")
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.GOODS_RECEIPT_CREATED, entity_id=receipt.pk
            ).count(),
            1,
        )
        self.login(self.owner)
        self.assert_response(
            self.client.get(reverse("procurement:receipt_create")), keys="ABCD"
        )
        self.invoke("C", actor=self.owner)

    def test_original_status_order_archival_and_version_guards_preserved(self):
        for status in ("draft", "completed", "cancelled"):
            PurchaseOrder.objects.filter(pk=self.orders["A"].pk).update(status=status)
            self.assertEqual(
                list(self.form().fields["purchase_order"].queryset), [self.orders["B"]]
            )
        with self.assertRaises(ValueError):
            self.invoke("A")
        PurchaseOrder.objects.filter(pk=self.orders["A"].pk).update(
            status="issued", current_version=None
        )
        with self.assertRaises(ValueError):
            self.invoke("A")
        Project.objects.filter(pk=self.projects["A"].pk).update(
            deleted_at=timezone.now()
        )
        self.assertEqual(
            list(self.form().fields["purchase_order"].queryset), [self.orders["B"]]
        )
        self.assertEqual(
            self.form().fields["purchase_order"].queryset.query.order_by,
            ("-order_date",),
        )

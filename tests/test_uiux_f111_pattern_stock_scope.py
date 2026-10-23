"""BATCH-05 protected movement sources use effective Project authority."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.inventory.forms import StockTransactionForm
from apps.inventory.models import StockTransaction, Warehouse
from apps.inventory.services import (
    create_stock_transaction,
    create_warehouse,
    get_stock_balance,
)
from apps.materials.models import Material
from apps.organizations.models import (
    MembershipRoleAssignment,
    MembershipScopeGrant,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.procurement.models import GoodsReceipt
from apps.procurement.services import (
    add_goods_receipt_item,
    create_goods_receipt,
    post_goods_receipt,
)
from tests import test_uiux_f111_pattern_receipt_scope as receipt_tests


class StockSourceScopeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        receipt_tests.ReceiptSourceScopeTests.setUpTestData.__func__(cls)
        cls.warehouses, cls.items = {}, {}
        for key, order in cls.orders.items():
            org, actor = order.organization, cls.foreign if key == "X" else cls.owner
            cls.warehouses[key] = create_warehouse(
                organization=org,
                actor=actor,
                code=f"B05-W-{key}",
                name=f"B05 Warehouse {key}",
                project=cls.projects[key],
            )
            receipt = create_goods_receipt(
                organization=org,
                actor=actor,
                purchase_order=order,
                receipt_number=f"B05-GR-{key}",
                received_at=timezone.now(),
            )
            cls.items[key] = add_goods_receipt_item(
                organization=org,
                actor=actor,
                goods_receipt=receipt,
                purchase_order_item=order.items.get(),
                quantity=Decimal(1),
            )
            post_goods_receipt(organization=org, actor=actor, goods_receipt=receipt)
        cls.central = create_warehouse(
            organization=cls.org,
            actor=cls.owner,
            code="B05-CENTRAL",
            name="B05 central",
        )
        cls.second = create_warehouse(
            organization=cls.org,
            actor=cls.owner,
            code="B05-B2",
            name="B05 second B",
            project=cls.projects["B"],
        )
        cls.material = cls.items["B"].material

    membership = classmethod(receipt_tests.ReceiptSourceScopeTests.membership.__func__)
    site_only = receipt_tests.ReceiptSourceScopeTests.site_only

    def setUp(self):
        self.login(self.user)

    def login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.org.pk)
        session.save()

    def form(self, data=None, membership="default"):
        return StockTransactionForm(
            data,
            organization=self.org,
            membership=self.member if membership == "default" else membership,
        )

    def payload(self, kind="receipt", key="B"):
        return {
            "transaction_number": f"B05-{kind}-{key}",
            "transaction_type": kind,
            "material": str(self.material.pk),
            "project": str(self.projects[key].pk),
            "source_warehouse": str(self.warehouses[key].pk)
            if kind in ("issue", "transfer", "adjustment_out")
            else "",
            "destination_warehouse": str(
                self.second.pk
                if kind == "transfer" and key == "B"
                else self.warehouses[key].pk
            )
            if kind in ("receipt", "transfer", "adjustment_in")
            else "",
            "goods_receipt_item": str(self.items[key].pk) if kind == "receipt" else "",
            "quantity": "1",
            "occurred_at": "2026-10-22T10:00",
            "reference": "",
            "notes": "Disposable B05",
        }

    def counts(self):
        return (
            StockTransaction.objects.count(),
            AuditEvent.objects.filter(
                action=AuditAction.STOCK_TRANSACTION_CREATED
            ).count(),
            tuple(
                get_stock_balance(
                    organization=self.org,
                    user=self.owner,
                    warehouse=w,
                    material=self.material,
                )
                for w in (*self.warehouses.values(), self.central, self.second)
                if w.organization_id == self.org.pk
            ),
        )

    def assert_scoped(self, form, keys="AB", central=False):
        for field, sources in (
            ("project", self.projects),
            ("goods_receipt_item", self.items),
            ("source_warehouse", self.warehouses),
            ("destination_warehouse", self.warehouses),
        ):
            expected = {sources[k].pk for k in keys}
            if "warehouse" in field:
                if "B" in keys:
                    expected.add(self.second.pk)
                if central:
                    expected.add(self.central.pk)
            self.assertEqual(
                set(form.fields[field].queryset.values_list("pk", flat=True)), expected
            )

    def assert_response(self, response, keys="AB", central=False):
        self.assertEqual(response.status_code, 200)
        self.assert_scoped(response.context["form"], keys, central)
        for key in "ABCDX":
            tokens = [
                str(self.projects[key].pk),
                self.projects[key].name,
                str(self.warehouses[key].pk),
                str(self.warehouses[key]),
                self.warehouses[key].name,
                self.warehouses[key].code,
                str(self.items[key].pk),
                str(self.items[key]),
                self.items[key].goods_receipt.receipt_number,
            ]
            for token in tokens:
                if key not in keys and not (
                    keys == ""
                    and token in (str(self.projects["A"].pk), self.projects["A"].name)
                ):
                    self.assertNotContains(response, token)
        if not central:
            for token in (str(self.central.pk), str(self.central), self.central.code):
                self.assertNotContains(response, token)

    def test_qualifying_sources_get_bound_and_tenant_master_material(self):
        self.assertTrue(
            all(
                GoodsReceipt.objects.get(pk=i.goods_receipt_id).status == "posted"
                and not i.stock_transactions.exists()
                for i in self.items.values()
            )
        )
        self.assert_response(self.client.get(reverse("inventory:transaction_create")))
        for kind in ("receipt", "issue", "transfer", "adjustment_in", "adjustment_out"):
            with self.subTest(kind=kind):
                form = self.form(self.payload(kind))
                self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            set(self.form().fields["material"].queryset),
            set(Material.objects.filter(organization=self.org)),
        )

    def test_fail_closed_membership_grants_and_inactive_state(self):
        for member in (None, object(), self.foreign_member):
            with self.subTest(member=type(member).__name__):
                self.assert_scoped(self.form(membership=member), "")
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
                self.assert_scoped(self.form(), "")
                self.assertEqual(
                    self.client.get(
                        reverse("inventory:transaction_create")
                    ).status_code,
                    403,
                )

    def test_inactive_membership_user_tenant(self):
        for model, pk, field, bad, good in (
            (OrganizationMembership, self.member.pk, "status", "suspended", "active"),
            (User, self.user.pk, "is_active", False, True),
            (type(self.org), self.org.pk, "status", "suspended", "active"),
        ):
            model.objects.filter(pk=pk).update(**{field: bad})
            member = OrganizationMembership.objects.select_related(
                "organization", "user"
            ).get(pk=self.member.pk)
            with self.subTest(model=model.__name__):
                self.assert_scoped(self.form(membership=member), "")
                self.assertIn(
                    self.client.get(
                        reverse("inventory:transaction_create")
                    ).status_code,
                    (302, 403),
                )
            model.objects.filter(pk=pk).update(**{field: good})

    def test_site_only_cannot_promote_parent_or_sources(self):
        self.site_only()
        self.assert_response(
            self.client.get(reverse("inventory:transaction_create")), ""
        )
        before = self.counts()
        self.assert_response(
            self.client.post(reverse("inventory:transaction_create"), self.payload()),
            "",
        )
        with self.assertRaises(PermissionDenied):
            self.invoke(self.payload())
        self.assertEqual(self.counts(), before)

    def test_forced_project_warehouse_receipt_ids_rejected_without_audit_or_balance(
        self,
    ):
        for key in "CDX":
            for kind, field, value in (
                ("issue", "project", self.projects[key].pk),
                ("issue", "source_warehouse", self.warehouses[key].pk),
                ("transfer", "destination_warehouse", self.warehouses[key].pk),
                ("receipt", "goods_receipt_item", self.items[key].pk),
            ):
                with self.subTest(key=key, field=field):
                    before = self.counts()
                    data = self.payload(kind)
                    data[field] = str(value)
                    response = self.client.post(
                        reverse("inventory:transaction_create"), data
                    )
                    self.assert_response(response)
                    self.assertIn(field, response.context["form"].errors)
                    self.assertEqual(self.counts(), before)
        # Unauthorized receipt cannot derive its Project during clean().
        data = self.payload()
        data["goods_receipt_item"] = str(self.items["C"].pk)
        data["project"] = ""
        form = self.form(data)
        self.assertFalse(form.is_valid())
        self.assertIsNone(form.cleaned_data.get("project"))

    def invoke(self, data, actor=None):
        # Direct-service controls deliberately resolve raw IDs without form filtering.
        return create_stock_transaction(
            organization=self.org,
            actor=actor or self.user,
            transaction_number=data["transaction_number"],
            transaction_type=data["transaction_type"],
            material=self.material,
            unit_of_measure=self.material.unit_of_measure,
            quantity=Decimal(1),
            occurred_at=timezone.now(),
            project=type(self.projects["B"]).objects.get(pk=data["project"])
            if data.get("project")
            else None,
            source_warehouse=Warehouse.objects.get(pk=data["source_warehouse"])
            if data.get("source_warehouse")
            else None,
            destination_warehouse=Warehouse.objects.get(
                pk=data["destination_warehouse"]
            )
            if data.get("destination_warehouse")
            else None,
            goods_receipt_item=type(self.items["B"]).objects.get(
                pk=data["goods_receipt_item"]
            )
            if data.get("goods_receipt_item")
            else None,
        )

    def test_existing_service_denials_and_mixed_authorized_relationships(self):
        for key in "CDX":
            before = self.counts()
            with self.subTest(key=key), self.assertRaises(PermissionDenied):
                self.invoke(self.payload("issue", key))
            self.assertEqual(self.counts(), before)
        for kind in ("receipt", "transfer"):
            data = self.payload(kind)
            data["destination_warehouse"] = str(self.warehouses["A"].pk)
            before = self.counts()
            response = self.client.post(reverse("inventory:transaction_create"), data)
            self.assert_response(response)
            self.assertIn("__all__", response.context["form"].errors)
            self.assertEqual(self.counts(), before)

    def test_required_type_shape_material_project_and_service_redisplay(self):
        for kind, field in (
            ("receipt", "goods_receipt_item"),
            ("issue", "project"),
            ("transfer", "source_warehouse"),
            ("adjustment_in", "destination_warehouse"),
            ("adjustment_out", "source_warehouse"),
        ):
            data = self.payload(kind)
            data[field] = ""
            with self.subTest(kind=kind):
                self.assertFalse(self.form(data).is_valid())
        data = self.payload()
        data["project"] = ""
        form = self.form(data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["project"], self.projects["B"])
        data = self.payload()
        data["project"] = str(self.projects["A"].pk)
        self.assertIn("project", self.form(data).errors)
        data = self.payload("transfer")
        data["destination_warehouse"] = data["source_warehouse"]
        self.assertIn("destination_warehouse", self.form(data).errors)
        data = self.payload()
        data["transaction_number"] = ""
        self.assert_response(
            self.client.post(reverse("inventory:transaction_create"), data)
        )
        for exc in (PermissionDenied("B05 denial"), ValueError("B05 invalid")):
            with patch(
                "apps.inventory.views.create_stock_transaction", side_effect=exc
            ):
                self.assert_response(
                    self.client.post(
                        reverse("inventory:transaction_create"), self.payload()
                    )
                )

    def test_role_capability_entry_and_direct_service_denial(self):
        role = OrganizationRole.objects.get(code="project_manager")
        permission = role.permissions.get(code="stock_transactions.create")
        role.permissions.remove(permission)
        self.assertEqual(
            self.client.get(reverse("inventory:transaction_create")).status_code, 403
        )
        with self.assertRaises(PermissionDenied):
            self.invoke(self.payload("issue"))
        role.permissions.add(permission)
        MembershipRoleAssignment.objects.filter(membership=self.member).update(
            revoked_at=timezone.now()
        )
        self.assertEqual(
            self.client.get(reverse("inventory:transaction_create")).status_code, 403
        )

    def test_valid_draft_variants_no_stock_posting_and_org_central(self):
        for kind in ("receipt", "issue", "transfer", "adjustment_in", "adjustment_out"):
            before = self.counts()
            with self.subTest(kind=kind):
                response = self.client.post(
                    reverse("inventory:transaction_create"), self.payload(kind)
                )
                self.assertEqual(response.status_code, 302)
                record = StockTransaction.objects.get(
                    transaction_number=f"B05-{kind.upper()}-B"
                )
                self.assertEqual(record.status, "draft")
                self.assertEqual(record.project, self.projects["B"])
                self.assertEqual(self.counts()[0:2], (before[0] + 1, before[1] + 1))
                self.assertEqual(self.counts()[2], before[2])
        # Consumed receipt excluded for all actors; the others remain eligible.
        self.assertFalse(
            self.form()
            .fields["goods_receipt_item"]
            .queryset.filter(pk=self.items["B"].pk)
            .exists()
        )
        self.login(self.owner)
        form = StockTransactionForm(organization=self.org, membership=self.owner_member)
        for field in ("source_warehouse", "destination_warehouse"):
            self.assertIn(self.central, form.fields[field].queryset)
        data = self.payload("adjustment_in")
        data.update(
            project="",
            destination_warehouse=str(self.central.pk),
            transaction_number="B05-CENTRAL",
        )
        self.assertEqual(
            self.client.post(reverse("inventory:transaction_create"), data).status_code,
            302,
        )

    def test_lifecycle_predicates_and_receipt_material_mismatch(self):
        Warehouse.objects.filter(pk=self.warehouses["A"].pk).update(is_active=False)
        self.assertFalse(
            self.form()
            .fields["source_warehouse"]
            .queryset.filter(pk=self.warehouses["A"].pk)
            .exists()
        )
        GoodsReceipt.objects.filter(pk=self.items["A"].goods_receipt_id).update(
            status="draft"
        )
        self.assertFalse(
            self.form()
            .fields["goods_receipt_item"]
            .queryset.filter(pk=self.items["A"].pk)
            .exists()
        )
        other = Material.objects.create(
            organization=self.org,
            code="B05-OTHER",
            name="B05 other material",
            unit_of_measure=self.material.unit_of_measure,
        )
        data = self.payload()
        data["material"] = str(other.pk)
        self.assertIn("material", self.form(data).errors)

    def test_organization_catalogue_and_central_manipulation(self):
        self.login(self.owner)
        self.assert_response(
            self.client.get(reverse("inventory:transaction_create")),
            "ABCD",
            central=True,
        )
        self.login(self.user)
        for kind, field in (
            ("adjustment_in", "destination_warehouse"),
            ("adjustment_out", "source_warehouse"),
            ("transfer", "source_warehouse"),
        ):
            with self.subTest(kind=kind):
                before = self.counts()
                data = self.payload(kind)
                data[field] = str(self.central.pk)
                response = self.client.post(
                    reverse("inventory:transaction_create"), data
                )
                self.assert_response(response)
                self.assertIn(field, response.context["form"].errors)
                self.assertEqual(self.counts(), before)

    def test_original_archival_project_and_master_predicates(self):
        Warehouse.objects.filter(pk=self.warehouses["A"].pk).update(
            archived_at=timezone.now()
        )
        for field in ("source_warehouse", "destination_warehouse"):
            self.assertNotIn(self.warehouses["A"], self.form().fields[field].queryset)
        type(self.projects["A"]).objects.filter(pk=self.projects["A"].pk).update(
            deleted_at=timezone.now()
        )
        self.assertNotIn(self.projects["A"], self.form().fields["project"].queryset)
        # A warehouse/receipt does not gain a new parent lifecycle rule in this fix.
        self.assertIn(
            self.items["A"], self.form().fields["goods_receipt_item"].queryset
        )
        self.material.unit_of_measure.is_active = False
        self.material.unit_of_measure.save(update_fields=["is_active"])
        self.assertNotIn(self.material, self.form().fields["material"].queryset)

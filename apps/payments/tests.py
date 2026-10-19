"""Negative transition coverage while the schema awaits the readiness gate.

Current create/post/reversal, tenant, UI and cash projection behavior is covered
in apps.treasury.test_payment_retirement; settlement/caps/concurrency in
apps.billing.test_payment_retirement. These legacy names cannot resume work.
"""

from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase

from apps.payments import services


class RetiredPaymentCompatibilityTests(SimpleTestCase):
    def test_all_legacy_business_entry_points_fail_before_database_access(self):
        for name in (
            "create_payment",
            "void_payment",
            "allocate_payment",
            "reverse_payment_allocation",
            "get_organization_payments",
        ):
            with self.subTest(name=name), self.assertRaises(PermissionDenied):
                getattr(services, name)()

    def test_legacy_routes_have_no_active_consumer(self):
        for path in (
            "/payments/",
            "/payments/create/",
            f"/payments/{uuid4()}/",
            f"/payments/{uuid4()}/void/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

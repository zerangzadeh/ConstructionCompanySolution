from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, SimpleTestCase

from apps.payments.admin import PaymentAdmin
from apps.payments.models import Payment


class PaymentAdminTests(SimpleTestCase):
    def test_financial_mutations_are_not_available_in_admin(self) -> None:
        admin = PaymentAdmin(Payment, AdminSite())
        request = RequestFactory().get("/admin/payments/payment/")

        self.assertFalse(admin.has_module_permission(request))
        self.assertFalse(admin.has_view_permission(request))
        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_change_permission(request))
        self.assertFalse(admin.has_delete_permission(request))

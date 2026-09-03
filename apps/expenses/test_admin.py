from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, SimpleTestCase

from apps.expenses.admin import ExpenseAdmin
from apps.expenses.models import Expense


class ExpenseAdminTests(SimpleTestCase):
    def test_financial_mutations_are_not_available_in_admin(self) -> None:
        admin = ExpenseAdmin(Expense, AdminSite())
        request = RequestFactory().get("/admin/expenses/expense/")

        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_change_permission(request))
        self.assertFalse(admin.has_delete_permission(request))

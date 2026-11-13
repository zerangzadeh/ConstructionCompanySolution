from django.test import TestCase, TransactionTestCase

def pytest_collection_modifyitems(items):
    from apps.billing.test_mvp03_browser import ContractBillingBrowserTests
    for item in items:
        cls = item.cls
        if cls is None or not issubclass(cls, TransactionTestCase) or issubclass(cls, TestCase):
            continue
        cls.available_apps = None
        if cls._fixture_teardown is TransactionTestCase._fixture_teardown:
            cls._fixture_teardown = ContractBillingBrowserTests._fixture_teardown

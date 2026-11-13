def pytest_collection_modifyitems(items):
    from apps.procurement.test_mvp04a_browser import PurchaseRequestBrowserTests
    from apps.procurement.test_mvp04f_browser import ConnectedBrowserTests

    for cls in (PurchaseRequestBrowserTests, ConnectedBrowserTests):
        original = cls.browser
        def browser(self, actor, scenarios, run=original):
            for scenario in scenarios:
                for step in scenario.get("steps", []):
                    if step.get("clickSelector") or step.get("submit"):
                        step.setdefault("confirmIfShown", True)
            return run(self, actor, scenarios)
        cls.browser = browser

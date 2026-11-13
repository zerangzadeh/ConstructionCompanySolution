def pytest_collection_modifyitems(items):
    from apps.procurement.test_mvp04f_browser import ConnectedBrowserTests
    original = ConnectedBrowserTests.browser
    def browser(self, actor, scenarios):
        for scenario in scenarios:
            steps = scenario.get("steps", [])
            if scenario["name"].endswith("select-pr-line"):
                value = next(step for step in steps if "purchase_request_item_id" in step.get("fill", {}))["fill"].pop("purchase_request_item_id")
                steps[:0] = [
                    {"toggleSelector": ".rfq-config__line-add > summary"},
                    {"searchChoice": {"name":"purchase_request_item_id", "query":"سیمان", "value":value}},
                ]
            for step in steps:
                if step.get("clickSelector") or step.get("submit"):
                    step.setdefault("confirmIfShown", True)
        return original(self, actor, scenarios)
    ConnectedBrowserTests.browser = browser


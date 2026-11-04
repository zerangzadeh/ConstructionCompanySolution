"""Presentation adapter preserves the existing GET contract without querying."""

from django.core.paginator import Paginator
from django.test import RequestFactory, SimpleTestCase

from apps.accounts.templatetags.reference_lists import reference_list_state
from core.list_filters import build_table_filters


class OperationalListAdapterTests(SimpleTestCase):
    def test_existing_profiles_keep_their_quick_filter_layout(self):
        for profile, search in (("estimates", "title"), ("sites", "site")):
            request = RequestFactory().get(f"/{profile}/")
            state = reference_list_state(
                {
                    "request": request,
                    "filters": [
                        {"name": search, "kind": "text", "label": "جست‌وجو"},
                        {"name": "project", "kind": "text", "label": "پروژه"},
                    ],
                    "page_obj": Paginator([], 25).page(1),
                },
                profile,
            )
            self.assertEqual(
                [f.name for f in state["bar"]["quick_fields"]], ["project"]
            )
            self.assertEqual(state["bar"]["secondary_fields"], [])
            self.assertFalse(state["sort"]["descending"])

    def test_dates_chips_and_sort_state_preserve_existing_parameters(self):
        request = RequestFactory().get(
            "/expenses/?description=receipt&category=other&incurred_on_from=1405/07/01&sort=amount&direction=desc&page=2"
        )
        columns = [
            {"name": "description", "kind": "text", "label": "شرح"},
            {
                "name": "category",
                "kind": "select",
                "label": "گروه",
                "choices": [("other", "سایر")],
            },
            {"name": "incurred_on", "kind": "date_range", "label": "تاریخ"},
        ]
        state = reference_list_state(
            {
                "request": request,
                "filters": build_table_filters(request, columns),
                "page_obj": Paginator(range(28), 25).page(2),
            },
            "expenses",
        )
        self.assertEqual(
            state["sort"], {"key": "amount", "label": "مبلغ", "descending": True}
        )
        self.assertEqual(state["bar"]["result_count"], 28)
        self.assertTrue(state["bar"]["secondary_open"])
        chip = next(c for c in state["bar"]["chips"] if c["name"] == "category")
        self.assertNotIn("page=", chip["url"])
        self.assertNotIn("category=", chip["url"])
        self.assertIn("description=receipt", chip["url"])
        self.assertEqual(
            state["bar"]["clear_url"], "/expenses/?sort=amount&direction=desc"
        )

    def test_default_sort_and_advanced_filters_are_truthful(self):
        for profile, date_name in [
            ("expenses", "incurred_on"),
            ("safety", "occurred_at"),
            ("quality", "identified_at"),
        ]:
            search = "description" if profile == "expenses" else "number"
            request = RequestFactory().get(f"/{profile}/?sort=unknown")
            columns = [
                {"name": search, "kind": "text", "label": "جست‌وجو"},
                {"name": date_name, "kind": "date_range", "label": "تاریخ"},
            ]
            state = reference_list_state(
                {
                    "request": request,
                    "filters": columns,
                    "page_obj": Paginator([], 25).page(1),
                },
                profile,
            )
            self.assertEqual(state["sort"]["key"], date_name)
            self.assertTrue(state["sort"]["descending"])
            self.assertFalse(state["bar"]["secondary_open"])
            self.assertEqual(len(state["bar"]["secondary_fields"]), 2)

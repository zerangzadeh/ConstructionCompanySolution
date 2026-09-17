from datetime import date
from pathlib import Path
from unittest.mock import Mock

from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase

from apps.accounts.templatetags.table_filters import table_sort_header
from core.list_filters import (
    apply_table_sorting,
    has_active_table_filters,
    parse_user_date,
    table_pagination_query,
)


class UserDateParsingTests(SimpleTestCase):
    def test_accepts_jalali_and_iso_dates_for_table_ranges(self) -> None:
        self.assertEqual(parse_user_date("1405/06/24"), date(2026, 9, 15))
        self.assertEqual(parse_user_date("2026-09-15"), date(2026, 9, 15))

    def test_invalid_date_does_not_create_a_filter_bound(self) -> None:
        self.assertIsNone(parse_user_date("1405/13/40"))


class TableQueryBehaviorTests(SimpleTestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()

    def test_sorting_uses_whitelist_and_toggles_direction(self) -> None:
        queryset = Mock()
        request = self.factory.get(
            "/projects/?name=alpha&sort=name&direction=desc&page=3"
        )

        apply_table_sorting(
            queryset,
            request,
            sort_fields={"name": "name"},
            default_ordering=("name", "pk"),
        )

        queryset.order_by.assert_called_once_with("-name")

    def test_invalid_sort_uses_stable_default(self) -> None:
        queryset = Mock()
        request = self.factory.get("/projects/?sort=organization__secret")

        apply_table_sorting(
            queryset,
            request,
            sort_fields={"name": "name"},
            default_ordering=("name", "pk"),
        )

        queryset.order_by.assert_called_once_with("name", "pk")

    def test_pagination_query_keeps_filters_and_sort_and_removes_empty_values(
        self,
    ) -> None:
        request = self.factory.get(
            "/projects/?name=alpha&sort=name&direction=asc&page=4&status="
        )

        self.assertEqual(
            table_pagination_query(request), "name=alpha&sort=name&direction=asc"
        )

    def test_sort_header_preserves_filter_and_toggles_current_sort(self) -> None:
        request = self.factory.get(
            "/projects/?name=alpha&sort=name&direction=asc&page=2&status="
        )

        result = table_sort_header({"request": request}, "name", "نام پروژه")

        self.assertIn("name=alpha", result["url"])
        self.assertIn("sort=name", result["url"])
        self.assertIn("direction=desc", result["url"])
        self.assertNotIn("page=2", result["url"])
        self.assertNotIn("status=", result["url"])
        self.assertEqual(result["state"], "asc")

    def test_only_filter_values_count_as_active(self) -> None:
        request = self.factory.get("/projects/?sort=name&direction=asc&page=2&name=")

        self.assertFalse(has_active_table_filters(request))

    def test_shared_filter_markup_has_automatic_controls(self) -> None:
        request = self.factory.get("/projects/?name=alpha&sort=name&direction=asc")
        html = Template(
            '{% load table_filters %}{% table_filters filters "filters" %}'
        ).render(
            Context(
                {
                    "request": request,
                    "filters": [
                        {"name": "name", "kind": "text", "label": "نام"},
                        {
                            "name": "status",
                            "kind": "select",
                            "label": "وضعیت",
                            "choices": (("active", "فعال"),),
                        },
                    ],
                }
            )
        )

        self.assertIn("data-table-filter-form", html)
        self.assertNotIn("onchange=", html)
        self.assertIn("data-table-filter-clear", html)

    def test_shared_script_contains_debounce_clear_and_query_preservation_contract(
        self,
    ) -> None:
        script = Path("apps/accounts/static/js/erp_table.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("const debounceMs = 400", script)
        self.assertIn('event.target.matches("select")', script)
        self.assertIn("url.searchParams.delete(name)", script)
        self.assertIn('url.searchParams.set("page", "1")', script)
        self.assertIn("data-table-filter-clear", script)

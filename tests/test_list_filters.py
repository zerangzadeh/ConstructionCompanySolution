from datetime import date

from django.test import SimpleTestCase

from core.list_filters import parse_user_date


class UserDateParsingTests(SimpleTestCase):
    def test_accepts_jalali_and_iso_dates_for_table_ranges(self) -> None:
        self.assertEqual(parse_user_date("1405/06/24"), date(2026, 9, 15))
        self.assertEqual(parse_user_date("2026-09-15"), date(2026, 9, 15))

    def test_invalid_date_does_not_create_a_filter_bound(self) -> None:
        self.assertIsNone(parse_user_date("1405/13/40"))

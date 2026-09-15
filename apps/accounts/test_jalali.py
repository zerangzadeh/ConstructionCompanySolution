from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.template import Context, Template
from django.test import SimpleTestCase, override_settings

from apps.accounts.templatetags.erp_format import jalali_date, jalali_datetime
from core.jalali import format_jalali, gregorian_to_jalali


class JalaliFormattingTests(SimpleTestCase):
    def test_converts_known_gregorian_date(self) -> None:
        self.assertEqual(gregorian_to_jalali(2026, 9, 14), (1405, 6, 23))
        self.assertEqual(format_jalali(date(2026, 9, 14)), "1405/06/23")

    @override_settings(TIME_ZONE="Asia/Tehran", USE_TZ=True)
    def test_datetime_uses_active_timezone_and_preserves_time(self) -> None:
        value = datetime(2026, 9, 14, 10, 30, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(format_jalali(value, include_time=True), "1405/06/23 14:00")

    def test_template_filters_handle_empty_values(self) -> None:
        self.assertEqual(jalali_date(None), "")
        self.assertEqual(jalali_datetime(None), "")

    def test_jalali_filter_is_available_to_all_templates(self) -> None:
        rendered = Template("{{ value|jalali_date }}").render(
            Context({"value": date(2026, 9, 14)})
        )

        self.assertEqual(rendered, "1405/06/23")

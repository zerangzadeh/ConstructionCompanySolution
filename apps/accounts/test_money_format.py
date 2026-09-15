from decimal import Decimal

from django.template import Context, Template
from django.test import SimpleTestCase

from apps.accounts.templatetags.erp_format import erp_number, rial


class MoneyFormattingTests(SimpleTestCase):
    def test_formats_thousands_and_removes_redundant_zeros(self) -> None:
        self.assertEqual(erp_number(Decimal("125000000.00")), "125,000,000")

    def test_rial_filter_adds_the_persian_currency_unit(self) -> None:
        self.assertEqual(rial(Decimal("125000000.00")), "125,000,000 ریال")

    def test_rial_filter_is_available_to_all_templates(self) -> None:
        rendered = Template("{{ value|rial }}").render(
            Context({"value": Decimal("125000000.00")})
        )

        self.assertEqual(rendered, "125,000,000 ریال")

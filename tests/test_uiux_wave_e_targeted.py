"""Presentation contracts for the bounded Wave E accessibility/localization repair."""

from html.parser import HTMLParser

from django.template import Context, Template
from django.test import SimpleTestCase


class Labels(HTMLParser):
    def __init__(self):
        super().__init__()
        self.labels = {}
        self.target = None
        self.inputs = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "label":
            self.target = attrs.get("for")
            self.labels[self.target] = ""
        if tag == "input":
            self.inputs[attrs["id"]] = attrs

    def handle_data(self, data):
        if self.target:
            self.labels[self.target] += data

    def handle_endtag(self, tag):
        if tag == "label":
            self.target = None


class WaveEPresentationTests(SimpleTestCase):
    def test_each_date_boundary_has_a_distinct_associated_persian_name(self):
        for field, label in (
            ("start_date", "تاریخ شروع"),
            ("end_date", "تاریخ پایان"),
            ("identified_at", "زمان شناسایی"),
        ):
            with self.subTest(field=field):
                html = Template(
                    '{% include "components/table_filter_row.html" %}'
                ).render(
                    Context(
                        {
                            "form_id": "target-filters",
                            "filters": [
                                {
                                    "name": field,
                                    "label": label,
                                    "kind": "date_range",
                                    "from_value": "2026-09-15",
                                    "to_value": "2026-10-23",
                                }
                            ],
                        }
                    )
                )
                parsed = Labels()
                parsed.feed(html)
                names = []
                for boundary, value in (("from", "2026-09-15"), ("to", "2026-10-23")):
                    key = f"target-filters-{field}-{boundary}"
                    names.append(parsed.labels[key].strip())
                    self.assertIn(label, names[-1])
                    self.assertEqual(parsed.inputs[key]["name"], f"{field}_{boundary}")
                    self.assertEqual(parsed.inputs[key]["value"], value)
                    self.assertEqual(parsed.inputs[key]["form"], "target-filters")
                self.assertEqual(len(set(names)), 2)
                self.assertEqual(set(parsed.labels), set(parsed.inputs))

    def test_platform_company_label_preserves_filter_values_and_role_codes(self):
        html = Template('{% include "organizations/role_catalog.html" %}').render(
            Context(
                {
                    "platform_mode": True,
                    "organizations": [{"id": "fixture-org", "name": "شرکت آزمون"}],
                    "roles": [],
                }
            )
        )
        self.assertIn('for="organization-filter">شرکت</label>', html)
        self.assertNotIn('for="organization-filter">Tenant</label>', html)
        self.assertIn('name="organization"', html)
        self.assertIn('value="fixture-org"', html)

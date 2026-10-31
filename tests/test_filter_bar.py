"""URL and rendering contracts for the reusable, presentation-only Filter Bar."""

from urllib.parse import parse_qs, urlsplit

from django import forms
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from core.list_filters import build_filter_bar


class FilterBarTests(SimpleTestCase):
    def bar(self, query):
        class FilterForm(forms.Form):
            q = forms.CharField(label="جست‌وجو", required=False)
            side = forms.ChoiceField(
                label="سمت قرارداد",
                required=False,
                choices=[("", "همه"), ("receivable", "با کارفرما")],
            )
            number = forms.CharField(label="شماره", required=False)

        request = RequestFactory().get("/contracts/", query)
        form = FilterForm(request.GET)
        form.is_valid()
        return build_filter_bar(
            request,
            form=form,
            quick_fields=("side",),
            secondary_fields=("number",),
            context={"project_id": "trusted-parent"},
            result_count=43,
        )

    def test_remove_one_preserves_other_filters_context_sort_and_resets_page(self):
        bar = self.bar(
            {
                "q": "پل",
                "side": "receivable",
                "page": 7,
                "sort": "number",
                "direction": "desc",
                "unrelated": "ignored",
            }
        )
        chip = next(x for x in bar["chips"] if x["name"] == "side")
        self.assertEqual(
            parse_qs(urlsplit(chip["url"]).query),
            {
                "q": ["پل"],
                "project_id": ["trusted-parent"],
                "sort": ["number"],
                "direction": ["desc"],
            },
        )
        self.assertEqual(chip["value"], "با کارفرما")

    def test_clear_all_preserves_only_parent_and_sort(self):
        bar = self.bar({"q": "پل", "side": "receivable", "number": "42", "page": 3})
        self.assertEqual(
            parse_qs(urlsplit(bar["clear_url"]).query),
            {"project_id": ["trusted-parent"]},
        )
        self.assertEqual(bar["active_count"], 3)
        self.assertTrue(bar["secondary_open"])

    def test_rendered_chips_escape_search_and_expose_business_choice_labels(self):
        html = render_to_string(
            "components/filter_bar.html",
            {
                "bar": self.bar(
                    {"q": '<script>alert("x")</script>', "side": "receivable"}
                )
            },
        )
        self.assertNotIn('<script>alert("x")</script>', html)
        self.assertIn("با کارفرما", html)
        self.assertIn("data-filter-result-count", html)
        self.assertNotIn("data-table-filter-row", html)

    def test_invalid_choice_never_becomes_a_business_chip(self):
        bar = self.bar({"side": "forged"})
        self.assertEqual(bar["chips"], [])
        self.assertTrue(bar["form"].errors)

    def test_parent_does_not_count_as_removable_filter(self):
        bar = self.bar({"project_id": "forged", "q": ""})
        self.assertEqual(bar["active_count"], 0)
        self.assertEqual(bar["hidden"]["project_id"], "trusted-parent")

    def test_secondary_dates_reuse_existing_jalali_widget_and_chip_format(self):
        from core.forms import JalaliDateMixin

        class DateFilterForm(JalaliDateMixin, forms.Form):
            q = forms.CharField(required=False)
            since = forms.DateField(label="از تاریخ", required=False)

        request = RequestFactory().get("/list/", {"since": "1405/06/24"})
        form = DateFilterForm(request.GET)
        self.assertTrue(form.is_valid())
        bar = build_filter_bar(
            request,
            form=form,
            quick_fields=(),
            secondary_fields=("since",),
            result_count=1,
        )
        html = render_to_string("components/filter_bar.html", {"bar": bar})
        self.assertIn('data-jalali-date="date"', html)
        self.assertEqual(bar["chips"][0]["value"], "1405/06/24")

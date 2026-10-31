"""Focused CEP-017 navigation, breadcrumb, and mobile-shell contract checks."""

from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.test import SimpleTestCase


class Cep017NavigationTemplateTests(SimpleTestCase):
    def test_canonical_navigation_register_is_complete_and_persian_first(self) -> None:
        from core.product_surface import NAVIGATION_GROUPS, navigation_groups

        codes = {
            link.permission
            for group in NAVIGATION_GROUPS
            for link in group.links
            if link.permission
        }
        groups = navigation_groups(codes)
        rendered = Template('{% include "components/navigation_links.html" %}').render(
            Context(
                {
                    "navigation_is_authenticated": True,
                    "product_navigation_groups": groups,
                }
            )
        )
        self.assertEqual(rendered.count("data-surface-group="), 5)
        for group in groups:
            self.assertIn(group.label, rendered)
        self.assertNotIn('href="/treasury/"', rendered)
        self.assertNotIn('href="/workforce/ess/"', rendered)

    def test_empty_groups_and_hidden_targets_are_not_placeholders(self) -> None:
        from core.product_surface import navigation_groups

        rendered = Template('{% include "components/navigation_links.html" %}').render(
            Context(
                {
                    "navigation_is_authenticated": True,
                    "product_navigation_groups": navigation_groups({"accounting.view"}),
                }
            )
        )
        self.assertNotIn('data-surface-group="operations"', rendered)
        self.assertNotIn('aria-disabled="true"', rendered)
        self.assertNotIn('href="/accounting/"', rendered)

    def test_rfq_navigation_renders_one_state_for_each_permission_variant(self) -> None:
        from core.product_surface import navigation_groups

        template = Template('{% include "components/navigation_links.html" %}')
        for permissions in (set(), {"rfqs.view"}):
            with self.subTest(permissions=permissions):
                rendered = template.render(
                    Context(
                        {
                            "navigation_is_authenticated": True,
                            "product_navigation_groups": navigation_groups(permissions),
                        }
                    )
                )
                self.assertEqual(
                    rendered.count('href="/procurement/rfqs/"'), int(bool(permissions))
                )

    def test_shared_breadcrumb_and_mobile_close_contract_are_present(self) -> None:
        template_root = Path(settings.BASE_DIR) / "templates"
        base = (template_root / "base.html").read_text(encoding="utf-8")
        header = (template_root / "components" / "page_header.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("data-mobile-nav", base)
        self.assertIn("data-mobile-nav-close", base)
        self.assertIn('event.key === "Escape"', base)
        breadcrumbs = (template_root / "components" / "breadcrumbs.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('include "components/breadcrumbs.html"', header)
        self.assertIn('aria-label="مسیر صفحه"', breadcrumbs)
        self.assertIn("{% url 'home' %}", breadcrumbs)

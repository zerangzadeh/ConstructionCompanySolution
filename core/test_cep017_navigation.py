"""Focused CEP-017 navigation, breadcrumb, and mobile-shell contract checks."""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class Cep017NavigationTemplateTests(SimpleTestCase):
    def test_canonical_navigation_register_is_complete_and_persian_first(self) -> None:
        navigation = (
            Path(settings.BASE_DIR)
            / "templates"
            / "components"
            / "navigation_links.html"
        ).read_text(encoding="utf-8")
        expected_ids = {f"NAV-{number:03d}" for number in range(1, 44) if number != 42}
        rendered_ids = {
            token.split('"')[1]
            for token in navigation.split()
            if token.startswith("data-nav-id=")
        }
        self.assertEqual(rendered_ids, expected_ids)
        self.assertIn('data-canonical-navigation="43"', navigation)
        self.assertIn("صورت‌وضعیت و صورتحساب", navigation)
        self.assertIn("حاکمیت طرف‌های تجاری", navigation)
        base = (Path(settings.BASE_DIR) / "templates" / "base.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('data-nav-id="NAV-042"', base)
        self.assertIn("مدیریت پلتفرم", base)

    def test_unimplemented_targets_are_not_links_or_new_actions(self) -> None:
        navigation = (
            Path(settings.BASE_DIR)
            / "templates"
            / "components"
            / "navigation_links.html"
        ).read_text(encoding="utf-8")
        for node_id in (
            "NAV-009",
            "NAV-013",
            "NAV-015",
            "NAV-019",
            "NAV-039",
        ):
            marker = f'data-nav-id="{node_id}"'
            fragment = navigation[
                navigation.index(marker) : navigation.index(marker) + 220
            ]
            self.assertIn('aria-disabled="true"', fragment)
            self.assertNotIn("href=", fragment)

    def test_shared_breadcrumb_and_mobile_close_contract_are_present(self) -> None:
        template_root = Path(settings.BASE_DIR) / "templates"
        base = (template_root / "base.html").read_text(encoding="utf-8")
        header = (template_root / "components" / "page_header.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("data-mobile-nav", base)
        self.assertIn("data-mobile-nav-close", base)
        self.assertIn('event.key === "Escape"', base)
        self.assertIn('aria-label="مسیر صفحه"', header)
        self.assertIn("{% url 'home' %}", header)

import json
import os
from pathlib import Path
from secrets import token_urlsafe

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from apps.audit.models import AuditAction, AuditEvent
from apps.inventory.models import StockTransaction
from apps.inventory.test_inbound_transfers import InboundTransferFixture

root = Path(os.environ["B06_TMP"]) / "inbound-enhancement"
screens = root / "chrome"
screens.mkdir(exist_ok=True)


class InboundChrome(InboundTransferFixture, StaticLiveServerTestCase):
    host = "127.0.0.1"

    def _fixture_teardown(self):
        assert connections["default"].settings_dict["NAME"] in {
            "test_b06_inbound_chrome",
            "test_b06_inbound_chrome_retest",
        }

    def test_receiving_workbench(self):
        inbound = reverse("inventory:custody_workbench", query={"tab": "inbound"})
        history = reverse(
            "inventory:custody_workbench", query={"tab": "transfer-history"}
        )
        warehouse_list = reverse("inventory:warehouse_list")
        detail = reverse(
            "inventory:transfer_detail", args=[self.first.pk], query={"tab": "inbound"}
        )
        accept = reverse(
            "inventory:transfer_accept", args=[self.first.pk], query={"tab": "inbound"}
        )
        line = self.first.lines.get()
        payload = {f"accepted_{line.pk}": "3"}
        observations = {}

        def post(page, path, values=None):
            token = next(
                cookie["value"]
                for cookie in page.context.cookies()
                if cookie["name"] == "csrftoken"
            )
            return page.request.post(
                self.live_server_url + path,
                form=values or {},
                headers={"X-CSRFToken": token},
                max_redirects=0,
            ).status

        with (
            sync_playwright() as playwright,
            playwright.chromium.launch(channel="chrome", headless=True) as browser,
        ):
            observations["chrome_version"] = browser.version

            def sign_in(actor):
                password = token_urlsafe(26)
                actor.set_password(password)
                actor.save(update_fields=["password"])
                context = browser.new_context(
                    viewport={"width": 1440, "height": 900}, locale="fa-IR"
                )
                context.route(
                    "**/*",
                    lambda route: (
                        route.continue_()
                        if route.request.url.startswith(self.live_server_url + "/")
                        else route.abort()
                    ),
                )
                page = context.new_page()
                page.set_default_timeout(8000)
                page.goto(
                    self.live_server_url
                    + reverse("accounts:login", query={"next": warehouse_list})
                )
                page.locator("main [name=username]").fill(actor.username)
                page.locator("main [name=password]").fill(password)
                with page.expect_response(
                    lambda response: response.request.method == "POST"
                ) as login:
                    page.locator("main button[type=submit]").click()
                self.assertEqual(login.value.status, 302)
                page.wait_for_load_state()
                self.assertTrue(page.url.endswith(warehouse_list))
                return page

            page = sign_in(self.receiver)
            page.locator("main").get_by_role(
                "link", name="انتقال‌های ورودی در انتظار دریافت", exact=True
            ).click()
            self.assertTrue(page.url.endswith(inbound))
            self.assertEqual(
                page.locator("main h1").inner_text(), "انتقال‌های ورودی در انتظار دریافت"
            )
            page.wait_for_load_state()
            rows = page.locator("[data-receiving-transfer]")
            page.screenshot(path=root / "discovery-diagnostic.png", full_page=True)
            expect(rows).to_have_count(2)
            expect(rows.filter(has_text=self.first.transfer_number)).to_have_count(1)
            self.assertNotIn(
                self.hidden.transfer_number, page.locator("main").inner_text()
            )
            self.assertNotIn(
                self.dispatched.transfer_number, page.locator("main").inner_text()
            )
            self.assertNotIn("خلاصه موجودی شرکت", page.locator("main").inner_text())
            self.assertIn(self.source.name, page.locator("main").inner_text())
            self.assertIn(self.material.name, page.locator("main").inner_text())
            self.assertTrue(
                page.locator("[data-label='تاریخ ارسال']")
                .first.inner_text()
                .startswith("14")
            )
            options = page.locator(
                "select[name=destination] option"
            ).all_text_contents()
            self.assertEqual(len(options), 3)
            self.assertFalse(
                any(self.sibling_destination.name in option for option in options)
            )
            observations["discovery"] = {
                "start": "warehouse list",
                "pending": 2,
                "scoped_destination_options": 2,
                "initially_dispatched_only_hidden": True,
            }

            layouts = []
            for width in (1440, 1024, 390):
                page.set_viewport_size({"width": width, "height": 900})
                layout = page.evaluate("""() => ({
                    width:innerWidth, scrollWidth:document.documentElement.scrollWidth,
                    lang:document.documentElement.lang, direction:document.documentElement.dir,
                    rowLayout:getComputedStyle(document.querySelector('[data-receiving-transfer]')).display,
                    visibleActions:[...document.querySelectorAll('[data-receiving-transfer] a')].filter(el=>el.checkVisibility()).length
                })""")
                self.assertEqual(layout["direction"], "rtl")
                self.assertEqual(layout["lang"], "fa")
                self.assertEqual(layout["width"], layout["scrollWidth"])
                self.assertEqual(layout["visibleActions"], 2)
                layouts.append(layout)
                page.screenshot(path=screens / f"inbound-{width}.png", full_page=True)
            observations["layouts"] = layouts
            page.set_viewport_size({"width": 1440, "height": 900})

            page.get_by_label("جست‌وجوی انتقال", exact=True).fill("first")
            page.locator("[data-filter-apply]").click()
            expect(rows).to_have_count(1)
            self.assertIn(self.first.transfer_number, rows.first.inner_text())
            page.locator("[data-table-filter-clear]").click()
            expect(rows).to_have_count(2)
            selector = page.locator("select[name=destination]")
            control = selector.evaluate("el => el.tomselect.control_input.id")
            search = page.locator(f"[id='{control}']")
            search.click()
            search.fill("انبار دوم")
            page.locator(
                f".ts-dropdown [data-value='{self.second_destination.pk}']:visible"
            ).click()
            page.locator("[data-filter-apply]").click()
            expect(rows).to_have_count(1)
            self.assertIn(self.second.transfer_number, rows.first.inner_text())
            bad = page.goto(
                self.live_server_url
                + reverse(
                    "inventory:custody_workbench",
                    query={
                        "tab": "inbound",
                        "destination": self.sibling_destination.pk,
                    },
                )
            )
            self.assertEqual(bad.status, 200)
            expect(rows).to_have_count(0)
            self.assertIn(
                "انبار مقصد را از گزینه‌های مجاز انتخاب کنید",
                page.locator("main").inner_text(),
            )
            observations["filters"] = {
                "reference_search": True,
                "warehouse_search_and_filter": True,
                "forged_destination_empty": True,
            }

            for actor, label, expected_detail in (
                (self.sender, "source_only", 200),
                (self.sibling, "sibling_project", 404),
                (self.outsider, "foreign_tenant", 404),
            ):
                restricted = sign_in(actor)
                self.assertEqual(
                    restricted.goto(self.live_server_url + inbound).status, 200
                )
                self.assertNotIn(
                    self.first.transfer_number, restricted.locator("main").inner_text()
                )
                if label == "source_only":
                    self.assertIn(
                        "در حال حاضر انتقالی برای دریافت",
                        restricted.locator("main").inner_text(),
                    )
                self.assertEqual(
                    restricted.goto(self.live_server_url + detail).status,
                    expected_detail,
                )
                self.assertEqual(
                    restricted.get_by_role("button", name="ثبت پذیرش مستقل").count(), 0
                )
                self.assertEqual(post(restricted, accept, payload), 404)
                observations[label] = {
                    "absent_from_pending": True,
                    "detail_status": expected_detail,
                    "accept_status": 404,
                }
                restricted.context.close()

            page.goto(self.live_server_url + inbound)
            page.locator("[data-receiving-transfer]").filter(
                has_text=self.first.transfer_number
            ).get_by_role("link", name="مشاهده و دریافت").click()
            self.assertTrue(page.url.endswith(detail))
            self.assertEqual(
                post(
                    page, reverse("inventory:transfer_dispatch", args=[self.first.pk])
                ),
                404,
            )
            self.assertEqual(
                post(
                    page, reverse("inventory:transfer_in_transit", args=[self.first.pk])
                ),
                404,
            )
            with page.expect_response(
                lambda response: response.request.method == "POST"
            ) as submission:
                page.get_by_role("button", name="ثبت پذیرش مستقل").click()
                if page.locator(".swal2-confirm").is_visible():
                    page.locator(".swal2-confirm").click()
            self.assertEqual(submission.value.status, 302)
            page.wait_for_load_state()
            self.assertIn("پذیرفته‌شده", page.locator("main").inner_text())
            self.assertEqual(post(page, accept, payload), 302)
            page.locator("main").get_by_role(
                "link", name="انتقال‌های ورودی در انتظار دریافت", exact=True
            ).click()
            expect(rows).to_have_count(1)
            self.assertNotIn(
                self.first.transfer_number, page.locator("main").inner_text()
            )
            page.get_by_role("link", name="سوابق انتقال", exact=True).click()
            self.assertTrue(page.url.endswith(history))
            expect(rows).to_have_count(1)
            self.assertIn(self.first.transfer_number, rows.first.inner_text())
            self.assertIn("پذیرفته‌شده", rows.first.inner_text())
            page.screenshot(path=screens / "history-1440.png", full_page=True)
            rows.first.get_by_role("link", name="مشاهده جزئیات").click()
            self.assertIn("tab=transfer-history", page.url)
            self.assertEqual(
                page.get_by_role("button", name="ثبت پذیرش مستقل").count(), 0
            )

        self.first.refresh_from_db()
        self.assertEqual(self.first.accepted_by_id, self.receiver.pk)
        self.assertEqual(
            StockTransaction.objects.filter(
                organization=self.organization, reference=self.first.transfer_number
            ).count(),
            2,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                entity_id=str(self.first.pk),
                action=AuditAction.INVENTORY_TRANSFER_TRANSITIONED,
            ).count(),
            4,
        )
        observations["acceptance"] = {
            "accepted": True,
            "replay_stock_movements": 2,
            "dispatch_audit_plus_acceptance_transitions": 4,
            "pending_removed": True,
            "history_link_retained": True,
            "source_actions_denied": True,
        }
        (screens / "observations.json").write_text(
            json.dumps(observations, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

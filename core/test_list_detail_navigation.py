"""Focused navigation contracts; no business records or permissions are created."""

from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace as Row
from uuid import UUID

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.urls import resolve, reverse


class Links(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links = []
        self.current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.current = {**dict(attrs), "text": ""}

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.current["text"] = self.current["text"].strip()
            self.links.append(self.current)
            self.current = None


class ListDetailNavigationTests(SimpleTestCase):
    identifier = UUID("11111111-1111-4111-8111-111111111111")

    def row(self, **values):
        return Row(id=self.identifier, pk=self.identifier, **values)

    def links(self, template, **context):
        return Links(render_to_string(template, context)).links

    def assert_detail(self, links, url, identity=None):
        matching = [link for link in links if link.get("href") == url]
        self.assertTrue(matching, url)
        actions = [link for link in matching if link["text"] == "مشاهده جزئیات"]
        self.assertEqual(len(actions), 1)
        self.assertIn("erp-btn--secondary", actions[0]["class"])
        self.assertTrue(actions[0]["aria-label"].startswith("مشاهده جزئیات "))
        if identity:
            self.assertIn(identity, [link["text"] for link in matching])
        self.assertNotRegex(
            resolve(url).url_name, r"(?:^|_)(?:edit|change|transition|workbench)$"
        )

    def test_shared_action_has_no_empty_destination_and_escapes_record_name(self):
        self.assertEqual(self.links("components/record_detail_link.html"), [])
        html = render_to_string(
            "components/record_detail_link.html",
            {"detail_url": "/documents/example/", "record_label": '<img src="x">'},
        )
        self.assertNotIn('<img src="x">', html)
        self.assertIn("&lt;img", html)

    def test_list_primary_identity_and_action_share_the_canonical_destination(self):
        fixtures = [
            (
                "parties/list.html",
                "parties",
                self.row(display_name="همکار"),
                "parties:detail",
                "همکار",
            ),
            (
                "parties/governance_list.html",
                "parties",
                self.row(display_name="همکار"),
                "parties:governance_detail",
                "همکار",
            ),
            (
                "documents/list.html",
                "documents",
                self.row(title="سند"),
                "documents:detail",
                "سند",
            ),
            (
                "estimates/list.html",
                "estimates",
                self.row(title="برآورد", estimate_number="EST-1"),
                "estimates:detail",
                "EST-1",
            ),
            (
                "payroll/ess_history.html",
                "payslips",
                self.row(number="PAY-1"),
                "payroll:ess_payslip",
                "PAY-1",
            ),
        ]
        for template, collection, row, route, identity in fixtures:
            with self.subTest(template=template):
                links = self.links(template, **{collection: [row]})
                self.assert_detail(links, reverse(route, args=[row.pk]), identity)

    def test_search_results_link_the_title_to_the_same_scoped_result_url(self):
        url = reverse("materials:material_detail", args=[self.identifier])
        links = self.links(
            "core/global_search.html",
            search=Row(query="مصالح", results=[Row(title="مصالح", url=url)]),
        )
        self.assert_detail(links, url, "مصالح")

    def test_photo_title_opens_detail_while_preview_keeps_its_download_guard(self):
        document = self.row(
            title="تصویر",
            current_version=Row(is_available=True),
            created_at=datetime(2026, 10, 26, tzinfo=timezone.utc),
        )
        detail = reverse("documents:detail", args=[document.pk])
        preview = reverse("documents:photo-preview", args=[document.pk])
        for can_download in (False, True):
            links = self.links(
                "projects/gallery.html",
                project=self.row(),
                photos=[Row(document=document)],
                can_download=can_download,
            )
            self.assertIn(
                "تصویر", [link["text"] for link in links if link.get("href") == detail]
            )
            self.assertEqual(
                any(link.get("href") == preview for link in links), can_download
            )

    def test_every_compliance_table_kind_keeps_its_registered_record_detail(self):
        for kind in ("inspection", "permit", "test", "finding", "ncr", "capa"):
            with self.subTest(kind=kind):
                row = self.row(number="REC-1")
                if kind in {"inspection", "test", "finding"}:
                    row.title = "رکورد"
                links = self.links("compliance/_table.html", records=[row], kind=kind)
                url = reverse("compliance:detail", args=[kind, row.pk])
                self.assert_detail(links, url, "REC-1")

    def test_reporting_drillthrough_retains_the_existing_per_result_guard(self):
        result = self.row(
            run=Row(metric_version=Row(definition=Row(persian_name="شاخص")))
        )
        url = reverse("reporting:drillthrough", args=[result.pk])
        for allowed in (False, True):
            links = self.links(
                "reporting/_read_model_card.html",
                card=Row(result=result, can_drillthrough=allowed),
            )
            if allowed:
                self.assert_detail(links, url, "شاخص")
            else:
                self.assertFalse(any(link.get("href") == url for link in links))

    def test_treasury_rows_reuse_the_existing_resource_detail_url(self):
        url = reverse("treasury:operational_detail", args=["account", self.identifier])
        links = self.links(
            "treasury/operations.html",
            groups=[Row(title="حساب‌ها", rows=[Row(title="ACC-1", detail_url=url)])],
        )
        self.assert_detail(links, url, "ACC-1")

    def test_warehouse_transaction_links_retain_the_destination_permission(self):
        transaction = self.row(transaction_number="ST-1")
        material = self.row(name="مصالح")
        url = reverse("inventory:transaction_detail", args=[transaction.pk])
        material_url = reverse("materials:material_detail", args=[material.pk])
        for allowed in (False, True):
            links = self.links(
                "inventory/warehouse_detail.html",
                warehouse=self.row(),
                transactions=[transaction],
                balance_rows=[Row(material=material, quantity=1)],
                business_permission_codes=["stock_transactions.view", "materials.view"]
                if allowed
                else [],
            )
            self.assertEqual(any(link.get("href") == url for link in links), allowed)
            self.assertEqual(
                any(link.get("href") == material_url for link in links), allowed
            )

    def test_list_fragments_are_never_advertised_as_record_details(self):
        url = reverse("timekeeping:workbench") + f"#leave-{self.identifier}"
        row = Row(source_label="مرخصی", source_url=url)
        for template, context in (
            ("workflows/my_requests.html", {"request_rows": [row]}),
            ("workflows/manager_workspace.html", {"manager": Row(rows=[row])}),
        ):
            with self.subTest(template=template):
                links = self.links(template, **context)
                matching = [link for link in links if link.get("href") == url]
                self.assertEqual(
                    [link["text"] for link in matching], ["رفتن به ردیف منبع"]
                )

    def test_explicit_ess_source_details_and_unavailable_sources_stay_distinct(self):
        url = reverse("workforce:personal_change_detail", args=[self.identifier])
        for template, context in (
            (
                "workflows/my_requests.html",
                {"request_rows": [Row(source_label="درخواست", source_url=url)]},
            ),
            (
                "workforce/personal_change_requests.html",
                {"rows": [Row(source_label="درخواست", source_url=url)]},
            ),
        ):
            with self.subTest(template=template):
                self.assert_detail(self.links(template, **context), url, "درخواست")
        links = self.links(
            "workflows/my_requests.html", request_rows=[Row(source_url="")]
        )
        self.assertFalse(any(link["text"] == "مشاهده جزئیات" for link in links))

    def test_maintenance_work_item_navigation_uses_the_real_read_detail(self):
        from apps.workflows.registry import registry

        self.assertEqual(
            registry.subject_adapters["equipment.maintenance_record"].detail_url_name,
            "equipment:maintenance_detail",
        )
        url = reverse("equipment:maintenance_detail", args=[self.identifier])
        links = self.links(
            "workflows/_work_item_row.html",
            item=self.row(
                subject_title="تعمیر",
                source_url=url,
                instance=Row(subject_type="equipment.maintenance_record"),
            ),
        )
        self.assertEqual(
            [link["text"] for link in links if link.get("href") == url], ["تعمیر"]
        )

    def test_member_identity_does_not_disguise_edit_as_a_detail(self):
        membership = self.row(user=Row(username="sample"))
        url = reverse("organizations:member_update", args=[membership.pk])
        for allowed in (False, True):
            links = self.links(
                "organizations/members.html",
                memberships=[membership],
                can_manage_members=allowed,
            )
            matching = [link for link in links if link.get("href") == url]
            self.assertEqual(
                [link["text"] for link in matching], ["ویرایش عضویت"] if allowed else []
            )

    def test_site_identity_does_not_disguise_a_project_site_list_as_a_detail(self):
        project = self.row(name="پروژه")
        links = self.links(
            "projects/all_site_list.html",
            sites=[self.row(name="کارگاه", project=project, project_id=project.pk)],
        )
        url = reverse("projects:site_list", args=[project.pk])
        matching = [link for link in links if link.get("href") == url]
        self.assertEqual([link["text"] for link in matching], ["کارگاه‌های پروژه"])
        detail_url = reverse("projects:site_detail", args=[project.pk, self.identifier])
        self.assertIn(
            "کارگاه", [link["text"] for link in links if link.get("href") == detail_url]
        )

    def test_recursive_department_cards_have_real_detail_links(self):
        node = Row(department=self.row(name="واحد"), children=[])
        for template in (
            "workforce/_department_tree.html",
            "workforce/_organization_chart_node.html",
            "workforce/_organization_chart_details.html",
        ):
            with self.subTest(template=template):
                links = self.links(
                    template,
                    nodes=[Row(department=self.row(name="ریشه"), children=[node])],
                )
                url = reverse("workforce:department_detail", args=[node.department.pk])
                self.assertIn(
                    "واحد", [link["text"] for link in links if link.get("href") == url]
                )

    def test_publication_version_links_require_the_separate_publication_permission(
        self,
    ):
        version = self.row(version_number=2)
        item = Row(publication=Row(versions=Row(all=[version])))
        url = reverse("knowledge:publication_detail", args=[version.pk])
        for allowed in (False, True):
            links = self.links(
                "knowledge/publication_history.html",
                item=item,
                business_permission_codes=["knowledge.publications_view"]
                if allowed
                else [],
            )
            self.assertEqual(any(link.get("href") == url for link in links), allowed)

    def test_own_timekeeping_rows_keep_the_own_identity_route(self):
        row = self.row(created_at=datetime(2026, 10, 26, tzinfo=timezone.utc))
        for kind in (
            "leave",
            "mission",
            "overtime",
            "attendance",
            "correction",
            "timesheet",
        ):
            with self.subTest(kind=kind):
                url = reverse("workforce:ess_timekeeping_detail", args=[kind, row.pk])
                self.assert_detail(
                    self.links(
                        "workforce/ess_timekeeping.html",
                        panels=[
                            Row(kind=kind, label="سابقه", rows=[row], state="ready")
                        ],
                    ),
                    url,
                )

    def test_template_detail_action_labels_do_not_drift(self):
        roots = [
            settings.BASE_DIR / "templates",
            *settings.BASE_DIR.glob("apps/*/templates"),
        ]
        for root in roots:
            for path in root.rglob("*.html"):
                for link in Links(path.read_text(encoding="utf-8-sig")).links:
                    if "detail" not in link.get("href", ""):
                        continue
                    self.assertNotIn(
                        link["text"],
                        {
                            "مشاهده",
                            "نمایش",
                            "باز کردن",
                            "بررسی",
                            "جزئیات",
                            "جزئیات و اقدام",
                            "بررسی جزئیات ←",
                        },
                        str(path.relative_to(Path(settings.BASE_DIR))),
                    )


class ClassifiedNavigationTests(SimpleTestCase):
    identifier = ListDetailNavigationTests.identifier
    row = ListDetailNavigationTests.row
    links = ListDetailNavigationTests.links

    def test_resolution_source_producers_return_authoritative_details(self):
        from apps.workflows.personal_workspaces import _source_url

        for kind in ("leave", "overtime", "correction"):
            self.assertEqual(
                _source_url(kind, self.identifier, allowed=True),
                reverse("timekeeping:record_detail", args=[kind, self.identifier]),
            )
            self.assertEqual(_source_url(kind, self.identifier, allowed=False), "")

    def test_resolution_source_links_retain_existing_destination_permissions(self):
        cases = [
            (
                "inventory/valuation_workbench.html",
                "events",
                self.row(
                    stock_transaction_id=self.identifier,
                    stock_transaction=Row(transaction_number="ST-1"),
                ),
                "visible_transaction_ids",
                reverse("inventory:transaction_detail", args=[self.identifier]),
            ),
            (
                "projects/control_exceptions.html",
                None,
                Row(advisory_overruns=[Row(expense=self.row(description="هزینه"))]),
                "visible_expense_ids",
                reverse("expenses:detail", args=[self.identifier]),
            ),
        ]
        for template, collection, row, visibility_key, url in cases:
            for allowed in (False, True):
                context = (
                    {collection: [row]}
                    if collection
                    else {"snapshot": row, "project": self.row()}
                )
                links = self.links(
                    template,
                    **context,
                    **{visibility_key: {self.identifier} if allowed else set()},
                )
                self.assertEqual(
                    any(link.get("href") == url for link in links), allowed
                )

    def test_resolution_read_detail_preserves_zero_and_has_no_forms(self):
        html = render_to_string(
            "components/read_only_record_detail.html",
            {
                "detail_title": "رکورد",
                "back_url": "/projects/",
                "detail_rows": [
                    ("مبلغ", 0, "number"),
                    ("شرح", "<script>alert(1)</script>", "text"),
                ],
            },
        )
        self.assertIn("<bdi>0</bdi>", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertNotIn('method="post"', html.split("<main", 1)[-1])

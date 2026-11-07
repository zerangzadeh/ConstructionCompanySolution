"""Contract-local source identity, narrowing, permissions and offline Chrome evidence."""

import json
import os
import subprocess
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing.models import ProgressRecord
from apps.billing.services import (
    create_progress_record,
    request_progress_verification,
)
from apps.contracts.models import Contract
from apps.contracts.test_payable_detail_dashboard import PayableDetailFixture
from apps.projects.test_command_center import scoped_reader
from core.templatetags.product_surface import module_selector_links

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "output/contract-hub-remediation"


def quantities(contract, **query):
    return (
        reverse("contracts:detail", args=[contract.pk])
        + "?"
        + urlencode({"section": "quantities", **query}, doseq=True)
    )


class HubFixture(PayableDetailFixture):
    def prepare_hub(self):
        self.prepare_payable()
        self.old_record = self._verified_record()
        self.new_baseline = self._approved_baseline()
        self.new_record = create_progress_record(
            organization=self.organization,
            actor=self.owner,
            baseline=self.new_baseline,
            baseline_item=self.new_baseline.items.get(),
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            measured_on=date(2026, 10, 15),
            source_type="site_report",
            source_reference="HUB-NEW-01",
            period_quantity=Decimal("0.1000"),
            cumulative_quantity=Decimal("0.6000"),
        )
        self.login(self.owner)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ContractHubTests(HubFixture, TestCase):
    def setUp(self):
        self.prepare_hub()

    def test_unmapped_lines_and_historical_versions_keep_independent_identity(self):
        response = self.client.get(quantities(self.contract, pane="basis"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["hub"]["baseline"], self.new_baseline)
        self.assertIsNone(
            response.context["hub"]["page"].object_list[0].contract_item_id
        )
        self.assertContains(response, "line_key=ITEM-01")
        historical = self.client.get(
            quantities(
                self.contract, pane="basis", baseline=self.old_record.baseline_id
            )
        )
        self.assertEqual(historical.context["hub"]["baseline"].status, "superseded")
        self.assertContains(historical, "تأییدکننده")
        self.assertContains(historical, "زمان تأیید")
        self.assertContains(historical, "وضعیت یا مجازبودن عملیات آن را تغییر نمی‌دهد")
        self.assertNotIn(
            'type="submit"',
            historical.content.decode().split('class="contract-detail"', 1)[1],
        )
        # Selecting a snapshot cannot mutate or rebase historical source records.
        self.old_record.refresh_from_db()
        self.assertNotEqual(self.old_record.baseline_id, self.new_baseline.pk)

    def test_line_history_includes_versions_and_retains_context_on_search_clear(self):
        path = reverse("billing:progress_list")
        query = {"contract": str(self.contract.pk), "line_key": "ITEM-01"}
        response = self.client.get(path, {**query, "q": self.contract.title})
        self.assertEqual(
            {r.pk for r in response.context["progress_records"]},
            {self.old_record.pk, self.new_record.pk},
        )
        self.assertEqual(
            response.context["filter_bar"]["hidden"]["line_key"], "ITEM-01"
        )
        self.assertIn("line_key=ITEM-01", response.context["clear_filters_url"])
        self.assertContains(response, "نسخه مبنا")
        for bad in (
            {"line_key": "ITEM-01"},
            {**query, "contract": "invalid"},
            {**query, "line_key": ["ITEM-01", "OTHER"]},
            {**query, "line_key": "x" * 81},
        ):
            with self.subTest(query=bad):
                self.assertEqual(
                    self.client.get(path, bad).context["page_obj"].paginator.count, 0
                )

    def test_payable_items_and_contract_line_history_are_separate_from_baselines(self):
        from apps.contracts.services import add_contract_item, create_contract

        draft = create_contract(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            contract_number="HUB-ORDER",
            title="ترتیب ردیف‌ها",
            counterparty_name=self.party.display_name,
            party=self.party,
            direction="receivable",
        )
        labels = ["ردیف نخست", "ردیف دوم", "ردیف سوم"]
        for label in labels:
            add_contract_item(
                organization=self.organization,
                actor=self.owner,
                contract=draft,
                description=label,
                quantity=Decimal(1),
                unit_price=Decimal(1),
                sort_order=0,
            )
        self.assertEqual(
            [
                row.description
                for row in self.client.get(quantities(draft)).context["hub"]["page"]
            ],
            labels,
        )
        response = self.client.get(quantities(self.payable))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["hub"]["basis_allowed"])
        self.assertNotContains(response, "pane=basis")
        item = self.payable.items.get()
        self.assertContains(response, f"contract_item={item.pk}")
        history = reverse("billing:payable_measurement_list")
        result = self.client.get(
            history, {"contract": self.payable.pk, "contract_item": item.pk}
        )
        self.assertEqual(len(result.context["measurements"]), 3)
        self.assertEqual(
            len(
                self.client.get(
                    history, {"contract": self.contract.pk, "contract_item": item.pk}
                ).context["measurements"]
            ),
            0,
        )
        self.assertEqual(
            len(
                self.client.get(history, {"contract": "invalid"}).context[
                    "measurements"
                ]
            ),
            0,
        )

    def test_no_baseline_or_measurement_authority_is_granted_by_contract_access(self):
        reader, _, _ = scoped_reader(
            self.organization, self.project, ["contracts.view"], username="hub-reader"
        )
        self.login(reader)
        result = self.client.get(quantities(self.contract))
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.context["hub"]["basis_allowed"])
        self.assertFalse(result.context["hub"]["history_url"])
        self.assertEqual(
            self.client.get(quantities(self.contract, pane="basis")).status_code, 404
        )
        self.assertEqual(
            self.client.get(reverse("billing:progress_list")).status_code, 403
        )
        self.assertEqual(
            self.client.get(reverse("billing:payable_measurement_list")).status_code,
            403,
        )
        Contract.objects.filter(pk=self.payable.pk).update(contract_type="supplier")
        self.login(self.owner)
        supplier = self.client.get(quantities(self.payable))
        self.assertFalse(supplier.context["hub"]["history_url"])
        self.assertFalse(supplier.context["hub"]["basis_allowed"])

    def test_foreign_contract_and_foreign_baseline_fail_closed(self):
        # A baseline belonging to a different authorized contract is still invalid here.
        other_contract = Contract.objects.create(
            organization=self.organization,
            project=self.project,
            contract_number="HUB-OTHER",
            title="Other authorized contract",
            counterparty_name="Synthetic client",
            direction="receivable",
            status="active",
        )
        self.assertEqual(
            self.client.get(
                quantities(other_contract, pane="basis", baseline=self.new_baseline.pk)
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                quantities(self.payable, pane="basis", baseline=self.new_baseline.pk)
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                quantities(self.contract, pane="basis", baseline="invalid")
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                quantities(
                    self.contract,
                    pane="basis",
                    baseline=[
                        str(self.new_baseline.pk),
                        str(self.old_record.baseline_id),
                    ],
                )
            ).status_code,
            404,
        )
        from apps.organizations.models import Organization
        from apps.projects.models import Project

        foreign = Organization.objects.create(
            name="Foreign synthetic", slug="hub-foreign"
        )
        project = Project.objects.create(
            organization=foreign, code="FOREIGN", name="Foreign"
        )
        contract = Contract.objects.create(
            organization=foreign,
            project=project,
            contract_number="FOREIGN",
            title="Hidden",
            counterparty_name="Hidden",
        )
        self.assertEqual(self.client.get(quantities(contract)).status_code, 404)
        history = self.client.get(
            reverse("billing:progress_list"),
            {"contract": contract.pk, "line_key": "ITEM-01"},
        )
        self.assertEqual(history.context["page_obj"].paginator.count, 0)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ContractHubBrowserTests(HubFixture, StaticLiveServerTestCase):
    serialized_rollback = True
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown

    def test_measurement_detail_states_and_shared_decisions(self):
        from apps.billing.services import reject_progress_record, verify_progress_record

        self.ready()
        records = {}
        for state in ("verified", "rejected", "submitted", "draft"):
            record = self._record()
            record.source_reference = "SYNTHETIC-LONG-SOURCE-REFERENCE-" + "A" * 75
            record.evidence = (
                "گزارش اندازه‌گیری نمونه؛ شواهد صرفاً برای آزمون رابط کاربری."
            )
            record.save(update_fields=["source_reference", "evidence"])
            if state != "draft":
                request_progress_verification(
                    organization=self.organization, actor=self.owner, record=record
                )
            if state == "verified":
                verify_progress_record(
                    organization=self.organization,
                    actor=self.manager,
                    record=record,
                    reason="کنترل مستقل شواهد و مقدار ثبت‌شده نمونه",
                )
            elif state == "rejected":
                reject_progress_record(
                    organization=self.organization,
                    actor=self.manager,
                    record=record,
                    reason="شواهد اندازه‌گیری نمونه نیازمند بررسی است",
                )
            record.refresh_from_db()
            records[state] = record
        self.browser_evidence_directory = OUTPUT / "measurement-detail/browser"
        scenarios = []
        geometry = """(() => {const root=document.querySelector('.measurement-detail');return !!root && !root.querySelector('[data-billing-navigation]') && document.documentElement.scrollWidth<=innerWidth+1 && [...root.querySelectorAll('.measurement-values article')].length===3 && [...root.querySelectorAll('.measurement-values article')].every(e=>e.scrollWidth<=e.clientWidth+1)})()"""
        for width in (1440, 1024, 390):
            for state, record in records.items():
                steps = [
                    {
                        "inspect": geometry,
                        "description": "Single-record hierarchy, three original quantities and no document overflow",
                    },
                    {
                        "toggleSelector": ".measurement-source summary",
                        "inspect": "document.querySelector('.measurement-source').open && [...document.querySelectorAll('.measurement-source dd')].every(e=>e.scrollWidth<=e.clientWidth+1)",
                        "description": "Long source reference and evidence fit disclosure",
                    },
                    {
                        "toggleSelector": ".measurement-source summary",
                        "inspect": "!document.querySelector('.measurement-source').open",
                        "description": "Source disclosure closes without changing state",
                    },
                ]
                if state == "submitted":
                    for action in ("verify", "reject"):
                        form = f'form[action$="/{action}/"]'
                        steps += [
                            {
                                "fill": {"reason": "دلیل آزمایشی حفظ شود"},
                                "formSelector": form,
                                "inspect": "true",
                                "description": "Reason stays in the original inline field",
                            },
                            {
                                "toggleSelector": form + " button",
                                "waitMs": 300,
                                "inspect": "Swal.isVisible() && getComputedStyle(Swal.getPopup()).direction==='rtl' && Swal.getPopup().getBoundingClientRect().width<=innerWidth && document.activeElement===Swal.getCancelButton()",
                                "description": "Shared RTL confirmation fits viewport and defaults to cancel",
                            },
                            {
                                "toggleSelector": ".swal2-cancel",
                                "waitMs": 300,
                                "inspect": f"!Swal.isVisible() && document.querySelector('{form} textarea').value==='دلیل آزمایشی حفظ شود'",
                                "description": "Cancel keeps entered reason and leaves the measurement pending",
                            },
                        ]
                elif state == "draft":
                    steps += [
                        {
                            "toggleSelector": 'form[action$="/submit/"] button',
                            "waitMs": 300,
                            "inspect": "Swal.isVisible() && Swal.getPopup().getBoundingClientRect().width<=innerWidth",
                            "description": "Draft submit consumes the same local shared confirmation",
                        },
                        {
                            "toggleSelector": ".swal2-cancel",
                            "waitMs": 300,
                            "inspect": "!Swal.isVisible()",
                            "description": "Cancelled submission leaves the draft unchanged",
                        },
                    ]
                scenarios.append(
                    {
                        "name": f"measurement-{state}-{width}",
                        "path": reverse("billing:progress_detail", args=[record.pk]),
                        "width": width,
                        "mobile": width == 390,
                        "status": 200,
                        "screenshot": True,
                        "bottomScreenshot": True,
                        "noJsErrors": True,
                        "noHttpErrors": True,
                        "mustText": [
                            "جزئیات کارکرد",
                            "کارکرد این ثبت",
                            "کارکرد تجمعی تا این ثبت",
                            "مقدار مبنای قلم",
                            "نتیجه بررسی",
                        ],
                        "mustLinks": [
                            reverse("billing:progress_list")
                            + f"?contract={self.contract.pk}&line_key=ITEM-01"
                        ],
                        "steps": steps,
                    }
                )
        browser_fixture.ContractBillingBrowserTests.browser(
            self, self.manager, scenarios
        )
        for state, record in records.items():
            record.refresh_from_db()
            self.assertEqual(record.status, state)

    def test_history_explains_records_and_supports_line_focus_and_search(self):
        from apps.billing.services import (
            add_baseline_item,
            approve_project_baseline,
            create_project_baseline,
            request_project_baseline_approval,
            verify_progress_record,
        )

        self.ready()
        baseline = create_project_baseline(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            contract=self.contract,
            effective_date=date(2026, 9, 1),
        )
        items = []
        for key, description in (
            ("WORK", "عملیات اجرایی و تأمین نیروی متخصص"),
            ("MATERIALS", "تأمین مصالح و تجهیزات مرتبط"),
        ):
            items.append(
                add_baseline_item(
                    organization=self.organization,
                    actor=self.owner,
                    baseline=baseline,
                    line_key=key,
                    description=description,
                    unit="ea",
                    planned_quantity=Decimal(1),
                    unit_rate=Decimal(60),
                )
            )
        request_project_baseline_approval(
            organization=self.organization, actor=self.owner, baseline=baseline
        )
        baseline = approve_project_baseline(
            organization=self.organization,
            actor=self.manager,
            baseline=baseline,
            reason="Independent synthetic fixture review",
        )
        previous = Decimal(0)
        for day, cumulative in (
            (2, Decimal("0.10")),
            (4, Decimal("0.25")),
            (6, Decimal("0.35")),
            (8, Decimal("0.45")),
        ):
            for item in items:
                record = create_progress_record(
                    organization=self.organization,
                    actor=self.owner,
                    baseline=baseline,
                    baseline_item=item,
                    period_start=date(2026, 9, 1),
                    period_end=date(2026, 9, 30),
                    measured_on=date(2026, 9, day),
                    source_type="site_report",
                    source_reference=f"HISTORY-{item.line_key}-{day}",
                    period_quantity=cumulative - previous,
                    cumulative_quantity=cumulative,
                )
                request_progress_verification(
                    organization=self.organization, actor=self.owner, record=record
                )
                verify_progress_record(
                    organization=self.organization,
                    actor=self.manager,
                    record=record,
                    reason="Independent synthetic quantity review",
                )
            previous = cumulative
        snapshot = list(
            ProgressRecord.objects.filter(baseline=baseline)
            .order_by("pk")
            .values_list("pk", "period_quantity", "cumulative_quantity", "status")
        )
        self.browser_evidence_directory = OUTPUT / "history-clarity/browser"
        listing = reverse("billing:progress_list")
        context = f"?contract={self.contract.pk}"
        rows = "document.querySelectorAll('[data-progress-records] tbody tr').length"
        common = {
            "status": 200,
            "screenshot": True,
            "bottomScreenshot": True,
            "noJsErrors": True,
            "noHttpErrors": True,
            "mustText": [
                "این صفحه را چطور بخوانیم؟",
                "مقدار کارکرد دوره",
                "کارکرد تجمعی تا این تاریخ",
                "جزئیات کارکرد ثبت‌شده",
            ],
        }
        scenarios = []
        for width in (1440, 1024, 390):
            size = {"width": width, "mobile": width == 390}
            scenarios += [
                {
                    **common,
                    **size,
                    "name": f"history-reading-{width}",
                    "path": listing + context,
                    "steps": [
                        {
                            "inspect": f"{rows}===8 && ![...document.querySelectorAll('.history-records .erp-list-title')].some(e=>e.innerText.includes({json.dumps(self.contract.title)})) && document.documentElement.scrollWidth<=innerWidth+1",
                            "description": "Eight source measurements, no repeated contract title, fitted reading guide",
                        },
                        {
                            "fill": {"q": "مصالح"},
                            "formSelector": "#list-filter-bar",
                            "inspect": "true",
                            "description": "Search the actual work-item description",
                        },
                        {
                            "clickSelector": ".erp-list-search__submit",
                            "afterPath": listing,
                        },
                        {
                            "inspect": f"{rows}===4 && new URLSearchParams(location.search).get('contract')==='{self.contract.pk}'",
                            "description": "Description search narrows to four records in the same contract",
                        },
                        {
                            "clickSelector": '[data-filter-chip="q"]',
                            "afterPath": listing,
                        },
                        {
                            "inspect": f"{rows}===8",
                            "description": "Clear search restores all eight records",
                        },
                        {
                            "clickSelector": '.history-line-link[href*="line_key=WORK"]',
                            "afterPath": listing,
                        },
                        {
                            "inspect": f"{rows}===4 && !!document.querySelector('.history-line-context') && new URLSearchParams(location.search).get('line_key')==='WORK'",
                            "description": "Exact line focus shows four historical measurements",
                        },
                        {
                            "clickSelector": ".history-line-context a",
                            "afterPath": listing,
                        },
                        {
                            "inspect": f"{rows}===8 && !document.querySelector('.history-line-context') && document.documentElement.scrollWidth<=innerWidth+1",
                            "description": "Return to all contract lines without changing source quantities",
                        },
                    ],
                },
                {
                    **common,
                    **size,
                    "name": f"history-one-line-{width}",
                    "path": listing + context + "&line_key=WORK",
                    "mustText": [
                        *common["mustText"],
                        "نمایش سوابق یک قلم کار",
                        items[0].description,
                    ],
                    "steps": [
                        {
                            "inspect": f"{rows}===4 && !!document.querySelector('.history-line-context') && document.documentElement.scrollWidth<=innerWidth+1",
                            "description": "One-line history has explicit context and four preserved source records",
                        }
                    ],
                },
            ]
        browser_fixture.ContractBillingBrowserTests.browser(self, self.owner, scenarios)
        self.assertEqual(
            list(
                ProgressRecord.objects.filter(baseline=baseline)
                .order_by("pk")
                .values_list("pk", "period_quantity", "cumulative_quantity", "status")
            ),
            snapshot,
        )

    def test_measurement_history_is_a_focused_contract_collection(self):
        self.ready()
        record = self._verified_record()
        self.browser_evidence_directory = (
            OUTPUT / "measurement-history-followup/browser"
        )
        listing = reverse("billing:progress_list")
        parent = quantities(self.contract)
        scenarios = []
        for width in (1440, 1024, 390):
            for line in (False, True):
                scenarios.append(
                    {
                        "name": f"history-{'line' if line else 'contract'}-{width}",
                        "path": quantities(
                            self.contract, **({"pane": "basis"} if line else {})
                        ),
                        "width": width,
                        "mobile": width == 390,
                        "status": 200,
                        "screenshot": True,
                        "noJsErrors": True,
                        "noHttpErrors": True,
                        "steps": [
                            {
                                "clickSelector": ".cd-quantity-table a[href*=line_key]"
                                if line
                                else '.cd-quantity-tabs a[href*="/billing/progress/"]',
                                "afterPath": listing,
                            },
                            {
                                "inspect": f"!document.querySelector('[data-billing-navigation]') && new URLSearchParams(location.search).get('contract')==='{self.contract.pk}' && new URLSearchParams(location.search).get('line_key')==={json.dumps(record.baseline_item.line_key if line else None)} && document.documentElement.scrollWidth<=innerWidth+1 && document.querySelector('.erp-list-scope a').getAttribute('href')==={json.dumps(parent)}",
                                "description": "Focused history retains exact contract/line and the authorized parent return path",
                            },
                        ],
                        "mustText": [
                            "سوابق کارکرد",
                            "بازگشت به مقادیر و بهای قرارداد",
                            self.contract.title,
                        ],
                        "mustLinks": [
                            parent,
                            reverse("billing:progress_detail", args=[record.pk]),
                        ],
                    }
                )
        browser_fixture.ContractBillingBrowserTests.browser(self, self.owner, scenarios)

    def test_quantities_layout_with_long_descriptions_and_large_amounts(self):
        from apps.billing.services import (
            add_baseline_item,
            approve_project_baseline,
            create_project_baseline,
            request_project_baseline_approval,
        )
        from apps.contracts.services import (
            add_contract_item,
            create_contract,
            transition_contract_status,
        )
        from apps.organizations.models import OrganizationSettings

        self.ready()
        OrganizationSettings.objects.update_or_create(
            organization=self.organization, defaults={"currency": "IRR"}
        )
        total = Decimal(30425000000000)
        contract = create_contract(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            contract_number="LAYOUT-RECEIVABLE",
            title="قرارداد نمونه اجرای سازه و محوطه‌سازی مجتمع مسکونی",
            counterparty_name=self.party.display_name,
            party=self.party,
            direction="receivable",
            contract_type="client",
            contract_value=total,
        )
        rows = [
            (
                "عملیات اجرایی و تأمین نیروی متخصص برای اجرای سازه و محوطه‌سازی پروژه نمونه",
                Decimal(16733750000000),
            ),
            (
                "تأمین مصالح، ماشین‌آلات و تجهیزات مرتبط با عملیات اجرایی پروژه نمونه",
                Decimal(13691250000000),
            ),
        ]
        items = []
        for index, (description, rate) in enumerate(rows):
            items.append(
                add_contract_item(
                    organization=self.organization,
                    actor=self.owner,
                    contract=contract,
                    description=description,
                    quantity=Decimal(1),
                    unit_price=rate,
                    unit="ea",
                    sort_order=index,
                )
            )
        contract = transition_contract_status(
            organization=self.organization,
            actor=self.owner,
            contract=contract,
            status="active",
        )
        baseline = create_project_baseline(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            contract=contract,
            effective_date=date(2026, 9, 1),
        )
        for index, ((description, rate), item) in enumerate(
            zip(rows, items, strict=True)
        ):
            add_baseline_item(
                organization=self.organization,
                actor=self.owner,
                baseline=baseline,
                line_key=f"LAYOUT-{index}",
                contract_item=item,
                description=description,
                unit="ea",
                planned_quantity=Decimal(1),
                unit_rate=rate,
                sort_order=index,
            )
        request_project_baseline_approval(
            organization=self.organization, actor=self.owner, baseline=baseline
        )
        approve_project_baseline(
            organization=self.organization,
            actor=self.manager,
            baseline=baseline,
            reason="تأیید مستقل نسخه مبنای قرارداد نمونه برای آزمون چیدمان — SYNTHETIC-LAYOUT-REFERENCE-20261102-ONLY؛ مقادیر و نرخ‌های نمونه بررسی شده‌اند.",
        )
        self.browser_evidence_directory = OUTPUT / "quantities-layout-followup/browser"
        geometry = """(() => {
          const card=document.querySelector('[data-contract-quantities]'), table=card.querySelector('table'), wrap=table.parentElement;
          const box=card.getBoundingClientRect(), row=table.tBodies[0].rows[0];
          const responsive=innerWidth<1200;
          return getComputedStyle(card).paddingTop!=='0px' && table.getBoundingClientRect().width>=box.width-40 &&
            document.documentElement.scrollWidth<=innerWidth+1 &&
            (responsive ? getComputedStyle(row).display==='grid' && wrap.scrollWidth<=wrap.clientWidth+1 : getComputedStyle(row).display==='table-row') &&
            [...table.querySelectorAll('td.erp-list-amount')].every(c=>c.scrollWidth<=c.clientWidth+1) &&
            [...card.querySelectorAll('.cd-quantity-tabs a')].every(a=>{const r=a.getBoundingClientRect();return r.left>=box.left && r.right<=box.right;}) &&
            [...document.querySelectorAll('link[rel=stylesheet]')].some(e=>e.href.includes('/contracts/detail.css?v=20261102-quantities-2'));
        })()"""
        scenarios = []
        for width in (1440, 1024, 390):
            for pane in ("items", "basis"):
                scenarios.append(
                    {
                        "name": f"quantities-{pane}-{width}",
                        "path": quantities(
                            contract, **({"pane": "basis"} if pane == "basis" else {})
                        ),
                        "width": width,
                        "mobile": width == 390,
                        "status": 200,
                        "screenshot": True,
                        "bottomScreenshot": True,
                        "noJsErrors": True,
                        "noHttpErrors": True,
                        "mustText": [description for description, _ in rows],
                        "absentText": ["واحد پول تنظیم نشده"],
                        "steps": [
                            {
                                "inspect": geometry,
                                "description": "Full-width styled table/cards, readable large amounts, fitted subnavigation and versioned local CSS",
                            },
                            *(
                                [
                                    {
                                        "toggleSelector": ".cd-approval-evidence > summary",
                                        "inspect": "document.querySelector('.cd-approval-evidence').open && document.querySelector('.cd-approval-reason dd').scrollWidth<=document.querySelector('.cd-approval-reason dd').clientWidth+1",
                                        "description": "Long approval evidence remains readable inside its disclosure",
                                    },
                                    {
                                        "toggleSelector": ".cd-approval-evidence > summary",
                                        "inspect": "!document.querySelector('.cd-approval-evidence').open",
                                        "description": "Approval disclosure closes without changing the selected snapshot",
                                    },
                                ]
                                if pane == "basis"
                                else []
                            ),
                        ],
                    }
                )
        browser_fixture.ContractBillingBrowserTests.browser(self, self.owner, scenarios)

    def test_view_all_claims_opens_a_focused_list_at_all_widths(self):
        self.ready()
        claim = self._claim()
        self.browser_evidence_directory = OUTPUT / "claims-list-followup/browser"
        listing = reverse("billing:claim_list")
        for width in (1440, 1024, 390):
            browser_fixture.ContractBillingBrowserTests.browser(
                self,
                self.owner,
                [
                    {
                        "name": f"view-all-claims-{width}",
                        "path": reverse("contracts:detail", args=[self.contract.pk]),
                        "width": width,
                        "mobile": width == 390,
                        "status": 200,
                        "screenshot": True,
                        "noJsErrors": True,
                        "noHttpErrors": True,
                        "steps": [
                            {
                                "clickSelector": ".cd-claims .cd-footer",
                                "afterPath": listing,
                            },
                            {
                                "inspect": f"!document.querySelector('.claim-journey,[data-billing-navigation]') && new URLSearchParams(location.search).get('contract')==='{self.contract.pk}' && document.documentElement.scrollWidth<=innerWidth+1",
                                "description": "Focused claims list retains the exact contract without document overflow",
                            },
                        ],
                        "mustText": [
                            "صورت‌وضعیت‌ها",
                            self.contract.title,
                        ],
                        "mustLinks": [
                            reverse("contracts:detail", args=[self.contract.pk]),
                            reverse("billing:claim_detail", args=[claim.pk]),
                        ],
                    }
                ],
            )

    def test_contract_hub_and_shared_foundation_offline_in_installed_chrome(self):
        self.prepare_hub()
        request_progress_verification(
            organization=self.organization, actor=self.owner, record=self.new_record
        )
        reader, _, _ = scoped_reader(
            self.organization, self.project, ["contracts.view"], username="hub-reader"
        )
        sessions, scenarios = {}, []
        for name, actor in (
            ("owner", self.owner),
            ("reviewer", self.manager),
            ("restricted", reader),
        ):
            self.client = Client()
            self.login(actor)
            sessions[name] = self.client.cookies["sessionid"].value
        for width in (1440, 1024, 390):
            cases = [
                (
                    "hub-handoff",
                    "owner",
                    reverse("contracts:detail", args=[self.contract.pk]),
                    {
                        "steps": [
                            {
                                "click": '[data-contract-hub-navigation] a[href*="section=quantities"]',
                                "path": quantities(self.contract),
                            },
                            {
                                "click": '.cd-quantity-tabs a[href*="pane=basis"]',
                                "path": quantities(self.contract, pane="basis"),
                            },
                            {
                                "click": ".cd-quantity-table a[href*=line_key]",
                                "path": reverse("billing:progress_list")
                                + f"?contract={self.contract.pk}&line_key=ITEM-01",
                            },
                        ]
                    },
                ),
                ("receivable-items", "owner", quantities(self.contract), {}),
                (
                    "receivable-basis",
                    "owner",
                    quantities(self.contract, pane="basis"),
                    {
                        "inspect": "document.querySelectorAll('.cd-quantity-table tbody tr').length===1 && !!document.querySelector('.cd-quantity-table a[href*=line_key]')"
                    },
                ),
                (
                    "historical-basis",
                    "owner",
                    quantities(
                        self.contract,
                        pane="basis",
                        baseline=self.old_record.baseline_id,
                    ),
                    {"inspect": "!!document.querySelector('.cd-history-note')"},
                ),
                (
                    "payable-items",
                    "owner",
                    quantities(self.payable),
                    {
                        "inspect": "!document.querySelector('[href*=\"pane=basis\"]') && !!document.querySelector('.cd-quantity-table a[href*=contract_item]')"
                    },
                ),
                (
                    "measurement-history",
                    "owner",
                    reverse("billing:progress_list")
                    + f"?contract={self.contract.pk}&line_key=ITEM-01",
                    {
                        "inspect": "document.querySelectorAll('[data-progress-records] tbody tr').length===2"
                    },
                ),
                (
                    "contract-selector",
                    "owner",
                    reverse("contracts:create"),
                    {"choice": "project", "query": "Baseline"},
                ),
                (
                    "restricted-items",
                    "restricted",
                    quantities(self.contract),
                    {
                        "inspect": '!document.querySelector(\'[href*="pane=basis"],.cd-quantity-tabs a[href*="/billing/"]\')'
                    },
                ),
                (
                    "measurement-decision",
                    "reviewer",
                    reverse("billing:progress_detail", args=[self.new_record.pk]),
                    {"decision": True, "confirm": width == 390},
                ),
            ]
            for label, actor_name, path, extra in cases:
                # Preflight responses must not rotate the sessions retained for Chrome.
                self.client = Client()
                self.login(
                    {
                        "owner": self.owner,
                        "reviewer": self.manager,
                        "restricted": reader,
                    }[actor_name]
                )
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                expected = [
                    {"label": link.label, "url": reverse(link.route)}
                    for group in response.context["product_navigation_groups"]
                    for link in group.links
                ]
                active = [
                    item["url"]
                    for item in module_selector_links(
                        response.context["product_navigation_groups"],
                        response.resolver_match.view_name,
                        response.wsgi_request.path,
                    )
                    if item["active"]
                ]
                self.assertLessEqual(len(active), 1)
                if response.resolver_match.namespace == "contracts":
                    self.assertEqual(len(active), 1)
                scenarios.append(
                    {
                        "name": f"{label}-{width}",
                        "actor": actor_name,
                        "path": path,
                        "width": width,
                        "expected": expected,
                        "active": active,
                        **extra,
                    }
                )
        output = OUTPUT / "browser"
        output.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["HUB_SESSIONS"] = json.dumps(sessions)
        env["HUB_SCENARIOS"] = json.dumps(scenarios)
        result = subprocess.run(
            [
                "node",
                str(ROOT / "scripts/verification/contract_hub_browser.mjs"),
                self.live_server_url,
                str(output),
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=420,
            check=False,
        )
        (output / "command.txt").write_text(
            f"exit={result.returncode}\n{result.stdout}\n{result.stderr}",
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, (result.stderr or result.stdout)[-5000:])
        self.assertEqual(json.loads(result.stdout)["pages"], 27)
        self.new_record.refresh_from_db()
        self.assertEqual(self.new_record.status, "verified")
        self.assertEqual(
            ProgressRecord.objects.filter(pk=self.new_record.pk).count(), 1
        )

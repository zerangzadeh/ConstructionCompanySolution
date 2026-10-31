"""Targeted presentation coverage; existing source services own every transition."""

from datetime import date
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.billing.models import ProgressClaim, ProgressRecord
from apps.billing.services import (
    approve_progress_claim,
    create_progress_claim,
    create_progress_claim_correction,
    request_progress_verification,
    return_progress_claim,
    submit_progress_claim,
)
from apps.billing.test_mvp03 import JourneyFixture
from apps.estimates.models import Estimate
from apps.estimates.services import create_estimate
from apps.projects.models import Project
from core.jalali import format_jalali


class BalancedMarkup(HTMLParser):
    """Check explicit closing tags in rendered markup without an added dependency."""

    void = frozenset(
        {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }
    )

    def __init__(self, html):
        super().__init__()
        self.stack = []
        self.errors = []
        self.feed(html)
        self.errors.extend(f"unclosed {tag}" for tag in self.stack)

    def handle_starttag(self, tag, attrs):
        if tag not in self.void:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.void:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.errors.append(f"unexpected closing {tag}")


class RemediationFixture(JourneyFixture):
    def claim_states(self):
        """Produce all six visual states through the existing governed services."""
        original = self._claim()

        def approve(claim):
            submit_progress_claim(
                organization=self.organization, actor=self.owner, claim=claim
            )
            approve_progress_claim(
                organization=self.organization,
                actor=self.manager,
                claim=claim,
                reason="Independent synthetic UI review",
            )

        approve(original)
        replacement = create_progress_claim_correction(
            organization=self.organization,
            actor=self.owner,
            claim=original,
            correction_kind="replacement",
            reason="Synthetic replacement review",
        )
        approve(replacement)
        cancellation = create_progress_claim_correction(
            organization=self.organization,
            actor=self.owner,
            claim=replacement,
            correction_kind="cancellation",
            reason="Synthetic cancellation review",
        )
        approve(cancellation)
        returned = create_progress_claim(
            organization=self.organization,
            actor=self.owner,
            baseline=original.baseline,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            measurement_cutoff=date(2026, 10, 31),
        )
        submit_progress_claim(
            organization=self.organization, actor=self.owner, claim=returned
        )
        return_progress_claim(
            organization=self.organization,
            actor=self.manager,
            claim=returned,
            reason="Synthetic returned review",
        )
        returned.refresh_from_db()
        submitted = returned.returned_revision
        submit_progress_claim(
            organization=self.organization, actor=self.owner, claim=submitted
        )
        create_progress_claim(
            organization=self.organization,
            actor=self.owner,
            baseline=original.baseline,
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 30),
            measurement_cutoff=date(2026, 11, 30),
        )
        return {
            claim.status: claim
            for claim in ProgressClaim.objects.filter(organization=self.organization)
        }


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class JourneyRemediationTests(RemediationFixture, TestCase):
    def setUp(self):
        self.make_fixture()
        self.login(self.owner)

    def test_plain_titles_and_active_billing_navigation(self):
        for route, title in (
            ("baseline_list", "مبناهای اندازه‌گیری"),
            ("progress_list", "پیشرفت کار"),
            ("claim_list", "صورت‌وضعیت‌ها"),
        ):
            with self.subTest(route=route):
                response = self.client.get(reverse("billing:" + route))
                html = response.content.decode()
                self.assertEqual(
                    html.split("<title>")[1].split("</title>")[0], title + " | بنیرا"
                )
                nav = html.split("data-billing-navigation")[1].split("</nav>")[0]
                self.assertEqual(nav.count("erp-btn--active"), 1)
                self.assertEqual(nav.count('aria-current="page"'), 1)
                self.assertEqual(BalancedMarkup(html).errors, [])

    def test_estimate_states_have_correct_copy_and_balanced_separate_forms(self):
        estimate = create_estimate(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            estimate_number="UI-E",
            title="برآورد نمونه",
        )
        url = reverse("estimates:detail", args=[estimate.pk])
        for status, text in (
            ("draft", "تأیید برآورد"),
            ("approved", "این برآورد تأیید شده"),
            ("revised", "این برآورد بازنگری شده"),
            ("archived", "این برآورد بایگانی شده"),
        ):
            # Read-only presentation fixtures: no new lifecycle transitions implied.
            Estimate.objects.filter(pk=estimate.pk).update(status=status)
            response = self.client.get(url)
            self.assertContains(response, text)
            html = response.content.decode()
            self.assertEqual(BalancedMarkup(html).errors, [])
            if status in {"revised", "archived"}:
                self.assertNotContains(response, "این برآورد تأیید شده")
            if status == "draft":
                approval = html.split(
                    f'action="{reverse("estimates:approve", args=[estimate.pk])}"'
                )[1].split("</form>")[0]
                self.assertNotIn("data-native", approval)
                self.assertNotIn("unit_of_measure", approval)

    def test_clear_filters_preserves_applied_context_and_global_session(self):
        self._claim()
        create_estimate(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            contract=self.contract,
            estimate_number="UI-E",
            title="برآورد نمونه",
        )
        sibling = Project.objects.create(
            organization=self.organization, code="UI-SIB", name="پروژه دیگر"
        )
        session = self.client.session
        session["active_project_id"] = str(sibling.pk)
        session.save()
        before = dict(self.client.session)
        for route, filters, context in (
            ("contracts:list", {"title": "no-match"}, {"project_id": self.project.pk}),
            (
                "estimates:list",
                {"title": "no-match"},
                {"project_id": self.project.pk, "contract": self.contract.pk},
            ),
            (
                "billing:claim_list",
                {"status": "approved"},
                {"project_id": self.project.pk, "contract": self.contract.pk},
            ),
            (
                "billing:baseline_list",
                {"q": "no-match"},
                {"contract": self.contract.pk},
            ),
            (
                "billing:progress_list",
                {"q": "no-match"},
                {"contract": self.contract.pk},
            ),
        ):
            with self.subTest(route=route):
                response = self.client.get(
                    reverse(route),
                    {**context, **filters, "page": "2", "sort": "number"},
                )
                self.assertEqual(response.status_code, 200)
                clear = response.context["clear_filters_url"]
                if route in {"contracts:list", "estimates:list"}:
                    from django.utils.html import escape

                    self.assertContains(
                        response, f'href="{escape(clear)}" data-table-filter-clear'
                    )
                    for key, value in context.items():
                        self.assertContains(response, f'name="{key}" value="{value}"')
                expected = {k: [str(v)] for k, v in context.items()}
                if route == "contracts:list":
                    expected["sort"] = ["number"]
                self.assertEqual(parse_qs(urlsplit(clear).query), expected)
                if route in {"contracts:list", "estimates:list", "billing:claim_list"}:
                    self.assertContains(response, "با فیلترهای فعلی نتیجه‌ای یافت نشد.")
                    self.assertTrue(response.context["scoped_has_records"])
                html = response.content.decode()
                self.assertLess(
                    html.index('id="erp-page-title"'),
                    html.index('method="get"', html.index('id="erp-page-title"')),
                )
                self.assertEqual(self.client.get(clear).status_code, 200)
                self.assertEqual(dict(self.client.session), before)

    def test_true_empty_context_is_distinct_from_filtered_empty(self):
        self._claim()
        empty = Project.objects.create(
            organization=self.organization, code="UI-EMPTY", name="پروژه بدون سابقه"
        )
        for route, text in (
            ("contracts:list", "هنوز قراردادی ثبت نشده است"),
            ("estimates:list", "هنوز برآوردی ثبت نشده است"),
            ("billing:claim_list", "هنوز صورت‌وضعیتی در این زمینه ثبت نشده است"),
        ):
            response = self.client.get(
                reverse(route), {"project_id": empty.pk, "q": "no-match"}
            )
            self.assertFalse(response.context["scoped_has_records"])
            self.assertContains(response, text)
            self.assertNotContains(response, "با فیلترهای فعلی نتیجه‌ای یافت نشد.")

    def test_all_claim_states_use_domain_labels_and_keep_state_actions(self):
        states = self.claim_states()
        self.assertEqual(
            set(states),
            {"draft", "submitted", "approved", "returned", "superseded", "cancelled"},
        )
        for state, claim in states.items():
            response = self.client.get(reverse("billing:claim_list"), {"status": state})
            self.assertEqual(
                [item.pk for item in response.context["claims"]], [claim.pk]
            )
            self.assertContains(response, claim.get_status_display())
            detail = self.client.get(reverse("billing:claim_detail", args=[claim.pk]))
            self.assertContains(detail, "وضعیت و اقدام بعدی")
            self.assertContains(
                detail, f"صورت‌وضعیت {claim.claim_number} · نسخه {claim.revision_number}"
            )
            self.assertEqual(BalancedMarkup(detail.content.decode()).errors, [])
            self.assertEqual(detail.context["can_recalculate"], state == "draft")

    def test_draft_creation_without_measurements_matches_prerequisite_copy(self):
        baseline = self._approved_baseline()
        self.assertFalse(ProgressRecord.objects.exists())
        response = self.client.post(
            reverse("billing:claim_create"),
            {
                "contract": self.contract.pk,
                "baseline": baseline.pk,
                "period_start": "2026-09-01",
                "period_end": "2026-09-30",
                "measurement_cutoff": "2026-09-30",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ProgressClaim.objects.get().gross_amount, 0)
        self.assertContains(
            self.client.get(reverse("billing:claim_create")),
            "ثبت کارکرد تأییدشده برای ایجاد پیش‌نویس الزامی نیست",
        )

    def test_contract_identity_jalali_dates_and_progress_reason_markup(self):
        # Synthetic metadata fixtures only; no change to stored date semantics.
        from apps.contracts.models import Contract

        Contract.objects.filter(pk=self.contract.pk).update(
            signed_at=date(2026, 9, 1),
            start_date=date(2026, 9, 2),
            end_date=date(2026, 9, 30),
        )
        response = self.client.get(reverse("contracts:detail", args=[self.contract.pk]))
        self.assertContains(
            response,
            f'<bdi class="font-semibold" dir="ltr">{self.contract.contract_number}</bdi>',
            html=True,
        )
        self.assertContains(response, format_jalali(date(2026, 9, 1)))
        self.assertNotContains(response, "Sept.")
        record = self._record()
        request_progress_verification(
            organization=self.organization, actor=self.owner, record=record
        )
        self.login(self.manager)
        response = self.client.get(reverse("billing:progress_detail", args=[record.pk]))
        self.assertContains(
            response,
            '<label class="block text-sm font-medium" for="progress-reject-reason">دلیل رد اندازه‌گیری</label>',
            html=True,
        )
        self.assertContains(response, 'id="progress-verify-reason"')
        self.assertEqual(response.content.decode().count('name="reason" rows="3"'), 2)
        self.assertEqual(BalancedMarkup(response.content.decode()).errors, [])

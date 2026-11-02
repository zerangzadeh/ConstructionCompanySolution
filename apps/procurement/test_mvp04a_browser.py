"""Real installed Chrome/CDP, isolated PostgreSQL; no developer data mutations."""

from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.billing import test_mvp03_browser as chrome_fixture
from apps.organizations.models import MembershipScopeGrant
from apps.projects.models import Project

from .models import PurchaseRequest
from .test_mvp04a import RequestJourneyFixture


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PurchaseRequestBrowserTests(RequestJourneyFixture, StaticLiveServerTestCase):
    serialized_rollback = True
    browser = chrome_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = chrome_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/mvp-04a/browser"
    )

    def setUp(self):
        super().setUp()
        for row, name in (
            (self.organization, "شرکت ساختمانی نمونه"),
            (self.project, "پروژه سازه نمونه"),
            (self.material, "سیمان پرتلند"),
            (self.unit, "کیسه"),
        ):
            row.name = name
            row.save(update_fields=["name"])

    def inspect(self, expression, description):
        return {"inspect": expression, "description": description}

    def scenario(self, name, path, **extra):
        # The qualified driver treats a fill and its submission as one step.
        steps = []
        pending_fill = None
        for step in extra.get("steps", []):
            if set(step) == {"fill"}:
                pending_fill = step["fill"]
                continue
            if pending_fill is not None:
                step = {**step, "fill": pending_fill}
                pending_fill = None
            steps.append(step)
        if "steps" in extra:
            extra["steps"] = steps
        return {
            "name": name,
            "path": path,
            "status": 200,
            "screenshot": True,
            "noJsErrors": True,
            "noHttpErrors": True,
            "absentText": [
                "UUID",
                "object (",
                "candidacy",
                "purchase_requests.",
                "RFQCommercialScope",
            ],
            **extra,
        }

    def test_real_chrome_pr_journey_responsive_and_authority_boundaries(self):
        listing = reverse("procurement:request_list")
        create = (
            reverse("procurement:request_create") + f"?project_id={self.project.pk}"
        )
        list_draft = self.draft("LIST-01")
        self.browser(
            self.owner,
            [
                self.scenario(
                    f"list-{width}",
                    listing,
                    width=width,
                    mobile=width == 390,
                    mustText=["درخواست خرید جدید", "مصالح فونداسیون"],
                    steps=[
                        self.inspect(
                            "document.querySelectorAll('.erp-list-row-menu').length===1",
                            "row action menu",
                        )
                    ],
                )
                for width in (1440, 1024, 390)
            ]
            + [
                self.scenario(
                    f"detail-draft-{width}",
                    self.url(list_draft),
                    width=width,
                    mobile=width == 390,
                    mustText=["افزودن قلم", "حداقل یک قلم"],
                )
                for width in (1440, 1024, 390)
            ]
            + [
                self.scenario(
                    f"create-{width}",
                    create,
                    width=width,
                    mobile=width == 390,
                    steps=[
                        self.inspect(
                            f"document.querySelector('[name=project]').type==='hidden' && document.querySelector('[name=project]').value==='{self.project.pk}'",
                            "inherited project is preserved without manual input",
                        )
                    ],
                )
                for width in (1440, 1024, 390)
            ]
            + [
                self.scenario(
                    "create-validation-retention",
                    create,
                    steps=[
                        {
                            "fill": {
                                "request_number": "PR-BROWSER",
                                "title": "",
                                "notes": "توضیح حفظ‌شده",
                            }
                        },
                        {
                            "submit": True,
                            "formSelector": "form[aria-label='درخواست خرید جدید']",
                            "afterPath": reverse("procurement:request_create"),
                        },
                        self.inspect(
                            "document.querySelector('[name=request_number]').value==='PR-BROWSER' && document.querySelector('[name=notes]').value==='توضیح حفظ‌شده' && !!document.querySelector('[role=alert]')",
                            "validation retains number, notes and parent",
                        ),
                    ],
                ),
                self.scenario(
                    "create-save",
                    create,
                    steps=[
                        {
                            "fill": {
                                "request_number": "PR-BROWSER",
                                "title": "خرید سیمان پروژه",
                            }
                        },
                        {
                            "submit": True,
                            "formSelector": "form[aria-label='درخواست خرید جدید']",
                            "afterPrefix": "/procurement/requests/",
                            "mustText": "افزودن قلم",
                        },
                    ],
                ),
            ],
        )
        record = PurchaseRequest.objects.get(request_number="PR-BROWSER")
        detail = self.url(record)
        self.browser(
            self.owner,
            [
                self.scenario(
                    "item-invalid-retention",
                    detail,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        {
                            "searchChoice": {
                                "name": "material",
                                "query": "سیمان",
                                "value": str(self.material.pk),
                            }
                        },
                        {"fill": {"quantity": "-1", "description": "مصرف فونداسیون"}},
                        {
                            "submit": True,
                            "formSelector": "form[aria-label='افزودن قلم']",
                            "afterPath": self.url(record, "item_add"),
                        },
                        self.inspect(
                            f"document.querySelector('[name=material]').value==='{self.material.pk}' && document.querySelector('[name=description]').value==='مصرف فونداسیون' && document.querySelector('[name=quantity]').value==='-1'",
                            "item values retained after server validation",
                        ),
                    ],
                ),
                self.scenario(
                    "add-submit-approve",
                    detail,
                    steps=[
                        {
                            "searchChoice": {
                                "name": "material",
                                "query": "سیمان",
                                "value": str(self.material.pk),
                            }
                        },
                        {"fill": {"quantity": "12.5", "description": "مصرف فونداسیون"}},
                        {
                            "submit": True,
                            "formSelector": "form[aria-label='افزودن قلم']",
                            "afterPath": detail,
                        },
                        {
                            "clickSelector": f"form[action='{self.url(record, 'submit')}'] button",
                            "afterPath": detail,
                            "mustText": "تأیید درخواست",
                        },
                        self.inspect(
                            "!document.querySelector('form[aria-label=\"افزودن قلم\"]') && !document.querySelector('[data-pr-rfq]')",
                            "submitted state hides item entry and continuation",
                        ),
                        {
                            "toggleSelector": "section[aria-label='وضعیت بررسی'] details summary"
                        },
                        {"fill": {"approve-reason": "بررسی و تأیید نیاز پروژه"}},
                        {
                            "clickSelector": f"form[action='{self.url(record, 'approve')}'] button",
                            "afterPath": detail,
                            "mustText": "ایجاد استعلام از این درخواست",
                        },
                        self.inspect(
                            "!!document.querySelector('[data-pr-rfq]') && !document.querySelector('form[action*=\"/requests/\"]')",
                            "approved state has contextual RFQ and no invalid PR actions",
                        ),
                    ],
                ),
            ],
        )
        record.refresh_from_db()
        self.assertEqual(record.status, "approved")
        self.assertEqual(str(record.items.get().quantity), "12.5000")
        rfq_entry = reverse("procurement:rfq_create") + f"?purchase_request={record.pk}"
        self.browser(
            self.owner,
            [
                self.scenario(
                    f"detail-approved-{width}", detail, width=width, mobile=width == 390
                )
                for width in (1440, 1024, 390)
            ],
        )
        self.browser(
            self.owner,
            [
                self.scenario(
                    f"approved-entry-{width}",
                    detail,
                    width=width,
                    mobile=width == 390,
                    steps=[
                        {
                            "clickSelector": "[data-pr-rfq]",
                            "afterPath": reverse("procurement:rfq_create"),
                        },
                        self.inspect(
                            f"document.querySelector('[name=purchase_request_id]').type==='hidden' && document.querySelector('[name=purchase_request_id]').value==='{record.pk}' && document.body.innerText.includes('پروژه سازه نمونه') && !/[a-f0-9]{{8}}-[a-f0-9]{{4}}-/i.test(document.querySelector('main').innerText)",
                            "RFQ preserves PR and project without UUID entry",
                        ),
                    ],
                )
                for width in (1440, 1024, 390)
            ],
        )
        reject = self.submitted("PR-REJECT")
        cancel_draft = self.draft("PR-CANCEL")
        cancel_submitted = self.submitted("PR-CANCEL-S")
        scenarios = []
        for candidate, action, reason in (
            (reject, "reject", "نیاز به اصلاح مقدار"),
            (cancel_draft, "cancel", "خرید منتفی شد"),
            (cancel_submitted, "cancel", "نیاز پروژه تغییر کرد"),
        ):
            selector = f"form[action='{self.url(candidate, action)}']"
            toggle = (
                "section[aria-label='وضعیت بررسی'] details:nth-child(2) summary"
                if action == "reject"
                else "#cancel-request summary"
            )
            scenarios.append(
                self.scenario(
                    action + candidate.request_number,
                    self.url(candidate),
                    width=390,
                    mobile=True,
                    steps=[
                        {"toggleSelector": toggle},
                        {"fill": {f"{action}-reason": reason}},
                        {
                            "clickSelector": selector + " button",
                            "afterPath": self.url(candidate),
                        },
                        self.inspect(
                            "!document.querySelector('form[action*=\"/requests/\"]') && !document.querySelector('[data-pr-rfq]')",
                            "terminal PR has no mutation or continuation CTA",
                        ),
                    ],
                )
            )
        self.browser(self.owner, scenarios)
        for candidate, status in (
            (reject, "rejected"),
            (cancel_draft, "cancelled"),
            (cancel_submitted, "cancelled"),
        ):
            candidate.refresh_from_db()
            self.assertEqual(candidate.status, status)
        self.browser(
            self.viewer,
            [
                self.scenario(
                    "viewer-approved-no-rfq",
                    detail,
                    steps=[
                        self.inspect(
                            "!document.querySelector('[data-pr-rfq]') && !document.querySelector('form[action*=\"/requests/\"]')",
                            "read-only user cannot continue or mutate",
                        )
                    ],
                ),
                self.scenario(
                    "viewer-create-denied", create, status=403, noHttpErrors=False
                ),
                self.scenario(
                    "viewer-rfq-denied", rfq_entry, status=403, noHttpErrors=False
                ),
            ],
        )
        membership = self.organization.memberships.get(user=self.member)
        MembershipScopeGrant.objects.filter(membership=membership).update(
            revoked_at=timezone.now()
        )
        project = Project.objects.create(
            organization=self.organization, name="پروژه محدود دیگر", code="SCOPED"
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="project",
            project=project,
            reason="Browser fixture",
            source="test_fixture",
        )
        self.browser(
            self.member,
            [
                self.scenario(
                    "wrong-project-detail", detail, status=404, noHttpErrors=False
                ),
                self.scenario(
                    "wrong-project-rfq", rfq_entry, status=404, noHttpErrors=False
                ),
                self.scenario(
                    "wrong-tenant-create",
                    reverse("procurement:request_create")
                    + f"?project_id={self.other_project.pk}",
                    status=404,
                    noHttpErrors=False,
                ),
            ],
        )

    def test_list_filter_navigation_pagination_and_searchable_project(self):
        PurchaseRequest.objects.bulk_create(
            [
                PurchaseRequest(
                    organization=self.organization,
                    project=self.project,
                    request_number=f"PAGE-{i:02}",
                    title="مصالح پروژه نمونه",
                )
                for i in range(28)
            ]
        )
        listing = reverse("procurement:request_list")
        query = f"?project_id={self.project.pk}&q=PAGE&status=draft&sort=number&direction=asc"
        self.browser(
            self.owner,
            [
                self.scenario(
                    "list-pagination-mobile",
                    listing + query,
                    mobile=True,
                    steps=[
                        {"clickSelector": "[rel=next]", "afterPath": listing},
                        self.inspect(
                            "document.querySelectorAll('tbody tr').length===3 && new URLSearchParams(location.search).get('page')==='2' && getComputedStyle(document.querySelector('tbody tr')).display==='grid'",
                            "mobile page two keeps filters and displays cards",
                        ),
                        {
                            "clickSelector": "[data-filter-chip=status]",
                            "afterPath": listing,
                        },
                        self.inspect(
                            f"!new URLSearchParams(location.search).has('page') && !new URLSearchParams(location.search).has('status') && new URLSearchParams(location.search).get('project_id')==='{self.project.pk}'",
                            "chip removal retains parent and resets page",
                        ),
                    ],
                ),
                self.scenario(
                    "list-search-sort-advanced",
                    listing,
                    steps=[
                        {
                            "searchChoice": {
                                "name": "project",
                                "query": "سازه",
                                "value": str(self.project.pk),
                            }
                        },
                        {
                            "fill": {"q": "PAGE", "status": "draft"},
                            "formSelector": "#list-filter-bar",
                            "clickSelector": "[data-filter-apply]",
                            "afterPath": listing,
                        },
                        {
                            "clickSelector": "th a[href*='sort=number']",
                            "afterPath": listing,
                        },
                        self.inspect(
                            "new URLSearchParams(location.search).get('q')==='PAGE' && new URLSearchParams(location.search).get('sort')==='number'",
                            "sort retains search and filters",
                        ),
                        {"toggleSelector": "[data-more-toggle]"},
                        self.inspect(
                            "document.querySelector('[data-more-filters]').open && !!document.querySelector('[name=required_by_from][data-jalali-date]')",
                            "advanced filters reuse Jalali date controls",
                        ),
                    ],
                ),
            ],
        )

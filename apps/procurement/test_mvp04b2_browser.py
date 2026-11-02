"""Actual installed Chrome with synthetic sourcing data and processing fixtures.

CLEAN assessments below are explicit test fixtures, never production scanner proof.
"""

import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.billing import test_mvp03_browser as chrome
from apps.documents.models import (
    DocumentProcessingAssessment,
    DocumentProcessingVerdict,
)
from apps.organizations.models import BusinessPermission, MembershipScopeGrant
from apps.organizations.services import set_active_organization
from apps.procurement import comparison_services as commercial
from apps.procurement import models as m
from apps.procurement.buyer_ui import action_url
from apps.procurement.opening_services import revoke_quote_confidential_access
from apps.procurement.test_mvp04b_scope import CommercialScopeFixture
from apps.procurement.test_p5_s11_comparison_award import (
    P5S11FixtureMixin,
    P5S11TwoRevisionFixtureMixin,
)
from apps.projects.models import Project


class BrowserMixin:
    browser = chrome.ContractBillingBrowserTests.browser
    _fixture_teardown = chrome.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/mvp-04b2/browser"
    )
    serialized_rollback = True

    def login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        set_active_organization(session, self.organization)
        session.save()

    def inspect(self, expression, description):
        return {"inspect": expression, "description": description}

    def case(self, name, path, **kwargs):
        steps = kwargs.pop("steps", [])
        return {
            "name": name,
            "path": path,
            "status": 200,
            "screenshot": True,
            "noJsErrors": True,
            "noHttpErrors": True,
            "absentText": ["UUID", "SHA-256", "idempotency", "object ("],
            **kwargs,
            "steps": [
                *steps,
                self.inspect(
                    "!/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}|\\b[a-f0-9]{64}\\b/i.test(document.querySelector('main')?.innerText||'') && [...document.querySelectorAll('main input')].filter(e=>e.name==='idempotency_key').every(e=>e.type==='hidden')",
                    "no visible technical identity or customer key entry",
                ),
            ],
        }

    def url(self, action, **parents):
        return action_url(self.rfq, action, **parents)

    def workspace(self):
        return reverse("procurement:rfq_buyer_workspace", args=[self.rfq.pk])

    def business_submit(self, fill=None, upload=None):
        steps = []
        if upload:
            steps.append(
                {"upload": {"selector": "main input[type=file]", "path": str(upload)}}
            )
        steps.append(
            {
                "fill": fill or {},
                "formSelector": "#buyer-action-form",
                "clickSelector": "#buyer-action-form button[type=submit]",
                "afterPath": self.workspace(),
            }
        )
        return steps

    def responsive(self, actor, prefix):
        self.browser(
            actor,
            [
                self.case(
                    f"{prefix}-{w}",
                    self.workspace(),
                    width=w,
                    mobile=w == 390,
                    mustText=[
                        "دعوت و پیشنهادهای دریافتی",
                        "گشایش حفاظت‌شده",
                        "انتخاب تأمین‌کننده",
                    ],
                )
                for w in (1440, 1024, 390)
            ],
        )

    def actor(self, username):
        user = User.objects.create_user(username=username)
        member = self.organization.memberships.create(
            user=user, role="tenant_manager", status="active"
        )
        self.establish_test_membership_authority(member)
        member.role_definition.permissions.add(
            *BusinessPermission.objects.filter(code__startswith="rfq")
        )
        return user


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class QuoteOpeningBrowserTests(
    BrowserMixin, CommercialScopeFixture, StaticLiveServerTestCase
):
    def setUp(self):
        super().setUp()
        protected_root = tempfile.TemporaryDirectory()
        storage_override = override_settings(
            DOCUMENT_PROTECTED_ROOT=protected_root.name
        )
        storage_override.enable()
        self.addCleanup(protected_root.cleanup)
        self.addCleanup(storage_override.disable)

    def test_receipt_revision_withdraw_close_custody_opening_grants_and_denials(self):
        self.rfq = self.draft_rfq()
        self.rfq.earliest_opening_at += timedelta(hours=1)
        self.rfq.save(update_fields=["earliest_opening_at"])
        self.define(self.rfq)
        version = self.issue(self.rfq)
        self.rfq.refresh_from_db()
        invitation = version.invitations.get()
        self.preparer = self.actor("buyer-reviewer")
        self.approver = self.actor("opening-approver")
        # Protected opening/custody/access management are explicit authorities;
        # the owner fixture does not receive them from the role name alone.
        self.organization.memberships.get(
            user=self.owner
        ).role_definition.permissions.add(
            *BusinessPermission.objects.filter(code__startswith="rfq")
        )
        path = self.browser_evidence_directory.parent / "synthetic-source.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"%PDF-1.7\nsynthetic supplier offer fixture\n%%EOF")
        self.responsive(self.owner, "issued-invitations")
        capture = self.url("capture", invitation=invitation.pk)
        self.browser(
            self.owner,
            [
                self.case(
                    "capture-source-receipt",
                    capture,
                    steps=self.business_submit(
                        {"source_channel": "manual_capture"}, path
                    ),
                )
            ],
        )
        first = m.QuoteRevision.objects.get()
        self.assertFalse(first.evidence_items.exists())
        self.browser(
            self.owner,
            [
                self.case(
                    "submit-first-revision",
                    self.url("submit", quote_revision=first.pk),
                    steps=self.business_submit(),
                )
            ],
        )
        self.browser(
            self.owner,
            [
                self.case(
                    "correction-new-revision",
                    capture,
                    steps=self.business_submit(
                        {"source_channel": "manual_capture"}, path
                    ),
                )
            ],
        )
        second = m.QuoteRevision.objects.get(revision_number=2)
        self.browser(
            self.owner,
            [
                self.case(
                    "submit-superseding-revision",
                    self.url("submit", quote_revision=second.pk),
                    steps=self.business_submit(),
                )
            ],
        )
        first.refresh_from_db()
        self.assertEqual(first.status, "superseded")
        self.browser(
            self.owner,
            [
                self.case(
                    "withdraw-current-revision",
                    self.url("withdraw", quote_revision=second.pk),
                    steps=self.business_submit(),
                )
            ],
        )
        second.refresh_from_db()
        self.assertEqual(second.status, "withdrawn")
        self.browser(
            self.owner,
            [
                self.case(
                    "third-receipt",
                    capture,
                    steps=self.business_submit(
                        {"source_channel": "manual_capture"}, path
                    ),
                )
            ],
        )
        revision = m.QuoteRevision.objects.get(revision_number=3)
        submit = self.url("submit", quote_revision=revision.pk)
        self.browser(
            self.owner,
            [
                self.case(
                    "submit-effective-revision",
                    submit,
                    steps=[
                        *self.business_submit(),
                        {"reload": True},
                        {"history": "back"},
                        {"history": "forward"},
                    ],
                )
            ],
        )
        self.assertEqual(m.QuoteRevision.objects.count(), 3)
        early = self.url("request_opening", quote_revision=revision.pk)
        self.browser(
            self.owner,
            [
                self.case(
                    "early-opening-denied-issued",
                    early,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        {
                            "fill": {"reason": "درخواست پیش از موعد"},
                            "clickSelector": "#buyer-action-form button[type=submit]",
                            "afterPath": early.split("?")[0],
                        }
                    ],
                )
            ],
        )
        self.assertFalse(m.QuoteOpeningRequest.objects.exists())
        # Closing is exercised through the existing RFQ UI at a controlled test clock.
        detail = reverse("procurement:rfq_detail", args=[self.rfq.pk])
        with patch(
            "apps.procurement.rfq_services.timezone.now",
            return_value=version.closing_at + timedelta(seconds=1),
        ):
            self.browser(
                self.owner,
                [
                    self.case(
                        "close-issued-rfq",
                        detail,
                        steps=[
                            {
                                "toggleSelector": 'details:has(form[action$="/close/"]) summary'
                            },
                            {
                                "clickSelector": 'form[action$="/close/"] button[type=submit]',
                                "afterPath": detail,
                            },
                        ],
                    )
                ],
            )
        self.rfq.refresh_from_db()
        self.assertEqual(self.rfq.status, "closed")
        self.browser(
            self.owner,
            [
                self.case(
                    "closed-before-opening-time",
                    self.workspace(),
                    mustText=["زمان مجاز گشایش هنوز فرا نرسیده است."],
                )
            ],
        )
        self.browser(
            self.owner,
            [
                self.case(
                    "sealed-document-denial-before-custody",
                    self.workspace(),
                    steps=[
                        self.inspect(
                            "document.querySelectorAll('main a[href*="
                            + '"/buyer/documents/"'
                            + "]').length===0",
                            "no sealed content links",
                        )
                    ],
                )
            ],
        )
        attach = self.url("attach_evidence", quote_revision=revision.pk)
        self.browser(
            self.owner,
            [
                self.case(
                    "custody-original-source",
                    attach,
                    steps=self.business_submit(
                        {"evidence_type": "supplier_original"}, path
                    ),
                )
            ],
        )
        evidence = revision.evidence_items.get()
        self.assertFalse(
            DocumentProcessingAssessment.objects.filter(
                version=evidence.document_version
            ).exists()
        )
        document = reverse(
            "procurement:rfq_buyer_document", args=[self.rfq.pk, evidence.pk]
        )
        self.browser(
            self.owner,
            [
                self.case(
                    "document-sealed-access-denied",
                    self.workspace(),
                    steps=[
                        self.inspect(
                            f"fetch('{document}').then(r=>r.status===403)",
                            "sealed download denied",
                        )
                    ],
                    noHttpErrors=False,
                )
            ],
        )
        # A late receipt stays visible and is never silently discarded.
        with patch(
            "apps.procurement.quote_services.timezone.now",
            return_value=version.closing_at + timedelta(seconds=3),
        ):
            self.browser(
                self.owner,
                [
                    self.case(
                        "late-receipt-metadata",
                        capture,
                        steps=self.business_submit(
                            {"source_channel": "manual_capture"}, path
                        ),
                    )
                ],
            )
        self.assertTrue(m.QuoteRevision.objects.get(revision_number=4).is_late)
        with patch(
            "apps.procurement.opening_services.timezone.now",
            return_value=version.earliest_opening_at + timedelta(seconds=1),
        ):
            self.browser(
                self.owner,
                [
                    self.case(
                        "request-protected-opening",
                        early,
                        steps=self.business_submit({"reason": "گشایش رسمی پیشنهاد"}),
                    )
                ],
            )
            opening_request = m.QuoteOpeningRequest.objects.get()
            approve = self.url("approve_opening", opening_request=opening_request.pk)
            self.browser(
                self.owner,
                [
                    self.case(
                        "opening-independent-actor-denial",
                        approve,
                        status=400,
                        noHttpErrors=False,
                        steps=[
                            {
                                "clickSelector": "#buyer-action-form button[type=submit]",
                                "afterPath": approve.split("?")[0],
                            }
                        ],
                    )
                ],
            )
            self.browser(
                self.approver,
                [
                    self.case(
                        "opening-missing-processing-denial",
                        approve,
                        status=400,
                        noHttpErrors=False,
                        steps=[
                            {
                                "clickSelector": "#buyer-action-form button[type=submit]",
                                "afterPath": approve.split("?")[0],
                            }
                        ],
                    )
                ],
            )
            self.assertFalse(m.QuoteOpeningEvent.objects.exists())
            # Explicit fixture only. This is not evidence of a deployed scanner.
            DocumentProcessingAssessment.objects.create(
                organization=self.organization,
                version=evidence.document_version,
                sequence=1,
                verdict=DocumentProcessingVerdict.CLEAN,
                input_sha256=evidence.canonical_sha256,
                adapter_code="mvp04b2-synthetic-test-fixture",
                adapter_version="1",
                recorded_by=self.owner,
            )
            self.browser(
                self.approver,
                [
                    self.case(
                        "independent-opening-approved",
                        approve,
                        steps=self.business_submit(),
                    )
                ],
            )
        self.assertTrue(
            m.QuoteOpeningEvent.objects.filter(quote_revision=revision).exists()
        )
        self.browser(
            self.owner,
            [
                self.case(
                    "opened-without-access-grant",
                    self.workspace(),
                    mustText=["بدون دسترسی محتوا"],
                )
            ],
        )
        membership = self.organization.memberships.get(user=self.preparer)
        grant = self.url("grant_access", quote_revision=revision.pk)
        self.browser(
            self.owner,
            [
                self.case(
                    "grant-exact-revision-access",
                    grant,
                    steps=self.business_submit(
                        {
                            "membership": str(membership.pk),
                            "reason": "بررسی مستند پیشنهاد",
                        }
                    ),
                )
            ],
        )
        self.browser(
            self.preparer,
            [
                self.case(
                    "authorized-source-document",
                    self.workspace(),
                    steps=[
                        self.inspect(
                            f"fetch('{document}').then(async r=>r.status===200 && (await r.text()).startsWith('%PDF'))",
                            "authorized exact bytes",
                        )
                    ],
                )
            ],
        )
        active = m.QuoteConfidentialAccessGrant.objects.get(
            quote_revision=revision, membership=membership
        )
        self.browser(
            self.owner,
            [
                self.case(
                    "revoke-version-access",
                    self.url("revoke_access", grant=active.pk),
                    steps=self.business_submit({"reason": "پایان دسترسی بررسی"}),
                )
            ],
        )
        self.browser(
            self.preparer,
            [
                self.case(
                    "revoked-document-access",
                    self.workspace(),
                    noHttpErrors=False,
                    steps=[
                        self.inspect(
                            f"fetch('{document}').then(r=>r.status===403)",
                            "revoked content denied",
                        )
                    ],
                )
            ],
        )
        self.responsive(self.owner, "closed-history")
        self.assertFalse(m.PurchaseOrder.objects.exists())


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ComparisonAwardBrowserTests(
    BrowserMixin, P5S11FixtureMixin, StaticLiveServerTestCase
):
    def test_admissibility_comparison_conflict_award_no_award_isolation(self):
        self.rfq = self.revision.envelope.rfq
        self.project.name = "پروژه سازه نمونه"
        self.project.save(update_fields=["name"])
        self.material.name = "سیمان پرتلند"
        self.material.save(update_fields=["name"])
        self.supplier.display_name = "تأمین مصالح پارس"
        self.supplier.save(update_fields=["display_name"])
        # Fixture has real Domain opening/grants/admissibility backed by synthetic test assessments.
        prepare = self.url("prepare_admissibility", quote_revision=self.revision.pk)
        self.browser(
            self.preparer,
            [
                self.case(
                    "nonconformance-review-proposal",
                    prepare,
                    steps=self.business_submit(
                        {
                            "state": "inadmissible",
                            "reason_code": "commercial_nonconformance",
                            "rationale": "عدم انطباق شرایط پیشنهاد با مدارک استعلام",
                        }
                    ),
                )
            ],
        )
        prep = m.QuoteAdmissibilityPreparation.objects.latest("created_at")
        self.browser(
            self.approver,
            [
                self.case(
                    "nonconformance-independent-decision",
                    self.url("approve_admissibility", preparation=prep.pk),
                    steps=self.business_submit({"supersedes": str(self.decision.pk)}),
                )
            ],
        )
        nonconforming = m.QuoteAdmissibilityDecision.objects.latest("created_at")
        self.browser(
            self.preparer,
            [
                self.case(
                    "nonconforming-visible-history",
                    self.workspace(),
                    mustText=["عدم انطباق شرایط پیشنهاد"],
                )
            ],
        )
        self.browser(
            self.preparer,
            [
                self.case(
                    "admissibility-corrective-review",
                    prepare,
                    steps=self.business_submit(
                        {
                            "state": "admissible",
                            "reason_code": "requirements_met",
                            "rationale": "رفع عدم انطباق با شاهد منبع رسمی",
                        }
                    ),
                )
            ],
        )
        prep = m.QuoteAdmissibilityPreparation.objects.latest("created_at")
        self.browser(
            self.approver,
            [
                self.case(
                    "admissibility-corrective-approval",
                    self.url("approve_admissibility", preparation=prep.pk),
                    steps=self.business_submit({"supersedes": str(nonconforming.pk)}),
                )
            ],
        )
        compare = self.url("prepare_comparison", scope=self.scope.pk)
        self.browser(
            self.preparer,
            [
                self.case(
                    "comparison-explicit-assertions",
                    compare,
                    steps=self.business_submit(
                        {
                            "rows-0-quote_revision_id": str(self.revision.pk),
                            "rows-0-offered_quantity": "10",
                            "rows-0-unit_price": "12500",
                            "rows-0-currency": "IRR",
                            "rows-0-explicit_discount": "0",
                            "rows-0-source_locator": "صفحه یک، ردیف سیمان",
                        }
                    ),
                )
            ],
        )
        comparison = m.CommercialComparison.objects.get()
        self.browser(
            self.preparer,
            [
                self.case(
                    "appoint-comparison-evaluator",
                    self.url("appoint_evaluator", comparison=comparison.pk),
                    steps=self.business_submit(
                        {
                            "membership": str(
                                self.organization.memberships.get(user=self.preparer).pk
                            )
                        }
                    ),
                )
            ],
        )
        appointment = m.EvaluatorAppointment.objects.get()
        self.browser(
            self.preparer,
            [
                self.case(
                    "declare-evaluator-conflict",
                    self.url("declare_conflict", appointment=appointment.pk),
                    steps=self.business_submit(
                        {"evidence": "ارتباط تجاری نیازمند بررسی مستقل"}
                    ),
                )
            ],
        )
        conflict = m.EvaluatorConflictDeclaration.objects.get()
        evaluate = self.url("evaluate", appointment=appointment.pk)
        item = comparison.inputs.get()
        self.browser(
            self.preparer,
            [
                self.case(
                    "unresolved-conflict-blocks-evaluation",
                    evaluate,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        {
                            "fill": {
                                "input": str(item.pk),
                                "recommendation": "بررسی پیشنهاد",
                                "evidence": "برگه بررسی",
                            },
                            "clickSelector": "#buyer-action-form button[type=submit]",
                            "afterPath": evaluate.split("?")[0],
                        }
                    ],
                )
            ],
        )
        self.browser(
            self.approver,
            [
                self.case(
                    "independent-conflict-disposition",
                    self.url("dispose_conflict", conflict=conflict.pk),
                    steps=self.business_submit(
                        {"approved": "no", "reason": "ارتباط مؤثر تأیید نشد"}
                    ),
                )
            ],
        )
        self.browser(
            self.preparer,
            [
                self.case(
                    "evaluate-source-assertions",
                    evaluate,
                    steps=self.business_submit(
                        {
                            "input": str(item.pk),
                            "recommendation": "شرایط تجاری بررسی شد",
                            "evidence": "برگه ارزیابی امضاشده",
                        }
                    ),
                )
            ],
        )
        self.responsive(self.preparer, "comparison-prepared")
        final = self.url("finalize_comparison", comparison=comparison.pk)
        self.browser(
            self.preparer,
            [
                self.case(
                    "comparison-self-finalization-denial",
                    final,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        {
                            "fill": {"reason": "بررسی کامل"},
                            "clickSelector": "#buyer-action-form button[type=submit]",
                            "afterPath": final.split("?")[0],
                        }
                    ],
                )
            ],
        )
        self.browser(
            self.approver,
            [
                self.case(
                    "comparison-independent-finalize",
                    final,
                    steps=self.business_submit({"reason": "بررسی کامل و مستند"}),
                )
            ],
        )
        finalized = m.CommercialComparison.objects.get(finalized_at__isnull=False)
        award = self.url("prepare_award", comparison=finalized.pk)
        self.browser(
            self.preparer,
            [
                self.case(
                    "partial-award-proposal",
                    award,
                    steps=self.business_submit(
                        {
                            "outcome": "awarded",
                            "reason": "تأمین مرحله نخست پروژه",
                            "evidence": "صورت‌جلسه کمیته خرید",
                            "rows-0-comparison_input_id": str(
                                finalized.inputs.get().pk
                            ),
                            "rows-0-quantity": "4",
                        }
                    ),
                )
            ],
        )
        preparation = m.SourcingAwardPreparation.objects.get()
        approve = self.url("finalize_award", preparation=preparation.pk)
        self.browser(
            self.preparer,
            [
                self.case(
                    "award-self-approval-denied",
                    approve,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        {
                            "clickSelector": "#buyer-action-form button[type=submit]",
                            "afterPath": approve.split("?")[0],
                        }
                    ],
                )
            ],
        )
        self.browser(
            self.approver,
            [
                self.case(
                    "award-independent-finalize", approve, steps=self.business_submit()
                )
            ],
        )
        awarded = m.SourcingAward.objects.get()
        self.assertEqual(awarded.allocations.get().quantity, 4)
        self.assertEqual(awarded.allocations.get().quote_revision_id, self.revision.pk)
        self.responsive(self.approver, "award-final")
        self.browser(
            self.preparer,
            [
                self.case(
                    "no-award-explicit-proposal",
                    award,
                    steps=self.business_submit(
                        {
                            "outcome": "no_award",
                            "reason": "صرف نظر مستند از خرید",
                            "evidence": "تصمیم کمیته خرید",
                        }
                    ),
                )
            ],
        )
        no_award = m.SourcingAwardPreparation.objects.get(outcome="no_award")
        self.browser(
            self.approver,
            [
                self.case(
                    "no-award-explicit-successor",
                    self.url("finalize_award", preparation=no_award.pk),
                    steps=self.business_submit({"supersedes": str(awarded.pk)}),
                )
            ],
        )
        final_award = m.SourcingAward.objects.get(preparation=no_award)
        self.assertFalse(final_award.allocations.exists())
        self.assertFalse(m.PurchaseOrder.objects.exists())
        grant = m.QuoteConfidentialAccessGrant.objects.get(
            quote_revision=self.revision, membership__user=self.preparer
        )
        revoke_quote_confidential_access(
            organization=self.organization,
            actor=self.owner,
            grant=grant,
            reason="review complete",
        )
        self.browser(
            self.preparer,
            [
                self.case(
                    "revoked-comparison-and-award-hidden",
                    self.workspace(),
                    absentText=["صفحه یک، ردیف سیمان", "تأمین مرحله نخست پروژه"],
                )
            ],
        )
        self.browser(
            self.outsider,
            [
                self.case(
                    "cross-tenant-workspace-denial",
                    self.workspace(),
                    status=403,
                    noHttpErrors=False,
                )
            ],
        )
        self.browser(
            self.viewer,
            [
                self.case(
                    "unauthorized-capture-denial",
                    self.url("capture"),
                    status=403,
                    noHttpErrors=False,
                )
            ],
        )
        member = self.organization.memberships.get(user=self.approver)
        MembershipScopeGrant.objects.filter(membership=member).update(
            revoked_at=timezone.now()
        )
        project = Project.objects.create(
            organization=self.organization, code="RESTRICT", name="پروژه محدود"
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=member,
            scope_type="project",
            project=project,
            reason="scope test fixture",
        )
        self.browser(
            self.approver,
            [
                self.case(
                    "cross-project-workspace-denial",
                    self.workspace(),
                    status=404,
                    noHttpErrors=False,
                )
            ],
        )

    def test_final_history_projection_does_not_continue_superseded_award(self):
        self.rfq = self.revision.envelope.rfq
        comparison, _ = self._evaluated_comparison()
        finalized = commercial.finalize_comparison(
            organization=self.organization,
            actor=self.approver,
            comparison=comparison,
            reason="final history fixture",
        )
        preparation = commercial.prepare_sourcing_award(
            organization=self.organization,
            actor=self.preparer,
            comparison=finalized,
            outcome="awarded",
            allocations=[
                {"comparison_input_id": str(finalized.inputs.get().pk), "quantity": "4"}
            ],
            reason="انتخاب مرحله اول",
            evidence="صورت‌جلسه خرید",
            idempotency_key="history-awarded",
        )
        award = commercial.finalize_sourcing_award(
            organization=self.organization, actor=self.approver, preparation=preparation
        )
        successor = commercial.prepare_sourcing_award(
            organization=self.organization,
            actor=self.preparer,
            comparison=finalized,
            outcome="no_award",
            allocations=[],
            reason="صرف نظر مستند از خرید",
            evidence="صورت‌جلسه جدید",
            idempotency_key="history-no-award",
        )
        commercial.finalize_sourcing_award(
            organization=self.organization,
            actor=self.approver,
            preparation=successor,
            supersedes=award,
        )
        self.browser(
            self.approver,
            [
                self.case(
                    f"final-history-{width}",
                    self.workspace(),
                    width=width,
                    mobile=width == 390,
                    mustText=["تصمیم پیشین محفوظ", "بدون انتخاب"],
                    absentText=["مرحله بعد: سفارش خرید"],
                    steps=[
                        self.inspect(
                            "[...document.querySelectorAll('main a')].filter(a=>a.textContent.includes('بررسی و نهایی')).length===0",
                            "final preparations have no redundant finalize action",
                        )
                    ],
                )
                for width in (1440, 1024, 390)
            ],
        )
        self.assertFalse(m.PurchaseOrder.objects.exists())

    def test_action_forms_at_desktop_tablet_mobile(self):
        self.rfq = self.revision.envelope.rfq
        comparison, _ = self._evaluated_comparison()
        finalized = commercial.finalize_comparison(
            organization=self.organization,
            actor=self.approver,
            comparison=comparison,
            reason="form layout fixture",
        )
        self.browser(
            self.preparer,
            [
                self.case(
                    f"{name}-form-{width}", path, width=width, mobile=width == 390
                )
                for name, path in [
                    ("capture", self.url("capture")),
                    ("comparison", self.url("prepare_comparison", scope=self.scope.pk)),
                    ("award", self.url("prepare_award", comparison=finalized.pk)),
                ]
                for width in (1440, 1024, 390)
            ],
        )


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SplitLotBrowserTests(
    BrowserMixin, P5S11TwoRevisionFixtureMixin, StaticLiveServerTestCase
):
    def setUp(self):
        from apps.procurement.commercial_scope_services import (
            define_rfq_commercial_scope,
        )

        def explicit_test_scopes(**kwargs):
            rfq = kwargs["rfq"]
            line = rfq.lines.get()
            common = {
                "lines": [
                    {
                        "purchase_request_item_id": str(line.purchase_request_item_id),
                        "quantity": "10",
                    }
                ]
            }
            entries = [
                {
                    **common,
                    "scope_type": "line",
                    "scope_code": code,
                    "required_quantity": "10",
                    "independently_awardable": True,
                    "allows_split_award": split,
                    "allows_alternates": True,
                }
                for code, split in kwargs["specifications"]
            ]
            entries.append(
                {
                    **common,
                    "scope_type": "lot",
                    "scope_code": "بسته مصالح سازه",
                    "required_quantity": "1",
                    "unit_of_measure_id": str(line.unit_of_measure_id),
                    "independently_awardable": False,
                    "allows_split_award": False,
                    "allows_alternates": False,
                }
            )
            return define_rfq_commercial_scope(
                organization=kwargs["organization"],
                actor=kwargs["actor"],
                rfq=rfq,
                version_number=1,
                scopes=entries,
                expected_revision=0,
                idempotency_key="explicit-split-lot-browser-fixture",
            )

        with patch(
            "apps.procurement.scope_test_helpers.define_fixture_scopes",
            side_effect=explicit_test_scopes,
        ):
            super().setUp()
        self.rfq = self.revision.envelope.rfq

    def finalized(self, comparison):
        appointment = commercial.appoint_evaluator(
            organization=self.organization,
            actor=self.preparer,
            comparison=comparison,
            membership=self.organization.memberships.get(user=self.preparer),
        )
        for item in comparison.inputs.all():
            commercial.evaluate_comparison(
                organization=self.organization,
                actor=self.preparer,
                appointment=appointment,
                input=item,
                recommendation="بررسی مستند مقدار و قیمت",
                evidence="صورت‌جلسه ارزیابی آزمایشی",
            )
        return commercial.finalize_comparison(
            organization=self.organization,
            actor=self.approver,
            comparison=comparison,
            reason="تکمیل ارزیابی",
        )

    def test_split_lot_and_alternate_existing_domain_structures(self):
        finalized = self.finalized(self._two_comparison())
        inputs = list(finalized.inputs.order_by("created_at"))
        proposal = self.url("prepare_award", comparison=finalized.pk)
        self.browser(
            self.preparer,
            [
                self.case(
                    "split-explicit-two-suppliers",
                    proposal,
                    steps=[
                        {"toggleSelector": "#add-action-row"},
                        *self.business_submit(
                            {
                                "outcome": "awarded",
                                "reason": "تقسیم صریح خرید میان دو تأمین‌کننده",
                                "evidence": "صورت‌جلسه انتخاب",
                                "rows-0-comparison_input_id": str(inputs[0].pk),
                                "rows-0-quantity": "4",
                                "rows-1-comparison_input_id": str(inputs[1].pk),
                                "rows-1-quantity": "6",
                            }
                        ),
                    ],
                )
            ],
        )
        prep = m.SourcingAwardPreparation.objects.get()
        self.browser(
            self.approver,
            [
                self.case(
                    "split-independent-finalize",
                    self.url("finalize_award", preparation=prep.pk),
                    steps=self.business_submit(),
                )
            ],
        )
        self.assertEqual(m.SourcingAward.objects.get().allocations.count(), 2)
        lot = self.revision.rfq_version.commercial_scopes.get(scope_type="lot")
        comparison = commercial.prepare_comparison(
            organization=self.organization,
            actor=self.preparer,
            scope=lot,
            assertions=[
                {
                    "quote_revision_id": self.revision_one.pk,
                    "offered_quantity": "1",
                    "unit_price": "1200",
                    "currency": "IRR",
                    "source_locator": "صفحه بسته کامل",
                }
            ],
            idempotency_key="lot-comparison-fixture",
        )
        lot_final = self.finalized(comparison)
        lot_proposal = self.url("prepare_award", comparison=lot_final.pk)
        fill = {
            "outcome": "awarded",
            "reason": "انتخاب بسته کامل",
            "evidence": "پیشنهاد بسته",
            "rows-0-comparison_input_id": str(lot_final.inputs.get().pk),
            "rows-0-quantity": "0.5",
        }
        self.browser(
            self.preparer,
            [
                self.case(
                    "lot-partial-allocation-denial",
                    lot_proposal,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        {
                            "fill": fill,
                            "clickSelector": "#buyer-action-form button[type=submit]",
                            "afterPath": lot_proposal.split("?")[0],
                        }
                    ],
                )
            ],
        )
        self.browser(
            self.preparer,
            [
                self.case(
                    "lot-complete-allocation",
                    lot_proposal,
                    steps=self.business_submit({**fill, "rows-0-quantity": "1"}),
                )
            ],
        )
        lot_prep = m.SourcingAwardPreparation.objects.get(comparison=lot_final)
        self.browser(
            self.approver,
            [
                self.case(
                    "lot-independent-finalize",
                    self.url("finalize_award", preparation=lot_prep.pk),
                    steps=self.business_submit(),
                )
            ],
        )
        self.assertEqual(
            m.SourcingAward.objects.get(preparation=lot_prep).unawarded_quantity, 0
        )
        compare = self.url("prepare_comparison", scope=self.scope.pk)
        self.browser(
            self.preparer,
            [
                self.case(
                    "alternate-explicit-source-assertion",
                    compare,
                    steps=self.business_submit(
                        {
                            "rows-0-quote_revision_id": str(self.revision_one.pk),
                            "rows-0-offered_quantity": "10",
                            "rows-0-unit_price": "1190",
                            "rows-0-currency": "IRR",
                            "rows-0-explicit_discount": "0",
                            "rows-0-source_locator": "پیوست پیشنهاد جایگزین",
                            "rows-0-is_alternate": True,
                            "rows-0-alternate_basis": "مدل جایگزین مجاز در استعلام",
                        }
                    ),
                )
            ],
        )
        alternate = m.CommercialComparison.objects.filter(
            inputs__assertion__is_alternate=True
        ).get()
        alternate_final = self.finalized(alternate)
        self.browser(
            self.preparer,
            [
                self.case(
                    "alternate-award-proposal",
                    self.url("prepare_award", comparison=alternate_final.pk),
                    steps=self.business_submit(
                        {
                            "outcome": "awarded",
                            "reason": "انتخاب صریح پیشنهاد جایگزین",
                            "evidence": "صورت‌جلسه بررسی جایگزین",
                            "rows-0-comparison_input_id": str(
                                alternate_final.inputs.get().pk
                            ),
                            "rows-0-quantity": "10",
                        }
                    ),
                )
            ],
        )
        alt_prep = m.SourcingAwardPreparation.objects.get(comparison=alternate_final)
        self.browser(
            self.approver,
            [
                self.case(
                    "alternate-award-finalize",
                    self.url("finalize_award", preparation=alt_prep.pk),
                    steps=self.business_submit(),
                )
            ],
        )
        self.assertTrue(
            m.SourcingAward.objects.get(preparation=alt_prep)
            .allocations.get()
            .comparison_input.assertion.is_alternate
        )
        self.assertFalse(m.PurchaseOrder.objects.exists())

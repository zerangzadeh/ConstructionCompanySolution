"""Read-only business presentation over the existing sourcing authorities."""

from django.urls import reverse
from django.utils import timezone

from apps.organizations.authorization import has_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from apps.procurement import models as m
from apps.procurement.rfq_action_forms import ACTIONS, confidential_revisions

STAGES = (
    ("quotes", "دعوت و پیشنهاد"),
    ("opening", "گشایش حفاظت‌شده"),
    ("admissibility", "بررسی پذیرش"),
    ("comparison", "مقایسه و ارزیابی"),
    ("award", "انتخاب یا عدم انتخاب"),
)


def action_url(rfq, action, **parents):
    from urllib.parse import urlencode

    url = reverse("procurement:rfq_buyer_action", args=[rfq.pk, action])
    return url + (
        "?" + urlencode({k: str(v) for k, v in parents.items()}) if parents else ""
    )


def presentation_error(exc):
    text = "؛ ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
    replacements = {
        "کلید یکتا": "شناسه ارسال",
        "کلید یکتای": "شناسه ارسال",
        "idempotency": "شناسه ارسال",
        "CLEAN": "تأیید سلامت پردازش فایل",
        "SHA-256": "صحت فایل",
        "Tenant": "شرکت",
        "RFQ": "استعلام",
        "FX": "تبدیل ارز",
        "MIME": "نوع محتوای",
        "کاتالوگ v1": "فهرست مصوب",
        "مانیفست": "صورت‌جلسه",
        "هش": "اثر صحت",
        "نرمال‌سازی": "هم‌مبنا کردن",
    }
    for source, label in replacements.items():
        text = text.replace(source, label)
    return text


def workspace_context(request, rfq):
    active = request.organization.status == "active" and rfq.project.deleted_at is None

    def allowed(code):
        return active and has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=code,
            project=rfq.project,
        )

    def link(action, **parents):
        if allowed(ACTIONS[action][0]):
            return {
                "code": action,
                "title": ACTIONS[action][1],
                "url": action_url(rfq, action, **parents),
            }
        return None

    can_metadata = allowed(P.RFQ_QUOTES_VIEW_METADATA)
    revisions = m.QuoteRevision.objects.filter(
        organization=request.organization, envelope__rfq=rfq
    )
    visible_ids = set(
        confidential_revisions(rfq=rfq, actor=request.user).values_list("pk", flat=True)
    )
    rows = []
    if can_metadata:
        for revision in (
            revisions.select_related(
                "envelope__supplier", "rfq_version", "opening_event"
            )
            .prefetch_related("evidence_items", "opening_requests__opening_event")
            .order_by("envelope__supplier__display_name", "-revision_number")
        ):
            current = revision.rfq_version.version_number == rfq.current_version_number
            mutable = (
                current
                and rfq.status == "issued"
                and timezone.now() <= revision.rfq_version.closing_at
            )
            opened = hasattr(revision, "opening_event")
            accessible = revision.pk in visible_ids
            evidence = list(revision.evidence_items.all())
            pending = next(
                (
                    r
                    for r in revision.opening_requests.all()
                    if not hasattr(r, "opening_event")
                ),
                None,
            )
            eligible = (
                current and revision.status == "submitted" and not revision.is_late
            )
            reason = ""
            if revision.status in {"withdrawn", "superseded"}:
                state = revision.get_status_display()
                reason = "این نسخه در تاریخچه محفوظ است و پیشنهاد مؤثر برای گشایش نیست."
            elif opened:
                state = "گشوده‌شده" if accessible else "گشوده‌شده · بدون دسترسی محتوا"
                reason = (
                    "مشاهده محتوا به مجوز و اعطای فعال برای همین نسخه نیاز دارد."
                    if not accessible
                    else "دسترسی فعال به همین نسخه برقرار است."
                )
            elif not eligible:
                state, reason = (
                    "مهروموم‌شده",
                    "دریافت دیرهنگام در سوابق محفوظ است؛ در گشایش عادی پیشنهاد مؤثر نیست."
                    if revision.is_late
                    else "ثبت نهایی به‌موقعِ نسخه جاری برای گشایش لازم است.",
                )
            elif rfq.status != "closed":
                state, reason = (
                    "مهروموم‌شده",
                    "ابتدا مهلت دریافت پایان یابد و استعلام با صورت‌جلسه نهایی بسته شود.",
                )
            elif timezone.now() < revision.rfq_version.earliest_opening_at:
                state, reason = "مهروموم‌شده", "زمان مجاز گشایش هنوز فرا نرسیده است."
            elif not any(e.evidence_type == "supplier_original" for e in evidence):
                state, reason = (
                    "مهروموم‌شده",
                    "اصل پیشنهاد باید در نگهداری حفاظت‌شده ثبت شود.",
                )
            elif pending:
                state, reason = (
                    "در انتظار تأیید مستقل",
                    "تأییدکننده باید فرد دیگری باشد؛ همه فایل‌ها به شاهد واقعی تأیید سلامت پردازش نیاز دارند.",
                )
            else:
                state, reason = (
                    "آماده درخواست گشایش",
                    "بسته مدارک تثبیت می‌شود؛ گشایش به تأیید مستقل و سلامت واقعی همه فایل‌ها نیاز دارد.",
                )
            actions = []

            def add(action, actions=actions, **parents):
                if item := link(action, **parents):
                    actions.append(item)

            if mutable:
                add("capture", invitation=revision.invitation_id)
                if revision.status == "captured":
                    add("submit", quote_revision=revision.pk)
                if revision.status in {"captured", "submitted"}:
                    add("withdraw", quote_revision=revision.pk)
            if eligible and rfq.status == "closed" and not opened:
                if not m.QuoteEvidencePackageFreeze.objects.filter(
                    quote_revision=revision
                ).exists():
                    add("attach_evidence", quote_revision=revision.pk)
                if state == "آماده درخواست گشایش":
                    add("request_opening", quote_revision=revision.pk)
                if pending and pending.requested_by_id != request.user.pk:
                    add("approve_opening", opening_request=pending.pk)
            if opened:
                add("grant_access", quote_revision=revision.pk)
                if accessible:
                    add("prepare_admissibility", quote_revision=revision.pk)
            decisions = (
                m.QuoteAdmissibilityDecision.objects.filter(
                    organization=request.organization, quote_revision=revision
                )
                .select_related("approved_by")
                .order_by("-approved_at")
                if accessible
                else []
            )
            preparations = (
                m.QuoteAdmissibilityPreparation.objects.filter(
                    organization=request.organization,
                    quote_revision=revision,
                    withdrawal__isnull=True,
                    decision__isnull=True,
                )
                if accessible
                else []
            )
            for preparation in preparations:
                add("approve_admissibility", preparation=preparation.pk)
            rows.append(
                {
                    "revision": revision,
                    "state": state,
                    "reason": reason,
                    "actions": actions,
                    "accessible": accessible,
                    "evidence": evidence if accessible else [],
                    "decisions": decisions,
                    "preparations": preparations,
                }
            )
    return {
        "stages": STAGES,
        "quote_rows": rows,
        "invitations": m.RequestForQuotationInvitation.objects.filter(
            organization=request.organization, rfq_version__rfq=rfq
        )
        .select_related("supplier", "rfq_version")
        .order_by("-rfq_version__version_number", "supplier__display_name")
        if can_metadata
        else [],
        "capture_action": link("capture")
        if can_metadata and rfq.status in {"issued", "closed"}
        else None,
        "scope_actions": [
            {"scope": scope, "action": link("prepare_comparison", scope=scope.pk)}
            for scope in m.RFQCommercialScope.objects.filter(
                organization=request.organization,
                rfq_version__rfq=rfq,
                rfq_version__version_number=rfq.current_version_number,
            ).select_related(
                "rfq_version_line__material", "unit_of_measure", "rfq_version"
            )
        ]
        if allowed(P.RFQ_QUOTES_PREPARE_COMPARISON) and visible_ids
        else [],
        "access_action": link("revoke_access"),
        "can_view_source": allowed(P.PURCHASE_REQUESTS_VIEW),
        "requested_lines": m.RequestForQuotationVersionLine.objects.filter(
            organization=request.organization,
            rfq_version__rfq=rfq,
            rfq_version__version_number=rfq.current_version_number,
        ).select_related("material", "unit_of_measure"),
    }

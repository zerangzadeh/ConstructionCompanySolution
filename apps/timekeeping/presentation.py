"""State/actor-aware UI affordances over the unchanged Timekeeping services."""

from django.urls import reverse

from apps.organizations.authorization import has_business_permission


def record_actions(request, record, kind: str) -> dict:
    source = record.attendance if kind == "correction" else record

    def allowed(permission):
        return has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=permission,
            project=source.project,
            site=source.site,
        )

    result = {}
    if kind == "attendance":
        if (
            record.state in ("draft", "exception")
            and record.check_out_at
            and record.captured_by_id != request.user.pk
            and allowed("attendance.review")
        ):
            result = {
                "url": reverse("timekeeping:attendance_finalize", args=[record.pk]),
                "label": "قطعی‌سازی حضور",
                "reason": True,
                "reason_required": record.state == "exception",
            }
        elif (
            record.state == "finalized"
            and request.user.pk not in (record.captured_by_id, record.finalized_by_id)
            and allowed("attendance.correct")
        ):
            result = {
                "url": reverse(
                    "timekeeping:attendance_correction_create", args=[record.pk]
                ),
                "label": "درخواست اصلاح حضور",
                "link": True,
            }
    elif kind == "correction":
        if (
            record.status == "pending"
            and record.requested_by_id != request.user.pk
            and allowed("attendance.correct")
        ):
            result = {
                "url": reverse(
                    "timekeeping:attendance_correction_review", args=[record.pk]
                ),
                "label": "بررسی اصلاح حضور",
                "review": True,
                "can_approve": source.state == "finalized",
                "approval_requirement": "حضور مبنا دیگر در وضعیت قطعی نیست؛ تأیید اصلاح ممکن نیست.",
                "reason": True,
            }
    else:
        prefix = "leave_mission" if kind == "leave" else "overtime"
        if (
            record.state == "draft"
            and record.requested_by_id == request.user.pk
            and allowed(f"{prefix}.request")
        ):
            if kind == "leave" and record.kind == "leave":
                from apps.workforce.leave_models import (
                    LeaveBalanceEntry,
                    LeaveEntryKind,
                )

                if not LeaveBalanceEntry.objects.filter(
                    organization=request.organization,
                    request=record,
                    kind=LeaveEntryKind.RESERVATION,
                ).exists():
                    return {
                        "label": "پیش‌نویس مرخصی",
                        "blocked": "برای ارسال، تخصیص مرخصی باید از مسیر مصوب شرکت ثبت شود.",
                    }
            result = {
                "url": reverse(f"timekeeping:{prefix}_submit", args=[record.pk]),
                "label": "ارسال درخواست",
            }
        elif (
            record.state == "submitted"
            and record.requested_by_id != request.user.pk
            and allowed(f"{prefix}.review")
        ):
            result = {
                "url": reverse(f"timekeeping:{prefix}_review", args=[record.pk]),
                "label": "بررسی درخواست",
                "review": True,
                "can_approve": bool(record.policy_reference.strip()),
                "approval_requirement": "تأیید به مرجع سیاست مصوب نیاز دارد.",
                "reason": True,
            }
    return result

"""Shared admission and replay checks for independent MVP record decisions."""

from django import forms
from django.core.exceptions import PermissionDenied

from apps.organizations.authorization import has_business_permission


class RecordDecisionForm(forms.Form):
    submission_id = forms.UUIDField(widget=forms.HiddenInput)
    outcome = forms.ChoiceField(
        label="تصمیم بررسی رکورد",
        choices=(
            ("approved", "تأیید رکورد"),
            ("returned", "بازگشت برای اصلاح"),
            ("rejected", "رد رکورد"),
        ),
    )
    reason = forms.CharField(
        label="دلیل تصمیم", max_length=2000, widget=forms.Textarea(attrs={"rows": 3})
    )


class RecordCorrectionForm(forms.Form):
    return_id = forms.UUIDField(widget=forms.HiddenInput)
    description = forms.CharField(
        label="شرح رکورد", widget=forms.Textarea(attrs={"rows": 4})
    )
    reason = forms.CharField(
        label="دلیل اصلاح", max_length=2000, widget=forms.Textarea(attrs={"rows": 3})
    )


def can_correct_record(request, record, permission) -> bool:
    return record.review_status == "returned" and has_business_permission(
        user=request.user,
        organization=request.organization,
        permission=permission,
        project=record.project,
        site=record.site,
    )


def can_decide_record(request, record, submission, permission) -> bool:
    return (
        record.review_status == "submitted"
        and submission is not None
        and submission.state == "submitted"
        and request.user.pk not in (record.created_by_id, submission.actor_id)
        and has_business_permission(
            user=request.user,
            organization=request.organization,
            permission=permission,
            project=record.project,
            site=record.site,
        )
    )


def check_independent_decision(record, actor, submission_id, outcome, reason):
    """Called with the source record locked by its domain service."""
    latest = record.review_revisions.order_by("-sequence").first()
    if latest is None:
        raise ValueError("نسخه ارسال‌شده برای بررسی در دسترس نیست.")
    if record.created_by_id == actor.pk:
        raise PermissionDenied("ثبت‌کننده رکورد نمی‌تواند درباره آن تصمیم بگیرد.")
    if latest.pk == submission_id and latest.state == "submitted":
        if latest.actor_id == actor.pk:
            raise PermissionDenied("ارسال‌کننده رکورد نمی‌تواند درباره آن تصمیم بگیرد.")
        return None
    if (
        latest.previous_id == submission_id
        and latest.prior_state == "submitted"
        and latest.state == outcome
        and latest.actor_id == actor.pk
        and latest.reason == reason.strip()
    ):
        return latest
    raise ValueError("رکورد پس از باز کردن فرم تغییر کرده است. آن را دوباره باز کنید.")

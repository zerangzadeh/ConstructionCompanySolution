"""Jalali forms over source-owned choices; no Employee/tenant identity inputs."""

from zoneinfo import ZoneInfo

from django import forms
from django.utils import timezone

from apps.organizations.authorization import get_active_membership, scope_queryset
from apps.projects.models import Activity, Project, ProjectSite
from core.forms import JalaliDateMixin

from .ess_timekeeping import subject
from .leave_models import LeavePolicyVersion
from .models import EmployeeProjectAssignment


class ESSForm(JalaliDateMixin, forms.Form):
    def __init__(self, *args, organization, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization, self.own = subject(actor=actor, organization=organization)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "erp-input w-full")


class LeaveForm(ESSForm):
    policy_id = forms.ChoiceField(label="نوع مرخصی و واحد سیاست")
    starts_at = forms.DateTimeField(label="شروع مرخصی")
    ends_at = forms.DateTimeField(label="پایان مرخصی")
    quantity = forms.DecimalField(
        label="مقدار در واحد سیاست انتخاب‌شده",
        max_digits=14,
        decimal_places=4,
        min_value=0,
    )
    reason = forms.CharField(
        label="دلیل درخواست", max_length=2000, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate(
            timezone=ZoneInfo(self.organization.settings.timezone)
        )
        policies = LeavePolicyVersion.objects.filter(
            organization=self.organization,
            effective_from__lte=today,
            effective_to__gt=today,
        ).order_by("category_code", "-version")
        seen = set()
        choices = []
        for policy in policies:
            if policy.category_code not in seen:
                seen.add(policy.category_code)
                choices.append(
                    (
                        str(policy.pk),
                        f"{policy.category_code} · {'دقیقه' if policy.unit == 'minutes' else 'روز'} · نسخه {policy.version}",
                    )
                )
        self.fields["policy_id"].choices = choices


class CorrectionForm(ESSForm):
    work_date = forms.DateField(label="تاریخ پیشنهادی")
    check_in_at = forms.DateTimeField(label="ورود پیشنهادی")
    check_out_at = forms.DateTimeField(label="خروج پیشنهادی")
    reason = forms.CharField(
        label="دلیل درخواست اصلاح",
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def clean(self):
        data = super().clean()
        if (
            data.get("check_in_at")
            and data.get("check_out_at")
            and data["check_out_at"] <= data["check_in_at"]
        ):
            raise forms.ValidationError("خروج باید پس از ورود باشد.")
        return data


class OvertimeForm(ESSForm):
    starts_at = forms.DateTimeField(label="شروع اضافه‌کاری")
    ends_at = forms.DateTimeField(label="پایان اضافه‌کاری")
    reason = forms.CharField(
        label="دلیل درخواست اضافه‌کاری",
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def clean(self):
        data = super().clean()
        if any(
            key in self.data
            for key in (
                "organization",
                "organization_id",
                "employee",
                "employee_id",
                "person_id",
                "relationship_id",
                "work_relationship_id",
                "policy_reference",
                "project",
                "project_id",
                "site",
                "site_id",
                "rate",
                "amount",
                "multiplier",
                "state",
                "approved_by",
            )
        ):
            raise forms.ValidationError("درخواست شامل مقدار غیرمجاز است.")
        if (
            data.get("starts_at")
            and data.get("ends_at")
            and data["ends_at"] <= data["starts_at"]
        ):
            raise forms.ValidationError("پایان اضافه‌کاری باید پس از شروع باشد.")
        return data


class TimesheetForm(ESSForm):
    period_start = forms.DateField(label="شروع دوره")
    period_end = forms.DateField(label="پایان دوره")
    declared_minutes = forms.IntegerField(label="کل دقیقه اعلام‌شده", min_value=1)


class EntryForm(ESSForm):
    work_date = forms.DateField(label="تاریخ کارکرد")
    project = forms.ModelChoiceField(label="پروژه", queryset=Project.objects.none())
    site = forms.ModelChoiceField(
        label="کارگاه", queryset=ProjectSite.objects.none(), required=False
    )
    activity = forms.ModelChoiceField(
        label="فعالیت", queryset=Activity.objects.none(), required=False
    )
    minutes = forms.IntegerField(label="مدت به دقیقه", min_value=1)

    def __init__(self, *args, organization, actor, **kwargs):
        super().__init__(*args, organization=organization, actor=actor, **kwargs)
        assignments = EmployeeProjectAssignment.objects.filter(
            organization=self.organization,
            employee=self.own.current_relationship.legacy_employee,
        ).exclude(status="cancelled")
        membership = get_active_membership(user=actor, organization=self.organization)
        self.fields["project"].queryset = scope_queryset(
            Project.objects.filter(
                organization=self.organization, pk__in=assignments.values("project_id")
            ),
            membership=membership,
            project_lookup="pk",
            include_site_parent=True,
        )
        self.fields["site"].queryset = scope_queryset(
            ProjectSite.objects.filter(
                organization=self.organization, pk__in=assignments.values("site_id")
            ),
            membership=membership,
            project_lookup="project",
            site_lookup="pk",
        )
        self.fields["activity"].queryset = scope_queryset(
            Activity.objects.filter(
                organization=self.organization, site__in=self.fields["site"].queryset
            ),
            membership=membership,
            project_lookup="project",
            site_lookup="site",
        )

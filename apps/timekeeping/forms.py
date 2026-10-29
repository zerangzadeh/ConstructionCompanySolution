import json

from django import forms
from django.core.exceptions import ValidationError

from apps.organizations.authorization import get_active_membership, scope_queryset
from apps.projects.models import Activity, Project, ProjectSite
from apps.workforce.field_forms import (
    business_label,
    choice_value,
    dependent_choices,
    searchable_choices,
)
from apps.workforce.field_selectors import (
    FieldContext,
    context_employees,
    scoped_employees,
)
from apps.workforce.models import Employee
from core.forms import JalaliDateMixin

from .models import ShiftDefinition, WorkCalendar


class StyledForm(JalaliDateMixin, forms.Form):
    def __init__(self, *args, organization=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.user = user
        for field in self.fields.values():
            if isinstance(field, forms.ModelChoiceField):
                field.label_from_instance = business_label
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm",
            )


class WorkingWeekdaysField(forms.TypedMultipleChoiceField):
    """Named choices with compatibility for the original comma-separated input."""

    def to_python(self, value):
        if isinstance(value, (list, tuple)) and len(value) == 1:
            value = value[0]
        if isinstance(value, str):
            value = [item.strip() for item in value.split(",") if item.strip()]
        return super().to_python(value)


class CalendarForm(StyledForm):
    code = forms.CharField(label="کد")
    name = forms.CharField(label="نام")
    effective_from = forms.DateField(
        label="شروع اعتبار", widget=forms.DateInput(attrs={"type": "date"})
    )
    effective_to = forms.DateField(
        label="پایان اعتبار",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    working_weekdays = WorkingWeekdaysField(
        label="روزهای کاری",
        choices=(
            (6, "شنبه"),
            (7, "یکشنبه"),
            (1, "دوشنبه"),
            (2, "سه‌شنبه"),
            (3, "چهارشنبه"),
            (4, "پنجشنبه"),
            (5, "جمعه"),
        ),
        coerce=int,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "grid grid-cols-2 gap-2 sm:grid-cols-4"}
        ),
    )


class ShiftForm(StyledForm):
    calendar = forms.ModelChoiceField(
        label="تقویم", queryset=WorkCalendar.objects.none()
    )
    code = forms.CharField(label="کد")
    name = forms.CharField(label="نام")
    starts_at = forms.TimeField(
        label="شروع", widget=forms.TimeInput(attrs={"type": "time"})
    )
    ends_at = forms.TimeField(
        label="پایان", widget=forms.TimeInput(attrs={"type": "time"})
    )
    crosses_midnight = forms.BooleanField(label="عبور از نیمه‌شب", required=False)
    effective_from = forms.DateField(
        label="شروع اعتبار", widget=forms.DateInput(attrs={"type": "date"})
    )

    def __init__(self, *args, organization=None, user=None, **kwargs):
        super().__init__(*args, organization=organization, **kwargs)
        self.fields["calendar"].queryset = WorkCalendar.objects.filter(
            organization=organization, is_active=True
        )


class HolidayForm(StyledForm):
    calendar = forms.ModelChoiceField(
        label="تقویم", queryset=WorkCalendar.objects.none()
    )
    holiday_date = forms.DateField(
        label="تاریخ", widget=forms.DateInput(attrs={"type": "date"})
    )
    name = forms.CharField(label="عنوان")
    reason = forms.CharField(label="دلیل", widget=forms.Textarea(attrs={"rows": 3}))
    source_reference = forms.CharField(label="مرجع منبع", required=False)
    is_working_override = forms.BooleanField(label="روز کاری جایگزین", required=False)

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, organization=organization, **kwargs)
        self.fields["calendar"].queryset = WorkCalendar.objects.filter(
            organization=organization, is_active=True
        )


class ShiftBreakForm(StyledForm):
    shift = forms.ModelChoiceField(
        label="شیفت", queryset=ShiftDefinition.objects.none()
    )
    sequence = forms.IntegerField(label="ترتیب", min_value=1)
    starts_at = forms.TimeField(
        label="شروع", widget=forms.TimeInput(attrs={"type": "time"})
    )
    ends_at = forms.TimeField(
        label="پایان", widget=forms.TimeInput(attrs={"type": "time"})
    )
    ends_next_day = forms.BooleanField(label="پایان در روز بعد", required=False)
    is_paid = forms.BooleanField(label="استراحت پرداخت‌شونده طبق سیاست", required=False)

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, organization=organization, **kwargs)
        self.fields["shift"].queryset = ShiftDefinition.objects.filter(
            organization=organization, is_active=True
        )


class ScopedForm(StyledForm):
    employee = forms.ModelChoiceField(label="کارمند", queryset=Employee.objects.none())
    project = forms.ModelChoiceField(
        label="پروژه", queryset=Project.objects.none(), required=False
    )
    site = forms.ModelChoiceField(
        label="کارگاه", queryset=ProjectSite.objects.none(), required=False
    )

    def __init__(self, *args, organization=None, user=None, **kwargs):
        super().__init__(*args, organization=organization, **kwargs)
        self.fields["employee"].queryset = (
            scoped_employees(organization=organization, user=user)
            if user is not None
            else Employee.objects.filter(
                organization=organization, archived_at__isnull=True
            )
        )
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization, deleted_at__isnull=True
        )
        self.fields["site"].queryset = ProjectSite.objects.filter(
            organization=organization, is_active=True
        )
        if user is not None:
            membership = get_active_membership(user=user, organization=organization)
            self.fields["project"].queryset = scope_queryset(
                self.fields["project"].queryset,
                membership=membership,
                project_lookup="id",
                include_site_parent=True,
            )
            self.fields["site"].queryset = scope_queryset(
                self.fields["site"].queryset,
                membership=membership,
                project_lookup="project_id",
                site_lookup="id",
            )
        dependent_choices(self, workers=True)
        self.order_fields(["project", "site", "employee"])
        for name in ("employee", "project", "site"):
            searchable_choices(self, name, name)

    def clean(self):
        cleaned = super().clean()
        project, site = cleaned.get("project"), cleaned.get("site")
        if site and (not project or site.project_id != project.pk):
            self.add_error("site", "کارگاه باید متعلق به پروژه انتخاب‌شده باشد.")
        return cleaned


class AttendanceForm(ScopedForm):
    calendar = forms.ModelChoiceField(
        label="تقویم", queryset=WorkCalendar.objects.none()
    )
    shift = forms.ModelChoiceField(
        label="شیفت", queryset=ShiftDefinition.objects.none(), required=False
    )
    work_date = forms.DateField(
        label="تاریخ کار", widget=forms.DateInput(attrs={"type": "date"})
    )
    check_in_at = forms.DateTimeField(
        label="ورود", widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )
    check_out_at = forms.DateTimeField(
        label="خروج",
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    source_reference = forms.CharField(label="مرجع ثبت", required=False)

    def __init__(self, *args, organization=None, user=None, **kwargs):
        super().__init__(*args, organization=organization, user=user, **kwargs)
        self.fields["calendar"].queryset = WorkCalendar.objects.filter(
            organization=organization, is_active=True
        )
        self.fields["shift"].queryset = ShiftDefinition.objects.filter(
            organization=organization, is_active=True
        )
        calendar = choice_value(self, "calendar")
        try:
            self.fields["shift"].queryset = (
                self.fields["shift"].queryset.filter(calendar_id=calendar)
                if calendar
                else self.fields["shift"].queryset.none()
            )
        except (ValueError, ValidationError):
            self.fields["shift"].queryset = self.fields["shift"].queryset.none()
        self.fields["shift"].widget.attrs["data-depends-on"] = "calendar"
        for name in ("calendar", "shift"):
            searchable_choices(self, name, name)


class TimeRequestForm(ScopedForm):
    starts_at = forms.DateTimeField(
        label="شروع", widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )
    ends_at = forms.DateTimeField(
        label="پایان", widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )
    reason = forms.CharField(label="دلیل", widget=forms.Textarea(attrs={"rows": 3}))
    policy_reference = forms.CharField(
        label="مرجع سیاست مصوب",
        required=False,
        help_text="برای تأیید الزامی است؛ سامانه مقدار قانونی یا حقوقی استنباط نمی‌کند.",
    )


class LeaveMissionForm(TimeRequestForm):
    kind = forms.ChoiceField(
        label="نوع", choices=(("leave", "مرخصی"), ("mission", "مأموریت"))
    )
    category_code = forms.CharField(label="کد دسته")


class OvertimeForm(TimeRequestForm):
    pass


class TimesheetForm(StyledForm):
    employee = forms.ModelChoiceField(label="کارمند", queryset=Employee.objects.none())
    period_start = forms.DateField(
        label="شروع دوره", widget=forms.DateInput(attrs={"type": "date"})
    )
    period_end = forms.DateField(
        label="پایان دوره", widget=forms.DateInput(attrs={"type": "date"})
    )
    declared_minutes = forms.IntegerField(label="کل دقیقه اعلام‌شده", min_value=1)

    def __init__(self, *args, organization=None, user=None, **kwargs):
        super().__init__(*args, organization=organization, **kwargs)
        self.fields["employee"].queryset = (
            scoped_employees(organization=organization, user=user)
            if user is not None
            else Employee.objects.filter(
                organization=organization, archived_at__isnull=True
            )
        )

        context = FieldContext(
            project=self.initial.get("project"), site=self.initial.get("site")
        )
        self.fields["employee"].queryset = context_employees(
            self.fields["employee"].queryset, context
        )
        searchable_choices(self, "employee", "employee", query=context.query)


class TimesheetEntryForm(StyledForm):
    work_date = forms.DateField(
        label="تاریخ", widget=forms.DateInput(attrs={"type": "date"})
    )
    project = forms.ModelChoiceField(label="پروژه", queryset=Project.objects.none())
    site = forms.ModelChoiceField(
        label="کارگاه", queryset=ProjectSite.objects.none(), required=False
    )
    activity = forms.ModelChoiceField(
        label="فعالیت", queryset=Activity.objects.none(), required=False
    )
    minutes = forms.IntegerField(label="دقیقه", min_value=1)
    note = forms.CharField(label="شرح", required=False)

    def __init__(self, *args, organization=None, user=None, **kwargs):
        super().__init__(*args, organization=organization, **kwargs)
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization, deleted_at__isnull=True
        )
        self.fields["site"].queryset = ProjectSite.objects.filter(
            organization=organization, is_active=True
        )
        self.fields["activity"].queryset = Activity.objects.filter(
            organization=organization, is_active=True
        )
        if user is not None:
            membership = get_active_membership(user=user, organization=organization)
            self.fields["project"].queryset = scope_queryset(
                self.fields["project"].queryset,
                membership=membership,
                project_lookup="id",
                include_site_parent=True,
            )
            self.fields["site"].queryset = scope_queryset(
                self.fields["site"].queryset,
                membership=membership,
                project_lookup="project_id",
                site_lookup="id",
            )
            self.fields["activity"].queryset = scope_queryset(
                self.fields["activity"].queryset,
                membership=membership,
                project_lookup="project_id",
                site_lookup="site_id",
            )

        dependent_choices(self)
        project, site = choice_value(self, "project"), choice_value(self, "site")
        try:
            self.fields["activity"].queryset = (
                self.fields["activity"].queryset.filter(
                    project_id=project, site_id=site or None
                )
                if project
                else self.fields["activity"].queryset.none()
            )
        except (ValueError, ValidationError):
            self.fields["activity"].queryset = self.fields["activity"].queryset.none()
        self.fields["activity"].widget.attrs["data-depends-on"] = "project site"
        for name in ("project", "site", "activity"):
            searchable_choices(self, name, name)

    def clean(self):
        cleaned = super().clean()
        project = cleaned.get("project")
        site = cleaned.get("site")
        activity = cleaned.get("activity")
        if activity and activity.project_id != getattr(project, "pk", None):
            self.add_error("activity", "فعالیت باید متعلق به پروژه انتخاب‌شده باشد.")
        if activity and activity.site_id != getattr(site, "pk", None):
            self.add_error(
                "activity",
                "فعالیت باید با کارگاه انتخاب‌شده سازگار باشد؛ کارگاه فعالیت قابل استنباط نیست.",
            )
        return cleaned


class ImportForm(StyledForm):
    idempotency_key = forms.CharField(label="کلید یکتای درخواست")
    source_label = forms.CharField(label="عنوان منبع")
    rows_json = forms.CharField(
        label="ردیف‌های نرمال‌شده JSON",
        widget=forms.Textarea(attrs={"rows": 10, "dir": "ltr"}),
    )

    def clean_rows_json(self):
        try:
            rows = json.loads(self.cleaned_data["rows_json"])
        except json.JSONDecodeError as exc:
            raise ValidationError("JSON معتبر نیست.") from exc
        if not isinstance(rows, list):
            raise ValidationError("ریشه JSON باید آرایه باشد.")
        return rows


class AttendanceCorrectionForm(StyledForm):
    kind = forms.ChoiceField(
        label="نوع", choices=(("correction", "اصلاح"), ("reversal", "برگشت"))
    )
    reason = forms.CharField(label="دلیل", widget=forms.Textarea(attrs={"rows": 3}))
    replacement_work_date = forms.DateField(
        label="تاریخ کار جایگزین",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    replacement_check_in_at = forms.DateTimeField(
        label="ورود جایگزین",
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    replacement_check_out_at = forms.DateTimeField(
        label="خروج جایگزین",
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("kind") == "correction" and not (
            cleaned.get("replacement_check_in_at")
            and cleaned.get("replacement_check_out_at")
        ):
            raise ValidationError("برای اصلاح، زمان ورود و خروج جایگزین الزامی است.")
        return cleaned

from django import forms
from django.db.models import Q
from django.urls import reverse

from apps.accounts.models import validate_iranian_national_id
from apps.projects.models import Project, ProjectSite
from core.business_choices import SearchChoiceSelect

from .forms import _StyledForm
from .identity_integrity import normalize_national_id
from .models import Employee, WorkTeam


def page_filter_values(request):
    """Default read-only page filters from resolved global context, never persist it."""
    values = request.GET.copy()
    if "page_filters" not in values and not {"project", "site"}.intersection(values):
        project = getattr(request, "active_project", None)
        site = getattr(request, "active_site", None)
        if project is not None:
            values["project"] = str(project.pk)
            if site is not None and site.project_id == project.pk:
                values["site"] = str(site.pk)
    return values


def business_label(record) -> str:
    if hasattr(record, "employee_number"):
        return f"{record.first_name} {record.last_name} · {record.employee_number}"
    label = (
        getattr(record, "name", None) or getattr(record, "title", None) or str(record)
    )
    code = getattr(record, "code", None)
    label = f"{label} · {code}" if code else label
    if getattr(record, "archived_at", None):
        return f"{label} (بایگانی‌شده)"
    if getattr(record, "is_active", True) is False:
        return f"{label} (غیرفعال)"
    return label


def choice_value(form, name):
    """Read bound values before initial values; a cleared parent stays cleared."""
    if form.is_bound:
        return form.data.get(form.add_prefix(name))
    value = form.initial.get(name)
    return getattr(value, "pk", value)


def dependent_choices(form, *, workers=False):
    """Constrain presentation AND validation using the form's authorized masters."""
    from .field_selectors import FieldContext, context_employees

    project = site = None
    for name in ("project", "site"):
        if name not in form.fields:
            continue
        field = form.fields[name]
        if name == "site":
            field.queryset = (
                field.queryset.filter(project=project)
                if project
                else field.queryset.none()
            )
            field.widget.attrs["data-depends-on"] = form.add_prefix("project")
        value = choice_value(form, name)
        try:
            selected = field.queryset.filter(pk=value).first() if value else None
        except (ValueError, forms.ValidationError):
            selected = None
        if name == "project":
            project = selected
        else:
            site = selected
    if workers and "employee" in form.fields:
        field = form.fields["employee"]
        invalid_parent = any(
            choice_value(form, name) and record is None
            for name, record in (("project", project), ("site", site))
            if name in form.fields
        )
        field.queryset = (
            field.queryset.none()
            if invalid_parent
            else context_employees(
                field.queryset, FieldContext(project=project, site=site)
            )
        )
        field.widget.attrs["data-depends-on"] = " ".join(
            form.add_prefix(n) for n in ("project", "site") if n in form.fields
        )


def searchable_choices(
    form, name: str, kind: str, *, query: str = "", business_names_primary=False
) -> None:
    """Bound rendered choices; the full scoped queryset still validates POSTs."""
    field = form.fields[name]
    field.label_from_instance = business_label
    queryset = field.queryset
    records = list(queryset[:40])
    selected = (
        form.data.get(form.add_prefix(name))
        if form.is_bound
        else form.initial.get(name)
    )
    if selected:
        try:
            chosen = queryset.filter(pk=getattr(selected, "pk", selected)).first()
        except (ValueError, forms.ValidationError):
            chosen = None
        if chosen and all(record.pk != chosen.pk for record in records):
            records.insert(0, chosen)
    field.widget = SearchChoiceSelect(
        attrs={
            **field.widget.attrs,
            "data-options-url": reverse("workforce:field_choices", args=[kind])
            + (f"?{query}" if query else ""),
            "data-business-choice": kind,
            **(
                {"data-business-names-primary": "true"}
                if business_names_primary
                else {}
            ),
            "data-placeholder": f"جست‌وجو یا انتخاب {field.label}…",
            "dir": "rtl",
        }
    )
    field.widget.choices = [
        ("", f"انتخاب {field.label}"),
        *((str(record.pk), business_label(record)) for record in records),
    ]


class FieldEmployeeForm(_StyledForm):
    employee_number = forms.CharField(label="شماره پرسنلی", max_length=50)
    first_name = forms.CharField(label="نام", max_length=150)
    last_name = forms.CharField(label="نام خانوادگی", max_length=150)
    national_id = forms.CharField(
        label="کد ملی",
        required=False,
        max_length=10,
        widget=forms.TextInput(
            attrs={"inputmode": "numeric", "dir": "ltr", "autocomplete": "off"}
        ),
    )
    start_date = forms.DateField(label="آغاز همکاری", required=False)
    work_team = forms.ModelChoiceField(
        label="اکیپ / گروه کاری", queryset=WorkTeam.objects.none(), required=False
    )
    phone_number = forms.CharField(label="شماره تماس", max_length=32, required=False)

    def __init__(self, *args, organization, employee=None, person=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["work_team"].queryset = WorkTeam.objects.filter(
            organization=organization
        ).filter(
            Q(is_active=True, archived_at=None)
            | Q(pk=employee.work_team_id if employee else None)
        )
        if employee:
            self.fields["employee_number"].disabled = True
        else:
            self.fields["start_date"].required = True
        if person:
            self.fields.pop("start_date")
        self.employee = employee
        self.person = person
        searchable_choices(self, "work_team", "team")

    def clean_national_id(self):
        value = normalize_national_id(self.cleaned_data.get("national_id"))
        if value:
            validate_iranian_national_id(value)
        return value

    def clean(self):
        cleaned = super().clean()
        if (
            not self.person
            and cleaned.get("national_id")
            and not cleaned.get("start_date")
        ):
            self.add_error(
                "start_date", "برای ثبت هویت، تاریخ آغاز همکاری را وارد کنید."
            )
        return cleaned


class FieldAssignmentForm(_StyledForm):
    project = forms.ModelChoiceField(label="پروژه", queryset=Project.objects.none())
    site = forms.ModelChoiceField(
        label="کارگاه", queryset=ProjectSite.objects.none(), required=False
    )
    role_title = forms.CharField(
        label="مسئولیت در این پروژه/کارگاه",
        max_length=255,
        required=False,
        help_text="اختیاری؛ مسئولیت این تخصیص، مستقل از سمت یا حرفه نیروی کار است.",
    )
    start_date = forms.DateField(label="تاریخ شروع")
    planned_end_date = forms.DateField(
        label="تاریخ پایان برنامه‌ریزی‌شده",
        required=False,
        help_text="اختیاری؛ تخصیص را پایان نمی‌دهد. پایان واقعی با «پایان تخصیص» ثبت می‌شود.",
    )
    notes = forms.CharField(
        label="یادداشت", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args, organization, user, context, **kwargs):
        from apps.organizations.authorization import (
            get_active_membership,
            scope_queryset,
        )

        super().__init__(*args, **kwargs)
        self.organization, self.user = organization, user
        membership = get_active_membership(user=user, organization=organization)
        self.fields["project"].queryset = scope_queryset(
            Project.objects.filter(organization=organization, deleted_at=None),
            membership=membership,
            project_lookup="pk",
            include_site_parent=True,
        )
        self.fields["site"].queryset = scope_queryset(
            ProjectSite.objects.filter(organization=organization, is_active=True),
            membership=membership,
            project_lookup="project_id",
            site_lookup="pk",
        )
        dependent_choices(self)
        for name in ("project", "site"):
            searchable_choices(
                self, name, name, query=context.query, business_names_primary=True
            )

    def clean(self):
        cleaned = super().clean()
        project, site = cleaned.get("project"), cleaned.get("site")
        if site and (not project or site.project_id != project.pk):
            self.add_error("site", "کارگاه باید متعلق به پروژه انتخاب‌شده باشد.")
        start, planned = cleaned.get("start_date"), cleaned.get("planned_end_date")
        if start and planned and planned < start:
            self.add_error(
                "planned_end_date",
                "تاریخ پایان برنامه‌ریزی‌شده نمی‌تواند پیش از تاریخ شروع باشد.",
            )
        return cleaned


class FieldFilterForm(_StyledForm):
    q = forms.CharField(
        label="جست‌وجوی نام یا شماره پرسنلی", required=False, max_length=150
    )
    status = forms.ChoiceField(
        label="وضعیت",
        required=False,
        choices=(
            ("", "همه وضعیت‌ها"),
            ("active", "فعال"),
            ("inactive", "غیرفعال"),
            ("terminated", "خاتمه همکاری"),
        ),
    )
    project = forms.ModelChoiceField(
        label="پروژه", queryset=Project.objects.none(), required=False
    )
    site = forms.ModelChoiceField(
        label="کارگاه", queryset=ProjectSite.objects.none(), required=False
    )

    def __init__(self, *args, organization, user, **kwargs):
        from apps.organizations.authorization import (
            get_active_membership,
            scope_queryset,
        )

        super().__init__(*args, **kwargs)
        membership = get_active_membership(user=user, organization=organization)
        self.fields["project"].queryset = scope_queryset(
            Project.objects.filter(organization=organization, deleted_at=None),
            membership=membership,
            project_lookup="pk",
            include_site_parent=True,
        )
        self.fields["site"].queryset = scope_queryset(
            ProjectSite.objects.filter(organization=organization),
            membership=membership,
            project_lookup="project_id",
            site_lookup="pk",
        )
        dependent_choices(self)
        for name in ("project", "site"):
            searchable_choices(self, name, name)


class AssignmentFilterForm(FieldFilterForm):
    employee = forms.ModelChoiceField(
        label="نیروی کار", queryset=Employee.objects.none(), required=False
    )
    role = forms.CharField(label="مسئولیت", required=False)
    start_date_from = forms.DateField(label="تاریخ شروع از", required=False)
    start_date_to = forms.DateField(label="تاریخ شروع تا", required=False)

    def __init__(self, *args, organization, user, **kwargs):
        from .field_selectors import scoped_employees

        super().__init__(*args, organization=organization, user=user, **kwargs)
        self.fields.pop("q")
        self.fields["status"].choices = (
            ("", "همه وضعیت‌ها"),
            ("active", "فعال"),
            ("completed", "پایان‌یافته"),
            ("cancelled", "لغوشده"),
        )
        self.fields["employee"].queryset = scoped_employees(
            organization=organization, user=user, assigned_only=True
        )
        self.fields["employee"].widget.attrs["data-choice-purpose"] = (
            "assignment_filter"
        )
        dependent_choices(self, workers=True)
        searchable_choices(self, "employee", "employee")

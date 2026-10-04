from django import forms

from apps.accounts.models import User
from apps.documents.models import (
    DocumentCategory,
    DocumentConfidentiality,
    DocumentType,
)
from apps.organizations.models import MembershipStatus, Organization
from apps.projects.models import Project, ProjectSite
from apps.workforce.models import (
    Competency,
    Department,
    Employee,
    Position,
    QualificationKind,
    Skill,
    TrainingOutcome,
    TrainingRequirement,
    WorkTeam,
)
from core.forms import JalaliDateMixin
from core.identifiers import canonicalize_upper_identifier


class _StyledForm(JalaliDateMixin, forms.Form):
    """Apply the shared ERP form appearance to workforce forms."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        field_class = (
            "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 "
            "text-slate-900 outline-none focus:border-blue-500 focus:ring-2 "
            "focus:ring-blue-100"
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", field_class)


class DepartmentForm(_StyledForm):
    code = forms.CharField(label="کد واحد سازمانی", max_length=50)
    name = forms.CharField(label="نام واحد سازمانی", max_length=255)
    parent = forms.ModelChoiceField(
        label="واحد سازمانی والد", queryset=Department.objects.none(), required=False
    )
    description = forms.CharField(
        label="شرح", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        exclude_department = kwargs.pop("exclude_department", None)
        super().__init__(*args, **kwargs)
        parents = Department.objects.filter(
            organization=organization, archived_at__isnull=True, is_active=True
        )
        if exclude_department is not None:
            parents = parents.exclude(pk=exclude_department.pk)
        self.fields["parent"].queryset = parents

    def clean_code(self) -> str:
        return canonicalize_upper_identifier(self.cleaned_data["code"])


class PositionForm(_StyledForm):
    code = forms.CharField(label="کد سمت", max_length=50)
    title = forms.CharField(label="عنوان سمت", max_length=255)
    department = forms.ModelChoiceField(
        label="واحد سازمانی", queryset=Department.objects.none(), required=False
    )
    parent_position = forms.ModelChoiceField(
        label="سمت بالادست", queryset=Position.objects.none(), required=False
    )
    description = forms.CharField(
        label="شرح", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    is_single_holder = forms.BooleanField(
        label="سمت تک‌متصدی",
        required=False,
        help_text="برای سمت‌هایی مانند مدیرعامل که فقط یک متصدی فعال دارند.",
        widget=forms.CheckboxInput(attrs={"class": "size-4 rounded border-slate-300"}),
    )

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        exclude_position = kwargs.pop("exclude_position", None)
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.objects.filter(
            organization=organization, archived_at__isnull=True, is_active=True
        )
        parents = Position.objects.filter(
            organization=organization, archived_at__isnull=True, is_active=True
        )
        if exclude_position is not None:
            parents = parents.exclude(pk=exclude_position.pk)
        self.fields["parent_position"].queryset = parents

    def clean_code(self) -> str:
        return canonicalize_upper_identifier(self.cleaned_data["code"])


class WorkTeamForm(_StyledForm):
    code = forms.CharField(label="کد گروه کاری", max_length=50)
    name = forms.CharField(label="نام گروه کاری", max_length=255)
    department = forms.ModelChoiceField(
        label="واحد سازمانی", queryset=Department.objects.none(), required=False
    )
    lead = forms.ModelChoiceField(
        label="سرپرست گروه", queryset=Employee.objects.none(), required=False
    )
    description = forms.CharField(
        label="شرح", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.objects.filter(
            organization=organization, archived_at__isnull=True, is_active=True
        )
        self.fields["lead"].queryset = Employee.objects.filter(
            organization=organization, archived_at__isnull=True, status="active"
        )

    def clean_code(self) -> str:
        return canonicalize_upper_identifier(self.cleaned_data["code"])


class MemberUserChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, user: User) -> str:
        full_name = user.get_full_name().strip() or user.username
        national_id = f"***{user.national_id[-4:]}" if user.national_id else "ثبت‌نشده"
        return f"{full_name} ({user.username}) · کد ملی {national_id}"


class EmployeeProfileImageInput(forms.ClearableFileInput):
    """Render employee image controls without exposing its storage path."""

    template_name = "widgets/profile_image_input.html"
    clear_checkbox_label = "حذف عکس فعلی"


class WorkforceCatalogueForm(_StyledForm):
    code = forms.CharField(label="کد", max_length=50)
    name = forms.CharField(label="نام", max_length=255)
    description = forms.CharField(label="شرح", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def clean_code(self) -> str:
        return canonicalize_upper_identifier(self.cleaned_data["code"])


class EmployeeSkillRecordForm(_StyledForm):
    employee = forms.ModelChoiceField(label="کارمند", queryset=Employee.objects.none())
    skill = forms.ModelChoiceField(label="مهارت", queryset=Skill.objects.none())
    competency = forms.ModelChoiceField(label="شایستگی مرتبط", queryset=Competency.objects.none(), required=False)
    proficiency_level = forms.IntegerField(label="سطح مهارت", min_value=1, max_value=5)
    effective_from = forms.DateField(label="مؤثر از", widget=forms.DateInput(attrs={"type": "date"}))
    effective_to = forms.DateField(label="مؤثر تا", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    notes = forms.CharField(label="یادداشت", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args: object, organization: Organization, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = Employee.objects.filter(organization=organization, archived_at__isnull=True)
        self.fields["skill"].queryset = Skill.objects.filter(organization=organization, is_active=True, archived_at__isnull=True)
        self.fields["competency"].queryset = Competency.objects.filter(organization=organization, is_active=True, archived_at__isnull=True)


class EmployeeQualificationForm(_StyledForm):
    employee = forms.ModelChoiceField(label="کارمند", queryset=Employee.objects.none())
    kind = forms.ChoiceField(label="نوع", choices=QualificationKind.choices)
    title = forms.CharField(label="عنوان", max_length=255)
    issuer = forms.CharField(label="مرجع صادرکننده", max_length=255, required=False)
    reference_number = forms.CharField(label="شماره مرجع", max_length=100, required=False)
    issued_on = forms.DateField(label="تاریخ صدور", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    valid_until = forms.DateField(label="تاریخ اعتبار", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args: object, organization: Organization, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = Employee.objects.filter(organization=organization, archived_at__isnull=True)


class TrainingRequirementForm(WorkforceCatalogueForm):
    competency = forms.ModelChoiceField(label="شایستگی مرتبط", queryset=Competency.objects.none(), required=False)
    position = forms.ModelChoiceField(label="سمت مرتبط", queryset=Position.objects.none(), required=False)
    project = forms.ModelChoiceField(label="پروژه مرتبط", queryset=Project.objects.none(), required=False)

    def __init__(self, *args: object, organization: Organization, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["competency"].queryset = Competency.objects.filter(organization=organization, is_active=True, archived_at__isnull=True)
        self.fields["position"].queryset = Position.objects.filter(organization=organization, is_active=True, archived_at__isnull=True)
        self.fields["project"].queryset = Project.objects.filter(organization=organization, deleted_at__isnull=True)


class EmployeeTrainingRecordForm(_StyledForm):
    employee = forms.ModelChoiceField(label="کارمند", queryset=Employee.objects.none())
    requirement = forms.ModelChoiceField(label="الزام آموزشی", queryset=TrainingRequirement.objects.none())
    occurred_on = forms.DateField(label="تاریخ", widget=forms.DateInput(attrs={"type": "date"}))
    outcome = forms.ChoiceField(label="نتیجه", choices=TrainingOutcome.choices)
    notes = forms.CharField(label="یادداشت", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args: object, organization: Organization, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = Employee.objects.filter(organization=organization, archived_at__isnull=True)
        self.fields["requirement"].queryset = TrainingRequirement.objects.filter(organization=organization, is_active=True, archived_at__isnull=True)


class PerformanceEvaluationForm(_StyledForm):
    employee = forms.ModelChoiceField(label="کارمند", queryset=Employee.objects.none())
    period_start = forms.DateField(label="شروع دوره", widget=forms.DateInput(attrs={"type": "date"}))
    period_end = forms.DateField(label="پایان دوره", widget=forms.DateInput(attrs={"type": "date"}))
    criteria_snapshot = forms.JSONField(label="شواهد معیارها", widget=forms.Textarea(attrs={"rows": 5}), help_text="یک شیء JSON غیرخالی وارد کنید.")
    result_summary = forms.CharField(label="نتیجه", widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args: object, organization: Organization, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = Employee.objects.filter(organization=organization, archived_at__isnull=True)


class LaborRateVersionForm(_StyledForm):
    employee = forms.ModelChoiceField(label="کارمند", queryset=Employee.objects.none())
    component_name = forms.CharField(label="جزء هزینه", max_length=255)
    unit_label = forms.CharField(label="واحد", max_length=50)
    currency_code = forms.CharField(label="کد ارز", max_length=3)
    rate_amount = forms.DecimalField(label="نرخ", max_digits=18, decimal_places=2, min_value=0)
    effective_from = forms.DateField(label="مؤثر از", widget=forms.DateInput(attrs={"type": "date"}))
    effective_to = forms.DateField(label="مؤثر تا", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    notes = forms.CharField(label="یادداشت", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args: object, organization: Organization, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = Employee.objects.filter(organization=organization, archived_at__isnull=True)

    def clean_currency_code(self) -> str:
        return self.cleaned_data["currency_code"].strip().upper()


class EmployeeForm(_StyledForm):
    WITHOUT_ACCOUNT = "without_account"
    EXISTING_ACCOUNT = "existing_account"

    source_type = forms.ChoiceField(
        label="روش ثبت کارمند",
        choices=(
            (WITHOUT_ACCOUNT, "بدون حساب کاربری"),
            (EXISTING_ACCOUNT, "از حساب کاربری موجود شرکت"),
        ),
        initial=WITHOUT_ACCOUNT,
        widget=forms.RadioSelect,
    )
    user = MemberUserChoiceField(
        label="حساب کاربری موجود شرکت",
        queryset=User.objects.none(),
        required=False,
        help_text="فقط حساب‌های فعال همین شرکت که هنوز پرونده کارمندی ندارند نمایش داده می‌شوند.",
    )
    employee_number = forms.CharField(label="شماره پرسنلی", max_length=50)
    first_name = forms.CharField(label="نام", max_length=150, required=False)
    last_name = forms.CharField(label="نام خانوادگی", max_length=150, required=False)
    email = forms.EmailField(label="ایمیل", required=False)
    phone_number = forms.CharField(label="شماره تلفن", max_length=32, required=False)
    department = forms.ModelChoiceField(
        label="واحد سازمانی", queryset=Department.objects.none(), required=False
    )
    position = forms.ModelChoiceField(
        label="سمت شغلی", queryset=Position.objects.none(), required=False
    )
    work_team = forms.ModelChoiceField(
        label="گروه کاری", queryset=WorkTeam.objects.none(), required=False
    )
    hire_date = forms.DateField(
        label="تاریخ استخدام",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(
        self,
        *args: object,
        organization: Organization,
        can_link_account: bool,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        if can_link_account:
            self.fields["user"].queryset = (
                User.objects.filter(
                    is_active=True,
                    organization_memberships__organization=organization,
                    organization_memberships__status=MembershipStatus.ACTIVE,
                )
                .exclude(employee_profiles__organization=organization)
                .distinct()
                .order_by("last_name", "first_name", "username")
            )
        else:
            self.fields["source_type"].choices = (
                (self.WITHOUT_ACCOUNT, "بدون حساب کاربری"),
            )
        self.fields["user"].empty_label = "حساب کاربری را انتخاب کنید"
        self.fields["source_type"].widget.attrs["class"] = (
            "size-4 shrink-0 border-slate-300 text-blue-600 focus:ring-blue-500"
        )
        self.fields["department"].queryset = Department.objects.filter(
            organization=organization, archived_at__isnull=True, is_active=True
        )
        positions = Position.objects.filter(
            organization=organization, archived_at__isnull=True, is_active=True
        )
        department_id = (
            self.data.get(self.add_prefix("department")) if self.is_bound else None
        )
        if department_id:
            positions = positions.filter(department_id=department_id)
        self.fields["position"].queryset = positions
        self.fields["work_team"].queryset = WorkTeam.objects.filter(
            organization=organization, archived_at__isnull=True, is_active=True
        )

    def clean_employee_number(self) -> str:
        return canonicalize_upper_identifier(self.cleaned_data["employee_number"])

    def clean(self) -> dict[str, object]:
        cleaned = super().clean()
        source_type = cleaned.get("source_type")
        user = cleaned.get("user")
        if source_type == self.EXISTING_ACCOUNT:
            if user is None:
                self.add_error("user", "انتخاب حساب کاربری الزامی است.")
            elif not user.first_name.strip() or not user.last_name.strip():
                self.add_error(
                    "user",
                    "نام و نام خانوادگی این حساب کامل نیست؛ ابتدا اطلاعات حساب را تکمیل کنید.",
                )
            cleaned["first_name"] = ""
            cleaned["last_name"] = ""
            cleaned["email"] = ""
            cleaned["phone_number"] = ""
        elif source_type == self.WITHOUT_ACCOUNT:
            cleaned["user"] = None
            if not str(cleaned.get("first_name") or "").strip():
                self.add_error("first_name", "وارد کردن نام الزامی است.")
            if not str(cleaned.get("last_name") or "").strip():
                self.add_error("last_name", "وارد کردن نام خانوادگی الزامی است.")
        return cleaned


class EmployeeAccountLinkForm(_StyledForm):
    user = MemberUserChoiceField(
        label="حساب عضو شرکت",
        queryset=User.objects.none(),
        help_text="فقط اعضای همین شرکت که به کارمند دیگری متصل نیستند نمایش داده می‌شوند.",
    )

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = (
            User.objects.filter(
                is_active=True,
                organization_memberships__organization=organization,
                organization_memberships__status=MembershipStatus.ACTIVE,
            )
            .exclude(employee_profiles__organization=organization)
            .distinct()
            .order_by("last_name", "first_name", "username")
        )


class EmployeeProfileImageForm(forms.ModelForm):
    """Upload or clear the organization-owned employee profile image."""

    class Meta:
        model = Employee
        fields = ["profile_image"]  # noqa: RUF012
        widgets = {  # noqa: RUF012
            "profile_image": EmployeeProfileImageInput(
                attrs={
                    "class": (
                        "block w-full rounded-lg border border-slate-300 bg-white "
                        "px-3 py-2.5 text-sm text-slate-700"
                    ),
                    "accept": "image/png,image/jpeg,image/webp",
                }
            )
        }


class EmployeeAssignmentForm(_StyledForm):
    employee = forms.ModelChoiceField(label="کارمند", queryset=Employee.objects.none())
    project = forms.ModelChoiceField(label="پروژه", queryset=Project.objects.none())
    site = forms.ModelChoiceField(
        label="کارگاه", queryset=ProjectSite.objects.none(), required=False
    )
    role_title = forms.CharField(
        label="مسئولیت در پروژه", max_length=255, required=False
    )
    start_date = forms.DateField(
        label="تاریخ شروع تخصیص", widget=forms.DateInput(attrs={"type": "date"})
    )
    notes = forms.CharField(
        label="یادداشت", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = Employee.objects.filter(
            organization=organization, archived_at__isnull=True, status="active"
        )
        self.fields["project"].queryset = Project.objects.filter(
            organization=organization, deleted_at__isnull=True
        )
        project_id = (
            self.data.get(self.add_prefix("project")) if self.is_bound else None
        )
        self.fields["site"].queryset = ProjectSite.objects.filter(
            organization=organization, project_id=project_id, is_active=True
        )
        self.fields["site"].widget.attrs["disabled"] = not bool(project_id)


class EmployeePositionAssignmentForm(_StyledForm):
    position = forms.ModelChoiceField(
        label="سمت شغلی", queryset=Position.objects.none()
    )
    start_date = forms.DateField(
        label="تاریخ شروع", widget=forms.DateInput(attrs={"type": "date"})
    )
    is_primary = forms.BooleanField(
        label="سمت اصلی",
        required=False,
        help_text="سمت اصلی در پرونده و فهرست کارکنان نمایش داده می‌شود.",
        widget=forms.CheckboxInput(attrs={"class": "size-4 rounded border-slate-300"}),
    )
    notes = forms.CharField(
        label="یادداشت", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["position"].queryset = Position.objects.filter(
            organization=organization,
            archived_at__isnull=True,
            is_active=True,
        ).select_related("department")


class EmployeePositionEndForm(_StyledForm):
    end_date = forms.DateField(
        label="تاریخ پایان", widget=forms.DateInput(attrs={"type": "date"})
    )


class StatusTransitionForm(_StyledForm):
    target_status = forms.ChoiceField(label="وضعیت جدید")
    effective_date = forms.DateField(
        label="تاریخ اجرا",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(
        self, *args: object, choices: list[tuple[str, str]], **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["target_status"].choices = choices


class AssignmentStatusTransitionForm(_StyledForm):
    target_status = forms.ChoiceField(label="وضعیت جدید")
    end_date = forms.DateField(
        label="تاریخ پایان", widget=forms.DateInput(attrs={"type": "date"})
    )

    def __init__(
        self, *args: object, choices: list[tuple[str, str]], **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["target_status"].choices = choices


class WorkforceEvidenceUploadForm(_StyledForm):
    """First DMS version for an immutable Workforce evidence record."""

    document_type = forms.ChoiceField(label="نوع سند", choices=DocumentType.choices)
    title = forms.CharField(label="عنوان سند", max_length=255)
    category = forms.ModelChoiceField(
        label="دسته‌بندی", queryset=DocumentCategory.objects.none(), required=False
    )
    confidentiality = forms.ChoiceField(
        label="سطح محرمانگی",
        choices=DocumentConfidentiality.choices,
        initial=DocumentConfidentiality.INTERNAL,
    )
    access_expires_at = forms.DateTimeField(
        label="پایان دسترسی",
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    reference = forms.CharField(label="شماره مرجع", max_length=120, required=False)
    description = forms.CharField(
        label="توضیحات", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    file = forms.FileField(label="فایل نسخه اول")

    def __init__(
        self, *args: object, organization: Organization, **kwargs: object
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = DocumentCategory.objects.filter(
            organization=organization, archived_at__isnull=True
        ).order_by("name")


class QualificationRevocationForm(_StyledForm):
    occurred_on = forms.DateField(
        label="تاریخ ابطال",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    reason = forms.CharField(
        label="علت ابطال",
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

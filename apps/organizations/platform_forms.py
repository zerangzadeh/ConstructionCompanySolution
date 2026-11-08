from django import forms

from apps.organizations.forms import OrganizationSettingsForm
from apps.organizations.models import OrganizationStatus
from apps.organizations.platform_companies import PLATFORM_READ_ONLY_SETTINGS


class CompanySearchForm(forms.Form):
    q = forms.CharField(label="نام یا کد شرکت", required=False, max_length=100)
    status = forms.ChoiceField(
        label="وضعیت",
        required=False,
        choices=(("", "همه وضعیت‌ها"), *OrganizationStatus.choices),
    )


class ActivitySearchForm(forms.Form):
    q = forms.CharField(
        label="نام کاربری یا نوع رویداد", required=False, max_length=100
    )


class CompanyChangeForm(forms.Form):
    expected_updated_at = forms.DateTimeField(widget=forms.HiddenInput)
    reason = forms.CharField(
        label="دلیل عملیات", max_length=1000, widget=forms.Textarea(attrs={"rows": 3})
    )


class CompanyStatusForm(CompanyChangeForm):
    target_status = forms.ChoiceField(
        label="وضعیت جدید",
        choices=(
            (OrganizationStatus.SUSPENDED, "تعلیق شرکت"),
            (OrganizationStatus.ACTIVE, "فعال‌سازی مجدد"),
        ),
        widget=forms.HiddenInput,
    )


class PlatformCompanySettingsForm(OrganizationSettingsForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in PLATFORM_READ_ONLY_SETTINGS:
            self.fields[field].disabled = True

    class Meta(OrganizationSettingsForm.Meta):
        fields = tuple(
            field for field in OrganizationSettingsForm.Meta.fields if field != "logo"
        )

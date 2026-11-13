"""Organization-local input and presentation for tenant-owned timestamps."""

from zoneinfo import ZoneInfo

from django import forms
from django.core.exceptions import ValidationError
from django.shortcuts import render
from django.utils import timezone


class OrganizationDateTimeField(forms.DateTimeField):
    time_zone: ZoneInfo | None = None

    def to_python(self, value):
        if value not in self.empty_values and self.time_zone is None:
            raise ValidationError("منطقه زمانی شرکت برای ثبت زمان مشخص نشده است.")
        with timezone.override(self.time_zone):
            return super().to_python(value)

    def prepare_value(self, value):
        with timezone.override(self.time_zone):
            return super().prepare_value(value)


def bind_organization_time(form, organization) -> None:
    name = getattr(getattr(organization, "settings", None), "timezone", None)
    zone = ZoneInfo(name) if name else None
    for field in form.fields.values():
        if isinstance(field, OrganizationDateTimeField):
            field.time_zone = zone


def render_in_organization_time(request, *args, organization=None, **kwargs):
    if organization is None:
        organization = getattr(request, "organization", None)
    name = getattr(getattr(organization, "settings", None), "timezone", None)
    with timezone.override(ZoneInfo(name) if name else None):
        return render(request, *args, **kwargs)

from typing import Any

from django import forms

from apps.documents.models import PhotoSource
from apps.projects.models import ProjectSite
from core.forms import JalaliDateMixin


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault(
            "widget", MultipleImageInput(attrs={"accept": "image/jpeg,image/png"})
        )
        super().__init__(*args, **kwargs)

    def clean(self, data: Any, initial: Any = None) -> list[Any]:
        clean_one = super().clean
        if not data:
            return []
        return [clean_one(item, initial) for item in data]


class PhotoUploadForm(JalaliDateMixin, forms.Form):
    source = forms.ChoiceField(choices=PhotoSource.choices, widget=forms.HiddenInput)
    title = forms.CharField(label="عنوان / توضیح کوتاه", max_length=255, required=False)
    description = forms.CharField(
        label="توضیحات", widget=forms.Textarea, required=False
    )
    site = forms.ModelChoiceField(
        label="کارگاه",
        queryset=ProjectSite.objects.none(),
        required=False,
        empty_label="بدون کارگاه مشخص",
    )
    captured_at = forms.DateTimeField(
        label="زمان عکس (اختیاری)",
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    camera_file = forms.FileField(
        label="گرفتن عکس",
        required=False,
        widget=forms.ClearableFileInput(
            attrs={"accept": "image/*", "capture": "environment"}
        ),
    )
    files = MultipleImageField(label="انتخاب از دستگاه", required=False)

    def __init__(self, *args: Any, sites: Any = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["site"].queryset = (
            sites if sites is not None else ProjectSite.objects.none()
        )

    def clean(self) -> dict[str, Any]:
        data = super().clean()
        source = data.get("source")
        camera_file = data.get("camera_file")
        files = data.get("files") or []
        if source == PhotoSource.CAMERA:
            if not camera_file:
                self.add_error("camera_file", "یک تصویر از دوربین انتخاب کنید.")
            if files:
                self.add_error("files", "در حالت دوربین، فقط تصویر ثبت‌شده ارسال می‌شود.")
        elif source == PhotoSource.UPLOAD:
            if not files:
                self.add_error("files", "حداقل یک تصویر انتخاب کنید.")
            if camera_file:
                self.add_error(
                    "camera_file",
                    "در حالت بارگذاری، از گزینه انتخاب از دستگاه استفاده کنید.",
                )
        return data

    def uploads(self) -> list[Any]:
        if self.cleaned_data["source"] == PhotoSource.CAMERA:
            return [self.cleaned_data["camera_file"]]
        return self.cleaned_data["files"]

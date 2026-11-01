"""Presentation only over already-authorized, filtered progress-list results."""

from django import forms
from django.core.paginator import Page
from django.http import HttpRequest

from core.list_filters import build_filter_bar, contextual_list_filters


def progress_filter_bar(request: HttpRequest, page: Page) -> dict:
    form = forms.Form(request.GET)
    form.fields["q"] = forms.CharField(
        label="جست‌وجوی کارکرد",
        required=False,
        widget=forms.TextInput(
            attrs={
                "type": "search",
                "class": "erp-input w-full",
                "placeholder": "جست‌وجوی قرارداد یا پروژه…",
            }
        ),
    )
    form.is_valid()
    return build_filter_bar(
        request,
        form=form,
        quick_fields=(),
        context=contextual_list_filters(request, keys=("contract",))["filter_context"],
        result_count=page.paginator.count,
        result_label="کارکرد",
    )

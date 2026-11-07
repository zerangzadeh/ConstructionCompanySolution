"""Presentation adapters for existing operational workspace contracts only."""

from django import forms, template

from core.list_filters import build_filter_bar

register = template.Library()


@register.simple_tag(takes_context=True)
def workflow_filter_bar(context):
    """Reuse scoped choices; do not query, filter or authorize work items here."""
    labels = {
        "workflow": "گردش‌کار",
        "project": "پروژه",
        "assignment": "وضعیت تخصیص",
        "site": "کارگاه",
        "position": "سمت",
        "priority": "اولویت",
        "due": "مهلت",
    }
    all_labels = {
        "workflow": "همه گردش‌کارها",
        "project": "همه پروژه‌ها",
        "assignment": "همه وضعیت‌های تخصیص",
        "site": "همه کارگاه‌ها",
        "position": "همه سمت‌ها",
        "priority": "همه اولویت‌ها",
        "due": "همه مهلت‌ها",
    }
    form = forms.Form(context["request"].GET)
    for name, label in labels.items():
        form.fields[name] = forms.ChoiceField(
            label=label,
            required=False,
            choices=[("", all_labels[name]), *context["filter_choices"].get(name, ())],
            widget=forms.Select(attrs={"class": "erp-input"}),
        )
    form.is_valid()
    routing = context["request"].GET.get("routing")
    return build_filter_bar(
        context["request"],
        form=form,
        search_field="workflow",
        quick_fields=("project", "assignment"),
        secondary_fields=("site", "position", "priority", "due"),
        context={"routing": routing} if routing == "role_permission" else {},
        result_count=context["page_obj"].paginator.count,
        result_label="کار",
    )

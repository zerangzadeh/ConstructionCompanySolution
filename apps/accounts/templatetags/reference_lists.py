"""Present existing estimate/site GET controls in the shared list design.

No queries, filtering or authorization run here; views retain those contracts.
"""

from django import forms, template

from core.list_filters import build_filter_bar

register = template.Library()

PROFILES = {
    "estimates": {
        "search": "title",
        "placeholder": "جست‌وجو در عنوان برآورد…",
        "result_label": "برآورد",
        "default_sort": "title",
        "sorts": (
            ("number", "شماره برآورد"),
            ("title", "عنوان برآورد"),
            ("project", "پروژه / فاز"),
            ("status", "وضعیت"),
        ),
    },
    "sites": {
        "search": "site",
        "placeholder": "جست‌وجوی کد، نام یا نشانی کارگاه…",
        "result_label": "کارگاه",
        "default_sort": "project",
        "sorts": (
            ("code", "کد کارگاه"),
            ("name", "نام کارگاه"),
            ("project", "پروژه"),
            ("status", "وضعیت"),
            ("address", "نشانی"),
        ),
    },
}


@register.simple_tag(takes_context=True)
def reference_list_state(context, profile):
    """Adapt only the filter definitions and authorized page supplied by a view."""
    config = PROFILES[profile]
    request = context["request"]
    form = forms.Form(request.GET)
    for column in context["filters"]:
        if column is None:
            continue
        name = column["name"]
        attrs = {"class": "erp-input w-full"}
        if column["kind"] == "select":
            field = forms.ChoiceField(
                label=column["label"],
                required=False,
                choices=[("", "همه وضعیت‌ها"), *column["choices"]],
                widget=forms.Select(attrs=attrs),
                error_messages={"invalid_choice": "گزینه معتبر را انتخاب کنید."},
            )
        else:
            attrs["placeholder"] = column["label"]
            field = forms.CharField(
                label=column["label"],
                required=False,
                widget=forms.TextInput(attrs=attrs),
            )
        form.fields[name] = field
    search = config["search"]
    form.fields[search].widget = forms.TextInput(
        attrs={
            "type": "search",
            "class": "erp-input w-full",
            "placeholder": config["placeholder"],
        }
    )
    form.is_valid()
    bar = build_filter_bar(
        request,
        form=form,
        search_field=search,
        quick_fields=tuple(name for name in form.fields if name != search),
        context=context.get("filter_context", {}),
        result_count=context["page_obj"].paginator.count,
        result_label=config["result_label"],
    )
    labels = dict(config["sorts"])
    key = request.GET.get("sort", "").strip()
    # The existing site view also accepts the legacy 'active' sort alias.
    if profile == "sites" and key == "active":
        key = "status"
    explicit_sort = key in labels
    if not explicit_sort:
        key = config["default_sort"]
    return {
        "bar": bar,
        "sorts": [{"key": name, "label": label} for name, label in config["sorts"]],
        "sort": {
            "key": key,
            "label": labels[key],
            "descending": explicit_sort
            and request.GET.get("direction", "asc").strip().lower() == "desc",
        },
    }

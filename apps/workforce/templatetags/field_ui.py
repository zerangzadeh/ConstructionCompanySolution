"""Opt-in MVP-02 presentation; never used by Project pages."""

from django import template

register = template.Library()


@register.simple_tag
def field_form_sections(form):
    groups = (
        (
            "identity",
            "مشخصات اصلی",
            "document",
            {
                "employee_number",
                "first_name",
                "last_name",
                "national_id",
                "phone_number",
                "code",
                "name",
            },
        ),
        (
            "scope",
            "نیرو و محل فعالیت",
            "layers",
            {
                "employee",
                "project",
                "site",
                "work_team",
                "department",
                "lead",
                "role_title",
                "assign_here",
                "activity",
            },
        ),
        (
            "time",
            "تاریخ و زمان",
            "calendar",
            {
                "start_date",
                "planned_end_date",
                "end_date",
                "work_date",
                "check_in_at",
                "check_out_at",
                "starts_at",
                "ends_at",
                "period_start",
                "period_end",
                "minutes",
                "calendar",
                "shift",
                "effective_from",
                "effective_to",
                "holiday_date",
                "crosses_midnight",
                "ends_next_day",
                "replacement_work_date",
                "replacement_check_in_at",
                "replacement_check_out_at",
            },
        ),
        ("details", "جزئیات و توضیحات", "notes", set()),
    )
    remaining = list(form.visible_fields())
    result = []
    for key, title, icon, names in groups:
        fields = [field for field in remaining if not names or field.name in names]
        if fields:
            result.append(
                {"id": f"field-{key}", "title": title, "icon": icon, "fields": fields}
            )
            remaining = [field for field in remaining if field not in fields]
    return result

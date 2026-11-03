"""Template adapters for the single product surface authority."""

from django import template
from django.urls import reverse

from core.product_surface import route_exposed, url_exposed

register = template.Library()
register.filter("surface_exposed", route_exposed)
register.filter("surface_url_exposed", url_exposed)


@register.simple_tag
def breadcrumb_trail(current_label, *parents):
    """Assemble presentation labels and source-validated URLs for the shared renderer."""
    if len(parents) % 2:
        raise template.TemplateSyntaxError(
            "Breadcrumb parents require label/URL pairs."
        )
    return [
        {"label": "خانه", "url": reverse("home")},
        *(
            {"label": parents[i], "url": parents[i + 1]}
            for i in range(0, len(parents), 2)
        ),
        {"label": current_label},
    ]


@register.filter
def surface_link_active(link, view_name):
    return link.is_active_for(view_name)


@register.simple_tag
def module_selector_links(groups, view_name, current_path):
    """Present only already-authorized shell destinations; grant nothing.

    Canonical active-route aliases win. For descendants without an alias,
    highlight the longest existing destination path. No new destination,
    namespace map, permission or exposure policy is created.
    """
    items = [
        {"link": link, "url": reverse(link.route), "active": False}
        for group in groups
        for link in group.links
    ]
    active = next(
        (item for item in items if item["link"].is_active_for(view_name)), None
    )
    if active is None:
        candidates = [
            item
            for item in items
            if current_path == item["url"]
            or current_path.startswith(item["url"].rstrip("/") + "/")
        ]
        active = max(candidates, key=lambda item: len(item["url"]), default=None)
    if active is not None:
        active["active"] = True
    return items


# Presentation families only. Membership, exposure, permissions, URLs and active
# routes all come from module_selector_links; these families grant no access.
MODULE_CARD_PRESENTATION = (
    (
        "projects",
        "پروژه و کارگاه",
        "مدیریت پروژه‌ها و کارگاه‌ها",
        "projects",
        ("projects",),
    ),
    (
        "contracts",
        "پیمان و قرارداد",
        "قراردادها و مدیریت مالی",
        "document",
        ("contracts", "estimates", "billing"),
    ),
    (
        "procurement",
        "تدارکات و خرید",
        "درخواست، استعلام و سفارش",
        "cart",
        ("procurement",),
    ),
    (
        "inventory",
        "انبار و مصالح",
        "مصالح، کالا و موجودی",
        "boxes",
        ("inventory", "materials"),
    ),
    (
        "operations",
        "عملیات کارگاه",
        "نیروی کار، حضور و کارکرد",
        "people",
        ("workforce", "timekeeping", "daily_reports", "equipment", "expenses"),
    ),
    (
        "quality",
        "ایمنی و کیفیت",
        "ایمنی و کنترل کیفیت",
        "shield",
        ("safety", "quality"),
    ),
    ("documents", "اسناد", "مدارک و مستندات", "folder", ("documents",)),
    ("reporting", "گزارش‌ها", "گزارش‌ها و تحلیل‌ها", "chart", ("reporting",)),
    (
        "workflows",
        "کارتابل و گردش‌کار",
        "وظایف و درخواست‌های شما",
        "document",
        ("workflows",),
    ),
    ("parties", "طرف‌های تجاری", "اطلاعات طرف‌های همکاری", "people", ("parties",)),
    (
        "settings",
        "تنظیمات و دسترسی",
        "حساب کاربری و مدیریت شرکت",
        "grid",
        ("accounts", "organizations", "audit"),
    ),
)


@register.simple_tag
def module_selector_cards(groups, view_name, current_path):
    """Group filtered shell links, preferring an existing active destination.

    All underlying destinations remain in the unchanged sidebar. Unknown
    destinations retain their own card instead of being silently dropped.
    """
    items = module_selector_links(groups, view_name, current_path)
    cards = []
    assigned = set()
    for key, title, description, icon, namespaces in MODULE_CARD_PRESENTATION:
        members = [
            item for item in items if item["link"].route.partition(":")[0] in namespaces
        ]
        if not members:
            continue
        members.sort(
            key=lambda item: namespaces.index(item["link"].route.partition(":")[0])
        )
        destination = next((item for item in members if item["active"]), members[0])
        cards.append(
            {
                **destination,
                "key": key,
                "title": title,
                "description": description,
                "icon": icon,
            }
        )
        assigned.update(item["link"].route for item in members)
    for item in items:
        if item["link"].route not in assigned:
            cards.append(
                {
                    **item,
                    "key": item["link"].route,
                    "title": item["link"].label,
                    "description": "دسترسی به بخش انتخاب‌شده",
                    "icon": "grid",
                }
            )
    return cards

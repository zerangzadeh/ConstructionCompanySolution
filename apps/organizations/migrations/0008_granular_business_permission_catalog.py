from django.db import migrations


PERMISSIONS = {
    "membership.view": "مشاهده اعضای شرکت",
    "membership.change_role": "تغییر نقش اعضای شرکت",
    "membership.change_status": "تغییر وضعیت اعضای شرکت",
    "company.settings.view": "مشاهده تنظیمات شرکت",
    "company.settings.change": "ویرایش تنظیمات شرکت",
    "parties.view": "مشاهده طرف‌های تجاری",
    "parties.create": "ایجاد طرف تجاری",
    "parties.change": "ویرایش طرف تجاری",
    "parties.archive": "بایگانی طرف تجاری",
    "party_roles.assign": "تخصیص نقش به طرف تجاری",
    "party_contacts.add": "افزودن راه ارتباطی طرف تجاری",
    "units.view": "مشاهده واحدهای اندازه‌گیری",
    "units.create": "ایجاد واحد اندازه‌گیری",
    "units.archive": "بایگانی واحد اندازه‌گیری",
    "material_categories.view": "مشاهده دسته‌بندی‌های مصالح",
    "material_categories.create": "ایجاد دسته‌بندی مصالح",
    "material_categories.change": "ویرایش دسته‌بندی مصالح",
    "material_categories.archive": "بایگانی دسته‌بندی مصالح",
    "materials.view": "مشاهده مصالح",
    "materials.create": "ایجاد مصالح",
    "materials.change": "ویرایش مصالح",
    "materials.archive": "بایگانی مصالح",
    "projects.view": "مشاهده پروژه‌ها",
    "projects.create": "ایجاد پروژه",
    "projects.archive": "بایگانی پروژه",
    "project_sites.view": "مشاهده کارگاه‌های پروژه",
    "project_sites.create": "ایجاد کارگاه پروژه",
    "project_phases.view": "مشاهده فازهای پروژه",
    "project_phases.create": "ایجاد فاز پروژه",
    "project_phases.transition": "تغییر وضعیت فاز پروژه",
    "project_controls.view": "مشاهده کنترل پروژه",
    "wbs_nodes.view": "مشاهده ساختار شکست",
    "wbs_nodes.create": "ایجاد گره ساختار شکست",
    "wbs_nodes.change": "ویرایش گره ساختار شکست",
    "wbs_nodes.archive": "بایگانی گره ساختار شکست",
    "activities.view": "مشاهده فعالیت‌های پروژه",
    "activities.create": "ایجاد فعالیت پروژه",
    "activities.transition": "تغییر وضعیت فعالیت پروژه",
    "activities.archive": "بایگانی فعالیت پروژه",
    "contracts.view": "مشاهده قراردادها",
    "contracts.create": "ایجاد قرارداد",
    "contracts.change": "ویرایش قرارداد",
    "contracts.transition": "تغییر وضعیت قرارداد",
    "contract_items.add": "افزودن ردیف قرارداد",
    "contract_amendments.approve": "تأیید الحاقیه قرارداد",
    "estimates.view": "مشاهده برآوردها",
    "estimates.create": "ایجاد برآورد",
    "estimate_items.add": "افزودن ردیف برآورد",
    "estimates.approve": "تأیید برآوردها",
    "estimates.revise": "ایجاد بازنگری برآورد",
    "expenses.view": "مشاهده هزینه‌ها",
    "expenses.create": "ثبت هزینه",
    "expenses.void": "ابطال هزینه",
    "expense_categories.view": "مشاهده دسته‌های هزینه",
    "expense_categories.create": "ایجاد دسته هزینه",
    "expense_categories.archive": "بایگانی دسته هزینه",
    "payments.view": "مشاهده پرداخت‌ها",
    "payments.create": "ثبت پرداخت",
    "payments.void": "ابطال پرداخت",
    "payments.allocate": "تخصیص پرداخت",
    "documents.view": "مشاهده اسناد پروژه",
    "documents.upload": "بارگذاری سند پروژه",
    "documents.download": "دانلود سند پروژه",
    "documents.archive": "بایگانی سند پروژه",
    "daily_reports.view": "مشاهده گزارش‌های روزانه",
    "daily_reports.create": "ثبت گزارش روزانه",
    "daily_reports.add_labor": "افزودن نیروی کار به گزارش روزانه",
    "daily_reports.add_equipment": "افزودن تجهیز به گزارش روزانه",
    "daily_reports.add_material": "افزودن مصالح به گزارش روزانه",
    "daily_reports.add_activity": "افزودن فعالیت به گزارش روزانه",
    "daily_reports.add_delay": "افزودن رویداد تأخیر به گزارش روزانه",
    "daily_reports.submit": "ارسال گزارش روزانه",
    "daily_reports.approve": "تأیید گزارش روزانه",
    "departments.view": "مشاهده دپارتمان‌ها",
    "departments.create": "ایجاد دپارتمان",
    "departments.archive": "بایگانی دپارتمان",
    "positions.view": "مشاهده سمت‌های شغلی",
    "positions.create": "ایجاد سمت شغلی",
    "positions.archive": "بایگانی سمت شغلی",
    "work_teams.view": "مشاهده تیم‌های کاری",
    "work_teams.create": "ایجاد تیم کاری",
    "work_teams.archive": "بایگانی تیم کاری",
    "employees.view": "مشاهده کارکنان",
    "employees.create": "ایجاد پرونده کارمند",
    "employees.change_status": "تغییر وضعیت کارمند",
    "employees.archive": "بایگانی کارمند",
    "project_assignments.view": "مشاهده تخصیص نیروی پروژه",
    "project_assignments.create": "تخصیص نیرو به پروژه",
    "project_assignments.change_status": "تغییر وضعیت تخصیص نیروی پروژه",
    "purchase_requests.view": "مشاهده درخواست‌های خرید",
    "purchase_requests.create": "ایجاد درخواست خرید",
    "purchase_request_items.add": "افزودن ردیف درخواست خرید",
    "purchase_requests.submit": "ارسال درخواست خرید",
    "purchase_requests.approve": "تأیید درخواست خرید",
    "purchase_requests.reject": "رد درخواست خرید",
    "purchase_requests.cancel": "لغو درخواست خرید",
    "purchase_orders.view": "مشاهده سفارش‌های خرید",
    "purchase_orders.create": "ایجاد سفارش خرید",
    "purchase_order_items.add": "افزودن ردیف سفارش خرید",
    "purchase_orders.issue": "صدور سفارش خرید",
    "purchase_orders.cancel": "لغو سفارش خرید",
    "goods_receipts.view": "مشاهده رسیدهای کالا",
    "goods_receipts.create": "ایجاد رسید کالا",
    "goods_receipt_items.add": "افزودن ردیف رسید کالا",
    "goods_receipts.post": "ثبت نهایی رسید کالا",
    "goods_receipts.void": "ابطال رسید کالا",
    "warehouses.view": "مشاهده انبارها",
    "warehouses.create": "ایجاد انبار",
    "warehouses.archive": "بایگانی انبار",
    "stock_transactions.view": "مشاهده تراکنش‌های انبار",
    "stock_transactions.create": "ایجاد تراکنش انبار",
    "stock_transactions.post": "ثبت نهایی تراکنش انبار",
    "stock_transactions.reverse": "برگشت تراکنش انبار",
    "stock_balances.view": "مشاهده موجودی انبار",
    "financials.view": "مشاهده داشبورد و گزارش‌های مالی",
    "audit.view": "مشاهده گزارش رویدادها",
}

READ_ONLY = {
    code for code in PERMISSIONS if code.endswith(".view")
} | {"documents.download"}
MEMBER_OPERATIONS = {
    "daily_reports.create",
    "daily_reports.add_labor",
    "daily_reports.add_equipment",
    "daily_reports.add_material",
    "daily_reports.add_activity",
    "daily_reports.add_delay",
    "daily_reports.submit",
    "purchase_requests.create",
    "purchase_request_items.add",
    "purchase_requests.submit",
    "purchase_requests.cancel",
    "goods_receipts.create",
    "goods_receipt_items.add",
    "goods_receipts.post",
    "stock_transactions.create",
    "stock_transactions.post",
}
OPERATIONS_MANAGER_EXCLUSIONS = {
    "membership.view",
    "membership.change_role",
    "membership.change_status",
    "company.settings.view",
    "company.settings.change",
    "estimates.approve",
}
ROLE_METADATA = {
    "company_owner": ("مالک شرکت", True),
    "company_manager": ("مدیر شرکت", False),
    "operations_manager": ("مدیر اجرایی", False),
    "member": ("عضو", False),
    "viewer": ("مشاهده‌گر", False),
}


def rebuild_permission_catalog(apps, schema_editor):
    business_permission = apps.get_model("organizations", "BusinessPermission")
    organization_role = apps.get_model("organizations", "OrganizationRole")

    business_permission.objects.all().delete()
    business_permission.objects.bulk_create(
        [
            business_permission(
                code=code,
                name=name,
                description=f"مجوز سازمانی ریزدانه: {name}",
                is_active=True,
            )
            for code, name in PERMISSIONS.items()
        ]
    )

    all_codes = set(PERMISSIONS)
    role_permissions = {
        "company_owner": all_codes,
        "company_manager": all_codes,
        "operations_manager": all_codes - OPERATIONS_MANAGER_EXCLUSIONS,
        "member": READ_ONLY | MEMBER_OPERATIONS,
        "viewer": READ_ONLY,
    }
    for code, (name, is_owner) in ROLE_METADATA.items():
        organization_role.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "is_active": True,
                "is_system": True,
                "is_owner": is_owner,
            },
        )
    for role in organization_role.objects.all():
        codes = role_permissions.get(role.code, set())
        role.permissions.set(business_permission.objects.filter(code__in=codes))


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0007_contract_view_permission"),
    ]

    operations = [
        migrations.RunPython(rebuild_permission_catalog, migrations.RunPython.noop),
    ]

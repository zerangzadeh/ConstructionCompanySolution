from typing import Final


METRIC_SPECS: Final[dict[str, dict[str, object]]] = {
    "approved_budget": {
        "persian_name": "بودجه مصوب",
        "source_domain": "project_controls",
        "source_permission": "budgets.view",
        "source_owner": "کنترل پروژه / بودجه",
        "formula": "جمع تخصیص‌های نسخه بودجه پذیرفته‌شده حاکم",
        "unit": "money",
        "drillthrough": "projects:budget_detail",
        "requires_review": True,
    },
    "committed_cost": {
        "persian_name": "هزینه تعهدشده",
        "source_domain": "project_cost",
        "source_permission": "project_cost.view",
        "source_owner": "کنترل پروژه با منبع قرارداد/تدارکات",
        "formula": "تعهد مجاز + تعدیل تعهد - رفع تعهد",
        "unit": "money",
        "drillthrough": "projects:cost_sources",
        "requires_review": True,
    },
    "actual_cost_coverage": {
        "persian_name": "هزینه واقعی با پوشش منبع",
        "source_domain": "project_cost",
        "source_permission": "project_cost.view",
        "source_owner": "کنترل پروژه",
        "formula": "هزینه واقعی شناسایی‌شده + برگشت‌های ثبت‌شده",
        "unit": "money",
        "drillthrough": "projects:cost_sources",
        "requires_review": True,
    },
    "cleared_cash_position": {
        "persian_name": "موقعیت نقد تسویه‌شده",
        "source_domain": "treasury",
        "source_permission": "treasury.view",
        "source_owner": "خزانه‌داری",
        "formula": "دریافت‌های تسویه‌شده منهای پرداخت‌های تسویه‌شده",
        "unit": "money",
        "drillthrough": "treasury:workbench",
        "requires_review": True,
    },
    "procurement_cycle_time": {
        "persian_name": "زمان چرخه تدارکات",
        "source_domain": "procurement",
        "source_permission": "purchase_orders.view",
        "source_owner": "تدارکات",
        "formula": "میانگین زمان ارسال درخواست تا ثبت رسید کالای متناظر",
        "unit": "seconds",
        "drillthrough": "procurement:request_list",
        "requires_review": False,
    },
    "inventory_quantity_value": {
        "persian_name": "مقدار و ارزش موجودی",
        "source_domain": "inventory",
        "source_permission": "inventory_valuation.view",
        "source_owner": "انبار و ارزش‌گذاری موجودی",
        "formula": "جمع وضعیت جاری مخازن ارزش‌گذاری میانگین موزون",
        "unit": "quantity_and_money",
        "drillthrough": "inventory:valuation_workbench",
        "requires_review": True,
    },
}

GOVERNANCE_REFERENCE: Final = (
    "P10-M01–P10-M24=A; Product Owner authorization 2026-10-07"
)

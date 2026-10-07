import hashlib
import json

from django.db import migrations
from django.utils import timezone


METRICS = (
    ("approved_budget", "بودجه مصوب", "project_controls", "budgets.view", "کنترل پروژه / بودجه", "جمع تخصیص‌های نسخه بودجه پذیرفته‌شده حاکم", "money", "projects:budget_detail", True),
    ("committed_cost", "هزینه تعهدشده", "project_cost", "project_cost.view", "کنترل پروژه با منبع قرارداد/تدارکات", "تعهد مجاز + تعدیل تعهد - رفع تعهد", "money", "projects:cost_sources", True),
    ("actual_cost_coverage", "هزینه واقعی با پوشش منبع", "project_cost", "project_cost.view", "کنترل پروژه", "هزینه واقعی شناسایی‌شده + برگشت‌های ثبت‌شده", "money", "projects:cost_sources", True),
    ("cleared_cash_position", "موقعیت نقد تسویه‌شده", "treasury", "treasury.view", "خزانه‌داری", "دریافت‌های تسویه‌شده منهای پرداخت‌های تسویه‌شده", "money", "treasury:workbench", True),
    ("procurement_cycle_time", "زمان چرخه تدارکات", "procurement", "purchase_orders.view", "تدارکات", "میانگین زمان ارسال درخواست تا ثبت رسید کالای متناظر", "seconds", "procurement:request_list", False),
    ("inventory_quantity_value", "مقدار و ارزش موجودی", "inventory", "inventory_valuation.view", "انبار و ارزش‌گذاری موجودی", "جمع وضعیت جاری مخازن ارزش‌گذاری میانگین موزون", "quantity_and_money", "inventory:valuation_workbench", True),
)

GOVERNANCE = "P10-M01–P10-M24=A; Product Owner authorization 2026-10-07"


def forward(apps, schema_editor):
    del schema_editor
    definition_model = apps.get_model("reporting", "MetricDefinition")
    version_model = apps.get_model("reporting", "MetricDefinitionVersion")
    now = timezone.now()
    for code, name, domain, permission, source_owner, formula, unit, route, review in METRICS:
        definition = definition_model.objects.create(
            code=code,
            persian_name=name,
            source_domain=domain,
            source_permission=permission,
            sensitivity="normal",
            drillthrough_route_name=route,
            metric_owner="Product Owner through authoritative owning business domain",
            source_owner=source_owner,
            requires_independent_review=review,
            is_active=True,
        )
        specification = {
            "grain": "tenant/project/as_of",
            "formula": formula,
            "unit": unit,
            "time_basis": "explicit source cutoff and tenant timezone",
            "missing_input": "unknown_or_incomplete_never_zero",
            "late_correction": "linked_replacement_refresh",
            "drillthrough": route,
            "source_permission": permission,
        }
        payload_hash = hashlib.sha256(
            json.dumps(specification, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        version_model.objects.create(
            definition=definition,
            version=1,
            status="published",
            specification=specification,
            payload_hash=payload_hash,
            governance_reference=GOVERNANCE,
            published_at=now,
        )


def reverse(apps, schema_editor):
    del schema_editor
    codes = [item[0] for item in METRICS]
    apps.get_model("reporting", "MetricDefinitionVersion").objects.filter(
        definition__code__in=codes
    ).delete()
    apps.get_model("reporting", "MetricDefinition").objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):
    dependencies = [("reporting", "0001_initial")]
    operations = [migrations.RunPython(forward, reverse)]

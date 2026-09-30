from typing import ClassVar

from django.db import migrations


LINK_MODELS = {
    "project": ("projects", "ProjectDocumentLink"),
    "contract": ("contracts", "ContractDocumentLink"),
    "estimate": ("estimates", "EstimateDocumentLink"),
    "expense": ("expenses", "ExpenseDocumentLink"),
    "payment": ("payments", "PaymentDocumentLink"),
    "daily_report": ("daily_reports", "DailyReportDocumentLink"),
}


def backfill_typed_links(apps, schema_editor):
    del schema_editor
    LegacyLink = apps.get_model("documents", "DocumentLink")
    typed_rows = {key: [] for key in LINK_MODELS}
    for legacy in LegacyLink.objects.all().iterator(chunk_size=500):
        selected = [
            key
            for key in LINK_MODELS
            if getattr(legacy, f"{key}_id") is not None
        ]
        if len(selected) != 1:
            raise RuntimeError(
                "P1-S20 requires exactly one target for legacy DocumentLink "
                f"{legacy.pk}; resolve the row before migration."
            )
        key = selected[0]
        app_label, model_name = LINK_MODELS[key]
        TypedLink = apps.get_model(app_label, model_name)
        typed_rows[key].append(
            TypedLink(
                id=legacy.pk,
                legacy_link_id=legacy.pk,
                organization_id=legacy.organization_id,
                document_id=legacy.document_id,
                created_by_id=legacy.created_by_id,
                created_at=legacy.created_at,
                **{f"{key}_id": getattr(legacy, f"{key}_id")},
            )
        )

    for key, rows in typed_rows.items():
        if not rows:
            continue
        app_label, model_name = LINK_MODELS[key]
        apps.get_model(app_label, model_name).objects.bulk_create(
            rows, batch_size=500
        )


def reverse_backfill(apps, schema_editor):
    del schema_editor
    for app_label, model_name in LINK_MODELS.values():
        apps.get_model(app_label, model_name).objects.all().delete()


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("documents", "0005_p1_s19_document_governance"),
        ("projects", "0005_projectdocumentlink"),
        ("contracts", "0004_contractdocumentlink"),
        ("estimates", "0004_estimatedocumentlink"),
        ("expenses", "0004_expensedocumentlink"),
        ("payments", "0006_paymentdocumentlink"),
        ("daily_reports", "0004_dailyreportdocumentlink"),
    ]
    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.RunPython(backfill_typed_links, reverse_backfill)
    ]

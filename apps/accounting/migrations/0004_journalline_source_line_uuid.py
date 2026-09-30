from typing import ClassVar

from django.db import migrations, models


def backfill_source_line_uuid(apps, schema_editor):
    del schema_editor
    JournalLine = apps.get_model("accounting", "JournalLine")
    OpeningBalanceImport = apps.get_model("accounting", "OpeningBalanceImport")

    imported_journals = {
        opening_import.accepted_journal_id: opening_import.pk
        for opening_import in OpeningBalanceImport.objects.exclude(
            accepted_journal_id=None
        ).iterator()
    }
    for line in JournalLine.objects.select_related("journal").iterator():
        source_line_uuid = line.pk
        if line.journal_id in imported_journals:
            source_line = (
                apps.get_model("accounting", "OpeningBalanceImportLine")
                .objects.filter(
                    opening_import_id=imported_journals[line.journal_id],
                    line_number=line.line_number,
                )
                .first()
            )
            if source_line is not None:
                source_line_uuid = source_line.pk
        elif line.journal.reverses_id:
            original_line = JournalLine.objects.filter(
                journal_id=line.journal.reverses_id,
                line_number=line.line_number,
            ).first()
            if original_line is not None:
                source_line_uuid = original_line.pk
        JournalLine.objects.filter(pk=line.pk).update(source_line_uuid=source_line_uuid)


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("accounting", "0003_fiscalperiod_fiscal_period_no_year_overlap_and_more"),
    ]

    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.AddField(
            model_name="journalline",
            name="source_line_uuid",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_source_line_uuid, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="journalline",
            name="source_line_uuid",
            field=models.UUIDField(editable=False),
        ),
    ]

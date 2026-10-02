from typing import ClassVar

from django.db import migrations


FORWARD_SQL = """
CREATE OR REPLACE FUNCTION expenses_p4_control_guard() RETURNS trigger AS $$
BEGIN
    IF TG_TABLE_NAME IN ('expenses_expenseallocation', 'expenses_expensebudgetassessment') THEN
        RAISE EXCEPTION 'expense allocation and budget assessment evidence is immutable';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'expense evidence cannot be deleted';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.status IN ('submitted', 'approved', 'recorded', 'void')
       AND (
          NEW.organization_id IS DISTINCT FROM OLD.organization_id OR
          NEW.project_id IS DISTINCT FROM OLD.project_id OR
          NEW.phase_id IS DISTINCT FROM OLD.phase_id OR
          NEW.amount IS DISTINCT FROM OLD.amount OR
          NEW.incurred_on IS DISTINCT FROM OLD.incurred_on OR
          NEW.description IS DISTINCT FROM OLD.description OR
          NEW.source_reference IS DISTINCT FROM OLD.source_reference OR
          NEW.source_fingerprint IS DISTINCT FROM OLD.source_fingerprint OR
          NEW.classification IS DISTINCT FROM OLD.classification OR
          NEW.primary_group_id IS DISTINCT FROM OLD.primary_group_id
       ) THEN
        RAISE EXCEPTION 'submitted expense source and financial evidence is immutable';
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;
"""

REVERSE_SQL = FORWARD_SQL.replace(
    " OR\n          NEW.primary_group_id IS DISTINCT FROM OLD.primary_group_id", ""
)


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("expenses", "0007_expense_primary_group"),
    ]

    operations: ClassVar[list] = [
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
    ]

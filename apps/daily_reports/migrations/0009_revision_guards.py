"""Guard revision lineage and sealed operational content in PostgreSQL."""

from django.db import migrations

TABLES = (
    "dailyreportlaborentry", "dailyreportequipmententry", "dailyreportmaterialentry",
    "dailyactivity", "delayevent", "dailyreportrecordreference",
)
REPORT = """
CREATE FUNCTION bonira_daily_revision_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent daily_reports_dailyreport%ROWTYPE;
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.submission_hash <> '' OR OLD.previous_revision_id IS NOT NULL THEN
            RAISE EXCEPTION 'Retained daily report revision cannot be deleted' USING ERRCODE = '23514';
        END IF;
        RETURN OLD;
    END IF;
    IF TG_OP = 'INSERT' AND NEW.previous_revision_id IS NOT NULL THEN
        SELECT * INTO parent FROM daily_reports_dailyreport
            WHERE id = NEW.previous_revision_id FOR UPDATE;
        IF NOT FOUND OR parent.status <> 'returned' OR parent.submission_hash = ''
            OR NEW.status <> 'draft' OR NEW.submission_hash <> ''
            OR NEW.revision_number <> parent.revision_number + 1
            OR ROW(NEW.organization_id, NEW.project_id, NEW.site_id, NEW.phase_id,
                   NEW.reporting_date, NEW.created_by_id) IS DISTINCT FROM
               ROW(parent.organization_id, parent.project_id, parent.site_id, parent.phase_id,
                   parent.reporting_date, parent.created_by_id) THEN
            RAISE EXCEPTION 'Invalid daily report predecessor' USING ERRCODE = '23514';
        END IF;
    END IF;
    IF TG_OP = 'INSERT' AND NEW.submission_hash <> '' THEN
        RAISE EXCEPTION 'Daily report seal must follow creation' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF ROW(OLD.previous_revision_id, OLD.revision_number) IS DISTINCT FROM
           ROW(NEW.previous_revision_id, NEW.revision_number)
           OR (OLD.previous_revision_id IS NOT NULL AND
               ROW(OLD.organization_id, OLD.project_id, OLD.site_id, OLD.phase_id,
                   OLD.reporting_date, OLD.created_by_id) IS DISTINCT FROM
               ROW(NEW.organization_id, NEW.project_id, NEW.site_id, NEW.phase_id,
                   NEW.reporting_date, NEW.created_by_id)) THEN
            RAISE EXCEPTION 'Daily report revision lineage is immutable' USING ERRCODE = '23514';
        END IF;
        IF OLD.submission_hash <> '' THEN
            IF OLD.status <> 'submitted' OR NEW.status NOT IN ('returned', 'approved')
                OR (to_jsonb(OLD) - ARRAY['status','updated_at','updated_by_id','approved_at','approved_by_id'])
                   IS DISTINCT FROM
                   (to_jsonb(NEW) - ARRAY['status','updated_at','updated_by_id','approved_at','approved_by_id'])
                OR (NEW.status = 'returned' AND
                    ROW(OLD.approved_at, OLD.approved_by_id) IS DISTINCT FROM
                    ROW(NEW.approved_at, NEW.approved_by_id))
                OR (NEW.status = 'approved' AND (NEW.approved_at IS NULL OR NEW.approved_by_id IS NULL)) THEN
                RAISE EXCEPTION 'Sealed daily report is immutable' USING ERRCODE = '23514';
            END IF;
        ELSIF NEW.submission_hash <> '' THEN
            IF NEW.status <> 'submitted' OR OLD.status NOT IN ('draft', 'submitted')
                OR (to_jsonb(OLD) - ARRAY['status','submitted_at','updated_at','updated_by_id','submission_snapshot','submission_hash'])
                   IS DISTINCT FROM
                   (to_jsonb(NEW) - ARRAY['status','submitted_at','updated_at','updated_by_id','submission_snapshot','submission_hash'])
                OR (OLD.status = 'submitted' AND
                    ROW(OLD.submitted_at, OLD.updated_by_id) IS DISTINCT FROM ROW(NEW.submitted_at, NEW.updated_by_id)) THEN
                RAISE EXCEPTION 'Invalid daily report submission seal' USING ERRCODE = '23514';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER bonira_daily_revision_guard BEFORE INSERT OR UPDATE OR DELETE
ON daily_reports_dailyreport FOR EACH ROW EXECUTE FUNCTION bonira_daily_revision_guard();

CREATE FUNCTION bonira_daily_revision_decision_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM audit_auditevent event
        JOIN workflows_workitem item ON item.id::text = event.metadata->>'work_item_id'
        JOIN workflows_workflowinstance instance ON instance.id = item.instance_id
        WHERE event.entity_type = 'daily_report' AND event.entity_id = NEW.id::text
          AND event.organization_id = NEW.organization_id
          AND event.action = 'daily_report.' || NEW.status
          AND event.metadata->>'submission_hash' = NEW.submission_hash
          AND item.organization_id = NEW.organization_id
          AND item.status = 'completed' AND item.completion_outcome = NEW.status
          AND instance.organization_id = NEW.organization_id
          AND instance.subject_type = 'daily_reports.daily_report'
          AND instance.subject_id = NEW.id AND instance.status = 'completed'
    ) THEN
        RAISE EXCEPTION 'Sealed report decision requires completed review and audit'
            USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END
$$;
CREATE CONSTRAINT TRIGGER bonira_daily_revision_decision_guard AFTER UPDATE
ON daily_reports_dailyreport DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
WHEN (OLD.status IS DISTINCT FROM NEW.status AND NEW.status IN ('returned', 'approved')
      AND NEW.submission_hash <> '')
EXECUTE FUNCTION bonira_daily_revision_decision_guard();
"""

ENTRIES = """
CREATE FUNCTION bonira_daily_revision_entry_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent daily_reports_dailyreport%ROWTYPE;
DECLARE target uuid;
BEGIN
    IF TG_OP = 'UPDATE' AND ROW(NEW.report_id, NEW.organization_id)
        IS DISTINCT FROM ROW(OLD.report_id, OLD.organization_id) THEN
        RAISE EXCEPTION 'Daily report entry cannot be reparented' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'DELETE' THEN target := OLD.report_id; ELSE target := NEW.report_id; END IF;
    SELECT * INTO parent FROM daily_reports_dailyreport WHERE id = target FOR UPDATE;
    IF FOUND AND (parent.submission_hash <> '' OR
        (parent.previous_revision_id IS NOT NULL AND parent.status <> 'draft')) THEN
        RAISE EXCEPTION 'Sealed daily report entries are immutable' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    IF NOT FOUND OR NEW.organization_id IS DISTINCT FROM parent.organization_id THEN
        RAISE EXCEPTION 'Daily report entry tenant mismatch' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END
$$;
"""


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    # No bind parameters: preserve PL/pgSQL's literal %ROWTYPE instead of
    # sending it through psycopg's placeholder interpolation (the default ()).
    schema_editor.execute(REPORT, params=None)
    schema_editor.execute(ENTRIES, params=None)
    for table in TABLES:
        schema_editor.execute(
            f"CREATE TRIGGER bonira_daily_revision_entry_guard BEFORE INSERT OR UPDATE OR DELETE "
            f"ON daily_reports_{table} FOR EACH ROW EXECUTE FUNCTION bonira_daily_revision_entry_guard()"
        )


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    report = apps.get_model("daily_reports", "DailyReport")
    if report.objects.using(schema_editor.connection.alias).filter(
        previous_revision__isnull=False
    ).exists():
        raise RuntimeError("Cannot remove revision guards while correction history exists.")
    for table in TABLES:
        schema_editor.execute(
            f"DROP TRIGGER bonira_daily_revision_entry_guard ON daily_reports_{table}"
        )
    schema_editor.execute("DROP FUNCTION bonira_daily_revision_entry_guard()")
    schema_editor.execute("DROP TRIGGER bonira_daily_revision_decision_guard ON daily_reports_dailyreport")
    schema_editor.execute("DROP FUNCTION bonira_daily_revision_decision_guard()")
    schema_editor.execute("DROP TRIGGER bonira_daily_revision_guard ON daily_reports_dailyreport")
    schema_editor.execute("DROP FUNCTION bonira_daily_revision_guard()")


class Migration(migrations.Migration):
    dependencies = [
        ("daily_reports", "0008_daily_report_return"),
        ("workflows", "0028_daily_report_return_catalog"),
        ("audit", "0060_daily_report_return"),
    ]
    operations = [migrations.RunPython(install, uninstall)]

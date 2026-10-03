from typing import ClassVar

from django.db import migrations


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [
        ("contracts", "0008_contractualrecord_contractualrecordevidence_and_more"),
    ]
    operations: ClassVar[list] = [
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION contracts_contractual_record_guard()
            RETURNS trigger AS $$
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION 'contractual records are retained history';
                END IF;
                IF OLD.status IN ('returned', 'withdrawn', 'superseded', 'cancelled') THEN
                    RAISE EXCEPTION 'final contractual record history is immutable';
                END IF;
                IF OLD.status = 'approved' THEN
                    IF NEW.status NOT IN ('superseded', 'cancelled')
                       OR (to_jsonb(NEW) - ARRAY['status', 'updated_by_id', 'updated_at'])
                          IS DISTINCT FROM
                          (to_jsonb(OLD) - ARRAY['status', 'updated_by_id', 'updated_at']) THEN
                        RAISE EXCEPTION 'approved contractual record history is immutable';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER contracts_contractual_record_guard_trigger
            BEFORE UPDATE OR DELETE ON contracts_contractualrecord
            FOR EACH ROW EXECUTE FUNCTION contracts_contractual_record_guard();

            CREATE OR REPLACE FUNCTION contracts_contractual_evidence_guard()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'contractual evidence links are append-only';
            END;
            $$ LANGUAGE plpgsql;
            CREATE TRIGGER contracts_contractual_evidence_guard_trigger
            BEFORE UPDATE OR DELETE ON contracts_contractualrecordevidence
            FOR EACH ROW EXECUTE FUNCTION contracts_contractual_evidence_guard();
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS contracts_contractual_evidence_guard_trigger
                ON contracts_contractualrecordevidence;
            DROP FUNCTION IF EXISTS contracts_contractual_evidence_guard();
            DROP TRIGGER IF EXISTS contracts_contractual_record_guard_trigger
                ON contracts_contractualrecord;
            DROP FUNCTION IF EXISTS contracts_contractual_record_guard();
            """,
        )
    ]

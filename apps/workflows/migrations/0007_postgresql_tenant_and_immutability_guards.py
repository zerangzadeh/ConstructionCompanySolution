from django.db import migrations


FORWARD_SQL = r"""
CREATE OR REPLACE FUNCTION workflows_assert_tenant_links()
RETURNS trigger AS $$
DECLARE
    expected_org uuid;
BEGIN
    IF TG_TABLE_NAME = 'workflows_workflowversion' THEN
        SELECT organization_id INTO expected_org
        FROM workflows_workflowdefinition WHERE id = NEW.definition_id;
        IF expected_org IS DISTINCT FROM NEW.organization_id THEN
            RAISE EXCEPTION 'cross-tenant workflow definition reference'
                USING ERRCODE = '23514';
        END IF;
    ELSIF TG_TABLE_NAME = 'workflows_workflowstepdefinition' THEN
        SELECT organization_id INTO expected_org
        FROM workflows_workflowversion WHERE id = NEW.version_id;
        IF expected_org IS DISTINCT FROM NEW.organization_id THEN
            RAISE EXCEPTION 'cross-tenant workflow version reference'
                USING ERRCODE = '23514';
        END IF;
    ELSIF TG_TABLE_NAME = 'workflows_workflowtransitiondefinition' THEN
        SELECT organization_id INTO expected_org
        FROM workflows_workflowversion WHERE id = NEW.version_id;
        IF expected_org IS DISTINCT FROM NEW.organization_id
           OR EXISTS (
               SELECT 1 FROM workflows_workflowstepdefinition
               WHERE id IN (NEW.source_step_id, NEW.target_step_id)
                 AND (organization_id IS DISTINCT FROM NEW.organization_id
                      OR version_id IS DISTINCT FROM NEW.version_id)
           )
           OR (SELECT count(*) FROM workflows_workflowstepdefinition
               WHERE id IN (NEW.source_step_id, NEW.target_step_id)) <> 2 THEN
            RAISE EXCEPTION 'cross-tenant or cross-version transition reference'
                USING ERRCODE = '23514';
        END IF;
    ELSIF TG_TABLE_NAME = 'workflows_workflowcondition' THEN
        SELECT organization_id INTO expected_org
        FROM workflows_workflowversion WHERE id = NEW.version_id;
        IF expected_org IS DISTINCT FROM NEW.organization_id
           OR NOT EXISTS (
               SELECT 1 FROM workflows_workflowtransitiondefinition
               WHERE id = NEW.transition_id
                 AND organization_id = NEW.organization_id
                 AND version_id = NEW.version_id
           ) THEN
            RAISE EXCEPTION 'cross-tenant or cross-version condition reference'
                USING ERRCODE = '23514';
        END IF;
    ELSIF TG_TABLE_NAME = 'workflows_workflowroutingrule' THEN
        SELECT organization_id INTO expected_org
        FROM workflows_workflowversion WHERE id = NEW.version_id;
        IF expected_org IS DISTINCT FROM NEW.organization_id
           OR NOT EXISTS (
               SELECT 1 FROM workflows_workflowstepdefinition
               WHERE id = NEW.step_id
                 AND organization_id = NEW.organization_id
                 AND version_id = NEW.version_id
           ) THEN
            RAISE EXCEPTION 'cross-tenant or cross-version routing reference'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION workflows_guard_version_state()
RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.status <> 'draft' THEN
            RAISE EXCEPTION 'published or retired workflow versions cannot be deleted'
                USING ERRCODE = '23514';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.status = 'retired' THEN
        RAISE EXCEPTION 'retired workflow versions are immutable'
            USING ERRCODE = '23514';
    END IF;
    IF OLD.status = 'published' AND NOT (
        NEW.status = 'retired'
        AND NEW.organization_id IS NOT DISTINCT FROM OLD.organization_id
        AND NEW.definition_id IS NOT DISTINCT FROM OLD.definition_id
        AND NEW.version_number IS NOT DISTINCT FROM OLD.version_number
        AND NEW.change_summary IS NOT DISTINCT FROM OLD.change_summary
        AND NEW.validation_report IS NOT DISTINCT FROM OLD.validation_report
        AND NEW.validated_at IS NOT DISTINCT FROM OLD.validated_at
        AND NEW.validated_by_id IS NOT DISTINCT FROM OLD.validated_by_id
        AND NEW.published_at IS NOT DISTINCT FROM OLD.published_at
        AND NEW.published_by_id IS NOT DISTINCT FROM OLD.published_by_id
    ) THEN
        RAISE EXCEPTION 'published workflow versions are immutable except retirement'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION workflows_guard_draft_configuration()
RETURNS trigger AS $$
DECLARE
    target_version uuid;
    target_status varchar;
BEGIN
    target_version := CASE WHEN TG_OP = 'DELETE' THEN OLD.version_id ELSE NEW.version_id END;
    SELECT status INTO target_status
    FROM workflows_workflowversion WHERE id = target_version;
    IF target_status IS DISTINCT FROM 'draft' THEN
        RAISE EXCEPTION 'only draft workflow configuration can be changed'
            USING ERRCODE = '23514';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER workflows_version_tenant_guard
BEFORE INSERT OR UPDATE ON workflows_workflowversion
FOR EACH ROW EXECUTE FUNCTION workflows_assert_tenant_links();
CREATE TRIGGER workflows_version_state_guard
BEFORE UPDATE OR DELETE ON workflows_workflowversion
FOR EACH ROW EXECUTE FUNCTION workflows_guard_version_state();

CREATE TRIGGER workflows_step_tenant_guard
BEFORE INSERT OR UPDATE ON workflows_workflowstepdefinition
FOR EACH ROW EXECUTE FUNCTION workflows_assert_tenant_links();
CREATE TRIGGER workflows_transition_tenant_guard
BEFORE INSERT OR UPDATE ON workflows_workflowtransitiondefinition
FOR EACH ROW EXECUTE FUNCTION workflows_assert_tenant_links();
CREATE TRIGGER workflows_condition_tenant_guard
BEFORE INSERT OR UPDATE ON workflows_workflowcondition
FOR EACH ROW EXECUTE FUNCTION workflows_assert_tenant_links();
CREATE TRIGGER workflows_routing_tenant_guard
BEFORE INSERT OR UPDATE ON workflows_workflowroutingrule
FOR EACH ROW EXECUTE FUNCTION workflows_assert_tenant_links();

CREATE TRIGGER workflows_step_draft_guard
BEFORE INSERT OR UPDATE OR DELETE ON workflows_workflowstepdefinition
FOR EACH ROW EXECUTE FUNCTION workflows_guard_draft_configuration();
CREATE TRIGGER workflows_transition_draft_guard
BEFORE INSERT OR UPDATE OR DELETE ON workflows_workflowtransitiondefinition
FOR EACH ROW EXECUTE FUNCTION workflows_guard_draft_configuration();
CREATE TRIGGER workflows_condition_draft_guard
BEFORE INSERT OR UPDATE OR DELETE ON workflows_workflowcondition
FOR EACH ROW EXECUTE FUNCTION workflows_guard_draft_configuration();
CREATE TRIGGER workflows_routing_draft_guard
BEFORE INSERT OR UPDATE OR DELETE ON workflows_workflowroutingrule
FOR EACH ROW EXECUTE FUNCTION workflows_guard_draft_configuration();
"""


REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS workflows_routing_draft_guard ON workflows_workflowroutingrule;
DROP TRIGGER IF EXISTS workflows_condition_draft_guard ON workflows_workflowcondition;
DROP TRIGGER IF EXISTS workflows_transition_draft_guard ON workflows_workflowtransitiondefinition;
DROP TRIGGER IF EXISTS workflows_step_draft_guard ON workflows_workflowstepdefinition;
DROP TRIGGER IF EXISTS workflows_routing_tenant_guard ON workflows_workflowroutingrule;
DROP TRIGGER IF EXISTS workflows_condition_tenant_guard ON workflows_workflowcondition;
DROP TRIGGER IF EXISTS workflows_transition_tenant_guard ON workflows_workflowtransitiondefinition;
DROP TRIGGER IF EXISTS workflows_step_tenant_guard ON workflows_workflowstepdefinition;
DROP TRIGGER IF EXISTS workflows_version_state_guard ON workflows_workflowversion;
DROP TRIGGER IF EXISTS workflows_version_tenant_guard ON workflows_workflowversion;
DROP FUNCTION IF EXISTS workflows_guard_draft_configuration();
DROP FUNCTION IF EXISTS workflows_guard_version_state();
DROP FUNCTION IF EXISTS workflows_assert_tenant_links();
"""


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ("workflows", "0006_alter_workflowcondition_options_and_more"),
    ]

    operations = [  # noqa: RUF012
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
    ]


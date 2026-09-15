from django.db import migrations


FORWARD_SQL = r"""
CREATE OR REPLACE FUNCTION workflows_assert_runtime_tenant_links()
RETURNS trigger AS $$
DECLARE
    expected_org uuid;
    expected_instance uuid;
    expected_definition uuid;
    expected_version uuid;
BEGIN
    IF TG_TABLE_NAME = 'workflows_workflowinstance' THEN
        SELECT organization_id, definition_id INTO expected_org, expected_definition
        FROM workflows_workflowversion WHERE id = NEW.version_id;
        IF expected_org IS DISTINCT FROM NEW.organization_id
           OR expected_definition IS DISTINCT FROM NEW.definition_id THEN
            RAISE EXCEPTION 'workflow instance version tenant or definition mismatch';
        END IF;
        SELECT organization_id INTO expected_org
        FROM organizations_organizationmembership WHERE id = NEW.started_by_id;
        IF expected_org IS DISTINCT FROM NEW.organization_id THEN
            RAISE EXCEPTION 'workflow instance starter tenant mismatch';
        END IF;
    ELSIF TG_TABLE_NAME = 'workflows_workflowstepinstance' THEN
        SELECT organization_id, version_id INTO expected_org, expected_version
        FROM workflows_workflowinstance WHERE id = NEW.instance_id;
        IF expected_org IS DISTINCT FROM NEW.organization_id THEN
            RAISE EXCEPTION 'workflow step instance tenant mismatch';
        END IF;
        SELECT organization_id, version_id INTO expected_org, expected_definition
        FROM workflows_workflowstepdefinition WHERE id = NEW.step_definition_id;
        IF expected_org IS DISTINCT FROM NEW.organization_id
           OR (TG_OP = 'INSERT' AND expected_definition IS DISTINCT FROM expected_version) THEN
            RAISE EXCEPTION 'workflow step definition tenant or version mismatch';
        END IF;
    ELSIF TG_TABLE_NAME = 'workflows_workitem' THEN
        SELECT organization_id INTO expected_org
        FROM workflows_workflowinstance WHERE id = NEW.instance_id;
        IF expected_org IS DISTINCT FROM NEW.organization_id THEN
            RAISE EXCEPTION 'work item instance tenant mismatch';
        END IF;
        SELECT organization_id, instance_id INTO expected_org, expected_instance
        FROM workflows_workflowstepinstance WHERE id = NEW.step_instance_id;
        IF expected_org IS DISTINCT FROM NEW.organization_id
           OR expected_instance IS DISTINCT FROM NEW.instance_id THEN
            RAISE EXCEPTION 'work item step tenant or instance mismatch';
        END IF;
        IF NEW.current_assignee_id IS NOT NULL THEN
            SELECT organization_id INTO expected_org
            FROM organizations_organizationmembership WHERE id = NEW.current_assignee_id;
            IF expected_org IS DISTINCT FROM NEW.organization_id THEN
                RAISE EXCEPTION 'work item assignee tenant mismatch';
            END IF;
        END IF;
        IF NEW.assigned_via_position_id IS NOT NULL THEN
            SELECT organization_id INTO expected_org
            FROM workforce_employeepositionassignment WHERE id = NEW.assigned_via_position_id;
            IF expected_org IS DISTINCT FROM NEW.organization_id THEN
                RAISE EXCEPTION 'work item position assignment tenant mismatch';
            END IF;
        END IF;
    ELSIF TG_TABLE_NAME = 'workflows_workitemcandidate' THEN
        SELECT organization_id INTO expected_org
        FROM workflows_workitem WHERE id = NEW.work_item_id;
        IF expected_org IS DISTINCT FROM NEW.organization_id THEN
            RAISE EXCEPTION 'work item candidate item tenant mismatch';
        END IF;
        SELECT organization_id INTO expected_org
        FROM organizations_organizationmembership WHERE id = NEW.membership_id;
        IF expected_org IS DISTINCT FROM NEW.organization_id THEN
            RAISE EXCEPTION 'work item candidate membership tenant mismatch';
        END IF;
        IF NEW.qualifying_position_assignment_id IS NOT NULL THEN
            SELECT organization_id INTO expected_org
            FROM workforce_employeepositionassignment
            WHERE id = NEW.qualifying_position_assignment_id;
            IF expected_org IS DISTINCT FROM NEW.organization_id THEN
                RAISE EXCEPTION 'work item candidate position tenant mismatch';
            END IF;
        END IF;
    ELSIF TG_TABLE_NAME = 'workflows_workitemassignmenthistory' THEN
        SELECT organization_id INTO expected_org
        FROM workflows_workitem WHERE id = NEW.work_item_id;
        IF expected_org IS DISTINCT FROM NEW.organization_id THEN
            RAISE EXCEPTION 'work item history item tenant mismatch';
        END IF;
        SELECT organization_id INTO expected_org
        FROM organizations_organizationmembership WHERE id = NEW.actor_membership_id;
        IF expected_org IS DISTINCT FROM NEW.organization_id THEN
            RAISE EXCEPTION 'work item history actor tenant mismatch';
        END IF;
        IF NEW.from_membership_id IS NOT NULL THEN
            SELECT organization_id INTO expected_org
            FROM organizations_organizationmembership WHERE id = NEW.from_membership_id;
            IF expected_org IS DISTINCT FROM NEW.organization_id THEN
                RAISE EXCEPTION 'work item history source tenant mismatch';
            END IF;
        END IF;
        IF NEW.to_membership_id IS NOT NULL THEN
            SELECT organization_id INTO expected_org
            FROM organizations_organizationmembership WHERE id = NEW.to_membership_id;
            IF expected_org IS DISTINCT FROM NEW.organization_id THEN
                RAISE EXCEPTION 'work item history destination tenant mismatch';
            END IF;
        END IF;
        IF NEW.qualifying_position_assignment_id IS NOT NULL THEN
            SELECT organization_id INTO expected_org
            FROM workforce_employeepositionassignment
            WHERE id = NEW.qualifying_position_assignment_id;
            IF expected_org IS DISTINCT FROM NEW.organization_id THEN
                RAISE EXCEPTION 'work item history position tenant mismatch';
            END IF;
        END IF;
    ELSIF TG_TABLE_NAME = 'workflows_workflowdelegation' THEN
        FOR expected_org IN
            SELECT organization_id FROM organizations_organizationmembership
            WHERE id IN (NEW.delegator_id, NEW.delegate_id, NEW.created_by_id)
        LOOP
            IF expected_org IS DISTINCT FROM NEW.organization_id THEN
                RAISE EXCEPTION 'workflow delegation membership tenant mismatch';
            END IF;
        END LOOP;
        IF NEW.revoked_by_id IS NOT NULL THEN
            SELECT organization_id INTO expected_org
            FROM organizations_organizationmembership WHERE id = NEW.revoked_by_id;
            IF expected_org IS DISTINCT FROM NEW.organization_id THEN
                RAISE EXCEPTION 'workflow delegation revoker tenant mismatch';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION workflows_guard_runtime_history()
RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'workflow runtime history cannot be deleted';
    END IF;
    IF TG_TABLE_NAME = 'workflows_workitemassignmenthistory' THEN
        RAISE EXCEPTION 'work item assignment history is append-only';
    END IF;
    IF OLD.status IN ('completed', 'cancelled') THEN
        RAISE EXCEPTION 'finalized workflow runtime history is immutable';
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION workflows_guard_candidate_history()
RETURNS trigger AS $$
DECLARE
    item_status varchar;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'work item candidate history cannot be deleted';
    END IF;
    SELECT status INTO item_status FROM workflows_workitem WHERE id = NEW.work_item_id;
    IF item_status IN ('completed', 'cancelled') THEN
        RAISE EXCEPTION 'finalized work item candidates are immutable';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION workflows_guard_delegation_history()
RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'workflow delegation history cannot be deleted';
    END IF;
    IF OLD.organization_id IS DISTINCT FROM NEW.organization_id
       OR OLD.delegator_id IS DISTINCT FROM NEW.delegator_id
       OR OLD.delegate_id IS DISTINCT FROM NEW.delegate_id
       OR OLD.workflow_type_id IS DISTINCT FROM NEW.workflow_type_id
       OR OLD.permission_id IS DISTINCT FROM NEW.permission_id
       OR OLD.scope IS DISTINCT FROM NEW.scope
       OR OLD.idempotency_key IS DISTINCT FROM NEW.idempotency_key
       OR OLD.starts_at IS DISTINCT FROM NEW.starts_at
       OR OLD.ends_at IS DISTINCT FROM NEW.ends_at
       OR OLD.reason IS DISTINCT FROM NEW.reason
       OR OLD.created_by_id IS DISTINCT FROM NEW.created_by_id
       OR OLD.revoked_at IS NOT NULL THEN
        RAISE EXCEPTION 'workflow delegation evidence is immutable';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER workflows_runtime_instance_tenant_guard
BEFORE INSERT OR UPDATE ON workflows_workflowinstance
FOR EACH ROW EXECUTE FUNCTION workflows_assert_runtime_tenant_links();
CREATE TRIGGER workflows_runtime_step_tenant_guard
BEFORE INSERT OR UPDATE ON workflows_workflowstepinstance
FOR EACH ROW EXECUTE FUNCTION workflows_assert_runtime_tenant_links();
CREATE TRIGGER workflows_runtime_item_tenant_guard
BEFORE INSERT OR UPDATE ON workflows_workitem
FOR EACH ROW EXECUTE FUNCTION workflows_assert_runtime_tenant_links();
CREATE TRIGGER workflows_runtime_candidate_tenant_guard
BEFORE INSERT OR UPDATE ON workflows_workitemcandidate
FOR EACH ROW EXECUTE FUNCTION workflows_assert_runtime_tenant_links();
CREATE TRIGGER workflows_runtime_history_tenant_guard
BEFORE INSERT ON workflows_workitemassignmenthistory
FOR EACH ROW EXECUTE FUNCTION workflows_assert_runtime_tenant_links();
CREATE TRIGGER workflows_runtime_delegation_tenant_guard
BEFORE INSERT OR UPDATE ON workflows_workflowdelegation
FOR EACH ROW EXECUTE FUNCTION workflows_assert_runtime_tenant_links();

CREATE TRIGGER workflows_runtime_instance_immutable_guard
BEFORE UPDATE OR DELETE ON workflows_workflowinstance
FOR EACH ROW EXECUTE FUNCTION workflows_guard_runtime_history();
CREATE TRIGGER workflows_runtime_step_immutable_guard
BEFORE UPDATE OR DELETE ON workflows_workflowstepinstance
FOR EACH ROW EXECUTE FUNCTION workflows_guard_runtime_history();
CREATE TRIGGER workflows_runtime_item_immutable_guard
BEFORE UPDATE OR DELETE ON workflows_workitem
FOR EACH ROW EXECUTE FUNCTION workflows_guard_runtime_history();
CREATE TRIGGER workflows_runtime_history_append_only_guard
BEFORE UPDATE OR DELETE ON workflows_workitemassignmenthistory
FOR EACH ROW EXECUTE FUNCTION workflows_guard_runtime_history();
CREATE TRIGGER workflows_runtime_candidate_history_guard
BEFORE UPDATE OR DELETE ON workflows_workitemcandidate
FOR EACH ROW EXECUTE FUNCTION workflows_guard_candidate_history();
CREATE TRIGGER workflows_runtime_delegation_history_guard
BEFORE UPDATE OR DELETE ON workflows_workflowdelegation
FOR EACH ROW EXECUTE FUNCTION workflows_guard_delegation_history();
"""


REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS workflows_runtime_delegation_history_guard
ON workflows_workflowdelegation;
DROP TRIGGER IF EXISTS workflows_runtime_candidate_history_guard
ON workflows_workitemcandidate;
DROP TRIGGER IF EXISTS workflows_runtime_history_append_only_guard
ON workflows_workitemassignmenthistory;
DROP TRIGGER IF EXISTS workflows_runtime_item_immutable_guard ON workflows_workitem;
DROP TRIGGER IF EXISTS workflows_runtime_step_immutable_guard
ON workflows_workflowstepinstance;
DROP TRIGGER IF EXISTS workflows_runtime_instance_immutable_guard
ON workflows_workflowinstance;
DROP TRIGGER IF EXISTS workflows_runtime_delegation_tenant_guard
ON workflows_workflowdelegation;
DROP TRIGGER IF EXISTS workflows_runtime_history_tenant_guard
ON workflows_workitemassignmenthistory;
DROP TRIGGER IF EXISTS workflows_runtime_candidate_tenant_guard
ON workflows_workitemcandidate;
DROP TRIGGER IF EXISTS workflows_runtime_item_tenant_guard ON workflows_workitem;
DROP TRIGGER IF EXISTS workflows_runtime_step_tenant_guard
ON workflows_workflowstepinstance;
DROP TRIGGER IF EXISTS workflows_runtime_instance_tenant_guard
ON workflows_workflowinstance;
DROP FUNCTION IF EXISTS workflows_guard_runtime_history();
DROP FUNCTION IF EXISTS workflows_guard_candidate_history();
DROP FUNCTION IF EXISTS workflows_guard_delegation_history();
DROP FUNCTION IF EXISTS workflows_assert_runtime_tenant_links();
"""


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ("organizations", "0023_workflow_runtime_permissions"),
        ("workflows", "0008_workflowinstance_workflowstepinstance_workitem_and_more"),
    ]

    operations = [  # noqa: RUF012
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
    ]

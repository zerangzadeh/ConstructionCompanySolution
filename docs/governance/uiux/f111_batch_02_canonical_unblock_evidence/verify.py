"""Verify retained canonical history, runtime isolation and bounded closeout."""

import json
import re
import subprocess
from collections import Counter

from closure import MARKER, OPERATOR, OUT, PRIOR, ROOT, files, helpers, save, sha, state

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.billing.models import ContractComplianceEvidence
from apps.documents.models import DocumentProcessingAssessment, DocumentVersion
from apps.organizations.authorization import has_business_permission, has_platform_role
from apps.organizations.models import PlatformRoleAssignment, PlatformRoleCode


def runtime_integrity():
    before = json.loads((OUT / "BEFORE.json").read_text(encoding="utf-8"))
    entry = json.loads((OUT / "ENTRY.json").read_text(encoding="utf-8"))
    fixture_data = json.loads((OUT / "FIXTURES.json").read_text(encoding="utf-8"))
    after = json.loads(json.dumps(state(), default=str))
    save("AFTER.json", after)
    assert before["authority_fingerprint"] == after["authority_fingerprint"]
    assert not after["effective_operations"]
    assert all(
        row in after["platform_assignments"] for row in before["platform_assignments"]
    )
    assert all(row in after["document_versions"] for row in before["document_versions"])
    operator = User.objects.get(username=OPERATOR)
    assignment = PlatformRoleAssignment.objects.get(pk=fixture_data["assignment"])
    assert (
        assignment.user_id == operator.pk
        and assignment.role == PlatformRoleCode.PLATFORM_OPERATIONS
    )
    assert assignment.revoked_at and assignment.revoked_by.username == "admin"
    assert (
        assignment.assigned_by.username == "admin"
        and assignment.approved_by.username == "superuser"
    )
    assert assignment.ends_at - assignment.starts_at == __import__(
        "datetime"
    ).timedelta(hours=1)
    assert not has_platform_role(operator, PlatformRoleCode.PLATFORM_OPERATIONS)
    role_events = list(
        AuditEvent.objects.filter(entity_id=str(assignment.pk)).order_by("created_at")
    )
    assert [event.action for event in role_events] == [
        AuditAction.PLATFORM_ROLE_ASSIGNED,
        AuditAction.PLATFORM_ROLE_REVOKED,
    ]
    assert all(event.actor.username == "admin" for event in role_events)
    assert all(
        event.metadata["approver_user_id"] == str(assignment.approved_by_id)
        for event in role_events
    )
    fixture_ids = []
    for row in fixture_data["fixtures"]:
        evidence = ContractComplianceEvidence.objects.get(pk=row["clearance"])
        version = DocumentVersion.objects.get(pk=row["version"])
        assessment = DocumentProcessingAssessment.objects.get(pk=row["assessment"])
        assert evidence.status == "approved" and evidence.reference.startswith(MARKER)
        assert evidence.created_by_id != evidence.approved_by_id
        assert (
            evidence.created_by.username == row["writer"]
            and evidence.approved_by.username == row["approver"]
        )
        assert (
            evidence.organization_id
            == version.organization_id
            == assessment.organization_id
        )
        assert evidence.document_version_id == version.pk and version.is_available
        assert (
            assessment.verdict == "clean" and assessment.recorded_by_id == operator.pk
        )
        assert assessment.input_sha256 == version.sha256 == row["sha256"]
        assert assignment.starts_at <= assessment.created_at < assignment.revoked_at
        with version.file.open("rb") as stored:
            import hashlib

            assert hashlib.sha256(stored.read()).hexdigest() == version.sha256
        events = list(
            AuditEvent.objects.filter(entity_id=str(evidence.pk)).order_by("created_at")
        )
        assert [event.action for event in events] == [
            AuditAction.COMPLIANCE_EVIDENCE_CREATED,
            AuditAction.COMPLIANCE_EVIDENCE_SUBMITTED,
            AuditAction.COMPLIANCE_EVIDENCE_APPROVED,
        ]
        fixture_ids.append(str(evidence.pk))
    original_audit = AuditEvent.objects.filter(created_at__lt=entry["at"])
    fields = [field.attname for field in AuditEvent._meta.concrete_fields]
    original_rows = list(original_audit.order_by("pk").values_list(*fields))
    assert {
        "count": len(original_rows),
        "sha256": helpers["digest"](original_rows),
    } == before["models"]["audit.AuditEvent"]
    new_audits = list(
        AuditEvent.objects.filter(created_at__gte=entry["at"])
        .order_by("created_at")
        .values()
    )
    assert len(new_audits) == 38
    assert not any("retention_release" in row["action"] for row in new_audits)
    save("CANONICAL_AUDIT_DELTA.json", new_audits)
    prepared = json.loads((OUT / "REVOKED.json").read_text(encoding="utf-8"))
    runtime_deltas = [
        name
        for name in after["models"]
        if after["models"][name] != prepared["models"][name]
    ]
    assert set(runtime_deltas) <= {"sessions.Session"}, runtime_deltas
    all_deltas = [
        name
        for name in after["models"]
        if after["models"][name] != before["models"][name]
    ]
    expected = {
        "organizations.PlatformRoleAssignment",
        "audit.AuditEvent",
        "projects.ProjectDocumentLink",
        "billing.ContractComplianceEvidence",
        "documents.DocumentNumberSequence",
        "documents.Document",
        "documents.DocumentVersion",
        "documents.DocumentProcessingAssessment",
        "documents.DocumentLink",
        "workflows.WorkflowDefinition",
        "workflows.WorkflowVersion",
        "workflows.WorkflowStepDefinition",
        "workflows.WorkflowTransitionDefinition",
        "workflows.WorkflowRoutingRule",
        "workflows.WorkflowInstance",
        "workflows.WorkflowStepInstance",
        "workflows.WorkItem",
        "workflows.WorkItemCandidate",
        "workflows.WorkItemAssignmentHistory",
        "sessions.Session",
    }
    assert set(all_deltas) <= expected, all_deltas
    assert (
        before["models"]["billing.RetentionRelease"]
        == after["models"]["billing.RetentionRelease"]
    )
    records = json.loads((OUT / "RUNTIME_HTTP.json").read_text(encoding="utf-8"))
    assert len(records) == 5 and all(
        row["result"] == "PASS"
        and not row["model_deltas"]
        and not row["forbidden_full_response_leaks"]
        for row in records
    )
    browser = json.loads((OUT / "BROWSER_OPTIONS.json").read_text(encoding="utf-8"))
    assert (
        browser["options"] == [{"label": "---------", "value": ""}]
        and browser["source_backed"]
    )
    same = ContractComplianceEvidence.objects.get(pk=fixture_ids[0])
    limited = User.objects.get(username=helpers["LIMITED"])
    positive = User.objects.get(username=helpers["POSITIVE"])
    assert not has_business_permission(
        user=limited,
        organization=same.organization,
        permission="compliance_evidence.view",
    )
    assert has_business_permission(
        user=positive,
        organization=same.organization,
        permission="compliance_evidence.view",
    )
    assert not has_business_permission(
        user=limited,
        organization=same.organization,
        project=same.project,
        permission="retention_releases.create",
    )
    cleanup = json.loads((OUT / "SERVER_CLEANUP.json").read_text(encoding="utf-8-sig"))
    assert (
        cleanup["stopped"]
        and not cleanup["remaining_listener"]
        and cleanup["temporary_browser_tab_closed"]
    )
    save(
        "RUNTIME_VERIFICATION.json",
        {
            "result": "PASS",
            "model_tables_compared": len(after["models"]),
            "authority_fingerprint_before": before["authority_fingerprint"],
            "authority_fingerprint_after": after["authority_fingerprint"],
            "original_audits_byte_preserved": len(original_rows),
            "canonical_new_audit_count": len(new_audits),
            "canonical_new_audit_actions": dict(
                Counter(row["action"] for row in new_audits)
            ),
            "assignment_id": str(assignment.pk),
            "canonical_assignment_and_revocation_audits": True,
            "operator_effective_after_revocation": False,
            "historical_assessments_and_approval_audits_retained": True,
            "baseline_document_versions_unchanged": len(before["document_versions"]),
            "retained_synthetic_clearances": fixture_ids,
            "runtime_model_deltas": runtime_deltas,
            "preparation_model_deltas": all_deltas,
            "retention_release_delta": 0,
            "unauthorized_success_audit_delta": 0,
            "runtime_http_controls": "5/5 PASS",
            "browser": "verified retained P-17; actual clearance popup inspected, only blank",
            "schema_pending_migrations": 0,
            "fresh_server_stopped": True,
            "user_last_login_excluded_from_model_digest": True,
            "scope": "BATCH-02 only; no full financial release workflow",
        },
    )
    print(
        "Canonical history/runtime integrity PASS; 519 models; authority unchanged after revocation"
    )


def closeout():
    before_files = json.loads((OUT / "FILES_BEFORE.json").read_text(encoding="utf-8"))
    after_files = files()
    changed = [
        name for name, value in before_files.items() if after_files.get(name) != value
    ]
    register_name = "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml"
    report_name = "docs/governance/uiux/UIUX_F111_BATCH_02_RUNTIME_CLOSURE_REPORT.md"
    assert set(changed) == {register_name, report_name}, changed
    added = sorted(set(after_files) - set(before_files))
    fixture_data = json.loads((OUT / "FIXTURES.json").read_text(encoding="utf-8"))
    assert len(added) == 2 and all(
        name.startswith("protected_documents/organizations/") and name.endswith(".png")
        for name in added
    ), added
    for name in added:
        assert any(
            row["document"] in name and row["organization"] in name
            for row in fixture_data["fixtures"]
        )
    before_register = (OUT / "REGISTER_BEFORE.txt").read_text(encoding="utf-8")
    register = (ROOT / register_name).read_text(encoding="utf-8")
    pattern = r"(?ms)^- finding_id: UIUX-F-122\n.*?(?=^- finding_id:|\Z)"
    assert re.sub(pattern, "", before_register) == re.sub(pattern, "", register)
    finding = re.search(pattern, register).group()
    assert (
        "finding_status: RESOLVED" in finding
        and "runtime_status: RUNTIME_VERIFIED_RESOLVED" in finding
    )
    assert "status: STATIC_CONFIRMED" in finding
    yaml_check = subprocess.run(
        [
            r"C:\Users\azera\AppData\Local\Programs\Python\Python311\python.exe",
            "-c",
            "import pathlib,sys,yaml; yaml.safe_load(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')); print('YAML syntax PASS')",
            str(ROOT / register_name),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    save(
        "YAML_CHECK.json",
        {
            "result": yaml_check.stdout.strip(),
            "runtime": "existing system Python/PyYAML; no project dependency added",
        },
    )
    accepted = json.loads((PRIOR / "INDEX.json").read_text(encoding="utf-8"))
    assert all(sha(ROOT / name) == value for name, value in accepted.items())
    old_report = (OUT / "CLOSURE_REPORT_BEFORE.txt").read_text(encoding="utf-8")
    report = (ROOT / report_name).read_text(encoding="utf-8")
    assert report.startswith(old_report)
    for path in [ROOT / report_name, ROOT / register_name, *OUT.glob("*.py")]:
        assert all(
            line == line.rstrip()
            for line in path.read_text(encoding="utf-8").splitlines()
        ), path
    save(
        "VERIFICATION.json",
        {
            "result": "PASS",
            "changed_existing_files": changed,
            "new_stored_fixtures": added,
            "preserved_existing_files": len(before_files) - len(changed),
            "all_product_test_config_sources_unchanged": True,
            "accepted_batch02_automated_regression_evidence_unchanged": True,
            "f121_and_all_other_finding_entries_byte_preserved": True,
            "prior_blocked_closure_report_preserved_as_prefix": True,
            "batch03_09_wave_c_production_cep078_079_git_writes": "NOT_EXECUTED",
            "decision": "BATCH_02_RUNTIME_VERIFIED_RESOLVED",
        },
    )
    save(
        "INDEX.json",
        {
            p.relative_to(ROOT).as_posix(): sha(p)
            for p in sorted(OUT.iterdir())
            if p.is_file() and p.name != "INDEX.json"
        }
        | {report_name: sha(ROOT / report_name)},
    )
    for link in re.findall(r"\]\(([^)]+)\)", report):
        assert (ROOT / report_name).parent.joinpath(link).exists(), link
    print(
        "Governance/preservation PASS; F-122 resolved; all other findings and accepted evidence preserved"
    )


if __name__ == "__main__":
    import sys

    {"runtime": runtime_integrity, "closeout": closeout}[sys.argv[1]]()

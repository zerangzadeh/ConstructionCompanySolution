"""Authorized BATCH-02 Development fixture and runtime closure; no product edits."""

import hashlib
import json
import runpy
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
PRIOR = ROOT / "docs/governance/uiux/f111_batch_02_evidence"
helpers = runpy.run_path(str(PRIOR / "runtime_retest.py"), run_name="closure_helpers")
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from apps.accounts.models import User
from apps.billing.models import ContractComplianceEvidence
from apps.contracts.models import Contract
from apps.documents.models import (
    Document,
    DocumentProcessingAssessment,
    DocumentVersion,
)
from apps.documents.services import get_organization_document
from apps.organizations.authorization import (
    has_business_permission,
    has_platform_role,
)
from apps.organizations.models import (
    OrganizationMembership,
    PlatformRoleAssignment,
    PlatformRoleCode,
)
from apps.workflows.models import WorkflowVersion

MARKER = "BATCH_02_RUNTIME_CLOSURE_FIXTURE"
assert settings.SETTINGS_MODULE == "config.settings.development"
assert connection.settings_dict["NAME"] == "construction_erp"
assert connection.settings_dict["HOST"] in ("localhost", "127.0.0.1", "::1")


def save(name, data):
    (OUT / name).write_text(
        json.dumps(data, default=str, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def snapshot():
    return helpers["snapshot"]()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def file_snapshot():
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    return {
        name: sha(ROOT / name)
        for name in names
        if (ROOT / name).is_file()
        and not name.startswith(
            "docs/governance/uiux/f111_batch_02_runtime_closure_evidence/"
        )
    }


def inspect_sources():
    result = []
    for key, code, number in (
        ("C", "PRJ-01-03", "DOC-000005"),
        ("X", "PRJ-02-01", "DOC-000001"),
    ):
        contract = Contract.objects.select_related(
            "organization", "project", "party"
        ).get(
            project__code=code,
            contract_number__endswith="-05",
            status="active",
            party__isnull=False,
        )
        candidates = []
        for member in OrganizationMembership.objects.filter(
            organization=contract.organization, status="active", user__is_active=True
        ).select_related("user"):
            actor = member.user
            permissions = {
                permission: has_business_permission(
                    user=actor,
                    organization=contract.organization,
                    project=contract.project,
                    permission=permission,
                )
                for permission in (
                    "compliance_evidence.manage",
                    "compliance_evidence.submit",
                    "compliance_evidence.approve",
                )
            }
            if any(permissions.values()):
                candidates.append({"actor": actor.username, "permissions": permissions})
        writer = next(
            row["actor"]
            for row in candidates
            if row["actor"].endswith(".owner")
            and row["permissions"]["compliance_evidence.manage"]
            and row["permissions"]["compliance_evidence.submit"]
        )
        approver = next(
            (
                row["actor"]
                for row in candidates
                if row["actor"] != writer
                and row["permissions"]["compliance_evidence.approve"]
            ),
            None,
        )
        doc = Document.objects.select_related("current_version").get(
            organization=contract.organization, document_number=number
        )
        get_organization_document(
            user=User.objects.get(username=writer),
            organization=contract.organization,
            document_id=str(doc.pk),
        )
        # Unavailable versions cannot be supplied to the canonical clearance writer.
        existing = list(
            ContractComplianceEvidence.objects.filter(
                organization=contract.organization,
                evidence_kind="clearance",
                status="approved",
            ).values(
                "id",
                "reference",
                "contract_id",
                "project_id",
                "effective_from",
                "expires_on",
            )
        )
        result.append(
            {
                "key": key,
                "organization": contract.organization.slug,
                "contract": str(contract.pk),
                "contract_number": contract.contract_number,
                "project": code,
                "document": str(doc.pk),
                "version": str(doc.current_version_id),
                "version_sha256": doc.current_version.sha256,
                "version_available": doc.current_version.is_available,
                "writer": writer,
                "approver": approver,
                "eligible_actors": candidates,
                "existing_approved_clearances": existing,
                "published_workflow_versions": list(
                    WorkflowVersion.objects.filter(
                        organization=contract.organization,
                        definition__workflow_type__code="billing.compliance_evidence_approval",
                        status="published",
                    ).values_list("pk", flat=True)
                ),
            }
        )
    return result


def before():
    accepted = json.loads((PRIOR / "INDEX.json").read_text(encoding="utf-8"))
    drift = [
        name for name, expected in accepted.items() if sha(ROOT / name) != expected
    ]
    assert not drift, drift
    prior_entry = json.loads((PRIOR / "ENTRY.json").read_text(encoding="utf-8"))
    source_names = [
        name
        for name in prior_entry["hashes"]
        if name.startswith(("apps/", "core/", "config/", "templates/", "tests/"))
    ]
    unexpected = [
        name
        for name in source_names
        if sha(ROOT / name) != accepted.get(name, prior_entry["hashes"][name])
    ]
    assert not unexpected, unexpected
    register = (ROOT / "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml").read_text(
        encoding="utf-8"
    )
    f121 = register.split("- finding_id: UIUX-F-121\n", 1)[1].split(
        "- finding_id: UIUX-F-122\n", 1
    )[0]
    f122 = register.split("- finding_id: UIUX-F-122\n", 1)[1].split(
        "- finding_id: UIUX-F-123\n", 1
    )[0]
    assert (
        "finding_status: RESOLVED" in f121
        and "runtime_status: RUNTIME_VERIFIED_RESOLVED" in f121
    )
    assert (
        "finding_status: OPEN" in f122
        and "runtime_status: REMEDIATION_IMPLEMENTED_PENDING_RUNTIME_RETEST" in f122
    )
    state = helpers["preflight"]()
    pending = MigrationExecutor(connection)
    assert not pending.migration_plan(pending.loader.graph.leaf_nodes())
    diagnostics = {
        "document_versions": DocumentVersion.objects.count(),
        "processing_assessments": DocumentProcessingAssessment.objects.count(),
        "available_versions_in_required_tenants": sum(
            row["version_available"] for row in inspect_sources()
        ),
        "active_platform_operations_actors": [
            a.user.username
            for a in PlatformRoleAssignment.objects.filter(
                role=PlatformRoleCode.PLATFORM_OPERATIONS
            ).select_related("user")
            if has_platform_role(a.user, PlatformRoleCode.PLATFORM_OPERATIONS)
        ],
        "canonical_writer_requires_available_version": True,
        "canonical_assessment_requires_explicit_platform_operations": True,
    }
    assert (
        diagnostics["processing_assessments"] == 0
        and not diagnostics["active_platform_operations_actors"]
    )
    save(
        "PREREQUISITE_BLOCKER.json",
        diagnostics
        | {
            "blocker": "NO_CANONICALLY_AVAILABLE_DOCUMENT_VERSION_AND_NO_EXISTING_PLATFORM_OPERATIONS_AUTHORITY",
            "original_blocker": "NO_QUALIFYING_COMPLIANCE_EVIDENCE_RUNTIME_FIXTURE",
            "fixture_writes": 0,
            "authority_writes": 0,
            "product_writes": 0,
            "browser_status": "NOT_EXECUTED_FIXTURE_PREREQUISITE_BLOCKED",
        },
    )
    save(
        "ENTRY.json",
        {
            "at": timezone.now(),
            "branch": git("branch", "--show-current"),
            "head": git("rev-parse", "HEAD"),
            "upstream": git("rev-parse", "@{upstream}"),
            "divergence": git(
                "rev-list", "--left-right", "--count", "HEAD...@{upstream}"
            ),
            "dirty_state": git("status", "--short"),
            "diff_names": git("diff", "--name-status"),
            "accepted_evidence_drift": drift,
            "accepted_source_drift": unexpected,
            "source_hashes": {name: sha(ROOT / name) for name in source_names},
            "accepted_tests_repeated": False,
            "runtime": state,
            "fixture_sources": inspect_sources(),
            "actual_touch_set": [
                "new closure report/evidence",
                "UIUX-F-122 entry only",
                "read-only Development prerequisite inspection; no fixture/authority writes performed",
            ],
            "product_mutation": False,
            "blocker": diagnostics,
        },
    )
    save("FILES_BEFORE.json", file_snapshot())
    save("MODELS_BEFORE.json", snapshot())
    (OUT / "REGISTER_BEFORE.txt").write_bytes(
        (ROOT / "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml").read_bytes()
    )
    print("Accepted source/evidence unchanged; authorization/data preflight recorded")


if __name__ == "__main__":
    assert sys.argv[1] == "before"
    before()

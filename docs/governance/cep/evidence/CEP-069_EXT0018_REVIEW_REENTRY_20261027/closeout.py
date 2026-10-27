"""Reconcile only the authorized CEP-069 records after measured qualification."""

import csv
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

import yaml

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
PREFIX = OUT.relative_to(ROOT).as_posix()
QUAL = PREFIX + "/QUALIFICATION_RESULT.json"
REVIEW = (
    "docs/governance/cep/evidence/CEP-069_EXT0018_20261027/ADOPTED_EXPERT_REVIEW.md"
)
q = json.loads((OUT / "QUALIFICATION_RESULT.json").read_text("utf-8"))
assert q["nonproduction_qualification"] == "PASS" and q["database_removed"]
assert q["business_database_before"] == q["business_database_after"]
assert json.loads((OUT / "REMEDIATION_RESULT.json").read_text("utf-8"))["failures"] == 0
path = ROOT / "CEP_EXECUTION_REGISTRY.yaml"
raw = path.read_text("utf-8")
registry = yaml.safe_load(raw)
before = {key: value for key, value in registry["ceps"].items() if key != "CEP-069"}
c = registry["ceps"]["CEP-069"]
c["eligibility_status"] = "EXECUTED_HUMAN_APPROVED_NONPRODUCTION_QUALIFICATION"
c["authorization"] = {
    "status": "AUTHORIZED_BOUNDED_NONPRODUCTION",
    "authorization_id": "EXT0018-HUMAN-ADOPTED-20261027",
    "source": REVIEW,
    "scope": "Necessary Development remediation; isolated source-linked activation and CEP069 qualification; no Production/final Sign-off/Git writes",
}
c["execution"] = {
    "status": "COMPLETE",
    "lifecycle": "EXECUTION_COMPLETE_APPROVED_NONPRODUCTION_QUALIFICATION",
    "advisor_review": "HUMAN_ADOPTED_CONDITIONAL_DECISION_IMPLEMENTED_AND_VERIFIED",
}
c["acceptance"] = {
    "passed": 5,
    "total": 5,
    "status": "PASS_APPROVED_NONPRODUCTION_QUALIFICATION_ONLY",
}
c["dod"] = "MET_APPROVED_NONPRODUCTION_SCOPE"
c["blockers"] = []
c["remaining_utv"] = [
    "configured_business_environment_migration_and_persistent_activation_NOT_EXECUTED",
    "actual_Production_currentness_population_and_operating_evidence",
    "Human_final_Production_signoff_and_certification",
    "Production_deployment_migration_cutover_NOT_AUTHORIZED",
]
c["statutory_intake"] = {
    "status": "HUMAN_ADOPTED_CONDITIONS_VERIFIED_NONPRODUCTION_ACTIVATION_QUALIFIED",
    "evidence": QUAL,
    "historical_review_package": "docs/governance/cep/evidence/CEP-069_EXT0018_20261027/EXT0018_SOURCE_REVIEW_PACKAGE.json",
    "adopted_expert_review": REVIEW,
    "human_disposition": "APPROVED_WITH_CONDITIONS",
    "conditions_evidence": PREFIX + "/CONDITIONS_VERIFIED.json",
    "accepted_review": "Human conditional adoption retained; distinct accepted technical condition verification under prior explicit authority; no new Human decision or professional credential",
    "runtime_import_or_activation": "FOUR_SOURCE_LINKED_PACKAGES_EXPLICITLY_PUBLISHED_IN_DISPOSABLE_DEVELOPMENT_DATABASE_REMOVED_AFTER_VERIFICATION",
    "business_database_packages": 0,
    "business_database_new_migration": "0010_PENDING_NOT_APPLIED_TO_BUSINESS_DATABASE",
    "production_activation": "NOT_AUTHORIZED_NOT_EXECUTED",
    "blocker_classes": [],
}
c["completion_report"]["evidence_presence"] = (
    "CONFIRMED_IMPLEMENTATION_AND_APPROVED_NONPRODUCTION_QUALIFICATION"
)
c["git"]["current_session_documentation_committed"] = False
c["git"]["current_session_implementation_committed"] = False
history = {
    "date": "2026-10-27",
    "status": "COMPLETE_APPROVED_NONPRODUCTION_QUALIFICATION",
    "reason": "Direct Human-adopted review and implementation authority retained; conditions1-10 verified;36 behavioral tests PASS; four explicit source-linked publications, five native statutory calculations, source-specific history/housing correction delta and migration rollback/reapply PASS in disposable Development; no Production or Git writes.",
    "evidence": QUAL,
}
if history not in c["history"]:
    c["history"].append(history)
c["frontier_review"] = {
    "at": "2026-10-27",
    "head": "a1322c38e5c89d399c6ba54c239444a2b61c119a",
    "evidence": QUAL,
    "result": "ALL_APPROVED_NONPRODUCTION_CONDITIONS_AND_SCOPED_AC_DOD_PASS",
    "blocker_class": None,
    "smallest_remaining_prerequisite": "No in-scope prerequisite; actual Production qualification and final Human Sign-off remain separate.",
    "blocker_classes": [],
}


def replace_block(text, key, data):
    pattern = rf"(?ms)^  {re.escape(key)}:\n.*?(?=^  [A-Za-z0-9_-]+:|^\S|\Z)"
    block = yaml.safe_dump({key: data}, allow_unicode=True, sort_keys=False, width=140)
    block = "".join("  " + line + "\n" for line in block.splitlines())
    result, count = re.subn(pattern, lambda match: block, text, count=1)
    assert count == 1, key
    return result


raw = replace_block(raw, "CEP-069", c)
gate = registry["gates"]["GATE-11"]
gate["statutory_intake_evidence"] = QUAL
gate["required_imb_status"]["IMB-0083"] = (
    "PASS_HUMAN_APPROVED_NONPRODUCTION_SOURCE_ACTIVATION_QUALIFICATION_PRODUCTION_NOT_CERTIFIED"
)
gate["note"] = (
    "EXT0018 Human-adopted conditions implemented and verified; CEP069 approved non-production contribution PASS. Other retained contributions unchanged. Actual Production evidence/final Human certification remain separate; GATE11 NOT_PASSED."
)
gate_history = {
    "date": "2026-10-27",
    "status": "NOT_PASSED",
    "reason": "CEP069 IMB0083 now qualified only in Human-approved disposable Development scope; no actual Production certification or final Human Sign-off.",
    "evidence": QUAL,
}
if gate_history not in gate["history"]:
    gate["history"].append(gate_history)
raw = replace_block(raw, "GATE-11", gate)
counts = Counter(
    value["execution"]["status"]
    for key, value in registry["ceps"].items()
    if int(key.split("-")[1]) <= 79
)
assert counts == Counter({"COMPLETE": 79})
raw = raw.replace(
    "  execution_state_complete: 78\n", "  execution_state_complete: 79\n", 1
).replace("  partial_current: 1\n", "  partial_current: 0\n", 1)
raw = re.sub(
    r"(?m)^  pending_checkpoint_scope:.*$",
    "  pending_checkpoint_scope: CEP069_EXT0018_HUMAN_ADOPTED_REMEDIATION_AND_NONPRODUCTION_QUALIFICATION_UNCOMMITTED",
    raw,
    count=1,
)
state = registry["repository_state"]
state["pending_checkpoint_scope"] = (
    "CEP069_EXT0018_HUMAN_ADOPTED_REMEDIATION_AND_NONPRODUCTION_QUALIFICATION_UNCOMMITTED"
)
state["metadata_boundary"] = (
    "HEAD and cached origin/main unchanged at a1322c3; prior Human checkpoint retained. Current CEP069 code/migration/decision/evidence closeout uncommitted; no Git write or live remote assertion."
)
repo_block = yaml.safe_dump(
    {"repository_state": state}, sort_keys=False, allow_unicode=True, width=140
)
raw = re.sub(
    r"(?ms)^repository_state:\n.*?(?=^execution_frontier:)",
    lambda match: repo_block,
    raw,
    count=1,
)
front = registry["execution_frontier"]
front.update(
    dependency_ready_current_governed=[],
    current_session_continuation="STOP_CLEAN_COMPLETED_PROGRAM_BOUNDARY_NO_FURTHER_AUTHORIZED_CEP",
    boundary_reason="All79 current-governed CEPs COMPLETE in their recorded bounded scopes; CEP069 conditional Human review implemented and isolated activation qualified. GATE11 remains NOT_PASSED; Production/final Sign-off/Git/PostV1 excluded.",
    resume_cep_after_blocker_resolution=None,
    independent_candidates_entry_status="001..079_COMPLETE_RECORDED_SCOPES;080..086_DEFERRED_POST_V1",
    unblock_conditions={},
    reconciliation_evidence=QUAL,
)
front_block = yaml.safe_dump(
    {"execution_frontier": front}, sort_keys=False, allow_unicode=True, width=140
)
raw = re.sub(
    r"(?ms)^execution_frontier:\n.*\Z", lambda match: front_block, raw, count=1
)
parsed = yaml.safe_load(raw)
assert {
    key: value for key, value in parsed["ceps"].items() if key != "CEP-069"
} == before
assert parsed["gates"]["GATE-11"]["status"] == "NOT_PASSED"
assert parsed["execution_frontier"]["next_executable_frontier"] == []
path.write_text(raw, encoding="utf-8")

accept = ROOT / "docs/governance/cep/evidence/CEP-069_ACCEPTANCE_MAPPING.csv"
rows = list(csv.DictReader(accept.read_text("utf-8").splitlines()))
for row in rows:
    row["status"] = "PASS_APPROVED_NONPRODUCTION_QUALIFICATION_ONLY"
    row["evidence"] = (
        "CEP-069-EV-010;CEP-069-EV-011;CEP-069-EV-012;CEP-069-EV-013;CEP-069-EV-014"
    )
with accept.open("w", encoding="utf-8", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

manifest = ROOT / "docs/governance/cep/evidence/CEP-069_EVIDENCE_MANIFEST.csv"
existing = list(csv.reader(manifest.read_text("utf-8").splitlines()))
existing = [
    row
    for row in existing
    if not row or row[0] not in {f"CEP-069-EV-{n:03}" for n in range(10, 15)}
]
existing.extend(
    [
        [
            "CEP-069-EV-010",
            "Human conditional adoption",
            REVIEW
            + ";docs/governance/cep/supporting/EXT-0018_HUMAN_REVIEW_20261027.md",
            "Direct Human findings and expanded nonproduction implementation/activation authority; no Production/Git authority",
            "RECORDED_HUMAN_APPROVED_WITH_CONDITIONS",
        ],
        [
            "CEP-069-EV-011",
            "Adopted source mappings and conditions",
            PREFIX
            + "/CONDITIONS_VERIFIED.json;SOURCE_VERSION_DELTAS.json;TAX_PARAMETERS.json;INSURANCE_PARAMETERS.json;IMPLEMENTATION_BOUNDARY.md",
            "Superseding official housing retained; annual/YTD/profile/rounding/effective and component boundaries explicit",
            "PASS_APPROVED_NONPRODUCTION_SCOPE",
        ],
        [
            "CEP-069-EV-012",
            "Remediation and regression",
            PREFIX + "/REMEDIATION_TESTS.txt;REMEDIATION_RESULT.json",
            "36/36 cases PASS including inherited source framework and new adopted-condition paths; disposable target removed",
            "PASS",
        ],
        [
            "CEP-069-EV-013",
            "Actual isolated source-linked activation and delta",
            QUAL + ";QUALIFICATION_RUNTIME.txt;RUNTIME_SOURCE_PACKAGES.json",
            "Four published packages;five native calculations;31day floor/cap;annual oracle;housing replacement delta;rollback/reapply;business DB unchanged;test DB removed",
            "PASS_ISOLATED_DEVELOPMENT_ONLY",
        ],
        [
            "CEP-069-EV-014",
            "Integrity and program closeout",
            PREFIX + "/FINAL_CHECKS.json;ARTIFACT_HASHES.csv;ATTEMPTS.md",
            "Original37 source artifacts unchanged;review/payload/code hashes;checks;AC5/5;79complete;GATE11NOT_PASSED;frontier empty;noGit/Production",
            "PASS_SCOPED_NOT_PRODUCTION_CERTIFICATION",
        ],
    ]
)
with manifest.open("w", encoding="utf-8", newline="") as stream:
    csv.writer(stream).writerows(existing)

changed = subprocess.check_output(
    ["git", "diff", "--name-only"], cwd=ROOT, text=True
).splitlines()
untracked = subprocess.check_output(
    ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT, text=True
).splitlines()
allowed_code = {
    "apps/organizations/policy_specs.py",
    "apps/payroll/models.py",
    "apps/payroll/source_package_services.py",
    "apps/payroll/statutory_services.py",
    "apps/payroll/statutory_governance.py",
    "apps/payroll/test_cep069.py",
    "apps/payroll/migrations/0010_cep069_reviewed_statutory_context.py",
}
paths = sorted(
    set(
        changed
        + untracked
        + [PREFIX + "/FINAL_CHECKS.json", PREFIX + "/ARTIFACT_HASHES.csv"]
    )
)
assert all(
    p == "CEP_EXECUTION_REGISTRY.yaml"
    or p in allowed_code
    or p.startswith("docs/governance/cep/")
    and "CEP-069" in p
    or p == "docs/governance/cep/supporting/EXT-0018_HUMAN_REVIEW_20261027.md"
    for p in paths
)
with (ROOT / "docs/governance/cep/manifests/CEP-069_CHANGE_MANIFEST.csv").open(
    "w", encoding="utf-8", newline=""
) as stream:
    writer = csv.writer(stream)
    writer.writerow(["path", "purpose"])
    for p in paths:
        purpose = (
            "Human-adopted bounded statutory remediation and qualification evidence"
        )
        if p in allowed_code:
            purpose = "Implement and test adopted annual YTD/profile/opening/source/rounding conditions; additive schema only"
        elif "CEP-069_EXT0018_20261027/" in p and not p.endswith(
            "ADOPTED_EXPERT_REVIEW.md"
        ):
            purpose = "Preserved historical official source-intake artifact; original hashes/catalog unchanged"
        writer.writerow([p, purpose])
print(
    json.dumps(
        {
            "CEP069": "COMPLETE_APPROVED_NONPRODUCTION",
            "AC": "5/5",
            "counts": dict(counts),
            "gate11": "NOT_PASSED",
            "frontier": [],
            "other_cep_records_unchanged": True,
            "git_writes": "NONE",
        }
    )
)

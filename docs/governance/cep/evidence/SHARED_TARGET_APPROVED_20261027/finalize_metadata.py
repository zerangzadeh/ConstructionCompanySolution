"""Reconcile only approved shared-target closeout metadata; no Git mutations."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
PREFIX = OUT.relative_to(ROOT).as_posix()
AUTHORITY = "docs/governance/cep/supporting/BONIRA-PE-NP-01_HUMAN_APPROVAL_20261027.md"
PROFILE = (
    "docs/governance/cep/supporting/SHARED_PRODUCTION_EQUIVALENT_TARGET_PROFILE.md"
)
registry_path = ROOT / "CEP_EXECUTION_REGISTRY.yaml"
registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
registry["human_decisions"]["BONIRA-PE-NP-01-HUMAN-20261027"] = {
    "source": AUTHORITY,
    "authority": "HUMAN_DECISION_AUTHORITY / Product Owner",
    "status": "APPROVED",
    "scope": "One bounded Linux production-equivalent non-production reference; permitted differences; reversible provisioning and 070→074 plus075 execution",
    "production_authorized": False,
    "git_writes_authorized": False,
    "human_signoff_authorized": False,
}
registry["repository_state"]["pending_checkpoint_scope"] = (
    "PRIOR_DIRTY_WORK_PRESERVED;APPROVED_SHARED_LINUX_TARGET_CEP070_CEP074_CEP075_COMPLETE_UNCOMMITTED"
)
registry["repository_state"]["metadata_boundary"] = (
    "Existing main/origin main de6e208 retained; prior dirty work preserved. "
    "Approved shared Linux target qualification and selected070/074/075 closeout uncommitted; "
    "no Git write or fresh remote query. Historical integration checkpoint is not this execution."
)
registry["execution_frontier"]["independent_candidates_entry_status"] = (
    "069_PARTIAL_EXTERNAL_STATUTORY_PRODUCTION;070_074_075_COMPLETE_APPROVED_LINUX_REFERENCE;"
    "071_072_076_COMPLETE_RETAINED_DEVELOPMENT;073_077_078_079_COMPLETE_NOT_RERUN"
)
gate11 = registry["gates"]["GATE-11"]
gate11["contributor_evidence"]["CEP-070"] = PREFIX + "/runtime/070_RESULT.json"
gate11["relevant_implementation_convergence"]["CEP-075"] = {
    "status": "PASS_APPROVED_PARENT_AND_EXECUTED_NONPRODUCTION_REFERENCE",
    "parent_evidence": "docs/governance/cep/evidence/CEP-071_EXT0021_APPROVED_20261027/RESULT.json",
    "evidence": PREFIX + "/runtime/075_RESULT.json",
    "production_equivalent_target": "BONIRA-PE-NP-01_APPROVED_AND_QUALIFIED_BOUNDED_NONPRODUCTION",
    "global_gate_pass_inferred": False,
    "production_authorized": False,
}
registry_path.write_text(
    yaml.safe_dump(registry, sort_keys=False, allow_unicode=True, width=140),
    encoding="utf-8",
)

for phase in ("070", "074", "075"):
    manifest = ROOT / f"docs/governance/cep/manifests/CEP-{phase}_EXECUTION_MANIFEST.md"
    marker = "## Approved shared-reference final closeout"
    value = manifest.read_text(encoding="utf-8")
    if marker not in value:
        value += (
            f"\n\n{marker}\n\n"
            f"[Executed result](../evidence/SHARED_TARGET_APPROVED_20261027/runtime/{phase}_RESULT.json), "
            f"[verified closeout](../evidence/SHARED_TARGET_APPROVED_20261027/{phase}_CLOSEOUT.json): "
            "COMPLETE, six canonical AC PASS, scoped DoD MET on BONIRA-PE-NP-01. "
            "Earlier pending/partial entries above are dated history, superseded for this scope. "
            "Exact executed tools, failures, target checks, final consistency and shutdown evidence "
            "are retained in the same directory. No product/schema/permission/migration change, "
            "Production action, Human Sign-off, final certification, unrelated COMPLETE CEP rerun "
            "or Git write. GATE08 PASS for accepted bounded evidence;GATE11 NOT_PASSED. "
            "Final next_executable_frontier: `[]`.\n"
        )
        manifest.write_text(value, encoding="utf-8")
    changes = (
        ROOT / "docs/governance/cep/manifests/CEP-070_CHANGE_MANIFEST.csv"
        if phase == "070"
        else ROOT / f"docs/governance/cep/evidence/CEP-{phase}_CHANGE_MANIFEST.csv"
    )
    if not changes.exists():
        changes.write_text("path,change,reason\n", encoding="utf-8")
    value = changes.read_text(encoding="utf-8")
    if PREFIX not in value:
        value += f"{PREFIX}/,ADDED,ACTUAL_APPROVED_LINUX_REFERENCE_QUALIFICATION_AND_CLOSEOUT\n"
        value += f"{AUTHORITY},ADDED,DIRECT_HUMAN_REFERENCE_AND_EXECUTION_AUTHORITY\n"
        value += f"{PROFILE},UPDATED,ONE_APPROVED_QUALIFIED_SHARED_REFERENCE\n"
        value += f"docs/governance/cep/reports/CEP-{phase}_COMPLETION_REPORT.md,UPDATED,AC6OF6_SCOPED_DOD_MET\n"
        value += "CEP_EXECUTION_REGISTRY.yaml,UPDATED,SELECTED_CEPS_RELEVANT_GATES_FRONTIER_ONLY\n"
        changes.write_text(value, encoding="utf-8")
    evidence = ROOT / f"docs/governance/cep/evidence/CEP-{phase}_EVIDENCE_MANIFEST.csv"
    value = evidence.read_text(encoding="utf-8")
    if PREFIX + "/CHECKS.json" not in value:
        if phase == "070":
            value += f"CEP-070-EV-019,{PREFIX}/CHECKS.json,PASS,BOUNDED_NONPRODUCTION_FINAL_CONSISTENCY_ONLY\n"
        else:
            evidence_id = "002" if phase == "074" else "010"
            value += f"CEP-{phase}-EV-{evidence_id},FINAL_CONSISTENCY,{PREFIX}/CHECKS.json,PASS_BOUNDED_NONPRODUCTION\n"
        evidence.write_text(value, encoding="utf-8")

old_runbook = (
    ROOT / "docs/governance/cep/supporting/CEP-070_DEVELOPMENT_RECOVERY_RUNBOOK.md"
)
value = old_runbook.read_text(encoding="utf-8")
notice = (
    "> Historical Windows Development procedure. Current approved Linux shared-reference "
    "procedure/evidence: [BONIRA-PE-NP-01](SHARED_PRODUCTION_EQUIVALENT_TARGET_PROFILE.md). "
    "This retained procedure does not define a second production-equivalent target.\n\n"
)
if notice not in value:
    old_runbook.write_text(notice + value, encoding="utf-8")
print("Selected Registry/profile/manifests reconciled; no lifecycle/Gate expansion.")

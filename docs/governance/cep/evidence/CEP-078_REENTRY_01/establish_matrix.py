"""Define canonical coverage without substituting an available-browser subset."""
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
UI = ROOT / "docs/governance/uiux"
gate = json.loads((OUT / "GATE07_CONVERGENCE.json").read_text(encoding="utf-8"))
assert gate["decision"] == "PASS_FOR_CEP078_DEVELOPMENT_IMPLEMENTED_CAPABILITY_SCOPE"
inventory = json.loads((OUT / "BROWSER_INSTALLATIONS.json").read_text(encoding="utf-8-sig"))
application = json.loads((OUT / "APPLICATION_IDENTITY.json").read_text(encoding="utf-8"))
assert inventory["safari_provider"] == "NONE_IN_AVAILABLE_CUA_INVENTORY"
matrix_path = UI / "UIUX_RUNTIME_VALIDATION_MATRIX.yaml"
matrix_text = matrix_path.read_text(encoding="utf-8")
source_blocks = re.findall(r"^- scenario_id: (RV-\d{3})\n(.*?)(?=^- scenario_id:|\Z)", matrix_text, re.M | re.S)
assert len(source_blocks) == 33
scenarios = []
for i, (rv, text) in enumerate(source_blocks, 1):
    scenarios.append({
        "cep_scenario_id": f"CEP-078-SC-{i:03d}", "source_scenario": rv,
        "source_role": "Scenario/route/persona planning input only; original RV results never relabeled CEP execution",
        "canonical_input_block": text, "block_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "browser_dimensions": ["Chrome", "Edge", "Safari"],
        "runtime_topics_only": "Browser/authenticated rendering; shared responsive/navigation/overflow; keyboard/focus; labels/headings/landmarks/table/form/error semantics; RTL/LTR/Jalali; console/runtime errors. Existing business scenarios supply states, not authority to redo domain transactions.",
        "personas_and_routes": "Use the exact source block and current canonical persona/fixture registries; no role substitution or all-persona universal claim",
        "state_and_data_gate": "Existing safe source-owned state required; missing/expired fixture stays BLOCKED/UTV; no policy/grant/identity/business-state mutation",
        "responsive_rule": "Original scenario requirements plus representative cross-role RV-025 surfaces at all three canonical CSS viewports; no arbitrary device or route reduction",
        "execution_result": "UTV_ENTRY_BLOCKED",
    })
sources = [
    "docs/governance/cep/PROMPTS/CEP-078_EXECUTION_PROMPT.md", "docs/ui-guidelines.md",
    "docs/governance/uiux/UIUX_RUNTIME_VALIDATION_EXECUTION_PLAYBOOK.md",
    "docs/governance/uiux/UIUX_RUNTIME_VALIDATION_MATRIX.yaml",
    "docs/governance/uiux/UIUX_RUNTIME_PERSONA_DATA_MATRIX.yaml",
    "docs/governance/uiux/UIUX_RUNTIME_FIXTURE_REGISTRY.yaml",
]
result = {
    "at": datetime.now(timezone(timedelta(hours=3, minutes=30))).isoformat(),
    "status": "DEFINED_CANONICAL_COVERAGE_NOT_ENVIRONMENT_READY",
    "approval_semantics": "Current Human authorizes defining/proving the canonical CEP matrix. Codex derives technical planning under standing authority; no Human approval, support-policy exception or exclusion is fabricated. Execution approval remains conditional on all readiness evidence.",
    "canonical_browser_basis": gate["canonical_browser_gap"],
    "basis_interpretation": "UIGAP-025 expressly names unverified Chrome/Edge/Safari behavior for all critical journeys. All three remain in the plan; no approved exclusion/substitution was found. This preserves the named gap, without inventing supported release numbers or a new Firefox requirement.",
    "browsers": [
        {"name": b, "required_identity": "Actual browser product/full version, engine/runtime build, OS/device identity and observation tied to each execution", "installed_version": next((r["product_version"] for r in inventory["installed_browsers"] if r["browser"] == b), None), "observed_runtime_version": None, "readiness": "BLOCKED_NO_AVAILABLE_RUNTIME_PROVIDER_OR_VERSION" if b == "Safari" else "PARTIAL_INSTALLED_BINARY_IDENTIFIED_NOT_EXECUTED"}
        for b in ("Chrome", "Edge", "Safari")
    ],
    "viewports_css": [{"class": "desktop", "width": 1440, "height": 900}, {"class": "tablet_narrow_desktop", "width": 1024, "height": 768}, {"class": "mobile", "width": 390, "height": 844}],
    "device_rule": "These are CSS viewport classes, not claims of physical-device certification. Record actual OS/device/emulation per execution. Safari OS/device/full browser build remains unavailable; do not label a Windows viewport emulation or generic WebKit as Safari evidence.",
    "accessibility_basis": "docs/ui-guidelines.md section 49: WCAG 2.2 AA product target; keyboard/visible focus/RTL order, safe Escape/focus return, programmatic labels/errors, semantic headings/landmarks/tables, mixed-direction isolation, reduced motion. Target is not a conformance claim.",
    "scope_sources": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources},
    "scenario_plan": scenarios,
    "prerequisite_convergence": "GATE07_CONVERGENCE.json 19/19 implemented contributions, 42 current cases PASS; global/conditional activations not granted",
    "application_identity": {"artifact": "APPLICATION_IDENTITY.json", "head": application["head"], "dirty_source_manifest_sha256": application["source_manifest_sha256"], "files": application["dirty_source_files"]},
    "environment_inventory": "BROWSER_INSTALLATIONS.json; sanitized CUA provider inventory, no unrelated tab metadata retained",
    "exact_remaining_blocker": "EXT-0024 cannot be established: Safari target runtime/provider with exact OS/device/browser/engine version is absent from available test surfaces. Chrome/Edge installed versions do not prove observed execution identities. Full matrix readiness remains UTV, not reduced to available Chromium providers.",
    "next_safe_action": "Make the named canonical Safari environment and exact runtime identities available through an approved test surface, bind safe fixture/persona/state coverage and recheck all browser identities, then repeat CEP entry. No product or support-policy change is required by this plan.",
    "business_mutations": "NONE; read/focus/invalid-input observations only unless separately governed disposable state is proved",
    "entry": "BLOCKED_EXT0024; no CEP runtime scenario executed",
    "old_audit_evidence": "Retained for provenance/exact-scope reuse analysis only; no relabeling or duplicate runtime replay",
}
(OUT / "EXT0024_MATRIX.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
entry_review = {
    "at": result["at"], "formal_execution_entry": "NOT_PASSED_EXT0024; both blockers did not clear, so execution was not started",
    "implementation_prerequisites": "CEP003/017 available; unchanged canonical edges DEP0018/0019/0020",
    "gate07": "PASS_FOR_CEP078_DEVELOPMENT_IMPLEMENTED_CAPABILITY_SCOPE; global activation NOT_READY retained",
    "finding_001": "RESOLVED_SCOPED_ENTRY_CONVERGENCE",
    "ext0024": "PARTIAL_MATRIX_DEFINED; BLOCKED_SAFARI_RUNTIME_AND_EXACT_IDENTITIES",
    "finding_002": "OPEN_WITH_EXACT_ENVIRONMENT_GAP",
    "runtime_execution": "NOT_STARTED", "ac": "0/6 UNEXECUTED", "dod": "NOT_MET_ENTRY_BLOCKED",
    "supported_terminal_state": "BLOCKED_BEFORE_ENTRY", "canonical_report_verdict": "EXECUTION FAILED; entry blocker, not failed browser verification",
    "gate08": "NOT_PASSED_RETAINED; exit gate, no extra entry prerequisite",
    "existing_evidence_reuse": "Original accepted Wave D/E/RV025 evidence preserved; no old RV result promoted to CEP runtime PASS",
    "prior_blocked_review": "../CEP-078_ENTRY_REVIEW.json and original report/manifests preserved byte-for-byte",
    "next": result["next_safe_action"],
}
(OUT / "ENTRY_REVIEW.json").write_text(json.dumps(entry_review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("EXT0024: 3 named browsers / 3 viewport classes / 33 critical-journey source scenarios retained; Safari runtime readiness BLOCKED; CEP runtime NOT_STARTED.")

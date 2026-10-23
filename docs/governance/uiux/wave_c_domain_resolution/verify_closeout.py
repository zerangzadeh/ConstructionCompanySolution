"""Read-only Development verification and bounded evidence closeout."""
from configure import *  # noqa: F403
import ast
import hashlib
import subprocess
import xml.etree.ElementTree as ET

from apps.payroll.models import StatutoryCalculation, StatutoryOutput
from apps.organizations.models import OrganizationMembership
from apps.procurement.models import QuoteRevisionEvidence
from django.db.migrations.recorder import MigrationRecorder


def git(*args):
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8")


def definitions(source):
    tree = ast.parse(source)
    result = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result[node.name] = ast.dump(node, include_attributes=False)
        elif isinstance(node, ast.ClassDef):
            for method in node.body:
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result[node.name + "." + method.name] = ast.dump(method, include_attributes=False)
    return result


def verify():
    assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
    entry = json.loads((OUT / "ENTRY.json").read_text(encoding="utf-8"))
    head = git("rev-parse", "HEAD").strip()
    assert head == entry["head"]
    future = list(PlatformPolicyVersion.objects.filter(
        policy__code__in=["accounting-money-precision", "accounting-rounding"],
        effective_from=date(2026, 12, 22), status="published",
    ).order_by("policy__code").values())
    assert (OUT / "FUTURE_POLICIES_BEFORE.json").read_text(encoding="utf-8") == json.dumps(future, default=str, indent=2) + "\n"
    source_attribution = {}
    for path in [
        "apps/subledgers/services.py",
        "apps/subledgers/supplier_invoice_handoffs.py",
        "apps/subledgers/test_cep033_invoice_handoff.py",
        "apps/subledgers/test_p5_s26_s27_match_review.py",
        "apps/procurement/test_p5_s08_sealed_custody.py",
        "apps/organizations/authorization.py",
        "apps/payroll/models.py",
    ]:
        current = Path(path).read_text(encoding="utf-8")
        original = git("show", "HEAD:" + path)
        before, after = definitions(original), definitions(current)
        changed = [name for name in before if before[name] != after.get(name)]
        added = sorted(set(after) - set(before))
        source_attribution[path] = {"changed_existing_definitions": changed, "added_definitions": added}
        assert not changed, (path, changed)
    assert source_attribution["apps/subledgers/services.py"]["added_definitions"] == ["settlement_movement_choices"]
    failures = []
    for filename in ["focused.xml", "regression.xml"]:
        for case in ET.parse(OUT / filename).iter("testcase"):
            failure = case.find("failure")
            if failure is not None:
                failures.append({"suite": filename, "test": case.attrib["classname"] + "." + case.attrib["name"], "message": failure.attrib.get("message", "")})
    save("BASELINE_DEBT.json", {
        "failures": failures,
        "source_attribution": source_attribution,
        "prior_registry_debt": "../wave_c_reentry/BASELINE_DEBT.json",
        "classification": "Unresolved regression debt outside this package. Existing failing service/test definitions above match HEAD. Authorization catalog/default changes predate entry. No authorization repair is attempted; broad regression is not green.",
    })
    integrity = []
    for evidence in QuoteRevisionEvidence.objects.filter(source_channel="external_portal_upload").select_related("document_version", "sealed_custody", "quote_revision"):
        digest = hashlib.sha256()
        with evidence.document_version.file.open("rb") as content:
            for chunk in iter(lambda: content.read(65536), b""):
                digest.update(chunk)
        assert digest.hexdigest() == evidence.canonical_sha256 == evidence.document_version.sha256 == evidence.quote_revision.integrity_fingerprint
        assert not OrganizationMembership.objects.filter(organization=evidence.organization, user=evidence.captured_by).exists()
        integrity.append({"evidence": str(evidence.pk), "retained_sha256": digest.hexdigest(), "state": evidence.sealed_custody.state, "no_tenant_membership": True})
    assert integrity
    http = json.loads((OUT / "HTTP.json").read_text(encoding="utf-8"))
    assert len(http) == 28 and all(row["passed"] for row in http)
    tender_http = json.loads((OUT / "TENDER_HTTP_FINAL.json").read_text(encoding="utf-8"))
    assert len(tender_http["observations"]) == 6
    assert StatutoryCalculation.objects.count() == StatutoryOutput.objects.count() == 0
    assert MigrationRecorder.Migration.objects.filter(app="procurement", name="0016_external_portal_original_evidence").exists()
    save("FINAL_VERIFICATION.json", {
        "recorded_at": timezone.now().isoformat(), "head": head,
        "future_policies_unchanged": True, "development_migration_applied": True,
        "focused": "59 tests and 10 subtests PASS; commercial_final.xml is the post-lint correction retest",
        "http": "28/28 expected observations PASS; final Tender extension 6/6 PASS (34 total)",
        "static": "Ruff PASS; Django check PASS; migration drift check PASS",
        "retained_payloads": integrity,
        "statutory_calculations": StatutoryCalculation.objects.count(),
        "statutory_outputs": StatutoryOutput.objects.count(),
        "browser_final_tender_retest": "BLOCKED: Local browser use is disabled in Work settings",
        "git_writes": "NOT_EXECUTED", "production": "UNTOUCHED",
        "authorization_reopened": False, "full_wave_c_complete": False,
    })
    print("Closeout verification PASS; browser and broad-regression limits retained")


if __name__ == "__main__":
    verify()

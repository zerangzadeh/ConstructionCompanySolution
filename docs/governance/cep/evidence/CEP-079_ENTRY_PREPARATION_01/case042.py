"""Actual scan and source checks for new042 document; no UI substitution."""
from datetime import timedelta
import hashlib
import json
import logging
from pathlib import Path
import subprocess

import uat_execution_support as u
from apps.documents.models import Document
from apps.documents.services import record_document_processing_assessment
from apps.organizations.access_services import assign_platform_role


def scan():
    path = u.OUT / "UAT_CASE_042_RUNTIME.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    document = Document.objects.get(organization=u.ORG, reference="CEP079-UAT042-DOC")
    versions = list(document.versions.order_by("version_number"))
    assert len(versions) == 2 and document.current_version_id == versions[1].pk
    expected = json.loads((u.OUT / "DOCUMENT_STARTING_DATA.json").read_text(encoding="utf-8"))["upload"]["sha256"]
    logging.getLogger("django.request").disabled = True
    client = u.native_client("uiux.persona.project-manager")
    response = client.get(f"/documents/{document.pk}/download/")
    assert response.status_code == 403
    scanner = sorted(Path("C:/ProgramData/Microsoft/Windows Defender/Platform").glob("*/MpCmdRun.exe"))[-1]
    scans = []
    for version in versions:
        assert version.sha256 == expected
        assert hashlib.sha256(Path(version.file.path).read_bytes()).hexdigest() == expected
        result = subprocess.run([str(scanner), "-Scan", "-ScanType", "3", "-File", str(version.file.path), "-DisableRemediation"], capture_output=True, text=True, timeout=55)
        scans.append({"version": str(version.pk), "number": version.version_number,
                      "sha256": expected, "exit_code": result.returncode,
                      "stdout": result.stdout, "stderr": result.stderr,
                      "at": u.timezone.now().isoformat()})
        data["actual_scans"] = scans
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        assert result.returncode == 0 and "found no threats" in result.stdout.lower()
    superuser = u.actor("superuser")
    # Existing qualified synthetic candidate from the retained Platform Operations
    # readiness source. Do not edit/re-enable expired admin/custodian duties.
    operator = u.actor("account.demo-construction-03.viewer")
    duty = assign_platform_role(actor=superuser, approver=superuser, target=operator,
        role="platform_operations", reason="CEP079042 actual Defender scans of two exact new synthetic versions; five minute Development duty; expired history unchanged",
        ends_at=u.timezone.now()+timedelta(minutes=5))
    assessments = []
    for version in versions:
        assessment = record_document_processing_assessment(version=version, actor=operator,
            verdict="clean", adapter_code="microsoft-defender-mpcmdrun", adapter_version=scanner.parent.name)
        assessments.append(str(assessment.pk))
    data.update(pre_scan_download_status=403, actual_scans=scans, scanner_version=scanner.parent.name,
                scanning_duty={"assignment": str(duty.pk), "ends_at": duty.ends_at.isoformat()},
                assessments=assessments, versions=[{"id": str(v.pk), "number": v.version_number, "sha256": v.sha256} for v in versions])
    data["data_changes"].update(new_version=True, links_added=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("Two real clean Defender scans; audited native assessments; both immutable version hashes retained")


if __name__ == "__main__":
    scan()

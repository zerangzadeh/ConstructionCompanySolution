"""Serial, bounded CEP044 validation; no production actions or runtime PASS claim."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.stdout.reconfigure(encoding="utf-8")
os.chdir(ROOT)
EVIDENCE = ROOT / "docs/governance/cep/evidence"
environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
environment["BONIRA_CEP044_TRACE"] = str(EVIDENCE / "CEP-044_INTEGRATION_TRACE.json")
environment["BONIRA_CEP044_MIGRATION_TRACE"] = str(
    EVIDENCE / "CEP-044_ACTIONS_MIGRATION_TRACE.json"
)
common = ["-q", "--reuse-db", "--disable-warnings", "--tb=short"]
commands = {
    "FOCUSED": [
        "-m",
        "pytest",
        "apps/subledgers/test_cep044_lineage.py",
        "apps/subledgers/test_cep044_writeoffs.py",
        "apps/subledgers/test_cep044_billing.py",
        "apps/subledgers/test_cep044_migration.py",
        *common,
    ],
    "AFFECTED": [
        "-m",
        "pytest",
        "apps/accounting/test_cep008_recognition_registry.py",
        "apps/accounting/test_cep042_recognition.py",
        "apps/organizations/test_p1_s15_policy_localization.py",
        "apps/subledgers/tests.py::SubledgerFoundationTests",
        "apps/subledgers/test_cep033_invoice_handoff.py::SupplierInvoiceAPHandoffTests",
        "apps/subledgers/test_cep043_payroll_handoff.py::PayrollAPHandoffTests",
        *common,
    ],
}
result = {}
for name, command in commands.items():
    output = subprocess.run(
        [sys.executable, *command],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    text = output.stdout + output.stderr
    (EVIDENCE / f"CEP-044_{name}_FINAL_OUTPUT.txt").write_text(text, "utf-8")
    result[name] = {
        "argv": command,
        "exit_code": output.returncode,
        "summary": text.strip().splitlines()[-1:],
    }
    print(json.dumps({name: result[name]}), flush=True)
    (EVIDENCE / "CEP-044_VALIDATION_RESULTS.json").write_text(
        json.dumps(result, indent=2) + "\n", "utf-8"
    )
    if output.returncode:
        print(text[-12000:], flush=True)
        sys.exit(output.returncode)

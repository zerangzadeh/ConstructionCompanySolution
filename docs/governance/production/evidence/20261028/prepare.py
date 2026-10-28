"""Record this bounded readiness entry and recover identified upstream contracts."""

import csv
import hashlib
import io
import json
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, data):
    (OUT / name).write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main():
    assert not (OUT / "ENTRY.json").exists()
    registry = yaml.safe_load((ROOT / "CEP_EXECUTION_REGISTRY.yaml").read_text("utf-8"))
    manifest = yaml.safe_load(
        (ROOT / "docs/governance/cep/CEP_PROMPT_MANIFEST.yaml").read_text("utf-8")
    )
    prompts = {}
    for number in range(69, 80):
        key = f"CEP-{number:03}"
        item = manifest["prompts"][key]
        assert sha(ROOT / item["path"]) == item["sha256"]
        prompts[key] = item
    save(
        "ENTRY.json",
        {
            "client_date": "2026-10-28",
            "at": datetime.now(UTC).isoformat(),
            "branch": git("branch", "--show-current"),
            "head": git("rev-parse", "HEAD"),
            "origin_main": git("rev-parse", "origin/main"),
            "initial_working_tree": "CLEAN before graphify query; query changed only its generated cache stamp",
            "authorization": "Current attached direct Human Production Readiness instruction; bounded Development/non-production; no completed CEP reopening, Production action or Git writes",
            "registry_before_sha256": sha(ROOT / "CEP_EXECUTION_REGISTRY.yaml"),
            "ceps_before_sha256": hashlib.sha256(
                json.dumps(registry["ceps"], sort_keys=True, default=str).encode()
            ).hexdigest(),
            "canonical_prompts": prompts,
            "touch_set": [
                "docs/governance/production/PRODUCTION_READINESS_ASSESSMENT.md",
                "docs/governance/production/GATE11_EVALUATION.json",
                "docs/governance/production/PRODUCTION_REFERENCE_AND_CUTOVER.md",
                "docs/governance/production/production.env.example",
                "docs/governance/production/evidence/20261028/",
                "CEP_EXECUTION_REGISTRY.yaml: GATE-11 evidence/history only",
                "Attributable product/configuration fixes only if reproduced; none identified at entry",
            ],
            "qualification_trigger": "Statutory and fiscal-closing schema added since Linux release de6e208; qualify this release delta without re-executing completed CEPs",
        },
    )
    sources = json.loads(
        (
            ROOT / "docs/governance/cep/evidence/SHARED_TARGET_20261027/ENTRY.json"
        ).read_text("utf-8")
    )["recovered_sources"]
    recovered = {}
    names = {
        "BONIRA_IMPLEMENTATION_GATE_REGISTER.csv",
        "BONIRA_OPERATING_SPECIFICATION.md",
        "BONIRA_PRODUCTION_DEPLOYMENT_SPECIFICATION.md",
        "BONIRA_RECOVERY_POLICY_MATRIX.csv",
        "BONIRA_FINAL_PRODUCT_DECISION_REGISTER.md",
        "BONIRA_CEP_EXTERNAL_DEPENDENCY_REGISTER.csv",
    }
    for archive, source in sources.items():
        path = Path(source["path"])
        assert sha(path) == source["sha256"]
        item = {"path": str(path), "sha256": sha(path), "members": {}}
        with zipfile.ZipFile(path) as bundle:
            for name in bundle.namelist():
                if Path(name).name not in names:
                    continue
                data = bundle.read(name)
                digest = hashlib.sha256(data).hexdigest()
                if name in source["members"]:
                    assert digest == source["members"][name]
                member = {"sha256": digest}
                if "GATE_REGISTER" in name:
                    member["rows"] = [
                        row
                        for row in csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
                        if row["Gate ID"]
                        in {"GATE-08", "GATE-10", "GATE-11", "GATE-12"}
                    ]
                item["members"][name] = member
        recovered[archive] = item
    save(
        "SOURCE_CONTRACT.json",
        {
            "recovery_basis": "Required upstream Gate/specification/PD sources unavailable as local canonical files; approved recovery archives verified against retained entry identities; local CEP prompts take precedence",
            "archives": recovered,
        },
    )
    print("PASS: entry, 11 prompt identities, 4 recovery archive identities")


if __name__ == "__main__":
    main()

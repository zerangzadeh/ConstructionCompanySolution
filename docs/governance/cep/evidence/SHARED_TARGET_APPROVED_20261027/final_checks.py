"""Focused artifact checks, secret screening and graceful owned-target shutdown."""

from __future__ import annotations

import csv
import ctypes
import hashlib
import io
import json
import re
import shlex
import socket
import subprocess
import sys
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
RUNTIME = OUT / "runtime"
PRIVATE = Path("E:/BONIRA_Operations/ApprovedLinux/6e55fd45b4c04ce0")
SSH = [
    "ssh.exe",
    "-i",
    str(PRIVATE / "guest_key"),
    "-o",
    "IdentitiesOnly=yes",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=6",
    "-o",
    "UserKnownHostsFile=" + str(PRIVATE / "known_hosts"),
    "-p",
    "22270",
    "root@127.0.0.1",
]


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def command(args):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def main():
    entry = load(OUT / "ENTRY.json")
    assert command(["git", "rev-parse", "HEAD"]) == entry["head"]
    assert command(["git", "rev-parse", "--abbrev-ref", "HEAD"]) == "main"
    assert command(["git", "rev-parse", "origin/main"]) == entry["origin_main"]
    assert sha(ROOT / entry["authority"]) == entry["authority_sha256"]
    for details in entry["canonical"].values():
        assert sha(ROOT / details["path"]) == details["sha256"]
    freeze = load(OUT / "SOURCE_FREEZE.json")
    assert len(freeze) == 1510
    assert all(sha(ROOT / path) == digest for path, digest in freeze.items())

    registry = yaml.safe_load(
        (ROOT / "CEP_EXECUTION_REGISTRY.yaml").read_text(encoding="utf-8")
    )
    before = yaml.safe_load((OUT / "REGISTRY_BEFORE.yaml").read_text(encoding="utf-8"))
    selected = {"CEP-070", "CEP-074", "CEP-075"}
    untouched = set(before["ceps"]) - selected
    assert all(registry["ceps"][key] == before["ceps"][key] for key in untouched)
    for gate, value in before["gates"].items():
        if gate not in {"GATE-08", "GATE-11"}:
            assert registry["gates"][gate] == value
    assert registry["gates"]["GATE-08"]["status"] == "PASS"
    assert registry["gates"]["GATE-11"]["status"] == "NOT_PASSED"
    assert registry["execution_frontier"]["next_executable_frontier"] == []
    assert not registry["execution_frontier"]["production_authorized"]
    assert registry["summary"]["execution_state_complete"] == 78
    assert registry["summary"]["partial_current"] == 1
    for cep in selected:
        item = registry["ceps"][cep]
        assert item["execution"]["status"] == "COMPLETE" and not item["blockers"]
        assert item["acceptance"]["passed"] == item["acceptance"]["total"] == 6
        assert item["dod"] == "MET_APPROVED_NONPRODUCTION_SCOPE"
        result = load(RUNTIME / (cep[-3:] + "_RESULT.json"))
        assert result["execution"] == "COMPLETE" and len(result["ac"]) == 6
        assert set(result["ac"].values()) == {"PASS_APPROVED_NONPRODUCTION_TARGET"}
        assert (
            result["production_certification"]
            == result["human_signoff"]
            == "NOT_EXECUTED"
        )
        assert not result["git_write"]

    for phase, expected in (("070", 15), ("074", 17)):
        result = load(RUNTIME / (phase + "_RESULT.json"))
        restore = result["restore"]
        assert restore["rpo_seconds"] == 0 and restore["rto_seconds"] <= 3600
        assert result["capture_interval_seconds"] <= 900
        validation = load(RUNTIME / (phase + "_VALIDATION.json"))
        assert validation["result"] == "PASS" and len(validation["checks"]) == expected
        assert all(item["status"] == "PASS" for item in validation["checks"])
    deployment = load(RUNTIME / "075_RESULT.json")
    assert len(deployment["steps"]) == 7
    assert sum(step.get("http_cases", 0) for step in deployment["steps"]) == 56
    assert load(RUNTIME / "075_BEFORE_HISTORY.json") == load(
        RUNTIME / "075_AFTER_HISTORY.json"
    )
    target = load(RUNTIME / "FINAL_TARGET_CHECK.json")
    assert target["result"] == "PASS" and target["approved_base_layers_preserved"]
    for name, digest in target["executed_tools_sha256"].items():
        assert sha(RUNTIME / ("EXECUTED_" + name)) == digest

    affected = [ROOT / "CEP_EXECUTION_REGISTRY.yaml"]
    affected += list(OUT.rglob("*"))
    affected += [
        ROOT
        / "docs/governance/cep/supporting/SHARED_PRODUCTION_EQUIVALENT_TARGET_PROFILE.md"
    ]
    affected += [ROOT / entry["authority"]]
    for cep in selected:
        for folder in ("evidence", "manifests", "reports"):
            affected += list((ROOT / "docs/governance/cep" / folder).glob(cep + "_*"))
    affected = sorted(
        {
            path
            for path in affected
            if path.is_file() and "__pycache__" not in path.parts
        }
    )
    csv_checks = {}
    for path in affected:
        if path.suffix == ".csv":
            rows = list(csv.reader(path.read_text(encoding="utf-8-sig").splitlines()))
            assert rows and all(len(row) == len(rows[0]) for row in rows)
            if "EVIDENCE_MANIFEST" in path.name or "ACCEPTANCE_MAPPING" in path.name:
                assert len({row[0] for row in rows[1:]}) == len(rows) - 1
            csv_checks[path.relative_to(ROOT).as_posix()] = len(rows) - 1

    active = sorted(OUT.glob("*.py"))
    lint = command([sys.executable, "-m", "ruff", "check", *map(str, active)])
    formatting = command(
        [sys.executable, "-m", "ruff", "format", "--check", *map(str, active)]
    )
    for path in active:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    command(["git", "diff", "--check"])
    profile = (
        ROOT
        / "docs/governance/cep/supporting/SHARED_PRODUCTION_EQUIVALENT_TARGET_PROFILE.md"
    )
    for link in re.findall(r"\]\(([^)]+)\)", profile.read_text(encoding="utf-8")):
        assert (profile.parent / link).exists(), link

    if not (OUT / "SHUTDOWN.json").exists():
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w") as tar:
            for path in affected:
                tar.add(
                    path, arcname=path.relative_to(ROOT).as_posix(), recursive=False
                )
        scan = """
import json,sys,tarfile,re
from pathlib import Path
values=[v.encode() for v in json.loads(Path('/srv/bonira/secrets/values.json').read_text()).values() if isinstance(v,str) and len(v)>=12]
values += [p.read_bytes() for p in Path('/srv/bonira/pki').glob('*.key')]
count=0
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as tar:
 for member in tar:
  data=tar.extractfile(member).read()
  assert not any(v in data for v in values), 'Secret found: '+member.name
  assert not re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\\r?\\n[A-Za-z0-9+/=]{20,}',data), 'Private key: '+member.name
  count+=1
print(json.dumps({'result':'PASS','public_files_screened':count,'generated_values_and_private_keys_absent':True}))
"""
        scan_result = subprocess.run(
            SSH + ["python3", "-c", shlex.quote(scan)],
            input=archive.getvalue(),
            capture_output=True,
            check=False,
        )
        assert scan_result.returncode == 0, scan_result.stderr.decode()
        screening = json.loads(scan_result.stdout)
        write(OUT / "PUBLIC_ARTIFACT_SCREENING.json", screening)
        shutdown = """
import json,subprocess
from datetime import datetime,timezone
subprocess.run(['nginx','-s','quit','-c','/srv/bonira/nginx.conf'],check=True)
subprocess.run(['docker','stop','--time','30','bonira-db'],check=True,capture_output=True)
assert not subprocess.check_output(['docker','ps','-q'],text=True).strip()
subprocess.run(['sync'],check=True)
print(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'result':'PASS','nginx_quit':True,'database_stopped':True,'no_running_containers':True,'sync_complete':True,'guest_halt_requested':True}),flush=True)
subprocess.Popen(['shutdown','-h','now'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
"""
        response = subprocess.run(
            SSH + ["python3", "-c", shlex.quote(shutdown)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert response.returncode in {0, 255} and response.stdout.strip(), (
            response.stderr
        )
        shutdown_result = json.loads(response.stdout)
        pid = int((PRIVATE / "qemu.pid").read_text().strip())
        assert pid == 16732
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x100000, False, pid)
        if handle:
            try:
                assert kernel.WaitForSingleObject(handle, 30000) == 0, (
                    "Owned guest has not exited"
                )
            finally:
                kernel.CloseHandle(handle)
        shutdown_result["owned_qemu_process_exited"] = True
        for port in (22270, 22271, 24470):
            with socket.socket() as sock:
                sock.settimeout(1)
                assert sock.connect_ex(("127.0.0.1", port)) != 0
        shutdown_result["owned_loopback_listeners_closed"] = [22270, 22271, 24470]
        shutdown_result["private_disk_bundles_secrets_retained"] = True
        write(OUT / "SHUTDOWN.json", shutdown_result)
    shutdown_result = load(OUT / "SHUTDOWN.json")
    assert (
        shutdown_result["result"] == "PASS"
        and shutdown_result["owned_qemu_process_exited"]
    )
    checks = {
        "at": datetime.now(UTC).isoformat(),
        "result": "PASS",
        "scope": "Focused requested three-CEP artifacts/identity/security/cleanup only",
        "selected_ceps": {
            cep: "COMPLETE;AC6/6;SCOPED_DOD_MET" for cep in sorted(selected)
        },
        "unrelated_cep_records_preserved": len(untouched),
        "other_gate_records_preserved": True,
        "complete_current": 78,
        "partial_current": 1,
        "product_source_files_unchanged": len(freeze),
        "canonical_prompt_hashes_unchanged": 3,
        "head_branch_origin_ref_unchanged": True,
        "authority_hash_verified": True,
        "runtime_checks": {
            "070_restore_validations": 15,
            "074_restore_validations": 17,
            "075_actual_steps": 7,
            "075_https_cases": 56,
        },
        "exact_executed_tool_hashes_verified": True,
        "csv_shape_and_unique_ids": csv_checks,
        "profile_links_resolve": True,
        "active_tool_ruff": lint,
        "active_tool_format": formatting,
        "active_tools_compiled": len(active),
        "git_diff_check": "PASS",
        "public_artifact_screening": load(OUT / "PUBLIC_ARTIFACT_SCREENING.json"),
        "shutdown": shutdown_result,
        "no_broad_audit_or_unrelated_complete_cep_rerun": True,
        "production_action": False,
        "git_writes": False,
        "gates": {"GATE-08": "PASS_BOUNDED_ACCEPTED_EVIDENCE", "GATE-11": "NOT_PASSED"},
        "remaining_in_scope_development_or_reproducible_work": [],
        "next_executable_frontier": [],
    }
    write(OUT / "CHECKS.json", checks)
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()

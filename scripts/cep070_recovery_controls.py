"""EXT-0020 synthetic Development controls; no production or purge authority.

Uses the existing pg_dump capture adapter, Windows DACLs and OS file locks.
The bounded worker runs only while its caller is alive. A configured future due
date is never evidence of a future run or of an installed unattended service.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from scripts.backup_bundle import (
    BackupError,
    BackupPlan,
    _inventory,
    _reject_link,
    create_bundle,
    file_hash,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / (
    "docs/governance/cep/supporting/CEP-070_DEVELOPMENT_RECOVERY_POLICY.json"
)


class ControlError(Exception):
    """A qualification control failed; do not infer recovery readiness."""


def utc_now() -> datetime:
    return datetime.now(UTC)


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ControlError("UTC evidence timestamps are required.")
    return parsed


def load_policy(path: Path = POLICY_PATH) -> dict:
    policy = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema": "bonira.cep070.development-recovery.v1",
        "authority": "EXT-0020-HUMAN-20261027",
        "environment": "synthetic-development-only",
        "rpo_seconds": 900,
        "rto_seconds": 3600,
        "pitr_required": False,
        "backup_interval_seconds": 900,
        "minimum_retention_days": 30,
        "restore_test_interval_days": 30,
        "production_equivalent": False,
        "production_authorized": False,
        "purge_authorized": False,
    }
    if any(
        type(policy.get(key)) is not type(value) or policy[key] != value
        for key, value in expected.items()
    ):
        raise ControlError("Policy does not match the bounded Human approval.")
    if set(policy["data_classes"]) != {
        "transactional_database",
        "document_media",
        "configuration_metadata",
        "audit_operational",
    }:
        raise ControlError("All four approved classes must be governed together.")
    authority = ROOT / policy["authority_source"]
    if authority.resolve() != ROOT / (
        "docs/governance/cep/supporting/CEP-070_EXT0020_HUMAN_APPROVAL_20261027.md"
    ):
        raise ControlError("Unexpected Human authority reference.")
    policy["authority_sha256"] = file_hash(authority)
    policy["policy_sha256"] = file_hash(path)
    return policy


# Never interpolate a filesystem path or principal into shell source. Windows
# resolves the current token and well-known SIDs; the path travels in the env.
_ACL_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$target = $env:BONIRA_CEP070_ACL_TARGET
$current = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$allowed = @($current.Value, 'S-1-5-18', 'S-1-5-32-544')
$item = Get-Item -LiteralPath $target -Force
if ($env:BONIRA_CEP070_ACL_INITIALIZE -eq '2') {
    if ($item.PSIsContainer -or $item.Name -ne '.env') { throw 'Unexpected secret source' }
    (Get-Acl -LiteralPath $target).Sddl | Set-Content -LiteralPath $env:BONIRA_CEP070_ACL_RECEIPT -Encoding UTF8
    $acl = New-Object System.Security.AccessControl.FileSecurity
    $acl.SetOwner($current)
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($sid in $allowed) {
        $identity = New-Object System.Security.Principal.SecurityIdentifier($sid)
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
            $identity, 'FullControl', 'Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $target -AclObject $acl
}
if ($env:BONIRA_CEP070_ACL_INITIALIZE -eq '1') {
    if (-not $item.PSIsContainer -or @(Get-ChildItem -LiteralPath $target -Force).Count -ne 0) {
        throw 'Only a newly created empty directory may be initialized'
    }
    $acl = New-Object System.Security.AccessControl.DirectorySecurity
    $acl.SetOwner($current)
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($sid in $allowed) {
        $identity = New-Object System.Security.Principal.SecurityIdentifier($sid)
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
            $identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $target -AclObject $acl
}
$items = @($item)
if ($item.PSIsContainer) {
    $items += @(Get-ChildItem -LiteralPath $target -Recurse -Force)
}
foreach ($entry in $items) {
    if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Reparse points are forbidden'
    }
    $acl = Get-Acl -LiteralPath $entry.FullName
    if ($acl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value -ne $current.Value) {
        throw 'Unexpected owner'
    }
    $rules = @($acl.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier]))
    if ($rules.Count -eq 0) { throw 'Empty DACL is not accepted' }
    foreach ($rule in $rules) {
        if ($rule.AccessControlType -ne 'Allow' -or $rule.IdentityReference.Value -notin $allowed) {
            throw 'Unapproved access rule'
        }
    }
    if (-not ($rules | Where-Object {
        $_.IdentityReference.Value -eq $current.Value -and
        ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::FullControl) -eq
        [System.Security.AccessControl.FileSystemRights]::FullControl
    })) { throw 'Current operator needs full access' }
}
if ($env:BONIRA_CEP070_ACL_BOUNDARY -eq '1' -and $item.PSIsContainer -and
    -not (Get-Acl -LiteralPath $target).AreAccessRulesProtected) {
    throw 'The storage boundary must disable inherited access'
}
@{status='PASS'; paths_checked=$items.Count; owner_is_current_operator=$true;
  allowed_principals=@('current operator','Local System','local Administrators');
  encryption_qualification='NOT_ESTABLISHED'} | ConvertTo-Json -Compress
"""


def powershell_environment() -> tuple[str, dict]:
    executable = shutil.which("pwsh.exe")
    if executable is None:
        raise ControlError(
            "The qualified Development PowerShell runtime is unavailable."
        )
    env = os.environ.copy()
    env["PSModulePath"] = str(Path(executable).parent / "Modules")
    return executable, env


def verify_private_tree(
    path: Path, *, initialize: bool = False, boundary: bool = True
) -> dict:
    if os.name != "nt" or not path.is_absolute():
        raise ControlError("This approved qualification requires local Windows paths.")
    for ancestor in (path, *path.parents):
        if ancestor.exists() or ancestor.is_symlink():
            _reject_link(ancestor)
    executable, env = powershell_environment()
    env["BONIRA_CEP070_ACL_TARGET"] = str(path)
    env["BONIRA_CEP070_ACL_INITIALIZE"] = "1" if initialize else "0"
    env["BONIRA_CEP070_ACL_BOUNDARY"] = "1" if boundary else "0"
    result = subprocess.run(
        [executable, "-NoProfile", "-NonInteractive", "-Command", _ACL_SCRIPT],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=60,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        raise ControlError("Restricted filesystem access could not be verified.")
    return json.loads(result.stdout)


def create_private_store(parent: Path) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    directory = parent / uuid4().hex[:16]
    directory.mkdir(exist_ok=False)
    verify_private_tree(directory, initialize=True)
    return directory


def secure_development_secret_source(store: Path) -> dict:
    """Tighten only this repository's existing .env; never copy its contents."""
    verify_private_tree(store)
    source = ROOT / ".env"
    before = file_hash(source)
    try:
        result = verify_private_tree(source)
        result["acl_remediated"] = False
    except ControlError:
        executable, env = powershell_environment()
        env["BONIRA_CEP070_ACL_TARGET"] = str(source)
        env["BONIRA_CEP070_ACL_INITIALIZE"] = "2"
        env["BONIRA_CEP070_ACL_BOUNDARY"] = "0"
        env["BONIRA_CEP070_ACL_RECEIPT"] = str(store / "original-env-acl.sddl")
        process = subprocess.run(
            [executable, "-NoProfile", "-NonInteractive", "-Command", _ACL_SCRIPT],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=60,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if process.returncode:
            raise ControlError("Development secret-source restriction failed.")
        result = json.loads(process.stdout)
        result["acl_remediated"] = True
    if file_hash(source) != before:
        raise ControlError("Secret-source contents changed unexpectedly.")
    result["contents_unchanged"] = True
    return result


def write_json(path: Path, value: dict) -> None:
    """Replace a current-status projection atomically; events use unique paths."""
    _reject_link(path.parent)
    if path.exists() or path.is_symlink():
        _reject_link(path)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


@contextmanager
def exclusive_store(root: Path):
    """An OS lock dies with the process; no stale lock-file override is needed."""
    import msvcrt

    verify_private_tree(root)
    with (root / "worker.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise ControlError(
                "Another qualification worker owns this store."
            ) from None
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


class RecoveryControls:
    def __init__(self, root: Path):
        self.root = root
        self.policy = load_policy()
        verify_private_tree(root)
        for name in ("bundles", "events"):
            (root / name).mkdir(exist_ok=True)
        self.state_path = root / "schedule.json"
        self.reload()

    def reload(self) -> None:
        self.state = (
            json.loads(self.state_path.read_text(encoding="utf-8"))
            if self.state_path.exists()
            else {}
        )
        if (
            self.state
            and self.state.get("policy_sha256") != self.policy["policy_sha256"]
        ):
            raise ControlError("An existing store cannot silently change policy.")
        for key in ("next_backup_at", "next_restore_test_at"):
            if self.state.get(key):
                timestamp(self.state[key])

    def event(self, kind: str, **values) -> None:
        write_json(
            self.root / "events" / (uuid4().hex + ".json"),
            {"at": utc_now().isoformat(), "event": kind, **values},
        )

    def save(self) -> None:
        self.state["policy_sha256"] = self.policy["policy_sha256"]
        self.state["authority_sha256"] = self.policy["authority_sha256"]
        write_json(self.state_path, self.state)

    def backup_due(self, now: datetime) -> bool:
        return not self.state.get("next_backup_at") or now >= timestamp(
            self.state["next_backup_at"]
        )

    def restore_due(self, now: datetime) -> bool:
        return not self.state.get("next_restore_test_at") or now >= timestamp(
            self.state["next_restore_test_at"]
        )

    def validate_bundle(self, bundle: Path) -> dict:
        if bundle.parent != self.root / "bundles":
            raise ControlError("Only this store's recovery bundles are accepted.")
        verify_private_tree(bundle, boundary=False)
        capture = json.loads((bundle / "capture.json").read_text(encoding="utf-8"))
        if (
            capture.get("capture_status") != "CAPTURED_NOT_RESTORE_VERIFIED"
            or capture.get("environment") != "non-production"
            or set(capture["classes"]) != set(self.policy["data_classes"])
            or file_hash(bundle / "database.dump")
            != capture["classes"]["transactional_database"]["sha256"]
        ):
            raise ControlError("A complete, intact non-production bundle is required.")
        for key in self.policy["data_classes"]:
            if key == "transactional_database":
                continue
            inventory = _inventory(bundle / key)
            expected = json.loads(
                (bundle / (key + ".inventory.json")).read_text(encoding="utf-8")
            )
            if (
                inventory != expected
                or hashlib.sha256(
                    json.dumps(inventory, sort_keys=True).encode()
                ).hexdigest()
                != capture["classes"][key]["inventory_sha256"]
            ):
                raise ControlError("A recovery file class failed integrity validation.")
        return capture

    def capture(self, plan: BackupPlan) -> Path:
        verify_private_tree(self.root)
        if (
            plan.environment != "non-production"
            or plan.recovery_reference != self.policy["authority"]
        ):
            raise ControlError("The capture must reference this approved scope.")
        started = utc_now()
        bundle = self.root / "bundles" / uuid4().hex[:16]
        try:
            create_bundle(replace(plan, destination=bundle))
            self.validate_bundle(bundle)
        except (BackupError, ControlError, OSError, ValueError) as exc:
            self.event("CAPTURE_FAILED", failure_type=type(exc).__name__)
            # Last good backup and its due date are deliberately not advanced.
            raise ControlError(
                "Capture failed; retain bytes and exception evidence."
            ) from None
        completed = utc_now()
        receipt = {
            "capture_started_at": started.isoformat(),
            "completed_at": completed.isoformat(),
            "retain_until": (completed + timedelta(days=30)).isoformat(),
            "capture_manifest_sha256": file_hash(bundle / "capture.json"),
            "policy_sha256": self.policy["policy_sha256"],
            "purge_authorized": False,
        }
        write_json(bundle / "retention.json", receipt)
        self.state.update(
            last_good_bundle=bundle.name,
            last_capture_started_at=started.isoformat(),
            last_capture_completed_at=completed.isoformat(),
            next_backup_at=(started + timedelta(seconds=900)).isoformat(),
        )
        self.save()
        self.event("CAPTURE_COMPLETED", bundle=bundle.name, **receipt)
        return bundle

    def retention_status(self, now: datetime) -> list[dict]:
        result = []
        for bundle in sorted((self.root / "bundles").iterdir()):
            # Incomplete captures are deliberately retained, but never offered
            # as recovery points or counted as successful retention evidence.
            capture_path = bundle / "capture.json"
            if capture_path.exists():
                capture = json.loads(capture_path.read_text(encoding="utf-8"))
                if capture.get("capture_status") == "FAILED":
                    verify_private_tree(bundle, boundary=False)
                    result.append(
                        {
                            "bundle": bundle.name,
                            "state": "QUARANTINED_FAILED_CAPTURE_NO_PURGE",
                        }
                    )
                    continue
            self.validate_bundle(bundle)
            receipt = json.loads(
                (bundle / "retention.json").read_text(encoding="utf-8")
            )
            if (
                receipt["policy_sha256"] != self.policy["policy_sha256"]
                or receipt["capture_manifest_sha256"]
                != file_hash(bundle / "capture.json")
                or timestamp(receipt["retain_until"])
                < timestamp(receipt["completed_at"]) + timedelta(days=30)
                or receipt["purge_authorized"] is not False
            ):
                raise ControlError("Recovery retention evidence is inconsistent.")
            result.append(
                {
                    "bundle": bundle.name,
                    "retain_until": receipt["retain_until"],
                    "state": (
                        "PROTECTED_RETENTION"
                        if now < timestamp(receipt["retain_until"])
                        else "DISPOSITION_REQUIRES_SEPARATE_AUTHORITY"
                    ),
                }
            )
        return result

    def record_restore(
        self, *, bundle: Path, started: datetime, rpo_seconds: float, passed: bool
    ):
        self.validate_bundle(bundle)
        completed = utc_now()
        rto = (completed - started).total_seconds()
        passed = passed and 0 <= rpo_seconds <= 900 and 0 <= rto <= 3600
        result = {
            "bundle": bundle.name,
            "started_at": started.isoformat(),
            "completed_at": completed.isoformat(),
            "rpo_seconds": rpo_seconds,
            "rto_seconds": rto,
            "passed": passed,
            "scope": "EXECUTED_QUIESCENT_SYNTHETIC_FIXTURE_ONLY",
            "production_equivalent": False,
        }
        self.event("RESTORE_PASSED" if passed else "RESTORE_FAILED", **result)
        if not passed:
            raise ControlError("Recovery failed its checks or approved objectives.")
        self.state["last_restore"] = result
        self.state["next_restore_test_at"] = (
            completed + timedelta(days=30)
        ).isoformat()
        self.save()
        return result

    def run_cycles(self, plan: BackupPlan, *, cycles: int, restore=None) -> Path:
        """Run supervised captures; invoke the supplied drill when its test is due.

        A caller may perform the first drill immediately after this method, in
        which case its due state remains open until record_restore succeeds.
        """
        if type(cycles) is not int or cycles < 1:
            raise ControlError("A positive bounded cycle count is required.")
        with exclusive_store(self.root):
            # Another worker may have finished since this object was created.
            self.reload()
            self.event("BOUNDED_WORKER_STARTED", cycles=cycles)
            try:
                for _ in range(cycles):
                    waiting_since = time.monotonic()
                    # Start within the approved 15-minute maximum spacing with
                    # the existing 180-second pg_dump execution budget in hand.
                    # This dispatch lead is an engineering budget, not a new
                    # recovery objective or an allowed late-backup grace period.
                    lead = min(plan.command_timeout_seconds, 900)
                    while self.state.get("next_backup_at") and utc_now() < (
                        timestamp(self.state["next_backup_at"])
                        - timedelta(seconds=lead)
                    ):
                        # Fail on a backward wall clock rather than delaying the
                        # backup indefinitely. This is not an RPO grace period.
                        if time.monotonic() - waiting_since > 900:
                            raise ControlError(
                                "Clock movement prevented the due capture."
                            )
                        time.sleep(0.25)
                    bundle = self.capture(plan)
                    if restore is not None and self.restore_due(utc_now()):
                        started = utc_now()
                        try:
                            outcome = restore(bundle)
                        except Exception as exc:  # noqa: BLE001 -- sanitize external drill errors
                            self.event(
                                "RESTORE_FAILED", failure_type=type(exc).__name__
                            )
                            raise ControlError(
                                "The scheduled restore drill failed."
                            ) from None
                        self.record_restore(bundle=bundle, started=started, **outcome)
            finally:
                self.event("BOUNDED_WORKER_STOPPED", unattended_service_installed=False)
        return bundle

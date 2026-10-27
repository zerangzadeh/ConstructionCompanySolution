"""Inspect only this owned target; never emit environment or private key values."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import subprocess
from datetime import UTC, datetime
from pathlib import Path

BASE = Path("/srv/bonira")
OUT = BASE / "evidence"


def call(*args):
    return subprocess.check_output(args, text=True).strip()


def inspect(kind, name):
    return json.loads(call("docker", kind, "inspect", name))[0]


base = inspect(
    "image",
    "python@sha256:8fb0b110b022c70cbe09d3ff1fb313654f31f9c814abb0d48180af56d906a199",
)
app = inspect("image", "bonira-pe-np-runtime:20261027")
db = json.loads(call("docker", "inspect", "bonira-db"))[0]
network = inspect("network", "bonira-pe")
assert (
    app["RootFS"]["Layers"][: len(base["RootFS"]["Layers"])] == base["RootFS"]["Layers"]
)
assert network["Internal"] and not db["HostConfig"]["PortBindings"]
assert call("docker", "ps", "--format", "{{.Names}}") == "bonira-db"
assert not db["HostConfig"]["Privileged"]
permissions = {}
for folder in (
    "secrets",
    "pki",
    "shared/document_media",
    "shared/configuration_metadata",
    "shared/audit_operational",
):
    path = BASE / folder
    mode = stat.S_IMODE(path.stat().st_mode)
    permissions[folder] = oct(mode)
    assert mode & 0o007 == 0
    if folder in {"secrets", "pki"}:
        assert mode == 0o700

secret_files = list((BASE / "secrets").glob("*.env")) + list(
    (BASE / "pki").glob("*.key")
)
assert secret_files and all(
    stat.S_IMODE(path.stat().st_mode) == 0o600 for path in secret_files
)
protected = next(
    path for path in (BASE / "shared/document_media").rglob("*") if path.is_file()
)
assert (
    subprocess.run(
        ["runuser", "-u", "www-data", "--", "test", "-r", str(protected)], check=False
    ).returncode
    == 1
)

executed = {}
for path in (BASE / "tools").glob("*.py"):
    copy = OUT / ("EXECUTED_" + path.name)
    shutil.copyfile(path, copy)
    executed[path.name] = hashlib.sha256(copy.read_bytes()).hexdigest()

secrets = json.loads((BASE / "secrets/values.json").read_text())
values = [
    value.encode()
    for value in secrets.values()
    if isinstance(value, str) and len(value) >= 12
]
assert values
files = [
    path
    for path in OUT.rglob("*")
    if path.is_file() and "__pycache__" not in path.parts
]
for path in files:
    data = path.read_bytes()
    assert not any(value in data for value in values), (
        "Synthetic secret found in public artifact: " + path.name
    )
    assert (
        b"-----BEGIN PRIVATE KEY-----" not in data
        and b"-----BEGIN OPENSSH PRIVATE KEY-----" not in data
    )

result = {
    "at": datetime.now(UTC).isoformat(),
    "result": "PASS",
    "profile": "BONIRA-PE-NP-01",
    "kernel": call("uname", "-r"),
    "docker": call("docker", "--version"),
    "base_id": base["Id"],
    "app_id": app["Id"],
    "approved_base_layers_preserved": True,
    "internal_network": network["Internal"],
    "published_database_ports": db["HostConfig"]["PortBindings"],
    "only_running_container": "bonira-db",
    "app_process_stopped_after_scenarios": True,
    "directory_modes": permissions,
    "private_env_key_modes": "0600",
    "nginx_cannot_read_existing_protected_bytes": True,
    "executed_tools_sha256": executed,
    "public_artifacts_scanned": len(files),
    "synthetic_secrets_absent": True,
    "private_key_blocks_absent": True,
    "production_action": False,
}
(OUT / "FINAL_TARGET_CHECK.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))

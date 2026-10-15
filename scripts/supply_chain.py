"""Fail-closed CEP-013 dependency acquisition and release evidence gate.

This tool uses only the Python standard library and pip from the selected build
image. It does not install application dependencies into the caller's environment.
"""

from __future__ import annotations

import argparse
import email
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "security" / "supply_chain"
INDEX = "https://pypi.org/simple/"
OSV = "https://api.osv.dev/v1/querybatch"
LOCK_RE = re.compile(
    r"^([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+) \\"
    r"\n    --hash=sha256:([a-f0-9]{64})$",
    re.MULTILINE,
)
CANONICAL_NAME_RE = re.compile(r"[-_.]+")
TARGET = ("3.11", "manylinux2014_x86_64", "cp", "cp311")


class GateError(RuntimeError):
    """A missing or rejected security control."""


def normalize(name: str) -> str:
    return CANONICAL_NAME_RE.sub("-", name).lower()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_lock(path: Path) -> dict[str, dict[str, str]]:
    content = path.read_text(encoding="utf-8")
    without_comments = "\n".join(
        line
        for line in content.splitlines()
        if line.strip() and not line.startswith("#")
    )
    entries: dict[str, dict[str, str]] = {}
    matches = list(LOCK_RE.finditer(without_comments))
    remainder = LOCK_RE.sub("", without_comments).strip()
    if not matches or remainder:
        raise GateError(f"Invalid or unhashed lock entry: {path.name}")
    for match in matches:
        name, version, digest = match.groups()
        key = normalize(name)
        if key in entries:
            raise GateError(f"Duplicate package in {path.name}: {key}")
        entries[key] = {"version": version, "sha256": digest}
    return entries


def load_legacy_versions() -> dict[str, str]:
    text = (ROOT / "requirements-lock.txt").read_text(encoding="utf-8")
    return {
        normalize(name): version
        for name, version in re.findall(
            r"(?im)^([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)\s*\\", text
        )
    }


def validate_locks() -> dict[str, dict[str, dict[str, str]]]:
    prod = load_lock(ROOT / "requirements-prod-linux.lock")
    dev = load_lock(ROOT / "requirements-dev-linux.lock")
    legacy = load_legacy_versions()
    if set(prod) != {
        "django",
        "python-dotenv",
        "psycopg",
        "asgiref",
        "sqlparse",
        "typing-extensions",
        "tzdata",
    }:
        raise GateError("Production package set changed or is incomplete")
    if set(dev) != set(legacy) - {"psycopg-binary"} or not set(prod) < set(dev):
        raise GateError("Development lock or dependency-set separation drifted")
    for name, entry in dev.items():
        if entry["version"] != legacy[name]:
            raise GateError(f"Unapproved package version change: {name}")
    for name, entry in prod.items():
        if entry != dev[name]:
            raise GateError(f"Runtime artifact differs between locks: {name}")
    return {"prod": prod, "dev": dev}


def _url_json(url: str, *, data: dict | None = None) -> tuple[dict, dict]:
    body = json.dumps(data).encode("utf-8") if data is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Accept": "application/vnd.oci.image.index.v1+json, "
            "application/vnd.docker.distribution.manifest.list.v2+json, "
            "application/json",
            "Content-Type": "application/json",
        },
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response), dict(response.headers)


def verify_image_identity() -> dict:
    image = json.loads((POLICY / "build_image.json").read_text(encoding="utf-8"))
    if image["target"] != "linux/amd64" or image["python"] != "CPython 3.11.17":
        raise GateError("Unapproved build target")
    token_data, _ = _url_json(
        "https://auth.docker.io/token?service=registry.docker.io"
        "&scope=repository:library/python:pull"
    )
    token = token_data["token"]
    req = urllib.request.Request(
        "https://registry-1.docker.io/v2/library/python/manifests/" + image["tag"],
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.oci.image.index.v1+json, "
            "application/vnd.docker.distribution.manifest.list.v2+json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        actual = json.load(response)
        index_digest = response.headers.get("Docker-Content-Digest")
    matching = [
        item["digest"]
        for item in actual.get("manifests", [])
        if item.get("platform", {}).get("os") == "linux"
        and item["platform"].get("architecture") == "amd64"
    ]
    if index_digest != image["index_digest"] or matching != [image["platform_digest"]]:
        raise GateError("Official build-image tag no longer matches pinned digests")
    return image


def _pip_environment() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL", "PIP_TRUSTED_HOST"):
        env.pop(key, None)
    env["PIP_CONFIG_FILE"] = os.devnull
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return env


def pip_download(lock: Path, wheelhouse: Path, *, offline: bool = False) -> None:
    args = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--require-hashes",
        "--only-binary=:all:",
        "--no-cache-dir",
        "--platform",
        TARGET[1],
        "--python-version",
        TARGET[0],
        "--implementation",
        TARGET[2],
        "--abi",
        TARGET[3],
        "--dest",
        str(wheelhouse),
    ]
    if offline:
        args += ["--no-index", "--find-links", str(wheelhouse)]
    else:
        args += ["--index-url", INDEX]
    args += ["-r", str(lock)]
    with tempfile.TemporaryDirectory(prefix="cep013_verify_") as temp:
        if offline:
            args[args.index("--dest") + 1] = temp
        result = subprocess.run(
            args,
            cwd=ROOT,
            env=_pip_environment(),
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
    if result.returncode:
        raise GateError(
            "Hash-checked "
            + ("offline" if offline else "PyPI")
            + " acquisition failed: "
            + result.stderr[-1200:]
        )


def wheel_metadata(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(names) != 1:
            raise GateError(f"Wheel lacks unique METADATA: {path.name}")
        metadata = email.message_from_bytes(archive.read(names[0]))
        license_files = sorted(
            name
            for name in archive.namelist()
            if ".dist-info/licenses/" in name and not name.endswith("/")
        )
        license_digest = hashlib.sha256()
        for name in license_files:
            license_digest.update(name.encode("utf-8") + b"\0")
            license_digest.update(archive.read(name))
    return {
        "name": normalize(metadata["Name"]),
        "version": metadata["Version"],
        "license_expression": metadata.get("License-Expression"),
        "license": metadata.get("License"),
        "license_files": license_files,
        "license_text_sha256": license_digest.hexdigest() if license_files else None,
        "license_classifiers": [
            value
            for value in metadata.get_all("Classifier", [])
            if value.startswith("License ::")
        ],
    }


def inspect_wheelhouse(lock: dict[str, dict[str, str]], wheelhouse: Path) -> list[dict]:
    wheels = sorted(wheelhouse.glob("*.whl"))
    if len(wheels) != len(lock) or len(list(wheelhouse.iterdir())) != len(wheels):
        raise GateError("Wheelhouse has missing or extra artifacts")
    found = []
    for path in wheels:
        meta = wheel_metadata(path)
        expected = lock.get(meta["name"])
        digest = sha256(path)
        if not expected or expected != {"version": meta["version"], "sha256": digest}:
            raise GateError(f"Unpinned or mismatched wheel: {path.name}")
        found.append({"filename": path.name, "sha256": digest, **meta})
    if {item["name"] for item in found} != set(lock):
        raise GateError("Wheelhouse package identity mismatch")
    return found


def evaluate_vulnerabilities(
    packages: dict[str, dict[str, str]],
    results: list[dict],
    exceptions: dict,
    details: dict[str, dict],
    lock_digest: str,
) -> list[dict]:
    if len(results) != len(packages):
        raise GateError("Incomplete advisory response")
    findings = []
    for (name, entry), result in zip(sorted(packages.items()), results, strict=True):
        if not isinstance(result, dict) or not isinstance(
            result.get("vulns", []), list
        ):
            raise GateError("Malformed advisory response")
        for vuln in result.get("vulns", []):
            identifier = vuln.get("id")
            if not identifier:
                raise GateError("Advisory has no identity")
            detail = details.get(identifier)
            if not isinstance(detail, dict) or detail.get("id") != identifier:
                raise GateError(f"Missing advisory detail: {identifier}")
            database_specific = detail.get("database_specific")
            if not isinstance(database_specific, dict):
                raise GateError(f"Unknown advisory severity: {identifier}")
            severity = database_specific.get("severity", "UNKNOWN")
            severity = {"MODERATE": "MEDIUM"}.get(severity, severity)
            if severity not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
                raise GateError(f"Unknown advisory severity: {identifier}")
            finding = {
                "package": name,
                "version": entry["version"],
                "id": identifier,
                "severity": severity,
            }
            findings.append(finding)
            key = f"{name}=={entry['version']}:{identifier}"
            waiver = exceptions.get(key)
            if severity in {"CRITICAL", "HIGH"}:
                raise GateError(f"Non-waivable {severity} vulnerability: {key}")
            if not waiver or waiver.get("severity") != severity:
                raise GateError(f"Undispositioned vulnerability: {key}")
            required = {
                "candidate",
                "impact",
                "compensating_controls",
                "detection",
                "rollback",
                "owner",
                "remediation_date",
                "expires_at",
                "product_owner",
                "certification_owner",
                "security_reviewer",
            }
            if (
                not required <= waiver.keys()
                or not all(waiver.values())
                or waiver["candidate"] != lock_digest
            ):
                raise GateError(f"Incomplete vulnerability exception: {key}")
            expiry = datetime.fromisoformat(waiver["expires_at"]).date()
            if (
                expiry <= datetime.now(UTC).date()
                or (expiry - datetime.now(UTC).date()).days > 90
            ):
                raise GateError(f"Expired vulnerability exception: {key}")
    return findings


def query_osv(packages: dict[str, dict[str, str]]) -> list[dict]:
    queries = [
        {"version": entry["version"], "package": {"name": name, "ecosystem": "PyPI"}}
        for name, entry in sorted(packages.items())
    ]
    response, _ = _url_json(OSV, data={"queries": queries})
    results = response.get("results")
    if not isinstance(results, list):
        raise GateError("Advisory service gave no complete result set")
    return results


def fetch_advisory_details(results: list[dict]) -> dict[str, dict]:
    identifiers = sorted(
        {vuln["id"] for result in results for vuln in result.get("vulns", [])}
    )
    return {
        identifier: _url_json("https://api.osv.dev/v1/vulns/" + identifier)[0]
        for identifier in identifiers
    }


def evaluate_licenses(wheels: list[dict], approvals: dict) -> list[str]:
    blocked = []
    for wheel in wheels:
        key = f"{wheel['name']}=={wheel['version']}:{wheel['sha256']}"
        approval = approvals.get(key)
        if not approval or approval.get("status") != "ALLOW":
            blocked.append(key)
            continue
        required = {
            "license_text_sha256",
            "license_expression",
            "product_owner",
            "reviewed_at",
            "compatibility_reason",
        }
        declared = wheel["license_expression"] or wheel["license"]
        if (
            not required <= approval.keys()
            or not all(approval.values())
            or not wheel["license_text_sha256"]
            or approval["license_text_sha256"] != wheel["license_text_sha256"]
            or (declared and approval["license_expression"] != declared)
            or (not declared and not approval.get("license_source_evidence"))
        ):
            blocked.append(key)
    return blocked


def make_sbom(wheels: list[dict], image: dict, lock: Path) -> dict:
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(UTC).isoformat(),
            "component": {
                "type": "application",
                "name": "bonira-dependency-wheelhouse",
            },
            "properties": [
                {"name": "bonira:target", "value": image["target"]},
                {"name": "bonira:image-digest", "value": image["platform_digest"]},
                {"name": "bonira:lock-sha256", "value": sha256(lock)},
                {"name": "bonira:index", "value": INDEX},
            ],
        },
        "components": [
            {
                "type": "library",
                "name": wheel["name"],
                "version": wheel["version"],
                "purl": f"pkg:pypi/{wheel['name']}@{wheel['version']}",
                "hashes": [{"alg": "SHA-256", "content": wheel["sha256"]}],
                "properties": [
                    {"name": "bonira:wheel", "value": wheel["filename"]},
                    {
                        "name": "bonira:license-expression",
                        "value": wheel["license_expression"] or "",
                    },
                    {
                        "name": "bonira:license-classifiers",
                        "value": ";".join(wheel["license_classifiers"]),
                    },
                ],
            }
            for wheel in wheels
        ],
    }


def check_secret_config() -> None:
    if shutil.which("git"):
        tracked = subprocess.run(
            ["git", "ls-files", "--", ".env", ".env.*"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        if any(name != ".env.example" for name in tracked):
            raise GateError("A local environment/secret file is tracked")
    elif (ROOT / ".env").exists():
        raise GateError("Untracked environment file is present in build checkout")
    if ".env" not in (ROOT / ".gitignore").read_text(encoding="utf-8"):
        raise GateError("Environment files are not excluded from source control")
    for name in ("requirements-prod-linux.lock", "requirements-dev-linux.lock"):
        text = (ROOT / name).read_text(encoding="utf-8")
        if any(
            value in text
            for value in ("http://", "--extra-index-url", "--trusted-host")
        ):
            raise GateError("Unsafe acquisition configuration in lock")


def run_gate(wheelhouse: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    evidence = {
        "schema_version": 1,
        "started_at": datetime.now(UTC).isoformat(),
        "status": "BLOCKED",
        "production_readiness": "UTV",
        "source": INDEX,
        "target": "CPython 3.11.17 Debian 12 linux/amd64",
        "checks": {},
    }
    try:
        locks = validate_locks()
        evidence["checks"]["locks"] = "PASS"
        check_secret_config()
        evidence["checks"]["secret_config"] = "PASS"
        image = verify_image_identity()
        evidence["checks"]["image_identity"] = "PASS"
        evidence["image_digest"] = image["platform_digest"]
        exceptions = json.loads((POLICY / "vulnerability_exceptions.json").read_text())
        approvals = json.loads((POLICY / "license_approvals.json").read_text())
        evidence["sets"] = {}
        all_blocked = []
        for kind in ("prod", "dev"):
            lock_path = ROOT / f"requirements-{kind}-linux.lock"
            wheel_dir = wheelhouse / kind
            wheel_dir.mkdir(parents=True, exist_ok=True)
            pip_download(lock_path, wheel_dir)
            wheels = inspect_wheelhouse(locks[kind], wheel_dir)
            pip_download(lock_path, wheel_dir, offline=True)
            (output / f"sbom-{kind}.cdx.json").write_text(
                json.dumps(make_sbom(wheels, image, lock_path), indent=2) + "\n",
                encoding="utf-8",
            )
            results = query_osv(locks[kind])
            (output / f"osv-{kind}-response.json").write_text(
                json.dumps(results, indent=2) + "\n", encoding="utf-8"
            )
            details = fetch_advisory_details(results)
            (output / f"osv-{kind}-details.json").write_text(
                json.dumps(details, indent=2) + "\n", encoding="utf-8"
            )
            findings = evaluate_vulnerabilities(
                locks[kind], results, exceptions, details, sha256(lock_path)
            )
            (output / f"licenses-{kind}.json").write_text(
                json.dumps(wheels, indent=2) + "\n", encoding="utf-8"
            )
            blocked = evaluate_licenses(wheels, approvals)
            all_blocked.extend(blocked)
            evidence["sets"][kind] = {
                "lock_sha256": sha256(lock_path),
                "wheel_count": len(wheels),
                "vulnerabilities": findings,
                "license_unreviewed": blocked,
            }
            evidence["checks"][f"{kind}_wheelhouse_hash_offline"] = "PASS"
            evidence["checks"][f"{kind}_sbom"] = "PASS"
            evidence["checks"][f"{kind}_vulnerabilities"] = "PASS"
        if all_blocked:
            raise GateError(f"Unreviewed license artifacts: {len(set(all_blocked))}")
        evidence["checks"]["licenses"] = "PASS"
        evidence["status"] = "BUILD_CONTROL_PASS"
    except (
        GateError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        zipfile.BadZipFile,
        subprocess.TimeoutExpired,
        urllib.error.URLError,
    ) as exc:
        evidence["failure"] = str(exc)
    finally:
        evidence["completed_at"] = datetime.now(UTC).isoformat()
        (output / "gate-result.json").write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
        )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check-locks", "gate"))
    parser.add_argument(
        "--wheelhouse", type=Path, default=ROOT / "output/cep-013/artifacts"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "output/cep-013/gate")
    args = parser.parse_args()
    if args.command == "check-locks":
        try:
            validate_locks()
            check_secret_config()
        except GateError as exc:
            print(f"BLOCKED: {exc}")
            return 1
        print("PASS: exact Linux locks and secret/acquisition configuration")
        return 0
    result = run_gate(args.wheelhouse, args.output)
    print(result["status"], result.get("failure", ""))
    return 0 if result["status"] == "BUILD_CONTROL_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

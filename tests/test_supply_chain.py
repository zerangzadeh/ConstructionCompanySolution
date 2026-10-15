"""Focused fail-closed checks for the CEP-013 build control."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts import supply_chain as sc


def _wheel(directory: Path) -> Path:
    path = directory / "asgiref-3.12.1-py3-none-any.whl"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "asgiref-3.12.1.dist-info/METADATA",
            "Metadata-Version: 2.3\nName: asgiref\nVersion: 3.12.1\n"
            "License-Expression: BSD-3-Clause\n",
        )
        archive.writestr(
            "asgiref-3.12.1.dist-info/licenses/LICENSE", "BSD license text"
        )
    return path


def test_linux_locks_preserve_versions_and_separate_runtime() -> None:
    locks = sc.validate_locks()
    assert len(locks["prod"]) == 7
    assert len(locks["dev"]) == 15
    assert "pytest" not in locks["prod"]
    assert "ruff" not in locks["prod"]
    assert "psycopg-binary" not in locks["prod"]
    assert "psycopg-binary" not in locks["dev"]
    assert locks["prod"]["psycopg"] == locks["dev"]["psycopg"]


def test_lock_parser_rejects_unhashed_and_duplicate_entries(tmp_path: Path) -> None:
    path = tmp_path / "lock"
    path.write_text("django==5.2.17\n", encoding="utf-8")
    with pytest.raises(sc.GateError, match="unhashed"):
        sc.load_lock(path)
    line = "django==5.2.17 \\" + "\n    --hash=sha256:" + "a" * 64 + "\n"
    path.write_text(line * 2, encoding="utf-8")
    with pytest.raises(sc.GateError, match="Duplicate"):
        sc.load_lock(path)


def test_wheelhouse_rejects_missing_extra_and_tampered_artifact(tmp_path: Path) -> None:
    wheel = _wheel(tmp_path)
    lock = {"asgiref": {"version": "3.12.1", "sha256": sc.sha256(wheel)}}
    assert sc.inspect_wheelhouse(lock, tmp_path)[0]["name"] == "asgiref"
    wheel.write_bytes(wheel.read_bytes() + b"tamper")
    with pytest.raises(sc.GateError, match="mismatched"):
        sc.inspect_wheelhouse(lock, tmp_path)
    wheel.unlink()
    with pytest.raises(sc.GateError, match="missing"):
        sc.inspect_wheelhouse(lock, tmp_path)


def _waiver(severity: str) -> dict:
    return {
        "severity": severity,
        "candidate": "lock-digest",
        "impact": "bounded impact",
        "compensating_controls": "isolation",
        "detection": "scanner",
        "rollback": "restore previous release",
        "owner": "maintainer",
        "remediation_date": "2026-11-01",
        "expires_at": (datetime.now(UTC) + timedelta(days=30)).date().isoformat(),
        "product_owner": "approved",
        "certification_owner": "approved",
        "security_reviewer": "approved",
    }


@pytest.mark.parametrize("severity", ["HIGH", "CRITICAL", "UNKNOWN"])
def test_unwaivable_or_unknown_advisory_blocks(severity: str) -> None:
    packages = {"django": {"version": "5.2.17", "sha256": "a" * 64}}
    results = [{"vulns": [{"id": "GHSA-example"}]}]
    details = {
        "GHSA-example": {
            "id": "GHSA-example",
            "database_specific": {"severity": severity},
        }
    }
    with pytest.raises(sc.GateError):
        sc.evaluate_vulnerabilities(
            packages,
            results,
            {"django==5.2.17:GHSA-example": _waiver(severity)},
            details,
            "lock-digest",
        )


def test_medium_advisory_requires_exact_current_approval() -> None:
    packages = {"django": {"version": "5.2.17", "sha256": "a" * 64}}
    results = [{"vulns": [{"id": "GHSA-example"}]}]
    details = {
        "GHSA-example": {
            "id": "GHSA-example",
            "database_specific": {"severity": "MODERATE"},
        }
    }
    key = "django==5.2.17:GHSA-example"
    with pytest.raises(sc.GateError, match="Undispositioned"):
        sc.evaluate_vulnerabilities(packages, results, {}, details, "lock-digest")
    waiver = _waiver("MEDIUM")
    assert (
        sc.evaluate_vulnerabilities(
            packages, results, {key: waiver}, details, "lock-digest"
        )[0]["severity"]
        == "MEDIUM"
    )
    waiver["candidate"] = "other-lock"
    with pytest.raises(sc.GateError, match="Incomplete"):
        sc.evaluate_vulnerabilities(
            packages, results, {key: waiver}, details, "lock-digest"
        )


def test_unknown_or_unreviewed_license_blocks_exact_artifact(tmp_path: Path) -> None:
    wheel = sc.wheel_metadata(_wheel(tmp_path))
    wheel["sha256"] = "a" * 64
    key = f"asgiref=={wheel['version']}:{wheel['sha256']}"
    assert sc.evaluate_licenses([wheel], {}) == [key]
    approval = {
        "status": "ALLOW",
        "license_text_sha256": wheel["license_text_sha256"],
        "license_expression": wheel["license_expression"] or wheel["license"],
        "product_owner": "approved",
        "reviewed_at": "2026-10-15",
        "compatibility_reason": "reviewed exact license text",
    }
    assert sc.evaluate_licenses([wheel], {key: approval}) == []
    approval["license_text_sha256"] = "b" * 64
    assert sc.evaluate_licenses([wheel], {key: approval}) == [key]


def test_missing_license_expression_requires_review_source(tmp_path: Path) -> None:
    wheel = sc.wheel_metadata(_wheel(tmp_path))
    wheel.update({"sha256": "a" * 64, "license_expression": None, "license": None})
    key = f"asgiref=={wheel['version']}:{wheel['sha256']}"
    approval = {
        "status": "ALLOW",
        "license_text_sha256": wheel["license_text_sha256"],
        "license_expression": "BSD-3-Clause",
        "product_owner": "approved",
        "reviewed_at": "2026-10-15",
        "compatibility_reason": "exact text reviewed",
    }
    assert sc.evaluate_licenses([wheel], {key: approval}) == [key]
    approval["license_source_evidence"] = "reviewed LICENSE file in exact wheel"
    assert sc.evaluate_licenses([wheel], {key: approval}) == []

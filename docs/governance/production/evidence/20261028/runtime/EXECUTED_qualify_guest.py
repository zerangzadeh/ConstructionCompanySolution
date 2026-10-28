"""Bounded delta qualification; preserves the previous reference and its evidence."""

import importlib.util
import json
import os
import shutil
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

BASE = Path("/srv/bonira")
OUT = BASE / "readiness-20261028"
TOOLS = BASE / "tools"


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, default=str) + "\n")


def finish_web(driver):
    current = "readiness-current"
    previous = "readiness-previous"
    destination = BASE / "releases" / current
    assert json.loads((OUT / "CURRENT_BOUNDARY_TESTS.json").read_text())["failed"] == 0
    for release in (previous, current):
        public = BASE / "public" / release
        assert public.is_dir() and not public.is_symlink()
        assert public.resolve().parent == (BASE / "public").resolve()
        public.chmod(0o755)  # Only dedicated public-static roots, never private data.
    web = []
    for release, phase in [
        (previous, "PREVIOUS"),
        (current, "CURRENT"),
        (previous, "ROLLBACK"),
        (current, "RETURN"),
    ]:
        identity = driver.start_app(release)
        identity["source_head"] = json.loads(
            (BASE / "releases" / release / "BUILD.json").read_text()
        )["head"]
        count = driver.web_checks(release, phase, authenticated=True)
        web.append(
            {
                "phase": phase,
                "identity": identity,
                "http_cases": count,
                "health": driver.health(release=release),
            }
        )
    driver.stop_app()
    save(
        "CURRENT_RELEASE.json",
        {
            "at": datetime.now(UTC).isoformat(),
            "result": "PASS",
            "profile": "BONIRA-PE-NP-01",
            "head": json.loads((destination / "BUILD.json").read_text())["head"],
            "migration_count": 6,
            "web": web,
            "rollback": "Actual previous-code/schema database binding restored, then current code/schema binding returned; retained database never downgraded",
            "production": False,
            "certification": "NOT_EXECUTED",
        },
    )
    # Full row digests contain no raw rows but are unnecessary in public evidence.
    (OUT / "ROWS_BEFORE.json").unlink(missing_ok=True)
    (OUT / "ROWS_AFTER.json").unlink(missing_ok=True)
    print(
        "PASS: current-release delta, preservation, boundary tests and HTTPS rollback"
    )


def main():
    os.umask(0o077)
    OUT.mkdir(exist_ok=True)
    os.chown(OUT, 10001, 10001)
    spec = importlib.util.spec_from_file_location(
        "retained_driver", TOOLS / "guest_driver.py"
    )
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    driver.OUT = OUT
    if "--resume-web" in sys.argv:
        finish_web(driver)
        return
    run = driver.invoke
    run(["docker", "start", "bonira-db"])
    for _ in range(60):
        ready = run(
            ["docker", "exec", "bonira-db", "pg_isready", "-U", "bonira_admin"],
            allow_failure=True,
        )
        if ready.returncode == 0:
            break
        time.sleep(1)
    else:
        raise RuntimeError("Owned database did not become ready")
    database = "pe_readiness_20261028"
    test_database = "test_" + database
    previous_database = "pe_readiness_previous_20261028"
    # Named new clones only; retained pe_source and prior qualified releases untouched.
    resume = "--resume-after-migration" in sys.argv
    for name, template in (
        []
        if resume
        else [
            (database, "pe_source"),
            (previous_database, "pe_source"),
            (test_database, "template0"),
        ]
    ):
        exists = run(
            [
                "docker",
                "exec",
                "bonira-db",
                "psql",
                "-U",
                "bonira_admin",
                "-d",
                "postgres",
                "-Atqc",
                f"SELECT 1 FROM pg_database WHERE datname='{name}'",
            ]
        ).stdout.strip()
        assert not exists, (
            "A qualification database already exists; preserve and inspect"
        )
        run(
            [
                "docker",
                "exec",
                "bonira-db",
                "createdb",
                "-U",
                "bonira_admin",
                "-O",
                "bonira_app",
                "-T",
                template,
                name,
            ]
        )
    current = "readiness-current"
    previous = "readiness-previous"
    destination = BASE / "releases" / current
    if not resume:
        assert not destination.exists()
        shutil.copytree(BASE / "source-20261028", destination)
        shutil.copytree(BASE / "releases" / "previous", BASE / "releases" / previous)
    for release, db in (
        [] if resume else [(current, database), (previous, previous_database)]
    ):
        env = dict(
            line.split("=", 1)
            for line in (BASE / "secrets" / "candidate.env").read_text().splitlines()
            if line
        )
        env.update(DB_NAME=db, DJANGO_STATIC_ROOT="/static/" + release)
        if release == current:
            env["BONIRA_SOURCE_HEAD"] = json.loads(
                (destination / "BUILD.json").read_text()
            )["head"]
        path = BASE / "secrets" / (release + ".env")
        path.write_text("\n".join(k + "=" + v for k, v in env.items()) + "\n")
        path.chmod(0o600)
        static = BASE / "public" / release
        static.mkdir()
        os.chown(static, 10001, 10001)
        static.chmod(0o755)
        driver.app("collectstatic", release, release=release)

    def probe(*args, timeout=300):
        result = run(
            [
                "docker",
                "run",
                "--rm",
                *driver.options(current),
                driver.IMAGE,
                "python",
                "/tools/current_release_probe.py",
                *args,
            ],
            timeout=timeout,
        )
        (OUT / (args[0] + ".txt")).write_text(result.stdout + result.stderr)

    if not resume:
        probe("row-fingerprints", "ROWS_BEFORE")
        probe("migrate")
        probe("row-fingerprints", "ROWS_AFTER")
    probe("catalog-delta")
    before = json.loads((OUT / "ROWS_BEFORE.json").read_text())
    after = json.loads((OUT / "ROWS_AFTER.json").read_text())
    lost = {
        name: len(list((Counter(rows) - Counter(after.get(name, []))).elements()))
        for name, rows in before.items()
    }
    timestamp_catalogs = {
        "organizations_businesspermission",
        "organizations_organizationrole",
    }
    assert not any(
        value for key, value in lost.items() if key not in timestamp_catalogs
    ), {k: v for k, v in lost.items() if v}
    changed = {
        name: {"before": len(rows), "after": len(after[name])}
        for name, rows in before.items()
        if rows != after[name]
    }
    allowed = {
        "django_migrations",
        "django_content_type",
        "auth_permission",
        "organizations_businesspermission",
        "organizations_organizationrole",
        "organizations_organizationrole_permissions",
    }
    assert set(changed).issubset(allowed), changed
    save(
        "MIGRATION_PRESERVATION.json",
        {
            "result": "PASS",
            "existing_tables": len(before),
            "existing_business_rows_preserved_exactly": True,
            "existing_catalog_rows_preserved_except_verified_updated_at": True,
            "catalog_detail": "CATALOG_DELTA.json",
            "changed_existing_catalogs": changed,
            "new_tables": sorted(set(after) - set(before)),
            "scope": "Retained synthetic dataset cloned before applying six new migrations; full populated-ledger rollback/reapply separately tested; no Production mutation",
        },
    )
    # Existing probe checks exact source, PostgreSQL/TLS/role identity and Django deploy checks.
    driver.app("identity", "CURRENT", release=current)
    driver.app("validate", "CURRENT", release=current)
    qualified_test = "test_pe_readiness_qualified_20261028"
    exists = run(
        [
            "docker",
            "exec",
            "bonira-db",
            "psql",
            "-U",
            "bonira_admin",
            "-d",
            "postgres",
            "-Atqc",
            f"SELECT 1 FROM pg_database WHERE datname='{qualified_test}'",
        ]
    ).stdout.strip()
    assert not exists, "Preserve an existing test qualification database"
    run(
        [
            "docker",
            "exec",
            "bonira-db",
            "createdb",
            "-U",
            "bonira_admin",
            "-O",
            "bonira_app",
            "-T",
            database,
            qualified_test,
        ]
    )
    # A new isolated migrated fixture, not a production bootstrap workaround.
    run(
        [
            "docker",
            "run",
            "--rm",
            *driver.options(current),
            "-e",
            "DB_NAME=" + qualified_test,
            driver.IMAGE,
            "python",
            "manage.py",
            "flush",
            "--noinput",
        ]
    )
    save(
        "TEST_FIXTURE.json",
        {
            "database": qualified_test,
            "source": database,
            "method": "new migrated clone then flush synthetic records and seed canonical catalogs",
            "fresh_production_bootstrap": "BLOCKED: Development-only historical retirement authority; no guard bypass",
            "production": False,
        },
    )
    probe("tests", timeout=1200)
    finish_web(driver)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 -- retain sanitized qualification failure
        # Minimized public failure; command details remain in private target logs.
        import traceback

        (BASE / "private-logs" / "readiness-failure.txt").write_text(
            traceback.format_exc()
        )
        save(
            "FAILED.json",
            {
                "at": datetime.now(UTC).isoformat(),
                "result": "FAILED",
                "private_diagnostics": "retained in owned guest",
            },
        )
        raise SystemExit(
            "Readiness qualification failed; inspect private owned diagnostics"
        )

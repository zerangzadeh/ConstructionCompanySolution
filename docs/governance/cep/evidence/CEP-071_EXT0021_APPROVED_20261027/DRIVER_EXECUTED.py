"""Approved EXT-0021 Development deployment; no Production equivalence.

Existing Windows runtime, private settings source, existing isolated PostgreSQL
test database, local restricted releases and loopback stdlib WSGI only.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, make_server


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(path: Path) -> dict[str, str]:
    return {
        p.relative_to(path).as_posix(): digest(p)
        for p in path.rglob("*")
        if p.is_file()
    }


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def guard_database(settings) -> None:
    database = settings.DATABASES["default"]
    if not str(database["NAME"]).startswith("test_") or database["HOST"] not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise RuntimeError("Only the existing loopback test database is permitted.")


def child(action: str, stage: Path) -> int:
    # The copied application release, not the checkout, wins module resolution.
    sys.path.insert(0, str(Path.cwd()))
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"
    import django
    from django.conf import settings
    from django.test import override_settings

    guard_database(settings)
    config = json.loads((stage / "runtime.json").read_text(encoding="utf-8"))
    with override_settings(
        DEBUG=False,
        REFERENCE_PERSONA_CATALOGUE_ENABLED=False,
        ALLOWED_HOSTS=["127.0.0.1"],
        STATIC_ROOT=Path(config["static"]),
        MEDIA_ROOT=Path(config["media"]),
        DOCUMENT_PROTECTED_ROOT=Path(config["private"]),
    ):
        django.setup()
        from django.core.management import call_command

        if action == "prepare":
            call_command("check")
            call_command("collectstatic", interactive=False, verbosity=0)
            return 0
        if action == "health":
            call_command("operational_health")
            return 0
        if action == "startup-failure":
            print(
                json.dumps(
                    {
                        "result": "FAILED",
                        "reason": "controlled-candidate-startup-failure",
                    }
                )
            )
            return 78
        from django.contrib.staticfiles.handlers import StaticFilesHandler

        from config.wsgi import application

        class QuietHandler(WSGIRequestHandler):
            def log_message(self, *args):
                pass

        with make_server(
            "127.0.0.1",
            config["port"],
            StaticFilesHandler(application),
            handler_class=QuietHandler,
        ) as server:
            write_json(
                stage / "ready.json",
                {
                    "pid": os.getpid(),
                    "port": server.server_port,
                    "settings": settings.SETTINGS_MODULE,
                    "debug": settings.DEBUG,
                    "reference_personas": settings.REFERENCE_PERSONA_CATALOGUE_ENABLED,
                    "release": config["release"],
                    "scope": "loopback-development-only",
                },
            )
            server.serve_forever(poll_interval=0.1)
    return 0


def execute(output: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"
    import django
    import psycopg

    django.setup()
    from django.conf import settings
    from django.db import connection, transaction

    from scripts.cep070_recovery_controls import (
        create_private_store,
        verify_private_tree,
    )

    if not output.is_absolute() or not output.is_dir():
        raise RuntimeError("An existing absolute evidence directory is required.")
    if (output / "SCENARIO.json").exists():
        raise RuntimeError("Use a fresh directory; never overwrite a scenario attempt.")
    secret_acl = verify_private_tree(root / ".env", boundary=False)
    store = create_private_store(Path("E:/BONIRA_Operations/EXT0021"))
    database = settings.DATABASES["default"]
    test_name = database.get("TEST", {}).get("NAME") or "test_" + database["NAME"]
    connection.close()
    connection.settings_dict["NAME"] = test_name
    database["NAME"] = test_name
    guard_database(settings)

    def schema_identity():
        # Connection failure is fatal: never create a database or run migrations.
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SELECT current_database()")
            if cursor.fetchone()[0] != test_name:
                raise RuntimeError("Unexpected database identity.")
            cursor.execute("SELECT app, name FROM django_migrations ORDER BY app, name")
            rows = cursor.fetchall()
        return {
            "applied_migrations": len(rows),
            "history_sha256": hashlib.sha256(json.dumps(rows).encode()).hexdigest(),
            "scope": "existing-test-database-read-only",
        }

    before = schema_identity()
    source_files = (
        subprocess.check_output(
            [
                "git",
                "ls-files",
                "-z",
                "--",
                "apps",
                "config",
                "core",
                "templates",
                "static",
                "manage.py",
            ],
            cwd=root,
        )
        .decode()
        .split("\0")
    )
    source_files = [name for name in source_files if name and (root / name).is_file()]
    if any(
        Path(name).name == ".env" or (root / name).is_symlink() for name in source_files
    ):
        raise RuntimeError("Secret/link source is forbidden in the release.")
    sources = {name: digest(root / name) for name in source_files}
    source_hash = hashlib.sha256(
        json.dumps(sources, sort_keys=True).encode()
    ).hexdigest()
    write_json(output / "SOURCE_HASHES.json", sources)
    environment = os.environ.copy()
    for key, value in (
        ("DB_NAME", test_name),
        ("DB_USER", database["USER"]),
        ("DB_PASSWORD", database["PASSWORD"]),
        ("DB_HOST", database["HOST"]),
        ("DB_PORT", database["PORT"]),
        ("DJANGO_SECRET_KEY", settings.SECRET_KEY),
    ):
        environment[key] = str(value)
    environment["DJANGO_SETTINGS_MODULE"] = "config.settings.development"
    environment["PYTHONIOENCODING"] = "utf-8"
    # A copied release has no dotenv file. Existing private values travel only
    # in the child process environment and never in argv or evidence.
    worker = str(Path(__file__).resolve())
    command = [sys.executable, worker, "--action"]
    manifest = {
        "at": datetime.now(UTC).isoformat(),
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "source_sha256": source_hash,
        "source_files": len(sources),
        "driver_sha256": digest(Path(__file__).resolve()),
        "python": sys.version.split()[0],
        "django": django.get_version(),
        "psycopg": psycopg.__version__,
        "settings": "config.settings.development",
        "store": str(store),
        "secret_source": "existing-repository-private-.env-and-process-environment; no bytes copied",
        "secret_source_acl": secret_acl,
        "database_before": before,
        "production_equivalent": False,
        "production_readiness": "NOT_VALIDATED",
    }
    write_json(output / "ENVIRONMENT.json", manifest)
    steps = []
    running = []

    def step(name: str, **details):
        steps.append(
            {
                "step": name,
                "at": datetime.now(UTC).isoformat(),
                "result": "PASS",
                **details,
            }
        )

    def run_action(stage: Path, action: str, *, fault_port=None):
        env = environment.copy()
        if fault_port is not None:
            env.update(
                DB_HOST="127.0.0.1", DB_PORT=str(fault_port), DB_CONNECT_TIMEOUT="1"
            )
        return subprocess.run(
            [*command, action, "--stage", str(stage)],
            cwd=stage / "code",
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=False,
        )

    def package(name):
        stage = store / name
        code = stage / "code"
        code.mkdir(parents=True)
        for filename in sources:
            target = code / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / filename, target)
        if {name: digest(code / name) for name in sources} != sources:
            raise RuntimeError("Copied application identity mismatch.")
        config = {"release": name, "port": 0}
        for name in ("static", "media", "private"):
            config[name] = str(stage / name)
        for name in ("media", "private"):
            directory = Path(config[name])
            directory.mkdir()
            (directory / "fixture.txt").write_bytes(
                b"isolated-synthetic-private-fixture"
            )
        write_json(stage / "runtime.json", config)
        prepared = run_action(stage, "prepare")
        # Fixed command output contains no configuration dumps or credentials.
        (output / f"{stage.name}_prepare.txt").write_text(
            prepared.stdout + prepared.stderr, encoding="utf-8"
        )
        if prepared.returncode:
            raise RuntimeError(
                "Release preflight failed; inspect retained diagnostics."
            )
        return stage

    def start(stage, port=0):
        config = json.loads((stage / "runtime.json").read_text())
        config["port"] = port
        write_json(stage / "runtime.json", config)
        (stage / "ready.json").unlink(missing_ok=True)
        stream = (stage / "process.log").open("a", encoding="utf-8")
        process = subprocess.Popen(
            [*command, "serve", "--stage", str(stage)],
            cwd=stage / "code",
            env=environment,
            stdout=stream,
            stderr=stream,
        )
        running.append((process, stream))
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Deployment process exited before readiness.")
            if (stage / "ready.json").exists():
                ready = json.loads((stage / "ready.json").read_text())
                if ready["debug"] or ready["reference_personas"]:
                    raise RuntimeError("Unexpected validation settings.")
                return process, ready
            time.sleep(0.05)
        raise RuntimeError("Deployment process readiness timeout.")

    def stop(process):
        process.terminate()
        process.wait(timeout=15)
        if process.poll() is None:
            raise RuntimeError("Deployment process did not stop.")

    def validate(stage, port):
        health = run_action(stage, "health")
        if health.returncode:
            raise RuntimeError("Dependency health validation failed.")
        health_record = json.loads(health.stdout)
        if (
            health_record["signals"] != ["database.reachable", "cache.reachable"]
            or health_record["production_readiness"] != "NOT_VALIDATED"
        ):
            raise RuntimeError("Unexpected health/readiness classification.")
        assets = inventory(stage / "static")
        if not assets:
            raise RuntimeError("Static collection is empty.")
        asset = min(assets)
        cases = [
            ("GET", "/", 302),
            ("POST", "/accounts/login/", 403),
            ("GET", "/media/fixture.txt", 404),
            ("GET", "/private/fixture.txt", 404),
            ("GET", "/static/" + asset, 200),
        ]
        results = []
        for method, path, expected in cases:
            client = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
            try:
                client.request(method, path)
                response = client.getresponse()
                body = response.read()
                if (
                    response.status != expected
                    or b"isolated-synthetic-private-fixture" in body
                ):
                    raise RuntimeError("HTTP/security serving contract failed.")
                if expected == 302 and not response.getheader(
                    "Location", ""
                ).startswith("/accounts/login/"):
                    raise RuntimeError("Anonymous authorization boundary changed.")
                if (
                    expected == 200
                    and hashlib.sha256(body).hexdigest() != assets[asset]
                ):
                    raise RuntimeError(
                        "HTTP static asset differs from collected artifact."
                    )
                results.append(
                    {"method": method, "path": path, "status": response.status}
                )
            finally:
                client.close()
        return {
            "health": health_record,
            "requests": results,
            "static_files": len(assets),
            "static_manifest_sha256": hashlib.sha256(
                json.dumps(assets, sort_keys=True).encode()
            ).hexdigest(),
        }

    verdict = "FAILED"
    try:
        previous, candidate = package("previous"), package("candidate")
        media_before = {
            str(stage.name): {
                kind: inventory(stage / kind) for kind in ("media", "private")
            }
            for stage in (previous, candidate)
        }
        previous_static = inventory(previous / "static")
        if previous_static != inventory(candidate / "static"):
            raise RuntimeError("Release asset mismatch.")
        step(
            "BUILD_CONFIG_STATIC",
            same_application_source=True,
            static_files=len(previous_static),
            secret_bytes_packaged=False,
        )
        process, ready = start(previous)
        bound_port = ready["port"]
        step(
            "VERIFY_PREVIOUS_DEPLOYMENT",
            process=ready,
            validation=validate(previous, bound_port),
        )
        stop(process)
        failure = run_action(candidate, "startup-failure")
        if failure.returncode != 78:
            raise RuntimeError("Controlled startup failure was not detected.")
        step(
            "FAILED_CANDIDATE_START_REJECTED",
            exit_code=failure.returncode,
            evidence=json.loads(failure.stdout),
            activation="REJECTED",
        )
        process, ready = start(candidate, bound_port)
        step(
            "CANDIDATE_DEPLOYMENT",
            process=ready,
            validation=validate(candidate, bound_port),
        )
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            failed_health = run_action(
                candidate, "health", fault_port=reserved.getsockname()[1]
            )
            signals = json.loads(failed_health.stdout)
            if failed_health.returncode == 0 or signals["signals"] != [
                "database.unreachable",
                "cache.reachable",
            ]:
                raise RuntimeError("Failed readiness was not rejected.")
        step(
            "CANDIDATE_READINESS_FAILURE",
            exit_code=failed_health.returncode,
            signals=signals,
            activation="REJECTED",
            database_mutation=False,
        )
        stop(process)
        if schema_identity() != before:
            raise RuntimeError(
                "Database history changed; artifact rollback prohibited."
            )
        if any(
            digest(previous / "code" / name) != expected
            for name, expected in sources.items()
        ):
            raise RuntimeError("Previous artifact changed; rollback prohibited.")
        process, ready = start(previous, bound_port)
        step(
            "ACTUAL_PREVIOUS_BUILD_CONFIG_ROLLBACK",
            process=ready,
            validation=validate(previous, bound_port),
            compatibility="same-code-and-existing-schema; no database rollback",
        )
        stop(process)
        if inventory(previous / "static") != previous_static:
            raise RuntimeError("Retained previous static changed.")
        media_after = {
            str(stage.name): {
                kind: inventory(stage / kind) for kind in ("media", "private")
            }
            for stage in (previous, candidate)
        }
        if media_before != media_after or schema_identity() != before:
            raise RuntimeError("Retained media or schema changed.")
        step(
            "PRESERVATION_AND_RECOVERY_VALIDATED",
            previous_static_unchanged=True,
            media_private_unchanged=True,
            schema_history_unchanged=True,
        )
        verdict = "PASS_APPROVED_DEVELOPMENT_PROFILE"
    finally:
        for process, stream in running:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=15)
            stream.close()
        connection.close()
        acl = verify_private_tree(store)
        write_json(
            output / "SCENARIO.json",
            {
                "at": datetime.now(UTC).isoformat(),
                "result": verdict,
                "environment": manifest,
                "steps": steps,
                "acl_after": acl,
                "processes_stopped": all(p.poll() is not None for p, _ in running),
                "production_equivalence": "NOT_ESTABLISHED_NOT_CLAIMED",
                "production_readiness": "NOT_VALIDATED",
                "database_migration_rollback": "NOT_EXECUTED",
            },
        )
    print(
        json.dumps({"result": verdict, "steps": len(steps), "processes_stopped": True})
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--action", choices=["prepare", "health", "startup-failure", "serve"]
    )
    parser.add_argument("--stage", type=Path)
    arguments = parser.parse_args()
    if arguments.action:
        sys.exit(child(arguments.action, arguments.stage))
    execute(arguments.output)

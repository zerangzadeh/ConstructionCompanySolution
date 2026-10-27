"""Serial, evidence-producing acceptance on one approved isolated Linux target."""

from __future__ import annotations

import fcntl
import hashlib
import http.client
import http.cookiejar
import json
import os
import shutil
import ssl
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

BASE = Path("/srv/bonira")
OUT = BASE / "evidence"
IMAGE = "bonira-pe-np-runtime:20261027"
sys.path.insert(0, str(BASE / "source"))
from scripts.backup_bundle import BackupPlan, _inventory, create_bundle

os.umask(0o077)


def stamp():
    return datetime.now(UTC).isoformat()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(args, *, allow_failure=False, timeout=300):
    result = subprocess.run(
        [str(a) for a in args],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode and not allow_failure:
        logs = BASE / "private-logs"
        logs.mkdir(mode=0o700, exist_ok=True)
        (logs / (uuid4().hex + ".log")).write_text(result.stdout + result.stderr)
        raise RuntimeError("Bounded target command failed: " + str(args[0]))
    return result


def options(release="candidate", env=None, state=None, gid=10001):
    return [
        "--network",
        "bonira-pe",
        "--user",
        "10001:" + str(gid),
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,noexec,size=67108864",
        "--env-file",
        str(env or BASE / "secrets" / (release + ".env")),
        "-v",
        str(BASE / "releases" / release) + ":/app:ro",
        "-v",
        str(state or BASE / "shared") + ":/state",
        "-v",
        str(OUT) + ":/evidence",
        "-v",
        str(BASE / "public") + ":/static",
        "-v",
        str(BASE / "tools") + ":/tools:ro",
        "-v",
        str(BASE / "pki" / "ca.crt") + ":/tls/ca.crt:ro",
    ]


def app(action, phase, *, release="candidate", env=None, state=None, fail=False):
    return invoke(
        [
            "docker",
            "run",
            "--rm",
            *options(release, env, state),
            IMAGE,
            "python",
            "/tools/app_probe.py",
            action,
            phase,
        ],
        allow_failure=fail,
    )


def health(*, release="candidate", env=None, fail=False):
    value = invoke(
        [
            "docker",
            "run",
            "--rm",
            *options(release, env),
            IMAGE,
            "python",
            "manage.py",
            "operational_health",
        ],
        allow_failure=fail,
    )
    signal = json.loads(value.stdout)
    assert signal["production_readiness"] == "NOT_VALIDATED"
    assert value.returncode != 0 if fail else value.returncode == 0
    return {"at": stamp(), "exit_code": value.returncode, **signal}


def env_with(name, **changes):
    values = dict(
        line.split("=", 1)
        for line in (BASE / "secrets" / "candidate.env").read_text().splitlines()
        if line
    )
    values.update(changes)
    path = BASE / "secrets" / (name + ".env")
    path.write_text("\n".join(k + "=" + v for k, v in values.items()) + "\n")
    path.chmod(0o600)
    return path


def stop_app():
    names = invoke(["docker", "ps", "-a", "--format", "{{.Names}}"]).stdout.splitlines()
    if "bonira-app" in names:
        # This exact container is created and owned by this target only.
        invoke(["docker", "logs", "bonira-app"], allow_failure=True)
        result = invoke(["docker", "logs", "bonira-app"], allow_failure=True)
        destination = BASE / "private-logs"
        destination.mkdir(mode=0o700, exist_ok=True)
        (destination / ("gunicorn-" + uuid4().hex + ".log")).write_text(
            result.stdout + result.stderr
        )
        # Existing fixed-field telemetry only; retain real new target outcomes.
        events = []
        for line in (result.stdout + result.stderr).splitlines():
            if line.startswith("{"):
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("event") == "http.response":
                    assert set(event) == {
                        "timestamp",
                        "event",
                        "request_id",
                        "method",
                        "route",
                        "status_code",
                        "duration_ms",
                    }
                    events.append(event)
        if events:
            write(OUT / ("TELEMETRY_" + uuid4().hex[:10] + ".json"), events)
        invoke(["docker", "stop", "--time", "20", "bonira-app"])
        invoke(["docker", "rm", "bonira-app"])


def start_app(release):
    stop_app()
    active = BASE / "active_static"
    if active.is_symlink():
        active.unlink()
    assert not active.exists()
    target = BASE / "public" / release
    assert target.resolve().is_relative_to((BASE / "public").resolve())
    active.symlink_to(target, target_is_directory=True)
    socket_root = BASE / "run" / "app"
    socket_root.mkdir(exist_ok=True)
    os.chown(socket_root, 10001, 33)
    socket_root.chmod(0o2770)
    invoke(
        [
            "docker",
            "run",
            "-d",
            "--name",
            "bonira-app",
            *options(release, gid=33),
            "-v",
            str(socket_root) + ":/run/bonira",
            IMAGE,
            "python",
            "-m",
            "gunicorn",
            "config.wsgi:application",
            "--bind",
            "unix:/run/bonira/app.sock",
            "--umask",
            "7",
            "--workers",
            "1",
            "--worker-class",
            "sync",
            "--timeout",
            "120",
            "--access-logfile",
            "/dev/null",
            "--error-logfile",
            "-",
            "--no-control-socket",
        ]
    )
    pid_file = BASE / "run" / "nginx.pid"
    pid = pid_file.read_text().strip() if pid_file.exists() else ""
    running = pid.isdigit() and Path("/proc", pid, "comm").exists()
    if running:
        running = Path("/proc", pid, "comm").read_text().strip() == "nginx"
    if not running:
        invoke(["nginx", "-c", BASE / "nginx.conf"])
    deadline = time.monotonic() + 120
    while True:
        try:
            status, _, _ = request("/")
            if status == 302:
                break
        except (OSError, http.client.HTTPException):
            pass
        if time.monotonic() > deadline:
            raise RuntimeError("Own application failed actual HTTPS startup")
        time.sleep(1)
    identity = invoke(
        [
            "docker",
            "inspect",
            "bonira-app",
            "--format",
            "{{.Image}}|{{.State.Pid}}|{{.State.StartedAt}}|{{.Config.User}}",
        ]
    ).stdout.strip()
    return {
        "at": stamp(),
        "release": release,
        "image_pid_started_uid": identity,
        "source_head": json.loads((BASE / "source" / "BUILD.json").read_text())["head"],
    }


def request(path, method="GET", headers=None, context=None):
    connection = http.client.HTTPSConnection(
        "localhost",
        8443,
        timeout=90,
        context=context
        or ssl.create_default_context(cafile=str(BASE / "pki" / "ca.crt")),
    )
    try:
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def web_checks(release, phase, *, authenticated=False):
    cases = []

    def check(name, condition):
        cases.append({"case": name, "result": "PASS" if condition else "FAIL"})
        assert condition, name

    status, headers, _ = request("/")
    check("anonymous business root requires login", status == 302)
    check(
        "HSTS on real HTTPS", "max-age=" in headers.get("Strict-Transport-Security", "")
    )
    check("missing CSRF rejected", request("/accounts/login/", "POST")[0] == 403)
    assert (
        BASE / "shared" / "document_media" / "media" / "synthetic-media.txt"
    ).is_file()
    check(
        "legacy media not publicly served",
        request("/media/synthetic-media.txt")[0] == 404,
    )
    protected = BASE / "shared" / "document_media" / "protected"
    actual_private = next(path for path in protected.rglob("*") if path.is_file())
    check(
        "private document root not served",
        request(
            "/protected_documents/" + actual_private.relative_to(protected).as_posix()
        )[0]
        == 404,
    )
    check(
        "invalid Host rejected",
        request("/", headers={"Host": "untrusted.invalid"})[0] == 400,
    )
    status, forged_headers, _ = request("/", headers={"X-Forwarded-Proto": "http"})
    check(
        "proxy overwrites forged forwarded-proto",
        status == 302 and "Strict-Transport-Security" in forged_headers,
    )
    assets = json.loads((OUT / (release + "_STATIC.json")).read_text())
    name = next(iter(assets))
    status, _, body = request("/static/" + name)
    check(
        "actual static bytes match release",
        status == 200 and hashlib.sha256(body).hexdigest() == assets[name],
    )
    try:
        request("/", context=ssl.create_default_context())
    except ssl.SSLCertVerificationError:
        check("untrusted HTTPS CA rejected", True)
    else:
        check("untrusted HTTPS CA rejected", False)
    plain = http.client.HTTPConnection("localhost", 8082, timeout=10)
    plain.request("GET", "/")
    response = plain.getresponse()
    check(
        "plain HTTP boundary redirects HTTPS",
        response.status == 301
        and response.getheader("Location").startswith("https://"),
    )
    plain.close()
    if authenticated:
        app("http-fixture", phase)
        fixture = json.loads((BASE / "shared" / "http-fixture.json").read_text())
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(
                context=ssl.create_default_context(cafile=str(BASE / "pki" / "ca.crt"))
            ),
            urllib.request.HTTPCookieProcessor(jar),
        )
        origin = "https://localhost:8443"
        opener.open(origin + "/accounts/login/", timeout=90).read()
        csrf = next(cookie.value for cookie in jar if cookie.name == "csrftoken")
        data = urllib.parse.urlencode(
            {
                "username": "document-owner",
                "password": "test-password",
                "csrfmiddlewaretoken": csrf,
            }
        ).encode()
        response = opener.open(
            urllib.request.Request(
                origin + "/accounts/login/",
                data=data,
                headers={"Referer": origin + "/accounts/login/"},
            ),
            timeout=90,
        )
        response.read()
        check(
            "actual synthetic login succeeds",
            any(cookie.name == "sessionid" for cookie in jar),
        )
        check(
            "session and CSRF cookies Secure",
            all(
                cookie.secure
                for cookie in jar
                if cookie.name in {"sessionid", "csrftoken"}
            ),
        )
        body = opener.open(origin + fixture["own"], timeout=90).read()
        check(
            "authorized private bytes accessible through application",
            hashlib.sha256(body).hexdigest() == fixture["own_sha256"],
        )
        try:
            opener.open(origin + fixture["other"], timeout=90).read()
        except urllib.error.HTTPError as exc:
            check("HTTP cross-tenant private download denied", exc.code in {403, 404})
        else:
            check("HTTP cross-tenant private download denied", False)
    write(
        OUT / (phase + "_HTTP.json"),
        {"at": stamp(), "release": release, "checks": cases, "result": "PASS"},
    )
    return len(cases)


def validate_bundle(bundle):
    capture = json.loads((bundle / "capture.json").read_text())
    assert capture["environment"] == "non-production"
    assert capture["capture_status"] == "CAPTURED_NOT_RESTORE_VERIFIED"
    assert (
        sha(bundle / "database.dump")
        == capture["classes"]["transactional_database"]["sha256"]
    )
    for kind in ["document_media", "configuration_metadata", "audit_operational"]:
        expected = json.loads((bundle / (kind + ".inventory.json")).read_text())
        assert expected == _inventory(bundle / kind)
    return capture


def backup(phase):
    root = BASE / "recovery"
    (root / "bundles").mkdir(parents=True, mode=0o700, exist_ok=True)
    lock_path = root / "worker.lock"
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Prove a second process cannot concurrently own this same target store.
        exclusion = invoke(
            [
                "python3",
                "-c",
                "import fcntl,sys;f=open(sys.argv[1],'a+b');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)",
                lock_path,
            ],
            allow_failure=True,
        )
        assert exclusion.returncode != 0
        started = datetime.now(UTC)
        destination = root / "bundles" / (phase + "-" + uuid4().hex[:10])
        capture = create_bundle(
            BackupPlan(
                environment="non-production",
                source_revision=json.loads(
                    (BASE / "source" / "BUILD.json").read_text()
                )["head"],
                operator_reference="Codex-authorized-nonproduction-executor",
                recovery_reference="BONIRA-PE-NP-01-HUMAN-20261027",
                consistency_reference="controlled-synthetic-no-other-business-writers",
                database_service="bonira_shared",
                pg_dump=BASE / "pg_dump",
                roots={
                    kind: BASE / "shared" / kind
                    for kind in [
                        "document_media",
                        "configuration_metadata",
                        "audit_operational",
                    ]
                },
                destination=destination,
                command_timeout_seconds=180,
            )
        )
        validate_bundle(destination)
        completed = datetime.now(UTC)
        receipt = {
            "at": completed.isoformat(),
            "capture_started_at": started.isoformat(),
            "retain_until": (completed + timedelta(days=30)).isoformat(),
            "next_backup_due": (started + timedelta(seconds=900)).isoformat(),
            "capture_manifest_sha256": sha(destination / "capture.json"),
            "profile": "BONIRA-PE-NP-01",
            "bundle": destination.name,
            "exclusive_worker": "PASS_ACTUAL_SECOND_PROCESS_DENIED",
            "production": False,
            "cadence_scope": "supervised captures;future continuous service not asserted",
        }
        write(destination / "retention.json", receipt)
        write(root / "schedule.json", receipt)
        write(OUT / (phase + "_CAPTURE.json"), {"capture": capture, "receipt": receipt})
        return destination, started


def restore(phase, bundle):
    started = datetime.now(UTC)
    timer = time.monotonic()
    dbname = "pe_restore_" + phase
    assert dbname in {"pe_restore_070", "pe_restore_074"}
    invoke(
        [
            "docker",
            "exec",
            "bonira-db",
            "psql",
            "-U",
            "bonira_admin",
            "-v",
            "ON_ERROR_STOP=1",
            "-d",
            "postgres",
            "-c",
            "CREATE DATABASE " + dbname + " OWNER bonira_app",
        ]
    )
    invoke(
        [
            "docker",
            "cp",
            bundle / "database.dump",
            "bonira-db:/tmp/restore-" + phase + ".dump",
        ]
    )
    invoke(
        [
            "docker",
            "exec",
            "bonira-db",
            "pg_restore",
            "-U",
            "bonira_admin",
            "--role",
            "bonira_app",
            "--exit-on-error",
            "--no-owner",
            "--no-privileges",
            "-d",
            dbname,
            "/tmp/restore-" + phase + ".dump",
        ]
    )
    recovered = BASE / "restored" / phase
    recovered.mkdir(parents=True, mode=0o700)
    file_results = {}
    for kind in ["document_media", "configuration_metadata", "audit_operational"]:
        shutil.copytree(bundle / kind, recovered / kind)
        assert _inventory(bundle / kind) == _inventory(recovered / kind)
        file_results[kind] = "PASS_EXACT_COMPLETE_INVENTORY"
    (recovered / "cache").mkdir()
    for path in [recovered, *recovered.rglob("*")]:
        os.chown(path, 10001, 10001)
        path.chmod(0o700 if path.is_dir() else 0o600)
    env = env_with("restore-" + phase, DB_NAME=dbname)
    app("fingerprint", phase + "_RESTORED", env=env, state=recovered)
    source = json.loads((OUT / (phase + "_SOURCE_FINGERPRINT.json")).read_text())
    target = json.loads((OUT / (phase + "_RESTORED_FINGERPRINT.json")).read_text())
    assert source == target
    app("validate", phase, env=env, state=recovered)
    elapsed = time.monotonic() - timer
    assert elapsed <= 3600
    # All complete rows and the last committed version are present: zero loss
    # within this explicitly quiescent synthetic scenario, no Production SLA.
    report = {
        "at": stamp(),
        "phase": phase,
        "result": "PASS",
        "started_at": started.isoformat(),
        "rpo_seconds": 0,
        "rto_seconds": elapsed,
        "rpo_limit": 900,
        "rto_limit": 3600,
        "rpo_basis": "All rows/sequences/constraints and latest acknowledged synthetic version match;no concurrent business writers",
        "rto_boundary": "New database/file provisioning through integrity and authorized/denied domain service accessibility",
        "tables": len(target["tables"]),
        "rows": sum(t["rows"] for t in target["tables"].values()),
        "constraints": target["constraints_count"],
        "sequences": len(target["sequences"]),
        "files": file_results,
        "next_restore_test_due": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        "profile": "BONIRA-PE-NP-01",
        "production_certification": "NOT_EXECUTED",
    }
    write(OUT / (phase + "_RESTORE.json"), report)
    return report


def recovery(phase):
    if (OUT / (phase + "_RESULT.json")).exists():
        raise RuntimeError("Do not overwrite an executed package result")
    checks = []
    checkpoint = OUT / (phase + "_PREFLIGHT_CHECKPOINT.json")
    if checkpoint.exists():
        retained = json.loads(checkpoint.read_text())
        assert all(sha(OUT / name) == want for name, want in retained["files"].items())
    else:
        app("identity", phase)
        app("tls-negative", phase)
        app("cache-write", phase)
        app("cache-read", phase)
    checks.append(
        "actual approved runtime/TLS/non-superuser/shared-cache/source/config identity"
    )
    if phase == "070":
        if not checkpoint.exists():
            for release in ["previous", "candidate"]:
                app("collectstatic", release, release=release)
            write(
                checkpoint,
                {
                    "at": stamp(),
                    "files": {
                        name: sha(OUT / name)
                        for name in [
                            "070_IDENTITY.json",
                            "070_TLS_NEGATIVE.json",
                            "previous_STATIC.json",
                            "candidate_STATIC.json",
                        ]
                    },
                    "cache": "separate write/read processes exited0 before static builds",
                },
            )
        identity = start_app("candidate")
        web_checks("candidate", "070_QUALIFY")
        stop_app()
        checks.append("actual Nginx/Gunicorn production-settings HTTPS boundary")
        # Place actual fixed-field new-target records in the governed log class.
        telemetry = sorted(OUT.glob("TELEMETRY_*.json"))
        assert telemetry
        shutil.copy2(
            telemetry[-1], BASE / "shared" / "audit_operational" / "runtime.json"
        )
    else:
        assert (
            json.loads((OUT / "070_RESULT.json").read_text())["execution"] == "COMPLETE"
        )
        checks.append(
            "mandatory CEP070 exact target outcome available before074 execution"
        )
    app("fresh-write", phase)
    app("fingerprint", phase + "_SOURCE")
    first, first_started = backup(phase)
    checks.append(
        "actual complete four-class capture over verify-full TLS with OS process exclusion"
    )
    damaged = BASE / "recovery" / ("corrupt-" + phase)
    shutil.copytree(first, damaged)
    with (damaged / "database.dump").open("r+b") as handle:
        handle.seek(40)
        handle.write(b"CORRUPT")
    try:
        validate_bundle(damaged)
    except AssertionError:
        checks.append(
            "corrupted bundle rejected before restore and never advances last-good"
        )
    else:
        raise AssertionError("Corruption accepted")
    failed = invoke(
        [
            "docker",
            "exec",
            "bonira-db",
            "pg_restore",
            "--exit-on-error",
            "/tmp/absent-qualification.dump",
        ],
        allow_failure=True,
    )
    assert failed.returncode != 0
    write(
        OUT / (phase + "_FAILED_RESTORE_CONTROL.json"),
        {
            "at": stamp(),
            "result": "EXPECTED_FAILURE_REJECTED",
            "exit": failed.returncode,
            "readiness": "NOT_PASS",
        },
    )
    checks.append("actual failing restore leaves explicit failure evidence")
    restoration = restore(phase, first)
    checks.append(
        "complete integrity/accessibility/tenant read/write denial and approved objectives"
    )
    app("fingerprint", phase + "_SOURCE_AFTER")
    assert json.loads(
        (OUT / (phase + "_SOURCE_FINGERPRINT.json")).read_text()
    ) == json.loads((OUT / (phase + "_SOURCE_AFTER_FINGERPRINT.json")).read_text())
    second, second_started = backup(phase + "_SECOND")
    interval = (second_started - first_started).total_seconds()
    assert 0 < interval <= 900
    checks.append(
        "two actual supervised complete captures start within approved900-second maximum"
    )
    retained = json.loads((first / "retention.json").read_text())
    assert datetime.fromisoformat(retained["retain_until"]) - datetime.fromisoformat(
        retained["at"]
    ) == timedelta(days=30)
    assert validate_bundle(first) and validate_bundle(second)
    checks.append(
        "30-day minimum retention receipts/due dates;no purge and no future-elapsed claim"
    )
    write(
        OUT / (phase + "_RESULT.json"),
        {
            "at": stamp(),
            "cep": "CEP-" + phase,
            "execution": "COMPLETE",
            "ac": {
                "AC" + str(i): "PASS_APPROVED_NONPRODUCTION_TARGET" for i in range(1, 7)
            },
            "dod": "MET_APPROVED_NONPRODUCTION_SCOPE",
            "profile": "BONIRA-PE-NP-01",
            "checks": checks,
            "check_groups": len(checks),
            "capture_interval_seconds": interval,
            "restore": restoration,
            "identity": identity if phase == "070" else "074_IDENTITY.json",
            "authority": "BONIRA-PE-NP-01_HUMAN_APPROVAL_20261027",
            "limitations": [
                "synthetic lower-scale controlled dataset",
                "no Production SLA/HA/provider/storage/key-custody claim",
                "future retention/drill/continuous operation not asserted",
            ],
            "production_certification": "NOT_EXECUTED",
            "human_signoff": "NOT_EXECUTED",
            "git_write": False,
        },
    )
    print("CEP-" + phase + " runtime scenario PASS", flush=True)


def deploy():
    assert json.loads((OUT / "074_RESULT.json").read_text())["execution"] == "COMPLETE"
    steps = []
    app("history", "075_BEFORE")
    before_files = _inventory(BASE / "shared" / "document_media")
    for release in ["previous", "candidate"]:
        app("identity", "075_" + release, release=release)
        app("collectstatic", release, release=release)
    assert json.loads((OUT / "previous_STATIC.json").read_text()) == json.loads(
        (OUT / "candidate_STATIC.json").read_text()
    )
    previous = start_app("previous")
    previous_cases = web_checks("previous", "075_PREVIOUS", authenticated=True)
    steps.append(
        {
            "step": "previous verified current-source build",
            "identity": previous,
            "http_cases": previous_cases,
            "health": health(release="previous"),
        }
    )
    stop_app()
    invalid = env_with("invalid-candidate", DJANGO_SECRET_KEY="")
    failed = app("identity", "075_CONTROL_BAD_CONFIG", env=invalid, fail=True)
    assert failed.returncode != 0
    steps.append(
        {
            "step": "actual invalid candidate startup rejected",
            "exit_code": failed.returncode,
        }
    )
    candidate = start_app("candidate")
    candidate_cases = web_checks("candidate", "075_CANDIDATE", authenticated=True)
    steps.append(
        {
            "step": "candidate actual deployment",
            "identity": candidate,
            "http_cases": candidate_cases,
            "health": health(),
        }
    )
    unavailable = env_with("unavailable-db", DB_PORT="65432")
    bad_health = health(env=unavailable, fail=True)
    steps.append({"step": "failed candidate readiness rejected", "health": bad_health})
    stop_app()
    rollback = start_app("previous")
    rollback_cases = web_checks("previous", "075_ROLLBACK", authenticated=True)
    steps.append(
        {
            "step": "rollback to previously verified build/config/static",
            "identity": rollback,
            "http_cases": rollback_cases,
            "health": health(release="previous"),
        }
    )
    stop_app()
    final = start_app("candidate")
    final_cases = web_checks("candidate", "075_RETURN_CANDIDATE", authenticated=True)
    steps.append(
        {
            "step": "return to verified candidate",
            "identity": final,
            "http_cases": final_cases,
            "health": health(),
        }
    )
    stop_app()
    app("history", "075_AFTER")
    assert json.loads((OUT / "075_BEFORE_HISTORY.json").read_text()) == json.loads(
        (OUT / "075_AFTER_HISTORY.json").read_text()
    )
    assert before_files == _inventory(BASE / "shared" / "document_media")
    for release in ["previous", "candidate"]:
        app("identity", "075_FINAL_" + release, release=release)
    steps.append(
        {
            "step": "source/config/migration-history/protected-file preservation",
            "result": "PASS",
            "migration_operations": "NONE",
        }
    )
    write(
        OUT / "075_RESULT.json",
        {
            "at": stamp(),
            "cep": "CEP-075",
            "execution": "COMPLETE",
            "ac": {
                "AC" + str(i): "PASS_APPROVED_NONPRODUCTION_TARGET" for i in range(1, 7)
            },
            "dod": "MET_APPROVED_NONPRODUCTION_SCOPE",
            "profile": "BONIRA-PE-NP-01",
            "steps": steps,
            "source": "Both releases contain exact current source;no fictitious older code revision",
            "runtime": "Nginx HTTPS -> Gunicorn synchronous WSGI;approved Linux application runtime",
            "migration": "History read unchanged;no migration/reversal",
            "production_certification": "NOT_EXECUTED",
            "human_signoff": "NOT_EXECUTED",
            "git_write": False,
        },
    )
    print("CEP-075 runtime scenario PASS", flush=True)


if __name__ == "__main__":
    phase = sys.argv[1]
    try:
        if phase in {"070", "074"}:
            recovery(phase)
        elif phase == "075":
            deploy()
        else:
            raise ValueError("Unsupported package")
    except Exception as exc:
        frames = [
            {"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
            for f in traceback.extract_tb(exc.__traceback__)[-8:]
        ]
        write(
            OUT / (phase + "_FAILED_" + datetime.now(UTC).strftime("%H%M%S") + ".json"),
            {
                "at": stamp(),
                "execution": "FAILED_ATTEMPT_REPAIR_PENDING",
                "type": type(exc).__name__,
                "frames": frames,
            },
        )
        print(
            "Failed bounded " + phase + " attempt;retained sanitized evidence",
            flush=True,
        )
        raise

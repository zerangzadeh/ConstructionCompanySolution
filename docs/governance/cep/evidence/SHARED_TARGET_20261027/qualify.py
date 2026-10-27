"""Shared candidate controls, never equivalence, CEP-074 or Production.

Reproduce isolated TLS/config/cache/storage/recovery controls using existing
software. A reference WSGI harness is expressly not a Production process server.
Only this run's new native PostgreSQL cluster is started/stopped. No configured
application database, existing PostgreSQL service or global trust store is used.
"""

from __future__ import annotations

import hashlib
import http.client
import importlib.metadata
import json
import os
import platform
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
PG = Path("D:/Program Files/PostgreSQL/18/bin")
OPENSSL = Path("D:/Program Files/Git/usr/bin/openssl.exe")
sys.path.insert(0, str(ROOT))


def write(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def invoke(args, *, env=None, cwd=ROOT, timeout=50):
    if Path(args[0]).name == "pg_ctl.exe":
        # Native Windows server descendants inherit PIPE handles despite -l.
        # A private file avoids waiting for a long-lived server to close them.
        log_path = Path(args[args.index("-D") + 1]).parent / "pg_ctl.log"
        with log_path.open("ab") as log:
            completed = subprocess.run(
                [str(a) for a in args],
                env=env,
                cwd=cwd,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        if completed.returncode:
            raise RuntimeError(f"PostgreSQL control exit {completed.returncode}")
        return ""
    result = subprocess.run(
        [str(a) for a in args],
        env=env,
        cwd=cwd,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        # Raw subprocess output may contain connection details; private only.
        raise RuntimeError(f"Tool {Path(args[0]).name} exit {result.returncode}")
    return result.stdout


def child(action, config):
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.production"
    import django

    django.setup()
    from django.conf import settings
    from django.core.cache import cache
    from django.core.management import call_command

    assert settings.SETTINGS_MODULE == "config.settings.production"
    assert not settings.DEBUG and not settings.REFERENCE_PERSONA_CATALOGUE_ENABLED
    if action == "prepare":
        call_command("check", deploy=True, fail_level="WARNING")
        call_command("collectstatic", interactive=False, verbosity=0)
    elif action == "health":
        call_command("operational_health")
    elif action == "cache-write":
        cache.set("qualification-only", "cross-process-proof", timeout=60)
    elif action == "cache-read":
        assert cache.get("qualification-only") == "cross-process-proof"
        print("CACHE_CROSS_PROCESS_PASS")
    elif action == "serve":
        from wsgiref.simple_server import WSGIRequestHandler, make_server

        from config.wsgi import application

        class Handler(WSGIRequestHandler):
            def get_environ(self):
                result = super().get_environ()
                # wsgiref's ServerHandler derives wsgi.url_scheme from HTTPS.
                # This flag is server-owned and is set only on the TLS socket.
                result["HTTPS"] = "on"
                result["wsgi.url_scheme"] = "https"
                return result

            def log_message(self, *args):
                pass

        static = Path(os.environ["DJANGO_STATIC_ROOT"]).resolve()
        allowed = {
            "/static/" + p.relative_to(static).as_posix(): p
            for p in static.rglob("*")
            if p.is_file()
        }

        def static_boundary(environ, start_response):
            selected = allowed.get(environ["PATH_INFO"])
            if selected is not None:
                assert selected.resolve().is_relative_to(static)
                data = selected.read_bytes()
                start_response(
                    "200 OK",
                    [
                        ("Content-Type", "application/octet-stream"),
                        ("Content-Length", str(len(data))),
                    ],
                )
                return [data]
            return application(environ, start_response)

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(config["cert"], config["key"])
        with make_server(
            "127.0.0.1", config["web_port"], static_boundary, handler_class=Handler
        ) as server:
            server.socket = context.wrap_socket(server.socket, server_side=True)
            write(
                Path(config["ready"]),
                {
                    "pid": os.getpid(),
                    "bind": "127.0.0.1",
                    "port": server.server_port,
                    "settings": settings.SETTINGS_MODULE,
                    "debug": settings.DEBUG,
                    "reference_personas": False,
                    "server": "stdlib-wsgiref-TLS-qualification-harness-only",
                    "production_server_qualified": False,
                },
            )
            server.serve_forever(poll_interval=0.1)


def execute():
    import psycopg
    from psycopg import sql

    from scripts.backup_bundle import BackupPlan, _inventory, create_bundle
    from scripts.cep070_recovery_controls import (
        create_private_store,
        verify_private_tree,
    )

    result_path = OUT / "CONTROLS.json"
    if result_path.exists():
        raise RuntimeError("Preserve previous attempts; use a fresh evidence directory")
    store = create_private_store(Path("E:/BONIRA_Operations/SharedTarget"))
    data = store / "pgdata"
    tls = store / "tls"
    tls.mkdir()
    cert, key = tls / "localhost.crt", tls / "localhost.key"
    pg_port, web_port = port(), port()
    while web_port == pg_port:
        web_port = port()
    password = secrets.token_urlsafe(40)
    pwfile = store / "init-password"
    pwfile.write_text(password, encoding="ascii")
    started = False
    process = None
    checks = []
    result = {
        "started_at": datetime.now(UTC).isoformat(),
        "profile": "BONIRA-PE-NP-01",
        "scope": "NEW_CANDIDATE_CONTROL_QUALIFICATION_ONLY",
        "production_equivalent": False,
        "cep074_executed": False,
        "configured_business_database_accessed": False,
        "existing_postgresql_service_changed": False,
        "store": str(store),
        "runtime": {
            "os": platform.platform(),
            "python": platform.python_version(),
            "django": importlib.metadata.version("Django"),
            "psycopg": importlib.metadata.version("psycopg"),
        },
        "checks": checks,
        "limitations": [
            "No approved Production reference/permitted-difference mapping exists",
            "Reference WSGI server is a qualification harness, not a Production server",
            "Single Windows host does not prove Linux/HA/provider/failure-domain equivalence",
            "File cache is shared across local processes only; no multi-host claim",
            "Locally generated synthetic TLS/DB secrets do not qualify Production custody",
            "SMTP configuration is an unused synthetic endpoint; no mail delivery claim",
            "Recovery fixture is a small control fixture, not an ERP or CEP074 restore drill",
            "No extension of Development objective approval to Production or equivalence",
        ],
    }

    def passed(name, **detail):
        checks.append(
            {
                "check": name,
                "result": "PASS",
                "at": datetime.now(UTC).isoformat(),
                **detail,
            }
        )

    try:
        invoke(
            [
                OPENSSL,
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                key,
                "-out",
                cert,
                "-days",
                "2",
                "-subj",
                "/CN=localhost",
                "-addext",
                "subjectAltName=DNS:localhost,IP:127.0.0.1",
                "-addext",
                "basicConstraints=critical,CA:TRUE",
            ]
        )
        passed(
            "synthetic TLS identity created in restricted run directory",
            cert_sha256=sha(cert),
            trust="explicit-per-client;no-global-store-change",
        )
        invoke(
            [
                PG / "initdb.exe",
                "-D",
                data,
                "-U",
                "bonira_probe",
                "--pwfile",
                pwfile,
                "--auth=scram-sha-256",
                "--encoding=UTF8",
                "--locale=C",
            ]
        )
        pwfile.unlink()
        conf = data / "postgresql.conf"
        with conf.open("a", encoding="utf-8") as handle:
            handle.write(
                f"\nlisten_addresses='127.0.0.1'\nport={pg_port}\nssl=on\n"
                f"ssl_cert_file='{cert.as_posix()}'\nssl_key_file='{key.as_posix()}'\n"
            )
        (data / "pg_hba.conf").write_text(
            "hostssl all all 127.0.0.1/32 scram-sha-256\n"
            "hostnossl all all 127.0.0.1/32 reject\n",
            encoding="ascii",
        )
        invoke(
            [PG / "pg_ctl.exe", "-D", data, "-l", store / "postgres.log", "-w", "start"]
        )
        started = True
        options = {
            "host": "127.0.0.1",
            "port": pg_port,
            "user": "bonira_probe",
            "password": password,
            "sslmode": "verify-full",
            "sslrootcert": str(cert),
            "connect_timeout": 4,
        }
        with psycopg.connect(
            **options, dbname="postgres", autocommit=True
        ) as connection:
            version = connection.execute("SHOW server_version").fetchone()[0]
            ssl_row = connection.execute(
                "SELECT ssl,version,cipher FROM pg_stat_ssl WHERE pid=pg_backend_pid()"
            ).fetchone()
            assert ssl_row[0]
            connection.execute("CREATE DATABASE bonira_probe")
            connection.execute("CREATE DATABASE bonira_restore")
            connection.execute(
                sql.SQL("CREATE ROLE bonira_app LOGIN PASSWORD {}").format(
                    sql.Literal(password)
                )
            )
        passed(
            "isolated PostgreSQL with verify-full and observed TLS",
            version=version,
            tls_version=ssl_row[1],
            cipher=ssl_row[2],
            bind="127.0.0.1",
        )
        for name, modified in [
            ("non-TLS database connection rejected", {"sslmode": "disable"}),
            (
                "untrusted database CA rejected",
                {"sslrootcert": str(store / "absent-ca")},
            ),
            (
                "wrong database password rejected",
                {"password": "wrong-synthetic-password"},
            ),
        ]:
            try:
                with psycopg.connect(**(options | modified), dbname="bonira_probe"):
                    pass
            except psycopg.OperationalError:
                passed(name)
            else:
                raise AssertionError(name)
        with psycopg.connect(**options, dbname="bonira_probe") as connection:
            connection.execute(
                "CREATE TABLE target_control_fixture (tenant integer, amount numeric(16,2))"
            )
            connection.execute(
                "INSERT INTO target_control_fixture VALUES (1,123.45),(2,987.65)"
            )
        environment = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("DB_", "DJANGO_", "PG"))
        }
        roots = {name: store / name for name in ["static", "media", "private", "cache"]}
        for path in roots.values():
            path.mkdir()
        for name in ["media", "private"]:
            (roots[name] / "denied.txt").write_bytes(b"synthetic-restricted-fixture")
        environment.update(
            {
                "PYTHONIOENCODING": "utf-8",
                "PYTHONPATH": str(ROOT),
                "DJANGO_SETTINGS_MODULE": "config.settings.production",
                "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
                "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1",
                "DB_NAME": "bonira_probe",
                "DB_USER": "bonira_app",
                "DB_PASSWORD": password,
                "DB_HOST": "127.0.0.1",
                "DB_PORT": str(pg_port),
                "DB_SSLMODE": "verify-full",
                "DB_SSLROOTCERT": str(cert),
                "DJANGO_STATIC_ROOT": str(roots["static"]),
                "DJANGO_MEDIA_ROOT": str(roots["media"]),
                "DOCUMENT_PROTECTED_ROOT": str(roots["private"]),
                "DJANGO_CACHE_BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
                "DJANGO_CACHE_LOCATION": str(roots["cache"]),
                "DJANGO_EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
                "DJANGO_EMAIL_HOST": "127.0.0.1",
                "DJANGO_EMAIL_PORT": str(port()),
                "DJANGO_EMAIL_HOST_USER": "synthetic-unused",
                "DJANGO_EMAIL_HOST_PASSWORD": secrets.token_urlsafe(32),
                "DJANGO_DEFAULT_FROM_EMAIL": "qualification@localhost",
                "DJANGO_EMAIL_USE_TLS": "true",
                "DJANGO_USE_X_FORWARDED_PROTO": "false",
            }
        )
        configuration = {
            "cert": str(cert),
            "key": str(key),
            "web_port": web_port,
            "ready": str(store / "ready.json"),
        }
        config = store / "runtime.json"
        write(config, configuration)

        def run_child(action, env=environment):
            return invoke([sys.executable, __file__, action, config], env=env)

        run_child("prepare")
        static_files = [p for p in roots["static"].rglob("*") if p.is_file()]
        assert static_files
        passed(
            "actual production settings deployment check WARNING-fatal and collectstatic",
            settings="config.settings.production",
            assets=len(static_files),
            dotenv_loaded=False,
        )
        run_child("cache-write")
        assert "CACHE_CROSS_PROCESS_PASS" in run_child("cache-read")
        passed(
            "cache write/read in separate fresh processes",
            backend=environment["DJANGO_CACHE_BACKEND"],
        )
        health = json.loads(run_child("health"))
        passed(
            "actual production-settings DB/cache read-only operational health",
            health=health,
        )
        unavailable = environment | {"DB_PORT": str(port())}
        try:
            run_child("health", unavailable)
        except RuntimeError:
            passed("unavailable DB dependency exits nonzero")
        else:
            raise AssertionError("Missing dependency reported healthy")
        with (store / "http.log").open("wb") as log:
            process = subprocess.Popen(
                [sys.executable, __file__, "serve", str(config)],
                cwd=ROOT,
                env=environment,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            deadline = time.monotonic() + 25
            while not Path(configuration["ready"]).exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("TLS harness failed startup")
                time.sleep(0.1)
            trusted = ssl.create_default_context(cafile=str(cert))

            def request(path, *, method="GET", headers=None):
                conn = http.client.HTTPSConnection(
                    "localhost", web_port, context=trusted, timeout=8
                )
                conn.request(method, path, headers=headers or {})
                response = conn.getresponse()
                status, returned_headers, body = (
                    response.status,
                    dict(response.getheaders()),
                    response.read(),
                )
                conn.close()
                return status, returned_headers, body

            assert request("/")[0] == 302
            assert request("/accounts/login/", method="POST")[0] == 403
            assert request("/media/denied.txt")[0] == 404
            assert request("/protected_documents/denied.txt")[0] == 404
            assert request("/", headers={"Host": "untrusted.invalid"})[0] == 400
            status, headers, body = request("/")
            assert "max-age=" in headers.get("Strict-Transport-Security", "")
            status, headers, body = request("/", headers={"X-Forwarded-Proto": "http"})
            assert status == 302 and "max-age=" in headers.get(
                "Strict-Transport-Security", ""
            )
            chosen = static_files[0]
            status, _, body = request(
                "/static/" + chosen.relative_to(roots["static"]).as_posix()
            )
            assert status == 200 and hashlib.sha256(body).hexdigest() == sha(chosen)
            passed(
                "actual verified HTTPS WSGI/static/security boundary",
                http_cases=8,
                process=json.loads(Path(configuration["ready"]).read_text()),
            )
            for name, context in [
                ("untrusted HTTPS certificate rejected", ssl.create_default_context()),
            ]:
                try:
                    conn = http.client.HTTPSConnection(
                        "localhost", web_port, context=context, timeout=5
                    )
                    conn.request("GET", "/")
                except ssl.SSLCertVerificationError:
                    passed(name)
                else:
                    raise AssertionError(name)
                finally:
                    conn.close()
            process.terminate()
            process.wait(timeout=10)
            process = None
        operational_logs = (store / "http.log").read_text(encoding="utf-8")
        events = []
        for line in operational_logs.splitlines():
            if line.startswith("{"):
                event = json.loads(line)
                if "request_id" in event:
                    events.append(event)
        assert events
        passed(
            "structured request telemetry retained in restricted local sink",
            records=len(events),
            fields=sorted(events[0]),
        )
        backup_roots = {}
        for name in ["document_media", "configuration_metadata", "audit_operational"]:
            path = store / name
            path.mkdir()
            backup_roots[name] = path
        shutil.copy2(
            roots["private"] / "denied.txt",
            backup_roots["document_media"] / "fixture.txt",
        )
        write(
            backup_roots["configuration_metadata"] / "profile.json",
            {
                "profile": "BONIRA-PE-NP-01",
                "settings": "config.settings.production",
                "secret_recovery": "UNQUALIFIED_SYNTHETIC_ONLY",
                "code": json.loads((OUT / "ENTRY.json").read_text())["head"],
            },
        )
        shutil.copy2(store / "http.log", backup_roots["audit_operational"] / "http.log")
        service = store / "pg_service.conf"
        service.write_text(
            "[bonira_shared_probe]\n"
            + "\n".join(
                f"{k}={v}" for k, v in (options | {"dbname": "bonira_probe"}).items()
            ),
            encoding="utf-8",
        )
        old_service = os.environ.get("PGSERVICEFILE")
        os.environ["PGSERVICEFILE"] = str(service)
        try:
            capture = create_bundle(
                BackupPlan(
                    environment="non-production",
                    source_revision=json.loads((OUT / "ENTRY.json").read_text())[
                        "head"
                    ],
                    operator_reference="Human-authorized-shared-target-preparation",
                    recovery_reference="EXT-0020-HUMAN-20261027-Development-only",
                    consistency_reference="isolated-quiescent-synthetic-control-fixture",
                    database_service="bonira_shared_probe",
                    pg_dump=PG / "pg_dump.exe",
                    roots=backup_roots,
                    destination=store / "bundle",
                    command_timeout_seconds=30,
                )
            )
        finally:
            if old_service is None:
                os.environ.pop("PGSERVICEFILE", None)
            else:
                os.environ["PGSERVICEFILE"] = old_service
        restore_env = environment | {
            "PGPASSWORD": password,
            "PGSSLMODE": "verify-full",
            "PGSSLROOTCERT": str(cert),
        }
        dump = store / "bundle" / "database.dump"
        assert dump.exists()
        t0 = time.monotonic()
        invoke(
            [
                PG / "pg_restore.exe",
                "--exit-on-error",
                "--no-owner",
                "--no-privileges",
                "-h",
                "127.0.0.1",
                "-p",
                pg_port,
                "-U",
                "bonira_probe",
                "-d",
                "bonira_restore",
                dump,
            ],
            env=restore_env,
        )
        with psycopg.connect(**options, dbname="bonira_restore") as connection:
            rows = connection.execute(
                "SELECT tenant,amount::text FROM target_control_fixture ORDER BY tenant"
            ).fetchall()
            assert rows == [(1, "123.45"), (2, "987.65")]
        copied = store / "recovered-files"
        copied.mkdir()
        for name, original_root in backup_roots.items():
            target = copied / name
            shutil.copytree(store / "bundle" / name, target)
            assert _inventory(original_root) == _inventory(target)
        passed(
            "existing backup adapter over verified TLS and four-class synthetic control recovery",
            rows=2,
            file_classes=3,
            elapsed_seconds=round(time.monotonic() - t0, 6),
            capture_status=capture["capture_status"],
            erp_restore_claim=False,
            approved_objective_pass_claim=False,
        )
        passed(
            "recursive private candidate storage and secret ACL",
            **verify_private_tree(store),
        )
        result["result"] = "PASS_CANDIDATE_CONTROLS_ONLY_EQUIVALENCE_NOT_QUALIFIED"
    except Exception as exc:
        result["result"] = "FAILED_CANDIDATE_CONTROL_ATTEMPT"
        result["failure"] = {"type": type(exc).__name__, "message": str(exc)[:180]}
        raise
    finally:
        if process is not None:
            process.terminate()
            process.wait(timeout=10)
        if started:
            invoke([PG / "pg_ctl.exe", "-D", data, "-m", "fast", "-w", "stop"])
            result["own_cluster_stopped"] = True
        result["web_process_stopped"] = process is None or process.poll() is not None
        result["finished_at"] = datetime.now(UTC).isoformat()
        write(result_path, result)
    print(
        json.dumps(
            {"result": result["result"], "controls": len(checks), "store": str(store)}
        )
    )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        child(sys.argv[1], json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")))
    else:
        execute()

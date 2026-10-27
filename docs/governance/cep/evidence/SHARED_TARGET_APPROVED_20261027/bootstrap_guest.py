"""Provision only the disposable BONIRA-PE-NP-01 Linux guest."""

import json
import os
import secrets
import shutil
import subprocess
import time
from pathlib import Path

BASE = Path("/srv/bonira")
IMAGE = "bonira-pe-np-runtime:20261027"
PG_IMAGE = "postgres:18.6-bookworm"
BASE_IMAGE = (
    "python@sha256:8fb0b110b022c70cbe09d3ff1fb313654f31f9c814abb0d48180af56d906a199"
)


def command(args, **kwargs):
    result = subprocess.run(
        [str(a) for a in args], capture_output=True, text=True, check=False, **kwargs
    )
    if result.returncode:
        Path("/root/bonira-bootstrap-failure.log").write_text(
            result.stdout + result.stderr
        )
        raise RuntimeError("Guest prerequisite failed: " + str(args[0]))
    return (result.stdout or result.stderr).strip()


def private(path, text, owner=0):
    path.write_text(text)
    path.chmod(0o600)
    os.chown(path, owner, owner)


def main():
    assert 'VERSION_ID="12"' in Path("/etc/os-release").read_text()
    BASE.mkdir(exist_ok=True)
    for name in [
        "pki",
        "secrets",
        "run",
        "evidence",
        "shared",
        "public",
        "releases",
        "init",
    ]:
        directory = BASE / name
        directory.mkdir(exist_ok=True)
        directory.chmod(
            0o700 if name in {"pki", "secrets", "shared", "init"} else 0o755
        )
    os.chown(BASE / "evidence", 10001, 10001)
    source = BASE / "source"
    assert source.is_dir() and not (source / ".env").exists()
    for release in ["previous", "candidate"]:
        target = BASE / "releases" / release
        if not target.exists():
            shutil.copytree(source, target)
        static = BASE / "public" / release
        static.mkdir(exist_ok=True)
        os.chown(static, 10001, 10001)
    # Restore retained synthetic file material into this new isolated target.
    for name in ["document_media", "configuration_metadata", "audit_operational"]:
        target = BASE / "shared" / name
        if not target.exists():
            shutil.copytree(BASE / "seed" / name, target)
    (BASE / "shared" / "cache").mkdir(exist_ok=True)
    for path in [BASE / "shared", *(BASE / "shared").rglob("*")]:
        os.chown(path, 10001, 10001)
        path.chmod(0o700 if path.is_dir() else 0o600)

    pki = BASE / "pki"
    if not (pki / "ca.key").exists():
        command(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "7",
                "-keyout",
                pki / "ca.key",
                "-out",
                pki / "ca.crt",
                "-subj",
                "/CN=BONIRA synthetic qualification CA",
                "-addext",
                "basicConstraints=critical,CA:TRUE",
                "-addext",
                "keyUsage=critical,keyCertSign,cRLSign",
            ]
        )
        for name, san in [
            ("db", "DNS:db,DNS:localhost,IP:127.0.0.1"),
            ("web", "DNS:localhost,IP:127.0.0.1"),
        ]:
            command(
                [
                    "openssl",
                    "req",
                    "-newkey",
                    "rsa:2048",
                    "-nodes",
                    "-keyout",
                    pki / (name + ".key"),
                    "-out",
                    pki / (name + ".csr"),
                    "-subj",
                    "/CN=" + ("db" if name == "db" else "localhost"),
                ]
            )
            (pki / (name + ".ext")).write_text(
                "subjectAltName=" + san + "\nextendedKeyUsage=serverAuth\n"
            )
            command(
                [
                    "openssl",
                    "x509",
                    "-req",
                    "-in",
                    pki / (name + ".csr"),
                    "-CA",
                    pki / "ca.crt",
                    "-CAkey",
                    pki / "ca.key",
                    "-CAcreateserial",
                    "-out",
                    pki / (name + ".crt"),
                    "-days",
                    "7",
                    "-extfile",
                    pki / (name + ".ext"),
                ]
            )
    pg_uid = int(
        command(
            ["docker", "run", "--rm", "--entrypoint", "id", PG_IMAGE, "-u", "postgres"]
        )
    )
    for key in pki.glob("*.key"):
        key.chmod(0o600)
    os.chown(pki / "db.key", pg_uid, pg_uid)
    for cert in pki.glob("*.crt"):
        cert.chmod(0o644)

    secret_path = BASE / "secrets" / "values.json"
    if secret_path.exists():
        values = json.loads(secret_path.read_text())
    else:
        values = {
            name: secrets.token_urlsafe(48)
            for name in ["db_admin", "db_app", "django", "unused_smtp"]
        }
        private(secret_path, json.dumps(values))
    private(
        BASE / "secrets" / "postgres.env",
        "\n".join(
            [
                "POSTGRES_USER=bonira_admin",
                "POSTGRES_PASSWORD=" + values["db_admin"],
                "POSTGRES_HOST_AUTH_METHOD=scram-sha-256",
                "PGDATA=/var/lib/postgresql/18/data",
                "",
            ]
        ),
    )
    private(
        BASE / "init" / "10-bonira.sql",
        (
            "CREATE ROLE bonira_app LOGIN PASSWORD '"
            + values["db_app"]
            + "' NOSUPERUSER NOCREATEDB NOCREATEROLE;\n"
            "CREATE DATABASE pe_source OWNER bonira_app;\n"
        ),
        owner=pg_uid,
    )
    private(
        BASE / "init" / "20-tls.sh",
        "#!/bin/sh\nset -eu\n"
        '{ printf \'hostnossl all all all reject\\n\'; cat "$PGDATA/pg_hba.conf"; } > "$PGDATA/new-hba"\n'
        'mv "$PGDATA/new-hba" "$PGDATA/pg_hba.conf"\n',
        owner=pg_uid,
    )

    if (
        "bonira-pe"
        not in command(
            ["docker", "network", "ls", "--format", "{{.Name}}"]
        ).splitlines()
    ):
        command(["docker", "network", "create", "--internal", "bonira-pe"])
    if (
        "bonira-db"
        not in command(["docker", "ps", "-a", "--format", "{{.Names}}"]).splitlines()
    ):
        command(
            [
                "docker",
                "run",
                "-d",
                "--name",
                "bonira-db",
                "--network",
                "bonira-pe",
                "--network-alias",
                "db",
                "--env-file",
                BASE / "secrets" / "postgres.env",
                "-v",
                str(BASE / "pgdata") + ":/var/lib/postgresql",
                "-v",
                str(BASE / "init" / "10-bonira.sql")
                + ":/docker-entrypoint-initdb.d/10-bonira.sql:ro",
                "-v",
                str(BASE / "init" / "20-tls.sh")
                + ":/docker-entrypoint-initdb.d/20-tls.sh:ro",
                "-v",
                str(pki / "db.crt") + ":/run/secrets/db.crt:ro",
                "-v",
                str(pki / "db.key") + ":/run/secrets/db.key:ro",
                "-v",
                str(pki / "ca.crt") + ":/run/secrets/ca.crt:ro",
                "-v",
                str(BASE / "seed") + ":/seed:ro",
                PG_IMAGE,
                "-c",
                "ssl=on",
                "-c",
                "ssl_cert_file=/run/secrets/db.crt",
                "-c",
                "ssl_key_file=/run/secrets/db.key",
                "-c",
                "ssl_min_protocol_version=TLSv1.2",
            ]
        )
    for _ in range(90):
        ready = subprocess.run(
            [
                "docker",
                "exec",
                "bonira-db",
                "sh",
                "-c",
                (
                    'PGPASSWORD="$POSTGRES_PASSWORD" PGSSLMODE=verify-full PGSSLROOTCERT=/run/secrets/ca.crt '
                    'psql -h localhost -U bonira_admin -d pe_source -Atqc "SELECT 1"'
                ),
            ],
            capture_output=True,
            check=False,
        )
        if ready.returncode == 0:
            break
        time.sleep(1)
    else:
        raise RuntimeError("Own PostgreSQL target did not start")
    # App-owned restore; database/extension provisioning is fixture setup only.
    if not (BASE / "run" / "seed-restored").exists():
        command(
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
                "pe_source",
                "/seed/database.dump",
            ]
        )
        (BASE / "run" / "seed-restored").touch()

    common = {
        "DJANGO_SETTINGS_MODULE": "config.settings.production",
        "DJANGO_SECRET_KEY": values["django"],
        "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1",
        "DB_HOST": "db",
        "DB_PORT": "5432",
        "DB_NAME": "pe_source",
        "DB_USER": "bonira_app",
        "DB_PASSWORD": values["db_app"],
        "DB_SSLMODE": "verify-full",
        "DB_SSLROOTCERT": "/tls/ca.crt",
        "DJANGO_MEDIA_ROOT": "/state/document_media/media",
        "DOCUMENT_PROTECTED_ROOT": "/state/document_media/protected",
        "DJANGO_CACHE_BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "DJANGO_CACHE_LOCATION": "/state/cache",
        "DJANGO_USE_X_FORWARDED_PROTO": "true",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://localhost:8443,https://127.0.0.1:24470",
        "DJANGO_EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "DJANGO_EMAIL_HOST": "127.0.0.1",
        "DJANGO_EMAIL_PORT": "2525",
        "DJANGO_EMAIL_HOST_USER": "synthetic-unused",
        "DJANGO_EMAIL_HOST_PASSWORD": values["unused_smtp"],
        "DJANGO_EMAIL_USE_TLS": "true",
        "DJANGO_DEFAULT_FROM_EMAIL": "qualification@localhost",
        "PYTHONPATH": "/infra:/app",
        "PYTHONDONTWRITEBYTECODE": "1",
        "BONIRA_SOURCE_HEAD": json.loads((source / "BUILD.json").read_text())["head"],
    }
    for release in ["previous", "candidate"]:
        env = common | {"DJANGO_STATIC_ROOT": "/static/" + release}
        private(
            BASE / "secrets" / (release + ".env"),
            "\n".join(k + "=" + v for k, v in env.items()) + "\n",
        )
    service = (
        "[bonira_shared]\nhost=db\nport=5432\nuser=bonira_app\npassword="
        + values["db_app"]
        + "\ndbname=pe_source\nsslmode=verify-full\nsslrootcert=/run/secrets/ca.crt\n"
    )
    # A private named service is copied to this own container, not argv/evidence.
    private(BASE / "secrets" / "pg_service.conf", service)
    command(
        [
            "docker",
            "cp",
            BASE / "secrets" / "pg_service.conf",
            "bonira-db:/tmp/bonira-service.conf",
        ]
    )
    command(["docker", "exec", "bonira-db", "chmod", "600", "/tmp/bonira-service.conf"])
    private(
        BASE / "pg_dump",
        '#!/bin/sh\nexec python3 /srv/bonira/tools/pg_dump_bridge.py "$@"\n',
    )
    (BASE / "pg_dump").chmod(0o700)

    nginx = """user www-data;
worker_processes 1;
pid /srv/bonira/run/nginx.pid;
error_log /srv/bonira/run/nginx-error.log warn;
events { worker_connections 128; }
http {
    include /etc/nginx/mime.types;
    upstream bonira_backend { server unix:/srv/bonira/run/app/app.sock; }
    access_log /srv/bonira/run/nginx-access.log;
    proxy_temp_path /srv/bonira/run/proxy;
    client_body_temp_path /srv/bonira/run/body;
    server { listen 127.0.0.1:8082; return 301 https://localhost:8443$request_uri; }
    server {
        listen 8443 ssl;
        server_name localhost 127.0.0.1;
        ssl_certificate /srv/bonira/pki/web.crt;
        ssl_certificate_key /srv/bonira/pki/web.key;
        ssl_protocols TLSv1.2 TLSv1.3;
        location /static/ { alias /srv/bonira/active_static/; autoindex off; }
        location /media/ { return 404; }
        location /protected_documents/ { return 404; }
        location /private/ { return 404; }
        location / {
            proxy_pass http://bonira_backend;
            proxy_buffering on;
            proxy_set_header Host $http_host;
            proxy_set_header X-Forwarded-Proto https;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header Connection "";
        }
    }
}
"""
    private(BASE / "nginx.conf", nginx)
    command(["nginx", "-t", "-c", BASE / "nginx.conf"])
    redacted = {
        k: v
        for k, v in common.items()
        if k not in {"DJANGO_SECRET_KEY", "DB_PASSWORD", "DJANGO_EMAIL_HOST_PASSWORD"}
    }
    redacted["secrets"] = (
        "private per-target generated values;recovery reference retained outside public evidence"
    )
    write_path = BASE / "shared" / "configuration_metadata" / "profile.json"
    write_path.write_text(json.dumps(redacted, indent=2))
    os.chown(write_path, 10001, 10001)
    write_path.chmod(0o600)
    identity = {
        "profile": "BONIRA-PE-NP-01",
        "guest_os": Path("/etc/os-release").read_text(),
        "base_image": BASE_IMAGE,
        "db_image": command(
            [
                "docker",
                "image",
                "inspect",
                PG_IMAGE,
                "--format",
                "{{index .RepoDigests 0}}",
            ]
        ),
        "nginx": command(["nginx", "-v"]),
        "pg_uid": pg_uid,
        "source_head": common["BONIRA_SOURCE_HEAD"],
        "production": False,
        "network_internal": command(
            ["docker", "network", "inspect", "bonira-pe", "--format", "{{.Internal}}"]
        ),
    }
    (BASE / "evidence" / "BOOTSTRAP.json").write_text(json.dumps(identity, indent=2))
    print("Approved isolated Linux infrastructure provisioned;no Production access")


if __name__ == "__main__":
    main()

"""Synthetic request execution, not a selected deployment or CEP-075 drill.

Run with .venv-2/Scripts/python.exe from the repository root. Child processes
receive synthetic values only; dotenv, database and network connects are forbidden.
"""

import asyncio
import hashlib
import io
import json
import os
import runpy
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


def execute():
    sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
    with (
        tempfile.TemporaryDirectory(prefix="bonira-071-request-proof-") as directory,
        asyncio.Runner() as runner,
    ):
        # Windows creates an internal loopback socket pair for its event loop.
        # Initialize it before forbidding application network connections.
        runner.get_loop()
        root = Path(directory)
        for variable, folder in (
            ("DJANGO_STATIC_ROOT", "candidate-static"),
            ("DJANGO_MEDIA_ROOT", "media"),
            ("DOCUMENT_PROTECTED_ROOT", "private"),
            ("DJANGO_CACHE_LOCATION", "cache"),
        ):
            os.environ[variable] = str(root / folder)
        with (
            patch("dotenv.load_dotenv", side_effect=AssertionError("Dotenv forbidden")),
            patch("psycopg.connect", side_effect=AssertionError("Database forbidden")),
            patch(
                "socket.socket.connect", side_effect=AssertionError("Network forbidden")
            ),
        ):
            import django

            django.setup()
            from asgiref.testing import ApplicationCommunicator
            from django.conf import settings
            from django.core.management import call_command
            from django.test import RequestFactory, override_settings

            from config.asgi import application as asgi
            from config.wsgi import application as wsgi

            output = io.StringIO()
            call_command(
                "check", deploy=True, fail_level="WARNING", stdout=output, stderr=output
            )

            def inventory(path):
                return {
                    str(file.relative_to(path)): hashlib.sha256(
                        file.read_bytes()
                    ).hexdigest()
                    for file in path.rglob("*")
                    if file.is_file()
                }

            previous = root / "previous-static"
            with override_settings(STATIC_ROOT=previous):
                call_command(
                    "collectstatic", interactive=False, verbosity=0, stdout=output
                )
            retained = inventory(previous)
            call_command("collectstatic", interactive=False, verbosity=0, stdout=output)
            assert retained and inventory(settings.STATIC_ROOT) == retained
            assert inventory(previous) == retained

            # Actual fixture bytes prove that Django does not expose these paths.
            # They do not qualify a future reverse proxy or durable storage mount.
            for path in (settings.MEDIA_ROOT, settings.DOCUMENT_PROTECTED_ROOT):
                path.mkdir()
                (path / "fixture.txt").write_text(
                    "synthetic-private-marker", encoding="utf-8"
                )
            cases = [
                ("GET", "/", False, "fixture.invalid", 301),
                ("GET", "/", True, "fixture.invalid", 302),
                ("POST", "/accounts/login/", True, "fixture.invalid", 403),
                ("GET", "/media/fixture.txt", True, "fixture.invalid", 404),
                ("GET", "/private/fixture.txt", True, "fixture.invalid", 404),
                ("GET", "/static/" + min(retained), True, "fixture.invalid", 404),
                ("GET", "/", True, "unapproved.invalid", 400),
            ]

            def verify(status, headers, body, secure, expected):
                assert status == expected, (status, expected)
                assert b"synthetic-private-marker" not in body
                if expected == 301:
                    assert headers["location"] == "https://fixture.invalid/"
                if expected == 302:
                    assert headers["location"].startswith("/accounts/login/")
                if secure:
                    assert "strict-transport-security" in headers

            rows = []
            for method, path, secure, host, expected in cases:
                captured = {}

                def start_response(status, headers, exc_info=None, captured=captured):
                    captured.update(
                        status=int(status.split()[0]), headers=dict(headers)
                    )

                environ = (
                    RequestFactory()
                    .generic(method, path, secure=secure, HTTP_HOST=host)
                    .environ
                )
                response = wsgi(environ, start_response)
                try:
                    body = b"".join(response)
                finally:
                    response.close()
                verify(
                    captured["status"],
                    {k.lower(): v for k, v in captured["headers"].items()},
                    body,
                    secure,
                    expected,
                )
                rows.append(
                    {
                        "interface": "WSGI",
                        "method": method,
                        "path": path,
                        "https": secure,
                        "host": host,
                        "status": captured["status"],
                        "result": "PASS",
                    }
                )

            async def execute_asgi():
                for method, path, secure, host, expected in cases:
                    scope = {
                        "type": "http",
                        "asgi": {"version": "3.0"},
                        "http_version": "1.1",
                        "method": method,
                        "path": path,
                        "raw_path": path.encode(),
                        "query_string": b"",
                        "scheme": "https" if secure else "http",
                        "headers": [(b"host", host.encode())],
                        "server": ("fixture.invalid", 443 if secure else 80),
                        "client": ("127.0.0.1", 0),
                    }
                    communicator = ApplicationCommunicator(asgi, scope)
                    await communicator.send_input(
                        {"type": "http.request", "body": b"", "more_body": False}
                    )
                    head = await communicator.receive_output(timeout=15)
                    assert head["type"] == "http.response.start"
                    body = b""
                    while True:
                        message = await communicator.receive_output(timeout=15)
                        assert message["type"] == "http.response.body"
                        body += message.get("body", b"")
                        if not message.get("more_body", False):
                            break
                    await communicator.wait(timeout=15)
                    verify(
                        head["status"],
                        {k.decode().lower(): v.decode() for k, v in head["headers"]},
                        body,
                        secure,
                        expected,
                    )
                    rows.append(
                        {
                            "interface": "ASGI",
                            "method": method,
                            "path": path,
                            "https": secure,
                            "host": host,
                            "status": head["status"],
                            "result": "PASS",
                        }
                    )

            runner.run(execute_asgi())
            assert inventory(previous) == retained
            assert settings.DEBUG is False
            assert settings.REFERENCE_PERSONA_CATALOGUE_ENABLED is False
            print(
                json.dumps(
                    {
                        "observed_at": datetime.now(timezone.utc).isoformat(),
                        "profile": "SYNTHETIC_IN_MEMORY_REQUESTS_ONLY",
                        "django": django.get_version(),
                        "python": sys.version.split()[0],
                        "settings": settings.SETTINGS_MODULE,
                        "deployment_checks": "PASS",
                        "requests": rows,
                        "static_assets": len(retained),
                        "candidate_static_matches_previous": True,
                        "previous_static_preserved": True,
                        "database_dotenv_network": "FORBIDDEN",
                        "target_process_tls_proxy_storage_rollback": "UNVERIFIED",
                        "production_equivalence": "NOT_CLAIMED",
                        "cep075": "NOT_STARTED",
                    },
                    indent=2,
                )
            )


if __name__ == "__main__":
    if "--child" in sys.argv:
        execute()
    else:
        environment = {
            k: v
            for k, v in os.environ.items()
            if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP"}
        }
        environment.update(
            runpy.run_path("tests/test_production_configuration.py")["SYNTHETIC_ENV"]
        )
        environment.update(
            DJANGO_SETTINGS_MODULE="config.settings.production",
            PYTHONIOENCODING="utf-8",
        )
        process = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--child"],
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            check=False,
        )
        out = Path(__file__).resolve().parent
        (out / "REQUEST_EXECUTION.json").write_text(process.stdout, encoding="utf-8")
        (out / "REQUEST_DIAGNOSTICS.txt").write_text(process.stderr, encoding="utf-8")
        print("Synthetic request/static preflight:", process.returncode)
        sys.exit(process.returncode)

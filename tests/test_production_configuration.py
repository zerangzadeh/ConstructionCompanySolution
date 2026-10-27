"""Isolated production-setting guards; no deployed target, dotenv or network."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SYNTHETIC_ENV = {
    "DJANGO_SECRET_KEY": "synthetic-configuration-fixture-only-" + "x" * 50,
    "DJANGO_ALLOWED_HOSTS": "fixture.invalid",
    "DB_NAME": "synthetic_unopened",
    "DB_USER": "synthetic",
    "DB_PASSWORD": "synthetic-not-a-credential",
    "DB_HOST": "fixture.invalid",
    "DB_SSLMODE": "verify-full",
    "DJANGO_EMAIL_HOST": "smtp.fixture.invalid",
    "DJANGO_EMAIL_HOST_USER": "synthetic",
    "DJANGO_EMAIL_HOST_PASSWORD": "synthetic-not-a-credential",
    "DJANGO_DEFAULT_FROM_EMAIL": "fixture@fixture.invalid",
    "DJANGO_EMAIL_USE_TLS": "true",
    "DJANGO_CACHE_BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
    "DJANGO_CACHE_LOCATION": "unused-synthetic-location",
    "DJANGO_STATIC_ROOT": str(Path(tempfile.gettempdir()) / "bonira-fixture-static"),
    "DJANGO_MEDIA_ROOT": str(Path(tempfile.gettempdir()) / "bonira-fixture-media"),
    "DOCUMENT_PROTECTED_ROOT": str(
        Path(tempfile.gettempdir()) / "bonira-fixture-private"
    ),
}

LOAD_SETTINGS = """
import json
from unittest.mock import patch
from django.core.exceptions import ImproperlyConfigured
with (
    patch('dotenv.load_dotenv', side_effect=AssertionError('Dotenv forbidden')),
    patch('psycopg.connect', side_effect=AssertionError('Database forbidden')),
    patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')),
):
    try:
        import config.settings.production as settings
    except ImproperlyConfigured:
        result = {'outcome': 'REJECTED'}
    else:
        result = {
            'outcome': 'LOADED',
            'debug': settings.DEBUG,
            'session_secure': settings.SESSION_COOKIE_SECURE,
            'csrf_secure': settings.CSRF_COOKIE_SECURE,
            'database_sslmode': settings.DATABASES['default']['OPTIONS']['sslmode'],
        }
    print(json.dumps(result))
"""


class ProductionConfigurationTests(unittest.TestCase):
    def load(self, **overrides):
        # Never inherit application settings/credentials or a local dotenv file.
        environment = {
            key: value
            for key, value in os.environ.items()
            if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP"}
        }
        environment.update(SYNTHETIC_ENV)
        for key, value in overrides.items():
            if value is None:
                environment.pop(key, None)
            else:
                environment[key] = value
        process = subprocess.run(
            [sys.executable, "-c", LOAD_SETTINGS],
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads(process.stdout)

    def test_secure_defaults_load_without_connecting(self):
        self.assertEqual(
            self.load(),
            {
                "outcome": "LOADED",
                "debug": False,
                "session_secure": True,
                "csrf_secure": True,
                "database_sslmode": "verify-full",
            },
        )

    def test_explicit_secure_cookies_load(self):
        self.assertEqual(
            self.load(
                DJANGO_SESSION_COOKIE_SECURE="true", DJANGO_CSRF_COOKIE_SECURE="true"
            )["outcome"],
            "LOADED",
        )

    def test_insecure_or_invalid_cookie_overrides_fail_closed(self):
        for name in ("DJANGO_SESSION_COOKIE_SECURE", "DJANGO_CSRF_COOKIE_SECURE"):
            for value in ("false", "0", "off", "no", "invalid"):
                with self.subTest(setting=name, value=value):
                    self.assertEqual(
                        self.load(**{name: value}), {"outcome": "REJECTED"}
                    )

    def test_existing_required_configuration_guards_remain(self):
        cases = (
            {"DJANGO_SECRET_KEY": None},
            {"DJANGO_SECRET_KEY": "replace-with-fixture"},
            {"DB_HOST": None},
            {"DB_SSLMODE": "require"},
            {"DJANGO_EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend"},
            {"DJANGO_EMAIL_USE_TLS": "false"},
            {"DJANGO_CACHE_BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
        )
        for overrides in cases:
            with self.subTest(setting=next(iter(overrides))):
                self.assertEqual(self.load(**overrides), {"outcome": "REJECTED"})

    def test_insecure_hosts_secrets_and_redirect_fail_closed(self):
        for overrides in (
            {"DJANGO_SECRET_KEY": "development-only-insecure-key"},
            {"DJANGO_SECRET_KEY": "short"},
            {"DJANGO_SECRET_KEY": "x" * 60},
            {"DJANGO_ALLOWED_HOSTS": ", ,"},
            {"DJANGO_ALLOWED_HOSTS": "*"},
            {"DJANGO_ALLOWED_HOSTS": "fixture.invalid,*"},
            {"DJANGO_SECURE_SSL_REDIRECT": "false"},
            {"DJANGO_USE_X_FORWARDED_PROTO": "invalid"},
            {"DJANGO_HSTS_SECONDS": "-1"},
            {"DJANGO_HSTS_SECONDS": "invalid"},
            {"DJANGO_CACHE_BACKEND": "django.core.cache.backends.dummy.DummyCache"},
        ):
            with self.subTest(setting=next(iter(overrides))):
                self.assertEqual(self.load(**overrides), {"outcome": "REJECTED"})

    def test_storage_hooks_require_explicit_absolute_separate_roots(self):
        for name in (
            "DJANGO_STATIC_ROOT",
            "DJANGO_MEDIA_ROOT",
            "DOCUMENT_PROTECTED_ROOT",
        ):
            for value in (None, "relative/path", str(Path.cwd())):
                with self.subTest(setting=name, value=value):
                    self.assertEqual(
                        self.load(**{name: value}), {"outcome": "REJECTED"}
                    )
        static = SYNTHETIC_ENV["DJANGO_STATIC_ROOT"]
        for value in (static, str(Path(static) / "private"), str(Path(static).parent)):
            with self.subTest(overlap=value):
                self.assertEqual(
                    self.load(DOCUMENT_PROTECTED_ROOT=value), {"outcome": "REJECTED"}
                )

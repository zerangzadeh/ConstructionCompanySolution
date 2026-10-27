"""Repeat bounded, synthetic deployment checks and focused tests only."""

import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
os.chdir(ROOT)

FILES = [
    "config/settings/base.py", "config/settings/development.py",
    "config/settings/production.py", "tests/test_production_configuration.py",
    "core/operations.py", "apps/support/management/commands/operational_health.py",
    "tests/test_operations.py",
    "apps/support/test_p9_s16_s20.py",
]
COMMANDS = {
    "FOCUSED_TESTS": [sys.executable, "-m", "pytest", "tests/test_production_configuration.py", "tests/test_operations.py", "core/test_cep072_telemetry.py", "apps/support/test_p9_s16_s20.py::SupportP9S16S20Tests::test_support_access_sod_scope_expiry_revocation_and_audit", "apps/support/test_p9_s16_s20.py::SupportP9S16S20Tests::test_expired_access_and_stale_approval_fail_closed", "--reuse-db", "-q", "--disable-warnings"],
    "LINT": [sys.executable, "-m", "ruff", "check", *FILES],
    "FORMAT": [sys.executable, "-m", "ruff", "format", "--check", *FILES],
}
results = {}
for name, command in COMMANDS.items():
    start = time.monotonic()
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
    (OUT / f"{name}.txt").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    results[name] = {"command": command, "exit_code": completed.returncode, "seconds": round(time.monotonic()-start, 2)}
    print(name, completed.returncode, flush=True)

environment = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP"}}
environment.update(runpy.run_path("tests/test_production_configuration.py")["SYNTHETIC_ENV"])
environment["DJANGO_SETTINGS_MODULE"] = "config.settings.production"
environment["PYTHONIOENCODING"] = "utf-8"
smoke = r'''
import contextlib, hashlib, io, json, os, pathlib, tempfile
from unittest.mock import patch
with tempfile.TemporaryDirectory(prefix='bonira-deployment-synthetic-') as directory:
    root = pathlib.Path(directory)
    for variable, folder in [('DJANGO_STATIC_ROOT','static'), ('DJANGO_MEDIA_ROOT','media'), ('DOCUMENT_PROTECTED_ROOT','private')]:
        os.environ[variable] = str(root / folder)
    os.environ['DJANGO_CACHE_LOCATION'] = str(root / 'cache')
    with (
        patch('dotenv.load_dotenv', side_effect=AssertionError('Dotenv forbidden')),
        patch('psycopg.connect', side_effect=AssertionError('Database forbidden')),
        patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')),
    ):
        import django
        django.setup()
        from django.core.management import call_command
        from django.conf import settings
        captured = io.StringIO()
        call_command('check', deploy=True, fail_level='WARNING', stdout=captured, stderr=captured)
        call_command('collectstatic', interactive=False, verbosity=0, stdout=captured, stderr=captured)
        import config.wsgi, config.asgi
        files = sorted(settings.STATIC_ROOT.rglob('*'))
        assets = [p for p in files if p.is_file()]
        assert assets
        assert settings.DEBUG is False
        assert settings.REFERENCE_PERSONA_CATALOGUE_ENABLED is False
        assert not settings.MEDIA_ROOT.exists()
        assert not settings.DOCUMENT_PROTECTED_ROOT.exists()
        print(json.dumps({'django_deployment_checks':'PASS', 'wsgi_import':'PASS', 'asgi_import':'PASS', 'static_collection_files':len(assets), 'media_and_private_paths_unmodified':True, 'dotenv_network_database':'FORBIDDEN', 'production_readiness':'NOT_VALIDATED', 'profile':'SYNTHETIC_DISPOSABLE_ONLY'}))
'''
completed = subprocess.run([sys.executable, "-c", smoke], env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
(OUT / "DEPLOYMENT_SMOKE.txt").write_text(completed.stdout + completed.stderr, encoding="utf-8")
results["DEPLOYMENT_SMOKE"] = {"command": "synthetic isolated Django --deploy / collectstatic / WSGI+ASGI import", "exit_code":completed.returncode}
print("DEPLOYMENT_SMOKE", completed.returncode, flush=True)
(OUT / "VALIDATION.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
sys.exit(int(any(r['exit_code'] for r in results.values())))

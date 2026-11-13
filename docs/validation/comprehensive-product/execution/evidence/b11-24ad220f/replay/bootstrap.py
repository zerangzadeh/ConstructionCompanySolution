import csv
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys

repo = Path(__file__).resolve().parents[2]
root = Path(__file__).resolve().parent
docs = repo / 'docs/validation/comprehensive-product'
evidence = docs / 'execution/evidence/b11-24ad220f'
evidence.mkdir(parents=True, exist_ok=True)
pg = Path('D:/Program Files/PostgreSQL/18/bin')

def git(*args):
    return subprocess.check_output(['git', *args], cwd=repo).decode().rstrip()

def write(path, value):
    path.write_text(value + '\n', encoding='utf-8')

def snapshot():
    sources = ('apps/', 'config/', 'core/', 'templates/', 'frontend/', 'tests/')
    extras = {'conftest.py', 'manage.py', 'pytest.ini', 'pyproject.toml', 'package-lock.json'}
    names = [name for name in git('ls-files', '-c', '-o', '--exclude-standard').splitlines() if name.startswith(sources) or name in extras]
    canonical = [
        docs / name for name in ('TEST_EXECUTION_MATRIX_MVP.csv', 'DEFECT_REGISTER.csv',
        'DEFECT_REGISTER.md', 'USER_JOURNEY_CATALOG.md', 'APPROVED_DESIGN_CONFORMANCE_REGISTRY.md',
        'BUSINESS_RULE_COVERAGE_MATRIX.md', 'UI_UX_ACCEPTANCE_CHECKLIST.md')
    ] + [repo / 'Agents.md', repo / 'docs/ui-guidelines.md']
    hashes = {name: hashlib.sha256((repo/name).read_bytes()).hexdigest() for name in sorted(set(names)) if (repo/name).is_file()}
    return {'branch': git('branch','--show-current'), 'head': git('rev-parse','HEAD'),
            'origin/main': git('rev-parse','origin/main'),
            'divergence': git('rev-list','--left-right','--count','HEAD...origin/main'),
            'source_files': len(hashes),
            'source_fingerprint': hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
            'source_sha256': hashes,
            'validation_sha256': {p.relative_to(repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in canonical}}

if sys.argv[1:] == ['final']:
    final = snapshot()
    original = json.loads((root/'entry-full.json').read_text(encoding='utf-8'))
    hashes = final.pop('source_sha256')
    entry = original['source_sha256']
    final['source_delta'] = {k: [entry.get(k), hashes.get(k)] for k in sorted(entry.keys() | hashes.keys()) if entry.get(k) != hashes.get(k)}
    write(evidence/'final-source.json', json.dumps(final, indent=2))
    sys.exit()

baseline = snapshot()
write(root/'entry-full.json', json.dumps(baseline, indent=2))
baseline.pop('source_sha256')
write(evidence/'entry-source.json', json.dumps(baseline, indent=2))
for args, name in [(('status','--short','--branch'), 'entry-status.txt'),
                   (('diff','--name-status'), 'entry-diff.txt'), (('diff','--stat'), 'entry-stat.txt')]:
    write(evidence/name, git(*args))
for name in ('TEST_EXECUTION_MATRIX_MVP.csv','DEFECT_REGISTER.csv','DEFECT_REGISTER.md'):
    (root/('entry-'+name)).write_bytes((docs/name).read_bytes())
with (root/'entry-TEST_EXECUTION_MATRIX_MVP.csv').open(encoding='utf-8-sig', newline='') as stream:
    rows = [row for row in csv.DictReader(stream) if row['Batch'] == 'B11']
assert len(rows) == len({row['Execution_ID'] for row in rows}) == 302
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
write(root/'port.txt', str(port))
write(root/'secret.txt', secrets.token_urlsafe(48))
(root/'temp').mkdir(exist_ok=True)
write(root/'b11_settings.py', """import os
from pathlib import Path
from config.settings.base import *
private = Path(__file__).resolve().parent
dbname = os.environ.get('B11_DB', 'b11_base')
assert dbname in {'b11_base', 'b11_original', 'b11_retest'}
DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': dbname,
    'USER': 'b11_local', 'PASSWORD': '', 'HOST': '127.0.0.1',
    'PORT': (private/'port.txt').read_text().strip(),
    'OPTIONS': {'sslmode': 'disable', 'connect_timeout': 5},
    'TEST': {'NAME': os.environ.get('B11_TEST_DB', 'test_b11_focused')}}}
assert DATABASES['default']['TEST']['NAME'].startswith('test_b11_')
SECRET_KEY = (private/'secret.txt').read_text().strip()
DEBUG = False
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
MEDIA_ROOT = private / (DATABASES['default']['TEST']['NAME'] if 'pytest' in os.environ.get('B11_MODE', '') else dbname) / 'media'
DOCUMENT_PROTECTED_ROOT = MEDIA_ROOT.parent / 'protected'
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': dbname}}
PRODUCT_SURFACE_PROFILE = 'MVP'
""")
write(root/'env.ps1', f"""$env:DJANGO_SETTINGS_MODULE='b11_settings'
$env:PYTHONPATH='{root.as_posix()};{repo.as_posix()}'
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUNBUFFERED='1'
$env:TEMP='{root.as_posix()}/temp'
$env:TMP=$env:TEMP
""")
def run(args, log, env=None):
    with (evidence/log).open('a', encoding='utf-8') as stream:
        subprocess.run([str(x) for x in args], cwd=repo, env=env, stdout=stream,
            stderr=subprocess.STDOUT, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
run([pg/'initdb.exe', '-D', root/'pg', '-U', 'b11_local', '-A', 'trust', '--encoding=UTF8', '--locale=C'], 'bootstrap.log')
run([pg/'pg_ctl.exe', '-D', root/'pg', '-l', root/'postgres.log', '-o',
    f'-h 127.0.0.1 -p {port} -c max_locks_per_transaction=256', '-w', 'start'], 'bootstrap.log')
connection = ['-h', '127.0.0.1', '-p', port, '-U', 'b11_local']
run([pg/'createdb.exe', *connection, 'b11_base'], 'bootstrap.log')
env = {**os.environ, 'DJANGO_SETTINGS_MODULE':'b11_settings', 'B11_DB':'b11_base',
       'PYTHONPATH':os.pathsep.join((str(root),str(repo))), 'PYTHONIOENCODING':'utf-8'}
for args in [('migrate','--noinput'), ('migrate','--check'), ('check',), ('makemigrations','--check','--dry-run')]:
    run([sys.executable, 'manage.py', *args], 'migration.log', env)
for name in ('b11_original','b11_retest'):
    run([pg/'createdb.exe', *connection, '-T', 'b11_base', name], 'bootstrap.log')
run([pg/'psql.exe', *connection, '-d', 'b11_base', '-v', 'ON_ERROR_STOP=1', '-c',
     'BEGIN READ ONLY; SHOW server_version; SELECT count(*) AS migrations FROM django_migrations; SELECT count(*) AS users FROM accounts_user; SELECT count(*) AS tenants FROM organizations_organization; COMMIT;'], 'catalog.log')


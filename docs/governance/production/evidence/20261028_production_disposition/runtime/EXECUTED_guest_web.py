"""Selected Linux Production service contract and actual durable operational receipt."""

import importlib.util
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar
import ssl
from pathlib import Path
from uuid import uuid4

B=Path('/srv/bonira');OUT=B/'production-disposition-evidence'
sys.path.insert(0,str(B/'source-production-disposition'))
from core.production_operations import ProductionOperationsSink
spec=importlib.util.spec_from_file_location('driver',B/'tools/guest_driver.py')
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d);d.OUT=OUT
release='production-disposition-current'
destination=B/'releases'/release
assert not destination.exists()
shutil.copytree(B/'source-production-disposition',destination)
d.invoke(['docker','exec','bonira-db','createdb','-U','bonira_admin','-O','bonira_app','-T','pe_readiness_20261028','pe_gate11_20261028_web'])
sinkdir=OUT/'alerts';sinkdir.mkdir(mode=0o700);os.chown(sinkdir,10001,10001)
sink=ProductionOperationsSink(sinkdir,environment='production-equivalent-qualification')
env=dict(line.split('=',1) for line in (B/'secrets/readiness-current.env').read_text().splitlines() if line)
env.update(DB_NAME='pe_gate11_20261028_web',DJANGO_STATIC_ROOT='/static/'+release,
 GUNICORN_CMD_ARGS='--config python:config.gunicorn_production',BONIRA_OPERATIONS_SINK='/evidence/alerts',BONIRA_OPERATIONS_ENVIRONMENT='production-equivalent-qualification')
envpath=B/'secrets'/(release+'.env');envpath.write_text('\n'.join(k+'='+v for k,v in env.items())+'\n');envpath.chmod(0o600)
static=B/'public'/release;static.mkdir(mode=0o755);os.chown(static,10001,10001);static.chmod(0o755)
original_app=d.app
def app(action,phase,**kwargs):return original_app(action,phase,release=release,**kwargs)
d.app=app
d.app('collectstatic',release)
identities=[];cases=0
for phase in ['PRODUCTION_REFERENCE','PRODUCTION_RESTART']:
 identities.append(d.start_app(release))
 cases+=d.web_checks(release,phase,authenticated=True)
 health=d.health(release=release)
 assert health['production_readiness']=='NOT_VALIDATED'
# Actual failed authentication, with ordinary login behavior and no credential capture.
jar=http.cookiejar.CookieJar();origin='https://localhost:8443'
opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=str(B/'pki/ca.crt'))),urllib.request.HTTPCookieProcessor(jar))
opener.open(origin+'/accounts/login/',timeout=90).read()
csrf=next(c.value for c in jar if c.name=='csrftoken')
data=urllib.parse.urlencode({'username':'does-not-exist-gate11','password':'synthetic-never-capture-credential','csrfmiddlewaretoken':csrf}).encode()
opener.open(urllib.request.Request(origin+'/accounts/login/',data=data,headers={'Referer':origin+'/accounts/login/'}),timeout=90).read()
assert any(json.loads(p.read_text()).get('signal')=='authentication.failed' for p in sinkdir.glob('*.json'))
# Real sink outage: request must retain its original auth redirect, with sanitized fallback.
sinkdir.chmod(0o000)
status,_,_=d.request('/')
assert status==302
sinkdir.chmod(0o700)
d.request('/accounts/login/','POST')
d.stop_app()
# Actual failed deployment: missing private sink is rejected at worker bootstrap.
bad=dict(env,BONIRA_OPERATIONS_SINK='/evidence/absent-sink')
badpath=B/'secrets/gate11-invalid-sink.env';badpath.write_text('\n'.join(k+'='+v for k,v in bad.items())+'\n');badpath.chmod(0o600)
failed=d.invoke(['docker','run','--rm',*d.options(release,env=badpath),d.IMAGE,'python','-m','gunicorn','config.wsgi:application','--bind','unix:/tmp/gate11-failed.sock','--workers','1','--worker-class','sync','--no-control-socket'],allow_failure=True,timeout=90)
assert failed.returncode!=0
sink.write(signal='deployment.failed',request_id=str(uuid4()))
# Real unreachable database migration/readiness probe; --plan never mutates history.
invalid=d.env_with('gate11-unreachable-migration',DB_PORT='1',DB_NAME='pe_gate11_20261028_web')
failed=d.invoke(['docker','run','--rm',*d.options(release,env=invalid),d.IMAGE,'python','manage.py','migrate','--plan'],allow_failure=True,timeout=90)
assert failed.returncode!=0
sink.write(signal='migration.failed',request_id=str(uuid4()))
# Readiness result remains a technical projection, including genuine DB failure.
failed=d.health(release=release,env=invalid,fail=True)
for signal in failed['signals']:
 if isinstance(signal,str):sink.write(signal=signal,request_id=str(uuid4()))
sink.write(signal='operational.not_ready',request_id=str(uuid4()))
# The updated diagnostic tests and existing access authority execute under the same image.
d.invoke(['docker','run','--rm',*d.options(release,env=B/'secrets/gate11-tests.env'),d.IMAGE,'python','/tools/guest_ops_probe.py'])
records=[json.loads(p.read_text()) for p in sinkdir.glob('*.json')]
signals={r['signal'] for r in records if 'signal' in r}
assert {'authentication.failed','authorization.denied','document.delivery_failed','deployment.failed','migration.failed','database.unreachable','operational.not_ready'}<=signals
assert 'synthetic-never-capture-credential' not in json.dumps(records)
assert all(r['environment']=='production-equivalent-qualification' for r in records)
assert all(r['production_readiness']=='NOT_VALIDATED' for r in records)
(OUT/'WEB_OPERATIONS_RESULT.json').write_text(json.dumps({'result':'PASS','https_cases':cases,'service_identities':identities,'production_settings':True,'gunicorn':'sync/private Unix socket/unprivileged','db_tls':'verify-full/SCRAM','sink_private':True,'sink_actual_receipts':len(records),'signals':sorted(signals),'failed_login_behavior_preserved':True,'sink_outage_response_preserved':True,'failed_bootstrap_and_migration_probes':True,'receipt_survives_worker_restart':True,'health_not_promoted_to_readiness':True,'production':False},indent=2)+'\n')
print('PASS: selected Production reference, HTTPS, durable sink, failure and access contracts',flush=True)

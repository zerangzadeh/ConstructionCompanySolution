"""Disposable loopback-only Home fault fixture using the existing tested seam.

It runs the current real Django WSGI application; only an exact query on Home
patches authorized_home_links to throw. No shared server/source/data is changed.
The existing core.test_home.test_error_state_is_safe uses this same exception seam.
"""
import datetime
from contextvars import ContextVar
import json
from pathlib import Path
from html import escape
from socketserver import ThreadingMixIn
import sys
from wsgiref.simple_server import make_server, WSGIServer

OUT=Path(__file__).parent.resolve()
ROOT=OUT.parents[4]
sys.path.insert(0,str(ROOT/'docs/governance/uiux/rv007_controlled_time'))
from support import guard
guard()
from config.wsgi import application
from django.core.exceptions import PermissionDenied
from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.urls import path
from apps.organizations.decorators import active_organization_required, organization_permission_required
from apps.organizations.models import BusinessPermissionCode
from types import ModuleType
from django.conf import settings
import config.urls
import core.views

application = StaticFilesHandler(application)
fault_mode=ContextVar('cep078_fault_mode',default=None)
original_home_links=core.views.authorized_home_links
def home_links(**kwargs):
    mode=fault_mode.get()
    if mode=='unauthorized': raise PermissionDenied('CEP078_SAFE_FAULT_FIXTURE')
    if mode=='error': raise RuntimeError('CEP078_SAFE_FAULT_FIXTURE')
    return original_home_links(**kwargs)
core.views.authorized_home_links=home_links

class FixtureServer(ThreadingMixIn,WSGIServer):
    daemon_threads=True

@login_required
@active_organization_required
@organization_permission_required(BusinessPermissionCode.PURCHASE_ORDERS_CREATE)
def mismatch_driver(request):
    """Test request generator; response under test is the unchanged canonical view."""
    data=json.loads((OUT/'PO_MISMATCH_FIXTURE.json').read_text(encoding='utf8'))
    if request.user.username!=data['actor'] or str(request.organization.pk)!=data['organization']:
        raise PermissionDenied('Fixture actor/context mismatch')
    inputs=''.join('<input type="hidden" name="'+escape(k)+'" value="'+escape(v)+'">' for k,v in data['data'].items())
    html=('<!doctype html><html lang="en"><title>CEP078 isolated invalid request driver</title>'
        '<main><h1>Development negative test only</h1><p>This intentionally mismatched payload must never create an order.</p>'
        '<form method="post" action="/procurement/orders/create/">'
        '<input type="hidden" name="csrfmiddlewaretoken" value="'+escape(get_token(request))+'">'+inputs+
        '<button type="submit">Submit qualified mismatch to canonical endpoint</button></form></main></html>')
    return HttpResponse(html)

fixture_urls=ModuleType('cep078_fixture_urls')
fixture_urls.urlpatterns=[path('__cep078/po-mismatch/',mismatch_driver)]+config.urls.urlpatterns
sys.modules[fixture_urls.__name__]=fixture_urls
settings.ROOT_URLCONF=fixture_urls.__name__

def fixture(environ,start_response):
    mode=None
    if environ.get('PATH_INFO')=='/':
        mode={'cep078_fixture=403':'unauthorized','cep078_fixture=503':'error'}.get(environ.get('QUERY_STRING'))
    def observe(status,headers,exc_info=None):
        if mode:
            with (OUT/'HOME_FAULT_HTTP.jsonl').open('a',encoding='utf8') as f:
                f.write(json.dumps({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'state':mode,'status':status,'fixture':'isolated loopback WSGI exception seam; no original8000 source/config/data modification'})+'\n')
        return start_response(status,headers,exc_info)
    token=fault_mode.set(mode)
    try:
        return application(environ,observe)
    finally:
        fault_mode.reset(token)

with make_server('127.0.0.1',8002,fixture,server_class=FixtureServer) as server:
    print('CEP078 disposable Home fixture127.0.0.1:8002; real current Home403/503 branches',flush=True)
    server.serve_forever()

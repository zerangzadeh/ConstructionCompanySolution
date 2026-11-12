import os,sys,json
from pathlib import Path
repo=Path(r'E:\Construction_Company_Solution')
runtime=Path(os.environ['UX_RUNTIME'])
sys.path.insert(0,str(repo))
os.environ['DJANGO_SETTINGS_MODULE']='config.settings.base'
from django.conf import settings
settings.SECRET_KEY=(runtime/'key').read_text()
settings.DATABASES={'default':{'ENGINE':'django.db.backends.postgresql','NAME':'bonira_w01_final_browser','USER':'postgres','PASSWORD':'','HOST':'127.0.0.1','PORT':'55491','OPTIONS':{'sslmode':'disable','connect_timeout':3},
'TEST':{'NAME':'bonira_w01_final_tests','TEMPLATE':'bonira_w01_ux_clean'}}}
settings.DEBUG=False
settings.ALLOWED_HOSTS=['127.0.0.1','localhost','testserver']
settings.PRODUCT_SURFACE_PROFILE='MVP'
settings.MEDIA_ROOT=runtime/'media'
settings.DOCUMENT_PROTECTED_ROOT=runtime/'protected'
settings.CACHES={'default':{'BACKEND':'django.core.cache.backends.locmem.LocMemCache','LOCATION':'bonira-final-ux'}}
settings.SESSION_COOKIE_NAME='bonira_ux_session'
settings.CSRF_COOKIE_NAME='bonira_ux_csrf'
settings.EMAIL_BACKEND='django.core.mail.backends.filebased.EmailBackend'
settings.EMAIL_FILE_PATH=runtime/'mail'
import django
django.setup()
from django.db import connection
with connection.cursor() as c:
    c.execute("select current_database(),inet_server_port(),current_setting('data_directory')")
    name,port,directory=c.fetchone()
assert (name,port,Path(directory).resolve())==('bonira_w01_final_browser',55491,(runtime.parent/'bonira-wave01-865fa3f3/pg').resolve())
connection.close()
from django.core.management import call_command
cmd=sys.argv[1]
if cmd=='serve':
    call_command('runserver','127.0.0.1:8189',use_reloader=False,insecure_serving=True)
elif cmd=='provision':
    import secrets
    from apps.accounts.models import User
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.http import urlsafe_base64_encode
    from django.utils.encoding import force_bytes
    user=User.objects.get(username='w01-platform')
    password=secrets.token_urlsafe(24)
    user.set_password(password); user.save(update_fields=['password'])
    recovery=User.objects.get(username='w01-owner')
    token=default_token_generator.make_token(recovery)
    fixture={'username':user.username,'password':password,'reset_path':'/accounts/password/reset/'+urlsafe_base64_encode(force_bytes(recovery.pk))+'/'+token+'/'}
    (runtime/'fixture.json').write_text(json.dumps(fixture),encoding='utf-8')
    print('Synthetic credentials and recovery token prepared privately.')
elif cmd=='test':
    import pytest
    raise SystemExit(pytest.main(['--reuse-db','-p','no:cacheprovider','-q','-rA','--tb=short','--show-capture=no','apps/organizations/test_wave01_ux_remediation.py::Wave01UXRemediationTests::test_audit_calendar_labels_and_inclusive_date_boundaries','apps/organizations/test_wave01_ux_remediation.py::Wave01UXRemediationTests::test_audit_jalali_invalid_redisplay_and_canonical_conversion']))
elif cmd=='check':
    call_command('check')

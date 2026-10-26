"""Focused actual Django view rendering, explicitly not browser/runtime conformance."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()
from django.conf import settings
from django.test import Client
from apps.accounts.models import User
from apps.billing.models import ProgressClaim
from apps.organizations.services import resolve_active_organization, set_active_organization

assert settings.SETTINGS_MODULE == 'config.settings.development' and settings.DEBUG
credential = json.loads(subprocess.check_output(['pwsh.exe','-NoProfile','-Command',
    "$referenceCredential = Import-Clixml -LiteralPath 'C:/Users/azera/AppData/Local/BONIRA/UIUXRuntimeAudit/credentials/uiux.audit.project.clixml'; @{username=$referenceCredential.UserName; password=$referenceCredential.GetNetworkCredential().Password} | ConvertTo-Json -Compress"], text=True))
client = Client(HTTP_HOST='localhost')
claim = ProgressClaim.objects.get(pk='c274c8c7-16c9-427f-8b31-6e1fdd1e5875')
fingerprint = lambda: hashlib.sha256(json.dumps(ProgressClaim.objects.filter(pk=claim.pk).values().get(),sort_keys=True,default=str).encode()).hexdigest()
before = fingerprint()
assert client.login(**credential)
credential.clear()
try:
    actor = User.objects.get(username='uiux.audit.project')
    organization = resolve_active_organization(actor, claim.organization_id)
    assert organization is not None
    session = client.session
    set_active_organization(session, organization)
    session.save()
    response = client.get(f'/billing/claims/{claim.pk}/')
    html = response.content.decode('utf8')
    result = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'actor': actor.username, 'actual_view_status': response.status_code,
        'claim_unchanged': fingerprint() == before,
        'checks': {text: text in html for text in ['مبنای محاسبه','خالص صورت‌وضعیت','مالیات','بیمه','ناخالص']},
        'html_sha256': hashlib.sha256(response.content).hexdigest(),
        'scope': 'Actual authenticated Django middleware/service/object-scope/template response only. Browser responsive/Jalali/native screen-reader and reduced-motion remain unverified.',
        'browser_pass_inferred': False}
    assert response.status_code == 200 and result['claim_unchanged'] and all(result['checks'].values())
    result['result'] = 'PASS_SCOPED_SERVER_RENDER_ONLY'
finally:
    client.logout()
Path(__file__).with_name('CLAIM_SERVER_RENDER.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(result,ensure_ascii=True))

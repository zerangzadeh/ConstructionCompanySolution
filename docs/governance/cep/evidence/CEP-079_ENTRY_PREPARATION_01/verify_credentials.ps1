$ErrorActionPreference = 'Stop'
$cep079EvidenceRoot = $PSScriptRoot
$cep079Actors = Get-Content -LiteralPath (Join-Path $cep079EvidenceRoot 'QUALIFIED_ACTORS.json') -Raw | ConvertFrom-Json
$cep079CredentialRows = @()
foreach ($cep079Actor in $cep079Actors) {
    $cep079CredentialFile = Join-Path $env:LOCALAPPDATA ('BONIRA/UIUXRuntimeAudit/credentials/' + $cep079Actor.alias + '.clixml')
    if (Test-Path -LiteralPath $cep079CredentialFile) {
        $cep079Credential = Import-Clixml -LiteralPath $cep079CredentialFile
        $cep079CredentialRows += @{ alias = $cep079Actor.alias; secret = $cep079Credential.GetNetworkCredential().Password }
    }
}
$cep079Checker = @'
import sys,os,json,pathlib
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django;django.setup()
from django.contrib.auth.hashers import check_password
from django.db import transaction,connection
from apps.accounts.models import User
records=json.load(sys.stdin)
result=[]
with transaction.atomic():
 with connection.cursor() as cursor:cursor.execute('SET TRANSACTION READ ONLY')
 for record in records:
  user=User.objects.get(username=record['alias'])
  result.append({'alias':record['alias'],'active':user.is_active,'credential_matches':check_password(record['secret'],user.password,setter=None)})
  record['secret']=None
out=pathlib.Path('docs/governance/cep/evidence/CEP-079_ENTRY_PREPARATION_01/CREDENTIAL_QUALIFICATION.json')
out.write_text(json.dumps({'method':'Existing current-user DPAPI credential -> stdin only -> Django trusted hasher with setter=None and read-only transaction. No login, reset, hash upgrade, credential logging or secret persistence.','results':result},indent=2),encoding='utf-8')
print(json.dumps({'checked':len(result),'matches':sum(x['credential_matches'] for x in result),'failures':[x['alias'] for x in result if not x['credential_matches']]}))
'@
($cep079CredentialRows | ConvertTo-Json -Compress) | & (Join-Path (Get-Location).Path '.venv/Scripts/python.exe') -B -c $cep079Checker
$cep079CredentialRows = $null
$cep079Credential = $null
if ($LASTEXITCODE -ne 0) { throw 'Credential qualification failed; no secrets were logged.' }

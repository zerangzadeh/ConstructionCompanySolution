from pathlib import Path
from django.db import connection, transaction
from django.test import Client
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.accounts.models import User
from apps.organizations.models import BusinessPermission, OrganizationRole, MembershipScopeGrant, MembershipRoleAssignment
from apps.projects.models import Project
from apps.documents.services import record_document_processing_assessment
import hashlib, json
ROOT=Path(__file__).resolve().parent
ASSETS=json.loads((ROOT.parents[1]/'docs/validation/comprehensive-product/execution/evidence/b09-24ad220f/assets-and-scan.json').read_text())
def save(name,obj):
    pass

def upload(n=1):
    p=ROOT.parent/'b09-validation/assets'/f'b09-v{n}.pdf'
    return SimpleUploadedFile(p.name,p.read_bytes(),content_type='application/pdf')

WITNESS_SQL=None
WITNESS_PREPARED=False

def witness():
    global WITNESS_SQL,WITNESS_PREPARED
    with connection.cursor() as c:
        if WITNESS_SQL is None:
            names=[name for name in sorted(connection.introspection.table_names()) if name.startswith(('documents_','audit_','contracts_','daily_reports_','materials_','quality_','safety_','workflows_','projects_','billing_','expenses_','estimates_','workforce_','organizations_','accounts_'))]
            WITNESS_SQL=' UNION ALL '.join(f'SELECT \'{name}\', count(*), md5(coalesce(string_agg(row_to_json(t)::text,\'\' ORDER BY row_to_json(t)::text),\'\')) FROM "{name}" t' for name in names)
        if not WITNESS_PREPARED:
            c.execute('PREPARE b09_readback AS '+WITNESS_SQL)
            WITNESS_PREPARED=True
        c.execute('EXECUTE b09_readback')
        result={row[0]:row[1:] for row in c.fetchall()}
    files={p.relative_to(settings.DOCUMENT_PROTECTED_ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
           for p in Path(settings.DOCUMENT_PROTECTED_ROOT).rglob('*') if p.is_file()}
    return {'tables':result,'storage':files}

def assess(f,version,verdict='clean'):
    with version.file.open('rb') as stream:
        data=stream.read()
    digest=hashlib.sha256(data).hexdigest()
    assert digest==version.sha256
    assert digest in {v['sha256'] for k,v in ASSETS.items() if k!='scanner'}
    return record_document_processing_assessment(version=version,actor=f.operator,verdict=verdict,
        adapter_code='b09-local-defender-verified-assets',adapter_version='MpCmdRun',
        details={'scope':'Actual local on-demand scan of hash-identical generated assets; external DMS scanner integration unverified',
                 'input_sha256':digest,'scanner_exit_code':ASSETS['scanner']['exit_code'],
                 'test_quarantine':verdict!='clean'})

def persona(f,name,codes,project=None):
    u=User.objects.create_user(username='b09-'+name)
    role=OrganizationRole.objects.create(organization=f.organization,code='b09-'+name,name=name)
    role.permissions.set(BusinessPermission.objects.filter(code__in=codes,is_active=True))
    m=f.organization.memberships.create(user=u,status='active',role_definition=role,authorization_migrated_at=timezone.now())
    MembershipRoleAssignment.objects.create(organization=f.organization,membership=m,role=role,reason='Isolated B09 explicit persona')
    MembershipScopeGrant.objects.create(organization=f.organization,membership=m,scope_type='project' if project else 'organization',project=project,reason='Isolated B09 explicit scope')
    return u

@transaction.atomic
def seed():
    from apps.documents.test_evidence_integration import EvidenceIntegrationTests
    from apps.documents.test_related_documents import RelatedDocumentsTests
    from apps.organizations.access_services import assign_platform_role
    f=EvidenceIntegrationTests();f.client=Client();f.setUp();f.media_override.disable()
    f._pdf_upload=lambda *args,**kwargs:upload(2 if kwargs.get('suffix') else 1)
    assigner=User.objects.create_superuser(username='b09-technical-assigner')
    approver=User.objects.create_superuser(username='b09-technical-approver')
    f.operator=User.objects.create_user(username='b09-processing-operator')
    assign_platform_role(actor=assigner,approver=approver,target=f.operator,role='platform_operations',reason='Isolated synthetic document processing assessment')
    f.clean_version=lambda version:assess(f,version)
    f.generic=dict(zip(('project','contract','estimate','expense','daily_report'),RelatedDocumentsTests.targets(f),strict=True))
    f.special={'safety':f.safety(),'quality':f.quality(),'field_observation':f.observation(),'material':f.material()}
    f.special.update(dict(f.commercial()))
    from apps.contracts.contractual_services import create_contractual_record
    f.special['contractual']=create_contractual_record(organization=f.organization,actor=f.owner,contract=f.contract,kind='claim',record_number='B09-CR',title='رکورد قراردادی شاهد',description='شاهد بدون اثر مالی خودکار',idempotency_key='b09-contractual-source')
    f.record=f.special['contractual']
    f.doc=f._create_document(reference='B09-EVIDENCE',title='سند شاهد آزمون بنیرا')
    assess(f,f.doc.current_version)
    from apps.contracts.models import Contract
    f.origin_contract=Contract.objects.create(organization=f.organization,project=f.project,contract_number='B09-ORIGIN',title='قرارداد منبع سند مشترک',counterparty_name='طرف نمونه',direction='receivable')
    f.second=f._create_document(reference='B09-CHOICE',title='سند قابل انتخاب بنیرا',target=f.origin_contract)
    assess(f,f.second.current_version)
    foreign_project=Project.objects.create(organization=f.other_organization,code='B09-F',name='FOREIGN B09 project')
    f.foreign=f._create_document(organization=f.other_organization,actor=f.other_user,target=foreign_project,reference='B09-FOREIGN',title='FOREIGN B09 PRIVATE')
    f.sibling_project=Project.objects.create(organization=f.organization,code='B09-SIB',name='پروژه خواهر محدود')
    codes=list(BusinessPermission.objects.filter(is_active=True).values_list('code',flat=True))
    views=[p for p in codes if p.endswith('.view')]
    dms=[p for p in codes if p in {'documents.view','documents.upload','documents.download'} or p.endswith('.view')]
    f.uploader=persona(f,'uploader',dms)
    f.linker=persona(f,'linker',dms)
    f.reviewer=f.manager
    f.readonly=persona(f,'readonly',views)
    f.nodownload=persona(f,'no-download',[p for p in codes if p!='documents.download'])
    f.denied=persona(f,'no-authority',[])
    f.sibling=persona(f,'sibling-project',codes,project=f.sibling_project)
    f.first=f.doc.current_version
    return f


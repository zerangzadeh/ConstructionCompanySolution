"""Actual Development RFQ lifecycle, real clock and real owning services."""
from datetime import timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess

import continue_uat as c
u = c.u
from apps.procurement import models as m
from apps.procurement.rfq_services import create_rfq, add_rfq_line, submit_rfq_for_issue, issue_rfq, close_rfq
from apps.procurement.quote_services import capture_quote_revision, submit_quote_revision
from apps.procurement.custody_services import custody_sealed_quote_evidence
from apps.procurement.opening_services import request_quote_opening, approve_quote_opening, grant_quote_confidential_access
from apps.procurement.admissibility_services import prepare_quote_admissibility, approve_quote_admissibility
from apps.procurement.comparison_services import appoint_evaluator, evaluate_comparison, finalize_comparison, finalize_sourcing_award

STATE = u.OUT / 'UAT_CASE_026_SOURCE.json'


def save(d):
    STATE.write_text(json.dumps(d, indent=2, default=str)+'\n', encoding='utf-8')


def prepare():
    assert not STATE.exists()
    source=m.PurchaseRequest.objects.get(organization=u.ORG,request_number='CEP079-UAT024-PR',status='approved')
    owner=u.actor('account.demo-construction-01.owner');buyer=u.actor('uiux.wavec.buyer')
    now=u.timezone.now()
    rfq=m.RequestForQuotation.objects.filter(organization=u.ORG,rfq_number='CEP079-UAT026-RFQ').first()
    if rfq is None:
        rfq=create_rfq(organization=u.ORG,actor=buyer,project=u.PROJECT,purchase_request=source,
        rfq_number='CEP079-UAT026-RFQ',title='آزمون پذیرش ۲۶ استعلام مصنوعی توسعه',
        closing_at=now+timedelta(minutes=2),earliest_opening_at=now+timedelta(minutes=2),
        terms='Synthetic Development only; actual clock; disclosed2minute test window; no actual supplier offer or commitment')
    if rfq.status=='draft':
        add_rfq_line(organization=u.ORG,actor=buyer,rfq=rfq,purchase_request_item=source.items.get(),quantity=Decimal('2'))
        submit_rfq_for_issue(organization=u.ORG,actor=buyer,rfq=rfq)
    supplier=m.PurchaseOrder.objects.get(organization=u.ORG,order_number='CEP079-UAT025-PO').supplier
    version=issue_rfq(organization=u.ORG,actor=owner,rfq=rfq,suppliers=[supplier],idempotency_key='CEP079-026-issue')
    payload=Path('docs/governance/uiux/rv007_controlled_time/SYNTHETIC_QUOTE.pdf').read_bytes()
    digest=hashlib.sha256(payload).hexdigest()
    revision=capture_quote_revision(organization=u.ORG,actor=buyer,invitation=version.invitations.get(),
        integrity_fingerprint=digest,source_channel='manual_capture',source_reference='CEP079-UAT026-SYNTHETIC-PDF',idempotency_key='CEP079-026-capture')
    revision=submit_quote_revision(organization=u.ORG,actor=buyer,revision=revision,idempotency_key='CEP079-026-submit')
    assert not revision.is_late
    save({'created_at':now,'rfq':rfq.pk,'version':version.pk,'revision':revision.pk,'source_sha256':digest,
        'payload_path':'docs/governance/uiux/rv007_controlled_time/SYNTHETIC_QUOTE.pdf','closing_at':version.closing_at,'earliest_opening_at':version.earliest_opening_at,
        'clock':'REAL_UNMODIFIED','source':'Existing approved synthetic Development PDF; no actual vendor quote'})
    print('Created actual issued RFQ and on-time submitted quote;2minute test receipt/opening deadline',version.closing_at)


def custody():
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.documents.services import record_document_processing_assessment
    from apps.organizations.access_services import assign_platform_role
    d=json.loads(STATE.read_text());rfq=m.RequestForQuotation.objects.get(pk=d['rfq']);revision=m.QuoteRevision.objects.get(pk=d['revision'])
    custodian=u.actor('uiux.wavec.custodian')
    manifest=close_rfq(organization=u.ORG,actor=custodian,rfq=rfq,idempotency_key='CEP079-026-close')
    evidence=custody_sealed_quote_evidence(organization=u.ORG,actor=custodian,quote_revision=revision,
        evidence_type='supplier_original',evidence_slot='primary',upload=SimpleUploadedFile('cep079-synthetic-quote.pdf',Path(d['payload_path']).read_bytes(),content_type='application/pdf'),idempotency_key='CEP079-026-custody')
    d.update(manifest=str(manifest.pk),evidence=str(evidence.pk),document_version=str(evidence.document_version_id));save(d)
    scanner=sorted(Path('C:/ProgramData/Microsoft/Windows Defender/Platform').glob('*/MpCmdRun.exe'))[-1]
    source=Path(evidence.document_version.file.path)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==d['source_sha256']
    scan=subprocess.run([str(scanner),'-Scan','-ScanType','3','-File',str(source),'-DisableRemediation'],capture_output=True,text=True,timeout=55)
    d['scan']={'at':u.timezone.now().isoformat(),'adapter':'microsoft-defender-mpcmdrun','version':scanner.parent.name,'exit_code':scan.returncode,'stdout':scan.stdout,'stderr':scan.stderr};save(d)
    assert scan.returncode==0 and 'found no threats' in scan.stdout.lower()
    superuser=u.actor('superuser')
    scanner_actor=u.actor('admin')
    duty=assign_platform_role(actor=superuser,approver=superuser,target=scanner_actor,role='platform_operations',reason='CEP079 exact synthetic source real Defender assessment; five minute isolated Development duty; expired custodian duty unchanged',ends_at=u.timezone.now()+timedelta(minutes=5))
    assessment=record_document_processing_assessment(version=evidence.document_version,actor=scanner_actor,verdict='clean',adapter_code='microsoft-defender-mpcmdrun',adapter_version=scanner.parent.name)
    d.update(scanner_duty=str(duty.pk),assessment=str(assessment.pk));save(d)
    print('Closed, custodized, actually scanned source; clean assessment',assessment.pk)


def open_and_qualify():
    from django.core.exceptions import PermissionDenied
    from apps.organizations.authorization import require_business_permission
    from apps.organizations.models import OrganizationMembership
    d=json.loads(STATE.read_text());revision=m.QuoteRevision.objects.get(pk=d['revision'])
    buyer=u.actor('uiux.wavec.buyer');approver=u.actor('uiux.wavec.opening-approver')
    request=m.QuoteOpeningRequest.objects.get(quote_revision=revision,idempotency_key='CEP079-026-opening')
    try:
        approve_quote_opening(organization=u.ORG,actor=buyer,opening_request=request)
    except PermissionDenied:
        d['same_actor_opening_denied']=True
    else:
        raise AssertionError('Opening was not independently controlled')
    opened=approve_quote_opening(organization=u.ORG,actor=approver,opening_request=request)
    grants=[]
    for alias in ['uiux.wavec.buyer','uiux.wavec.custodian']:
        membership=OrganizationMembership.objects.get(organization=u.ORG,user__username=alias)
        grant=grant_quote_confidential_access(organization=u.ORG,actor=approver,quote_revision=revision,membership=membership,
            reason='CEP079 exact synthetic opened revision review',idempotency_key='CEP079-026-access-'+alias)
        grants.append(str(grant.pk))
    preparation=prepare_quote_admissibility(organization=u.ORG,actor=buyer,quote_revision=revision,state='admissible',
        reason_code='requirements_met',rationale='Synthetic source on-time; retained original/hash; actual Defender clean; independent opening',idempotency_key='CEP079-026-admissibility')
    decision=approve_quote_admissibility(organization=u.ORG,actor=u.actor('uiux.wavec.custodian'),preparation=preparation)
    require_business_permission(user=buyer,organization=u.ORG,permission='rfq_quotes.prepare_comparison',project=u.PROJECT,message='CEP079 exact comparison scope')
    line=revision.rfq_version.lines.get()
    scope=m.RFQCommercialScope(organization=u.ORG,rfq_version=revision.rfq_version,rfq_version_line=line,scope_type='line',
        scope_code='CEP079-UAT026-LINE',required_quantity=line.quantity,unit_of_measure=line.unit_of_measure,created_by=buyer)
    scope.full_clean();scope.save()
    d.update(opening_request=str(request.pk),opening=str(opened.pk),access_grants=grants,admissibility=str(decision.pk),scope=str(scope.pk),qualified_at=u.timezone.now().isoformat());save(d)
    print('Independent protected opening, exact access grants, independent admissibility and native scope ready')


if __name__=='__main__':
    import sys
    {'prepare':prepare,'custody':custody,'qualify':open_and_qualify}[sys.argv[1]]()

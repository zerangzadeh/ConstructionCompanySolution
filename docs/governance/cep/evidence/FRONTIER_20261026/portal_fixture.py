"""Explicitly Human-authorized isolated synthetic portal lifecycle, Development only."""
import sys
import json
import hashlib
from pathlib import Path
from datetime import timedelta
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
sys.path.insert(0,str(ROOT/'docs/governance/uiux/rv007_controlled_time'))
from support import guard
from django.db import transaction
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationMembership
from apps.procurement.models import RequestForQuotationInvitation, SupplierPortalSubmissionReceipt
from apps.procurement.rfq_services import create_rfq, add_rfq_line, submit_rfq_for_issue, issue_rfq
from apps.procurement.portal_services import create_supplier_portal_invitation, accept_supplier_portal_invitation, submit_supplier_portal_quote, get_supplier_portal_rfq_context

guard()
assert not (OUT/'PORTAL_FIXTURE.json').exists()
org=Organization.objects.get(slug='demo-construction-01')
external=User.objects.get(username='uiux.wcd.external')
assert not OrganizationMembership.objects.filter(user=external).exists()
source=RequestForQuotationInvitation.objects.get(organization=org,rfq_version__rfq__rfq_number='WAVE-C-RFQ-A')
buyer=User.objects.get(username='uiux.persona.project-manager')
issuer=User.objects.get(username='account.demo-construction-01.owner')
manager=User.objects.get(username='uiux.wavec.portal')
now=timezone.now()
label='CEP078_SYNTHETIC_DEVELOPMENT_ONLY_NON_AUTHORITATIVE'
with transaction.atomic():
    closing=now+timedelta(hours=2)
    rfq=create_rfq(organization=org,actor=buyer,project=source.rfq_version.rfq.project,purchase_request=source.rfq_version.rfq.purchase_request,rfq_number='CEP078-20261026-PORTAL-01',title='نمونه مصنوعی توسعه — راستی‌آزمایی درگاه',closing_at=closing,earliest_opening_at=closing,terms=label)
    for line in source.rfq_version.lines.all():
        add_rfq_line(organization=org,actor=buyer,rfq=rfq,purchase_request_item=line.purchase_request_item,quantity=line.quantity,description=label)
    submit_rfq_for_issue(organization=org,actor=buyer,rfq=rfq)
    version=issue_rfq(organization=org,actor=issuer,rfq=rfq,suppliers=[source.supplier],idempotency_key='cep078-20261026-portal-issue-01')
    invitation=version.invitations.get()
    invite,token=create_supplier_portal_invitation(organization=org,actor=manager,rfq_invitation=invitation,invited_email=external.email,expires_at=now+timedelta(minutes=45))
    grant=accept_supplier_portal_invitation(actor=external,token=token)
    del token
    get_supplier_portal_rfq_context(actor=external,grant=grant)
# Reuse known benign bytes, never accepted evidence file writes.
payload=(ROOT/'docs/governance/uiux/wave_c_domain_resolution/synthetic_primary_bid.pdf').read_bytes()
receipt=submit_supplier_portal_quote(actor=external,grant=grant,upload=SimpleUploadedFile('CEP078-synthetic-runtime-bid.pdf',payload,content_type='application/pdf'),idempotency_key='cep078-20261026-primary-01',source_reference=label)
assert receipt.grant_id==grant.pk
assert not OrganizationMembership.objects.filter(user=external).exists()
result={'at':now,'authorization':'Current direct Human executable frontier instruction; correctable isolated Development fixture expiry','label':label,'external':external.username,'tenant_membership_count':0,'rfq':rfq.pk,'rfq_version':version.pk,'rfq_invitation':invitation.pk,'portal_invitation':invite.pk,'grant':grant.pk,'receipt':receipt.pk,'quote_revision':receipt.quote_revision_id,'path':f'/procurement/portal/grants/{grant.pk}/','receipt_path':f'/procurement/portal/receipts/{receipt.pk}/','expires_at':invite.expires_at,'closing_at':closing,'bytes_sha256':hashlib.sha256(payload).hexdigest(),'services':['create_rfq','add_rfq_line','submit_rfq_for_issue','issue_rfq','create_supplier_portal_invitation','accept_supplier_portal_invitation','submit_supplier_portal_quote'],'retention':'Retain labeled synthetic immutable source/receipt/custody/audit provenance; no hard delete or expiry rewrite. External grant expires naturally. Not real business/financial data.','old_accepted_records':'Not rewritten; only shared existing approved synthetic request/supplier references reused; new RFQ/version/invitation/quote/receipt/documents appended','token_persisted':False}
(OUT/'PORTAL_FIXTURE.json').write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Synthetic canonical portal RFQ/invitation/submission/receipt ready; external memberships0')

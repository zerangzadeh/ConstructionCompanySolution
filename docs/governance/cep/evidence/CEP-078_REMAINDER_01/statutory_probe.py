"""Read-only current source qualification for CEP078 SC014 only."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()
from django.conf import settings
from django.db import connection, transaction
from apps.organizations.models import PlatformPolicyVersion, PolicyReviewEvidence, InsuranceClassification
from apps.billing.models import ProgressClaim, TenantBillingConfiguration
from apps.contracts.models import ContractTermVersion
from apps.organizations.policy_services import resolve_effective_platform_regulatory_policy

assert settings.SETTINGS_MODULE == 'config.settings.development' and settings.DEBUG
assert connection.vendor == 'postgresql' and connection.settings_dict['NAME'] == 'construction_erp'
assert connection.settings_dict['HOST'] in {'localhost','127.0.0.1','::1'}
with transaction.atomic():
    with connection.cursor() as cursor:
        cursor.execute('SET TRANSACTION READ ONLY')
    versions = PlatformPolicyVersion.objects.filter(policy__code='receivable-claim-regulatory')
    result = {
        'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'all_status_regulatory_versions': list(versions.values('id','version','status','effective_from','effective_to','source_basis','insurance_classification_id')),
        'accepted_reviews_for_policy': PolicyReviewEvidence.objects.filter(policy_version__in=versions,disposition='accepted').count(),
        'all_tenant_claim_count': ProgressClaim.objects.count(),
        'all_tenant_terms_count': ContractTermVersion.objects.count(),
        'all_tenant_billing_configuration_count': TenantBillingConfiguration.objects.count(),
        'insurance_classification_count': InsuranceClassification.objects.count(),
        'claims': list(ProgressClaim.objects.values('id','contract_term_version_id','regulatory_rule_version_id','measurement_cutoff')),
        'no_mutation': True,
        'policy_details': [
            {'id': str(v.id), 'parameters': v.parameters, 'reason': v.reason,
             'sources': list(v.sources.values('issuer','title','source_identifier','source_location','version','publication_date','effective_from','effective_to','applicability','reason')),
             'reviews': list(v.review_evidence.values('qualification_summary','independence_statement','evidence_reference','reviewed_on','review_scope','disposition','conditions'))}
            for v in versions
        ],
    }
    claim = ProgressClaim.objects.select_related('contract_term_version__insurance_classification').get(pk='c274c8c7-16c9-427f-8b31-6e1fdd1e5875')
    term = claim.contract_term_version
    resolved = resolve_effective_platform_regulatory_policy(
        code='receivable-claim-regulatory', consumer='billing.progress_claim.calculate',
        on_date=claim.measurement_cutoff, insurance_classification=term.insurance_classification,
    )
    assert resolved.pk == claim.regulatory_rule_version_id
    assert term.organization_id == claim.organization_id and term.contract_id == claim.contract_id
    assert term.status == 'approved' and term.effective_from <= claim.measurement_cutoff
    result['qualification'] = {'result': 'PASS_FOR_EXISTING_APPROVED_DEVELOPMENT_UAT_CONTRACT',
        'claim': str(claim.pk), 'cutoff': claim.measurement_cutoff, 'contract_terms_status': term.status,
        'resolved_policy': str(resolved.pk), 'parameters': resolved.parameters,
        'source_of_authority': 'Retained direct Human B03 source/classification/review acceptance in BLOCKER_CLOSURE_TASKS.json; native effective resolver reproduced read-only.',
        'missing_statutory_input_or_review_for_this_fixture': [],
        'excluded_draft': 'product_defined v1 synthetic simulation remains draft and is not used.'}
recovery = ROOT / 'docs/governance/cep/evidence/CEP-079_ENTRY_PREPARATION_01/BILLING_SOURCE_RECOVERY.json'
result['retained_authoritative_recovery'] = {'path': str(recovery.relative_to(ROOT)), 'sha256': hashlib.sha256(recovery.read_bytes()).hexdigest(),
    'use': 'Retain existing repository plus approved archive qualification; do not rerun CEP079 or promote illustrative fixtures.'}
for v in versions:
    result.setdefault('version_provenance', []).append({'id': str(v.id), 'source_count': v.source_links.count(), 'accepted_review_count': v.review_evidence.filter(disposition='accepted').count()})
Path(__file__).with_name('STATUTORY_CURRENT.json').write_text(json.dumps(result, indent=2, default=str)+'\n', encoding='utf8')
print(json.dumps({'at':result['at'],'qualification':result['qualification']},default=str))

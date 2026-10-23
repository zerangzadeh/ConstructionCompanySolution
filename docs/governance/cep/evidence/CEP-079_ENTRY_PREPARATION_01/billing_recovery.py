"""Recover authoritative existing Billing inputs; never supply statutory values."""
import hashlib
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from django.db import connection, transaction
from apps.organizations.models import Organization, PlatformPolicyVersion
from apps.organizations.policy_specs import RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE
from apps.contracts.models import ContractTermVersion
from apps.billing.models import TenantBillingConfiguration, ProgressClaim

OUT = Path(__file__).parent
pattern = re.compile(r"tax[_ ]rate|tax[_ ]basis|insurance[_ ]rate|insurance[_ ]basis|receivable-claim-regulatory|نرخ مالیات|نرخ بیمه", re.I)


def describe(name, raw):
    text = raw.decode("utf-8-sig", errors="replace")
    matches = [(i, line.strip()) for i, line in enumerate(text.splitlines(),1) if pattern.search(line)]
    if not matches:
        return None
    return {"source":name,"sha256":hashlib.sha256(raw).hexdigest(),"matching_lines":len(matches),
            "sample":[{"line":i,"text":line[:500]} for i,line in matches[:5]],
            "classification":"Contract/schema/requirement or retained execution context, not automatically an approved effective statutory value"}


local = []
for directory in [ROOT/"docs/architecture", ROOT/"docs/governance/cep/supporting", ROOT/"docs/governance/cep/PROMPTS", ROOT/"docs/governance/uiux"]:
    for path in directory.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in (".md", ".csv", ".yaml"):
            continue
        found=describe(str(path.relative_to(ROOT)),path.read_bytes())
        if found:local.append(found)
for relative in ["apps/organizations/policy_specs.py","apps/organizations/policy_services.py","apps/contracts/models.py","apps/contracts/commercial_services.py","apps/billing/services.py","docs/governance/cep/evidence/CEP-078_REENTRY_05/SOURCE_AND_ACTOR_REVIEW.json"]:
    path=ROOT/relative
    if path.exists():
        found=describe(relative,path.read_bytes())
        if found:local.append(found)

archive_root=Path(r"E:\ERP_Construction_Documents\New Version\BONIRA_TRUE_LATEST_STATE_RECONSTRUCTION_20261013\Consolidated_Packages")
archives=[]
for archive in sorted(archive_root.glob("*.zip")):
    candidates=[]
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if Path(name).suffix.lower() not in (".md", ".csv", ".yaml", ".yml", ".json", ".txt"):
                continue
            found=describe(name,z.read(name))
            if found:candidates.append(found)
    archives.append({"archive":str(archive),"sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),"candidates":candidates})

with transaction.atomic():
    with connection.cursor() as cursor:cursor.execute("SET TRANSACTION READ ONLY")
    org=Organization.objects.get(slug="demo-construction-01")
    versions=PlatformPolicyVersion.objects.filter(policy__code=RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE)
    db={"policy_code":RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE,"all_status_version_count":versions.count(),
        "versions":list(versions.values("id","version","status","effective_from","effective_to","source_basis")),
        "target_tenant_contract_term_versions":ContractTermVersion.objects.filter(organization=org).count(),
        "all_tenant_contract_term_version_count":ContractTermVersion.objects.count(),
        "target_tenant_billing_config_count":TenantBillingConfiguration.objects.filter(organization=org).count(),
        "target_tenant_claim_count":ProgressClaim.objects.filter(organization=org).count()}

requirements=[
 {"field":"tax_rate","missing":"Approved effective Decimal rate value","authority":"Applicable external statutory/tax authority; accepted professional review; published/effective Platform policy"},
 {"field":"tax_basis","missing":"Approved applicable gross or after_contractual selection","authority":"Same external authority and accepted review; an allowed enum is not an approved selection"},
 {"field":"insurance_rate","missing":"Approved effective Decimal statutory-insurance rate value","authority":"Applicable external insurance authority; accepted professional review; published/effective Platform policy"},
 {"field":"insurance_basis","missing":"Approved applicable gross or after_contractual selection","authority":"Same external authority and accepted review; no engineering default"},
 {"field":"effective_source_provenance","missing":"Citable source identity/version and effective applicability tied to the four parameters","authority":"External authority; PlatformPolicyVersionSource and effective version lifecycle"},
 {"field":"accepted_professional_review","missing":"Real accepted review evidence on the same effective regulatory version","authority":"Authorized qualified reviewer; not a fictional test approval or Codex Human Sign-off"},
 {"field":"ContractTermVersion","missing":"Applicable independently approved effective contract terms for the isolated receivable contract","authority":"Authorized contract/commercial owner; preserve explicit payment, retention, advance-recovery and contractual-insurance terms"},
 {"field":"TenantBillingConfiguration","missing":"Applicable authorized tenant numbering/period/precision configuration","authority":"Existing governed Tenant configuration authority; no invented commercial/statutory ownership"},
]
result={"at":datetime.now(timezone.utc).isoformat(),"search_order":["Repository-local authoritative sources and configured versions","Approved consolidated recovery materials"],
        "local_candidates":local,"approved_recovery_archives":archives,"database_evidence":db,
        "authoritative_semantics":"policy_specs approves schema/ranges only, explicitly not statutory values. policy_services resolver requires effective published/eligible retired external-authority version, source links and ACCEPTED review. Contract terms are independently approved; Tenant config has no statutory authority.",
        "result":"BLOCKED_NO_QUALIFIED_EFFECTIVE_INPUTS_RECOVERED",
        "affected_cases":["UAT-CASE-009","UAT-CASE-023"],
        "conditional_intersection":"UAT-CASE-016 AR branch needs a registered receivable producer source; if Billing-backed it inherits these exact source inputs, not a new implementation dependency.",
        "missing_obligations":requirements,
        "excluded_as_authority":["Illustrative/test rates and fixture professional-review stubs","Allowed schema enums and ranges","Financial defaults, zero substitutions or technical catalog existence","Historical documents without exact effective applicability and accepted source/review evidence"],
        "no_values_created":True,"no_contract_configuration_claim_or_statutory_activation_created":True,
        "minimum_next_action":"Provide the governing external source/effective values and real accepted professional review, approved contract terms and tenant configuration. Publish/import only through existing governed lifecycles, then create minimal isolated claim/AR/settlement starting states. Do not broaden scope or infer Production authority."}
(OUT/"BILLING_SOURCE_RECOVERY.json").write_text(json.dumps(result,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
print(json.dumps({"local_candidates":len(local),"archives_scanned":len(archives),"archive_candidates":sum(len(x["candidates"]) for x in archives),"database":db,"result":result["result"]},default=str))

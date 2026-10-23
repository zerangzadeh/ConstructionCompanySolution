"""Author the bounded static sweep evidence; never import or mutate product state."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[4]
UIUX = ROOT / "docs/governance/uiux"
OUT = Path(__file__).parent
CANDIDATES = []

def add(module, surface, membership, filtering, classification, contract, forms, views, templates=(), severity=None, exposure=None, bound=None, cascade="No candidate cascade endpoint found in routed views/templates."):
    CANDIDATES.append(dict(candidate_id=f"SP-{len(CANDIDATES)+1:03}", module=module, surface=surface,
        membership_supplied=membership, scope_filtering=filtering, classification=classification,
        authorization_contract=contract, form_sources=forms, view_sources=views, templates=templates,
        severity=severity, exposed_metadata=exposure, bound_post_invalid=bound or "Same constructor handles GET and bound POST; ordinary invalid redisplay retains its queryset policy.", cascade=cascade))

A="AFFECTED_CONFIRMED"; N="NOT_APPLICABLE"; S="SAFE"; R="NEEDS_RUNTIME_CONFIRMATION"
def f(mod,*symbols): return [(f"apps/{mod}/forms.py",s) for s in symbols]
def v(mod,*symbols): return [(f"apps/{mod}/views.py",s) for s in symbols]

add("Procurement","Purchase Request create", "No", "Tenant + non-deleted only", A,
    "purchase_requests.create permits any effective grant at entry; Projects require effective project authority. No subsequent GET object check narrows choices.",
    f("procurement","PurchaseRequestForm"),v("procurement","purchase_request_create"),["templates/procurement/form.html"],"MEDIUM","Ungranted Project codes/names and option UUIDs.")
add("Procurement","Goods Receipt issued-order selector","No","Tenant + issued + non-deleted parent only",A,
    "goods_receipts.create admits limited grants. Purchase Orders have project authority; status=issued is not an authorization predicate.",
    f("procurement","GoodsReceiptForm"),v("procurement","goods_receipt_create"),["templates/procurement/form.html"],"HIGH","Issued Purchase Order numbers and UUIDs from ungranted projects.")
add("Equipment","Maintenance Record Project/Site","No","Tenant/lifecycle only",A,
    "maintenance_records.create supports object scope; capability entry accepts any grant. Tenant Equipment/provider masters are separate from protected Project/Site choices.",
    f("equipment","MaintenanceRecordForm"),v("equipment","maintenance_create"),["templates/equipment/form.html"],"MEDIUM","Project code/name, Site code/name, parent-project label, and UUIDs.")
add("Equipment","Meter/reading, usage, fuel, downtime, maintenance-plan and work-order selectors","No; validated at entry","Tenant only; organization grant required before construction",N,
    "equipment_meters/equipment_usage/equipment_fuel/equipment_downtime/equipment_maintenance_plans/equipment_work_orders are not object-scoped namespaces. Decorators therefore require an organization grant. Equipment/meters/plans are tenant fleet records; a deployment does not transfer master ownership to one project.",
    f("equipment","MeterReadingForm","UsageForm","FuelForm","DowntimeForm","MaintenancePlanForm","WorkOrderForm"),v("equipment","meter_reading_create","usage_create","fuel_create","downtime_create","maintenance_plan_create","work_order_create","_operation_form"),["templates/equipment/form.html"])
add("Equipment","Work-order spare StockTransaction selector","No; validated at entry","Organization-only gate + authorized parent record",N,
    "equipment_spare_links.manage is organization-gated. A limited project/site grant cannot reach the tenant transaction choices even though the form constructor itself uses only organization/status filters.",
    f("equipment","SpareLinkForm"),v("equipment","spare_link_create"),["templates/equipment/form.html"])
add("Equipment","Operator qualification selectors","No; validated at entry","Tenant Employee/qualification/Equipment masters; organization-only gate",N,
    "equipment_qualifications.manage requires organization scope at the HTTP gate. Tenant workforce/fleet masters are not exclusively project-owned objects.",
    f("equipment","OperatorQualificationForm"),v("equipment","operator_qualification_create"),["templates/equipment/form.html"])
add("Contracts","Contract create Project","No","Tenant + non-deleted only",A,
    "contracts.create permits limited grants; the Project field is neither parent-bound nor scope-intersected. BusinessParty is a tenant master and is not the claimed leak.",
    f("contracts","ContractForm"),v("contracts","contract_create"),["templates/contracts/create.html"],"MEDIUM","Project code/name and UUID.")
add("Contracts","Contractual-record Contract selector","No; validated at entry","Tenant/active/party only, behind organization gate",N,
    "contractual_records.prepare is outside OBJECT_SCOPED_PERMISSION_NAMESPACES. The HTTP decorator requires organization scope, regardless of the downstream scoped service semantics; no limited-grant actor reaches this selector.",
    f("contracts","ContractualRecordForm"),v("contracts","contractual_record_create"))
add("Inventory","Legacy Warehouse create Project","No","Tenant + non-deleted only",A,
    "warehouses.create admits limited grants. Existing warehouse readers use scope_queryset(project_id). A central-warehouse empty choice does not grant visibility to other Projects.",
    f("inventory","WarehouseForm"),v("inventory","warehouse_create"),["templates/inventory/warehouse_form.html"],"MEDIUM","Ungranted Project code/name and UUID.")
add("Inventory","Legacy Stock Transaction selectors","No","Tenant/lifecycle/status only",A,
    "stock_transactions.create accepts limited grants. Project-associated warehouses, receipt items and Projects need their existing object-scope intersection; Material is a tenant master, excluded from the finding.",
    f("inventory","StockTransactionForm"),v("inventory","transaction_create"),["templates/inventory/transaction_form.html"],"HIGH","Ungranted Project/warehouse labels and IDs, and posted GoodsReceiptItem option IDs/labels.")
add("Expenses","Allocation Project/WBS/Activity","No","Tenant + lifecycle only; parent expense lookup does not narrow form",A,
    "expenses.view/allocate support limited grants. An authorized draft/returned expense plus expenses.allocate renders the allocation form. The context processor admits that capability with any applicable grant; it does not narrow child querysets.",
    f("expenses","ExpenseAllocationForm"),v("expenses","expense_detail","expense_allocate"),["templates/expenses/detail.html"],"HIGH","Other-project Project/WBS/Activity option labels and UUIDs.",bound="Allocation POST returns empty 400 for an invalid form (no invalid form redisplay). Initial eligible expense detail renders all allocation choices.")
add("Expenses","Allocation CBS / CostCenter classifications","No; not needed for project ownership","Tenant + locked structure / leaf predicates",N,
    "CBSNode and CostCenter are organization-owned versioned classifications; neither model has a project/site owner. Project grants do not define their visibility. The Project/WBS/Activity finding must not be extended automatically to these masters.",
    f("expenses","ExpenseAllocationForm")+[("apps/projects/models.py","CBSNode"),("apps/projects/models.py","CostCenter")],v("expenses","expense_detail","expense_allocate"),["templates/expenses/detail.html"])
add("Expenses","Recurring template Project and same-page template list","No","Project choices and template collection are tenant-wide",A,
    "expenses.recurrences_manage is in the expenses scoped namespace. recurrence_list builds the tenant-wide form and template collection without scope intersection. Both are rendered on this same bounded candidate surface.",
    f("expenses","RecurringExpenseTemplateForm"),v("expenses","recurrence_list"),["templates/expenses/recurrences.html"],"HIGH","Project labels/UUIDs in choices; existing out-of-scope template description, project name and occurrence-form identifier in the same page. No template amounts are rendered by this template.")
add("Fixed Assets","Asset create Project/Site/CostCenter","No; validated at entry","Tenant choices behind fixed_assets organization gate",N,
    "fixed_assets.candidate_prepare is organization-scoped at entry. The constructor is broad but cannot serve these options to an actor with only limited project/site grants; CostCenter is a tenant classification.",
    f("fixed_assets","AssetForm"),v("fixed_assets","asset_create"))
add("Fixed Assets","Asset transaction target Project/Site/CostCenter","No; validated at entry","Tenant choices behind fixed_assets organization gate",N,
    "transaction_create requires fixed_assets.view, which requires an organization grant. This prevents limited-grant reachability before constructing AssetTransactionForm, independently of later transaction-service checks.",
    f("fixed_assets","AssetTransactionForm"),v("fixed_assets","transaction_create"))
add("Fixed Assets","Requested WBS/CBS selector dimensions","Not applicable","No WBS/CBS choice fields in either candidate form",N,
    "AssetForm and AssetTransactionForm define project/site/cost-center dimensions, not WBS/CBS selectors. No missing selector or new fixed-asset behavior is inferred.",
    f("fixed_assets","AssetForm","AssetTransactionForm"),v("fixed_assets","asset_create","transaction_create"))
add("Accounting","Journal and opening Project/Site/WBS choices","No; validated at entry","Tenant-only JournalLineForm behind organization-only accounting gates",N,
    "accounting.view and accounting.journals_prepare require an organization grant. Journal/opening detail additionally conditionally render line forms only for applicable draft states and prepare capability. An organization Accountant can legitimately see all tenant dimensions.",
    f("accounting","JournalLineForm","OpeningImportForm"),v("accounting","journal_detail","journal_line_add","opening_detail","opening_line_add"),["apps/accounting/templates/accounting/journal_detail.html","apps/accounting/templates/accounting/opening_detail.html"],bound="Journal invalid POST can re-render the same form, while opening POST redirects. Both require organization scope before construction.")
add("Accounting","Scoped-reader comparison against journal/opening forms","Gate resolves active membership","No organization grant -> denied before any form construction",S,
    "Even when a limited-grant role contains accounting.view, permission_supports_object_scope(accounting.view) is false; membership_has_scope with no object and allow_any_scope=False requires an explicit organization grant. This is a static denied-entry proof, not a new browser scenario.",
    f("accounting","JournalLineForm"),v("accounting","journal_detail","opening_detail"))
add("Billing","Shared commercial create Contract / DocumentVersion choices (three create forms)","No","_CommercialEvidenceForm._configure uses organization/lifecycle only",A,
    "Guarantee, compliance-evidence and retention-release create namespaces admit limited grants directly. _configure does not use that membership for Contracts or DocumentVersions. Revision/detail paths are separately organization-gated by their reader services and are not included in this confirmation.",
    f("billing","_CommercialEvidenceForm","GuaranteeForm","ComplianceEvidenceForm","RetentionReleaseForm"),v("billing","guarantee_create","compliance_evidence_create","retention_release_create"),["apps/billing/templates/billing/commercial_form.html"],"HIGH","Other-project Contract numbers/titles/UUIDs and Document titles/version numbers/UUIDs, including versions not authorized through their linked context.",bound="Create forms render the same choices after invalid submission; this confirmation excludes revision/detail entry paths.")
add("Billing","Retention release create approved clearance source","No","Tenant + clearance kind + approved only",A,
    "retention_releases.create accepts project-limited grants. The constructor's additional clearance_evidence queryset bypasses both project scope and the canonical get_compliance_evidence selector, independently of the shared Contract/DocumentVersion helper.",
    f("billing","RetentionReleaseForm"),v("billing","retention_release_create"),["apps/billing/templates/billing/commercial_form.html"],"HIGH","Approved out-of-scope clearance evidence option UUIDs and labels.")
add("Billing","Retention release correction approved clearance source","Reader resolves trusted membership","Tenant-only choices behind organization-only parent-reader gate",N,
    "The detail/correction views first call _commercial_record -> get_retention_releases -> _require(project=None), which does not set allow_any_scope. It therefore requires an organization grant and denies limited-only actors before the form is constructed. Its broad clearance queryset is not a reachable limited-scope leak through this caller.",
    f("billing","RetentionReleaseCorrectionForm"),v("billing","retention_release_detail","retention_release_correct"),["apps/billing/templates/billing/commercial_record_detail.html"],"HIGH","Approved out-of-scope clearance evidence UUIDs/labels on eligible release detail.",bound="POST and initial detail both resolve the organization-authorized parent before constructing correction choices.")
add("Billing","Payable measurement ContractItem selector","No","Tenant + payable/subcontract/active predicates only",A,
    "payable_measurements.record supports limited grants. ContractItem project authority is not intersected in the create form; lifecycle and payable direction do not grant scope.",
    f("billing","PayableMeasurementForm"),v("billing","payable_measurement_create"),["apps/billing/templates/billing/payable_form.html"],"HIGH","Other-project payable ContractItem option identifiers and model labels. No item rate/amount disclosure is asserted.")
add("Billing","Payable certificate Contract selector","No","Tenant + payable/subcontract/active predicates only",A,
    "payable_certificates.create supports limited grants. get_payable_certificates uses project scope for reads; the Contract form choice remains tenant-wide instead.",
    f("billing","PayableCertificateForm"),v("billing","payable_certificate_create"),["apps/billing/templates/billing/payable_form.html"],"HIGH","Other-project active subcontract number/title/UUID.")
add("Billing","Taxpayer invoice approved Claim / prior invoice selectors","No; validated at entry","Tenant/status only behind organization-only statutory gate",N,
    "taxpayer_invoices.prepare is not an object-scoped namespace. The HTTP boundary requires organization authority, so its approved claims/prior invoices are not exposed to a limited-grant-only actor by this route.",
    f("billing","TaxpayerInvoiceForm"),v("billing","taxpayer_invoice_create"),["apps/billing/templates/billing/commercial_form.html"])
add("Billing","Contractor assessment approved Certificate / clearance selectors","No; validated at entry","Tenant/status only behind organization-only statutory gate",N,
    "contractor_compliance.prepare is organization-gated at entry. Its approved Certificate/clearance sources are not reachable by a limited-grant-only actor.",
    f("billing","ContractorComplianceAssessmentForm"),v("billing","contractor_compliance_create"),["apps/billing/templates/billing/commercial_form.html"])
add("Billing","Claim settlement posted Treasury source choices","Validated parent + capability gate","Tenant + authorized parent project/party + posted receipt predicates",S,
    "_claim resolves through get_progress_claims, whose _require_progress_permission requires organization scope. The detail also requires organization-scope claim_settlements.allocate before constructing/rendering the form; choices are restricted to that claim's project/party. No permission or authority is inferred from Site-parent visibility.",
    f("billing","ClaimSettlementAllocationForm"),v("billing","_claim","claim_detail","claim_settlement_allocate"),["apps/billing/templates/billing/claim_detail.html"])
add("Documents","General Project/Contract/Estimate/Expense/Treasury/Daily Report targets","Trusted request.user; membership resolved by has_business_permission","Per-target organization-scope permission or .none()",S,
    "Although the candidate initially builds tenant-wide querysets, each field is cleared unless has_business_permission for that target succeeds with no project and no allow_any_scope. Limited-only grants therefore produce .none(); an organization grant legitimately spans all tenant projects. Existing document exclusion only removes already-linked objects and never adds authority.",
    f("documents","DocumentTargetForm","DocumentCreateForm","DocumentLinkForm"),v("documents","document_upload","_detail_context","document_link_add"),["templates/documents/upload.html","templates/documents/detail.html"],bound="Upload and link constructors preserve the same per-target fail-closed policy for bound input; invalid upload redisplays and invalid link returns to governed detail.")
add("Documents","Field Observation target choices","Trusted user -> get_active_membership","scope_queryset(project_id, site_id), draft status; earlier gate may already empty choices",S,
    "The dedicated FieldObservation branch validates active membership, capture capability and effective project/site grants. The earlier organization-style view check can leave a limited actor's queryset empty; that is fail-closed and is not evidence that all authorized observations are usable. No functionality change is authorized here.",
    f("documents","DocumentTargetForm"),v("documents","document_upload","_detail_context","document_link_add"),["templates/documents/upload.html","templates/documents/detail.html"])
add("Workforce","Employee form and Department->Position cascade","No; trusted organization + account-link capability","Tenant master relationships; organization-only employees.create",N,
    "Employee/User/Department/Position/WorkTeam are tenant identity/routing masters, not exclusively project-owned. EmployeeForm's account branch is explicitly capability-gated; the cascade filters positions by trusted organization before optional department ID. Project grants do not turn organizational positions into project objects.",
    f("workforce","EmployeeForm"),v("workforce","employee_create","employee_positions"),["templates/workforce/employee_form.html"],cascade="GET employee_positions uses tenant-filtered Position objects and optional department_id; employees.create requires organization scope before execution.")
add("Workforce","Training Requirement Project selector","No","Tenant + non-deleted only",A,
    "workforce_qualifications.manage supports any effective grant at the view. The Project selector is tenant-wide. The training service's later project check cannot protect metadata already rendered by _foundation_form.",
    f("workforce","TrainingRequirementForm"),v("workforce","workforce_training_requirement_create","_foundation_form"),["templates/workforce/foundation_form.html"],"MEDIUM","Other-project Project codes/names and UUIDs. Tenant competency/position masters are not included in the claim.")
add("Workforce","Employee Training Record requirement choices","No","Active tenant TrainingRequirement catalogue only",R,
    "TrainingRequirement can be global or project-associated; record_employee_training passes requirement.project to its authority check. Need a concrete project-associated requirement and an approved visibility comparison to distinguish catalogue-wide applicability from project-owned visibility; the present data cannot demonstrate the distinction. Employee master choices alone are not a project-scope finding.",
    f("workforce","EmployeeTrainingRecordForm"),v("workforce","workforce_training_record_create","_foundation_form"),["templates/workforce/foundation_form.html"],cascade="Read-only preflight: retained P-17 has workforce_qualifications.manage with A/B grants and no organization grant; there are zero active TrainingRequirements. No fixture was created; no rendering/HTTP test executed.")
add("Payroll","Employment configuration Project/Site","No; validated at entry","Tenant predicates behind payroll_configuration organization gate",N,
    "payroll_configuration.manage is organization-only at entry. Employee is a tenant master; current limited-only actors are denied before dimension choices are constructed.",
    f("payroll","EmploymentConfigurationForm"),v("payroll","employment_configuration_create"))
add("Payroll","Rule Project/Site","No; validated at entry","Tenant predicates behind payroll_configuration organization gate",N,
    "RuleForm shares the organization-only configuration boundary. Optional project/site applicability does not expose other projects to actors that cannot enter the form.",
    f("payroll","RuleForm"),v("payroll","rule_create"))
add("Payroll","Input Project/Site/Employee dimensions","No; validated at entry; tenant-validated run","Tenant Project/Site; run-membership Employee filter; organization-only payroll.prepare",N,
    "payroll.prepare is organization-gated. The run is fetched using organization plus PK and input employees are restricted to that run's employees. Do not infer payroll_results/ESS reader authority from Payroll preparation authority.",
    f("payroll","InputForm"),v("payroll","input_create"))
add("Quality","Quality issue Project/Site/Phase/Activity/DailyReport selectors","No","Tenant/lifecycle only",A,
    "quality_issues.create admits limited project/site grants. The canonical issue readers use scope_queryset; create choices do not intersect that scope. Generic form rendering includes every field.",
    f("quality","QualityIssueForm"),v("quality","issue_create"),["templates/quality/create.html"],"MEDIUM","Out-of-scope Project/Site/Phase/Activity/DailyReport option identifiers and labels; no issue description/content read is asserted.")
add("Safety","Safety incident Project/Site/Phase/Activity/DailyReport selectors","No","Tenant/lifecycle only",A,
    "safety_incidents.create admits limited project/site grants. The canonical incident readers use scope_queryset, but initial and bound create choices do not.",
    f("safety","SafetyIncidentForm"),v("safety","incident_create"),["templates/safety/create.html"],"MEDIUM","Out-of-scope Project/Site/Phase/Activity/DailyReport option identifiers and labels; no incident contents are asserted.")
for form,kind in [("InspectionForm","inspection"),("PermitForm","permit"),("QualityTestForm","test"),("FindingForm","finding"),("CapaForm","capa")]:
    add("Compliance",f"{form} ({kind}) / ScopedModelForm path","No; validated at entry","Tenant-only base and related querysets, behind organization-only compliance.view",N,
        "compliance.view (distinct from compliance_evidence.view) is NOT in the object-scoped namespace registry. create_record therefore requires an organization grant before selecting FORM_MAP or constructing this form. The class name ScopedModelForm does not prove filtering, but the real HTTP authority prevents limited-only actors receiving its choices. Project/Site fields occur on inspection/permit/test; finding/CAPA enumerate tenant source records.",
        f("compliance","ScopedModelForm",form),v("compliance","create_record"),["templates/compliance/form.html"])

add("Billing","Shared commercial revision Contract/DocumentVersion choices (three revision forms)","Parent-reader resolves trusted membership","Organization-only _require(project=None) before revision form construction",N,
    "guarantee_detail, compliance_evidence_detail and retention_release_detail resolve _commercial_record through get_guarantees/get_compliance_evidence/get_retention_releases. Their _require passes project=None with allow_any_scope left False, so limited-only actors are denied even though the outer capability decorators support object scope. A scope_queryset later in the reader does not remove that earlier organization-only requirement. Revision POST handlers use the same parent-reader boundary.",
    f("billing","GuaranteeRevisionForm","ComplianceEvidenceRevisionForm","RetentionReleaseCorrectionForm"),v("billing","_commercial_record","guarantee_detail","guarantee_revise","compliance_evidence_detail","compliance_evidence_revise","retention_release_detail","retention_release_correct"),["apps/billing/templates/billing/commercial_record_detail.html"])

assert len(CANDIDATES)==42
assert Counter(c['classification'] for c in CANDIDATES)=={A:15,N:22,S:4,R:1}

def anchor(path, symbol):
    p=ROOT/path; s=p.read_text(encoding="utf-8"); tree=ast.parse(s)
    parts=symbol.split("."); nodes=tree.body; found=None
    for part in parts:
        found=next(n for n in nodes if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==part)
        nodes=found.body
    start=min([found.lineno]+[d.lineno for d in getattr(found,"decorator_list",[])])
    return dict(path=path,symbol=symbol,line=start,end_line=found.end_lineno,source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),excerpt="\n".join(s.splitlines()[start-1:found.end_lineno]))

common=[("apps/organizations/decorators.py","require_organization_permission"),("apps/organizations/authorization.py","permission_supports_object_scope"),("apps/organizations/authorization.py","membership_has_scope"),("apps/organizations/authorization.py","has_business_permission"),("apps/organizations/authorization.py","scope_queryset"),("apps/organizations/authorization.py","effective_scope_grants"),("apps/organizations/context_processors.py","business_permissions"),("apps/organizations/form_scoping.py","scoped_projects_for_form"),("apps/organizations/form_scoping.py","scope_project_related_choices"),("apps/organizations/form_scoping.py","selected_form_project"),("apps/inventory/services.py","get_organization_warehouses"),("apps/inventory/services.py","get_organization_stock_transactions"),("apps/billing/commercial_services.py","_require"),("apps/billing/commercial_services.py","get_guarantees"),("apps/billing/commercial_services.py","get_retention_releases"),("apps/billing/commercial_services.py","get_compliance_evidence"),("apps/billing/payable_services.py","get_payable_certificates"),("apps/billing/services.py","_require_progress_permission"),("apps/billing/services.py","get_progress_claims"),("apps/workforce/services.py","_require_workforce_permission"),("apps/workforce/services.py","record_employee_training")]
anchors={}
for path,symbol in common+[(p,s) for c in CANDIDATES for p,s in c['form_sources']+c['view_sources']]:
    key=path+':'+symbol
    if key not in anchors: anchors[key]=anchor(path,symbol)
templates={p:{'sha256':hashlib.sha256((ROOT/p).read_bytes()).hexdigest(),'text':(ROOT/p).read_text(encoding='utf-8')} for c in CANDIDATES for p in c['templates']}
for c in CANDIDATES:
    c['anchors']=[p+':'+s for p,s in c['form_sources']+c['view_sources']]
    c['source_contract_basis']='Current code + explicit effective-scope gate behavior; no new Product Decision or visibility rule.'

register_path=UIUX/'UIUX_FINDINGS_REGISTER.yaml'
original=register_path.read_text(encoding='utf-8')
register=yaml.safe_load(original)
nextid=max(int(f['finding_id'].split('-')[-1]) for f in register['findings'])+1
assert nextid==113
findings=[]
for c in CANDIDATES:
    if c['classification']!=A:continue
    fid=f'UIUX-F-{nextid:03}';nextid+=1;c['finding_id']=fid
    findings.append(dict(finding_id=fid,module=c['module'],surface_id=c['candidate_id'],page_title=c['surface'],roles=['Authenticated nonprivileged membership with required capability and limited project/site grants'],category='SECURITY_SCOPE',severity=c['severity'],status='STATIC_CONFIRMED',runtime_status='NOT_EXECUTED',runtime_classification='NOT_TESTED',problem=c['exposed_metadata'],technical_root_cause=c['scope_filtering']+'; '+c['authorization_contract'],evidence={'source_paths':list(dict.fromkeys(p for p,s in c['form_sources']+c['view_sources']))+list(c['templates']),'sweep_report':'UIUX_F111_SAME_PATTERN_SECURITY_SWEEP.md','trace':'f111_same_pattern_evidence/SOURCE_TRACE.json','candidate_id':c['candidate_id'],'scope_note':'Static reachability/queryset/render proof. No browser/HTTP exploit or business mutation executed. Cross-tenant exposure not tested.'},user_impact='Unauthorized same-tenant metadata disclosure on the stated reachable rendering path. No successful mutation or full document content access claimed.',root_pattern_candidate=[],root_pattern_review='F-111 same-pattern static confirmation; original F-111 remains RUNTIME_VERIFIED_RESOLVED.',recommendation='Separate bounded remediation authorization required; preserve domain-specific object authority and tenant master visibility.',business_logic_impact='NO_CHANGE_AUTHORIZED',needs_domain_review=False,related_cep=[],related_standard=[]))
assert nextid==128
(OUT/'SOURCE_TRACE.json').write_text(json.dumps({'candidates':CANDIDATES,'source_anchors':anchors,'templates':templates},ensure_ascii=False,indent=2),encoding='utf-8')

# Append new finding documents at the end of the existing findings sequence,
# preserving every existing finding object and the following historical blocks.
needle='runtime_wave_a:'
assert '\n'+needle in original
prefix,suffix=original.split('\n'+needle,1)
newyaml=yaml.safe_dump(findings,allow_unicode=True,sort_keys=False,width=110)
updated=prefix+'\n'+newyaml+'\n'+needle+suffix
stats=register['register_status'];counts=Counter(f['severity'] for f in findings)
updated=updated.replace(f"  finding_count: {stats['finding_count']}\n",f"  finding_count: {stats['finding_count']+len(findings)}\n",1)
updated=updated.replace(f"  static_finding_count: {stats['static_finding_count']}\n",f"  static_finding_count: {stats['static_finding_count']+len(findings)}\n",1)
for severity,count in counts.items():
    updated=updated.replace(f"    {severity}: {stats['severity_counts'][severity]}\n",f"    {severity}: {stats['severity_counts'][severity]+count}\n",1)
updated=updated.replace('root_pattern_candidates:\n','  new_same_pattern_security_findings: 15\n  same_pattern_security_sweep_report: UIUX_F111_SAME_PATTERN_SECURITY_SWEEP.md\nroot_pattern_candidates:\n',1)
newregister=yaml.safe_load(updated)
assert newregister['findings'][:112]==register['findings']
assert newregister['runtime_wave_a']==register['runtime_wave_a']
register_path.write_text(updated,encoding='utf-8')

metrics=Counter(c['classification'] for c in CANDIDATES)
def sources(c):
    refs=[anchors[k] for k in c['anchors']]
    # Show form and actual view in the table; all inherited/dynamic seams live in JSON.
    form=refs[0];view=next((r for r in refs if r['path'].endswith('views.py')),refs[-1])
    return f"`{form['path']}:{form['line']}`; `{view['path']}:{view['line']}`"
table='\n'.join('| '+ ' | '.join([c['module'],c['candidate_id']+' — '+c['surface'],c['membership_supplied'],c['scope_filtering'],c['classification'],sources(c)+(('; '+c['finding_id']) if 'finding_id' in c else '')])+' |' for c in CANDIDATES)
details=[]
for c in CANDIDATES:
    if c['classification']!=A:continue
    refs=sources(c)
    details.append(f"### {c['finding_id']} — {c['surface']}\n\n- Severity: **{c['severity']}**; confirmation: **static**, not runtime.\n- Affected surface: {c['module']} / {c['candidate_id']}.\n- Exposed metadata: {c['exposed_metadata']}\n- Boundary: same tenant outside effective object grants; cross-tenant **NOT_TESTED**.\n- Technical root cause: {c['scope_filtering']}. {c['authorization_contract']}\n- Evidence: {refs}; rendering templates and exact current source excerpts are indexed under {c['candidate_id']} in [SOURCE_TRACE.json](f111_same_pattern_evidence/SOURCE_TRACE.json).\n")
traces=[]
for c in CANDIDATES:
    traces.append(f"### {c['candidate_id']} — {c['surface']}\n\nAuthorization contract: {c['authorization_contract']}\n\nInitial HTML / metadata: {'Protected choices are rendered on the eligible template path described above.' if c['classification']==A else ('No claimed disclosure; scope/entry behavior follows the stated contract.' if c['classification']!=R else 'Not runtime-confirmed: no suitable active requirement data.')}\n\nBound POST / invalid redisplay: {c['bound_post_invalid']}\n\nAJAX / cascade: {c['cascade']}\n")
safe='\n'.join('- **'+c['candidate_id']+' — '+c['surface']+':** '+c['authorization_contract'] for c in CANDIDATES if c['classification']==S)
na='\n'.join('- **'+c['candidate_id']+' — '+c['surface']+':** '+c['authorization_contract'] for c in CANDIDATES if c['classification']==N)
report=f'''# BONIRA F-111 Same-Pattern Security Sweep

## Baseline

- Branch: `main`.
- HEAD and `origin/main`: `43ac319c6e73e48ca9626461b73987922c498ec3`, identical to the frozen audit commit.
- Authorized F-111 remediation remains uncommitted in its eight existing form/view files (180 insertions / 50 deletions). The sweep did not modify them or any other product file.
- UIUX-F-111 remains **RUNTIME_VERIFIED_RESOLVED**. Existing original finding/evidence and retest evidence are preserved.
- Development browser/HTTP runtime: **NOT USED**. The sole database operation was a read-only training preflight in `config.settings.development` against the configured Development database, with `default_transaction_read_only=on`. No migrations, authentication/session operation, fixture preparation or business write occurred.
- Date: 2026-10-22, Asia/Tehran.

Entry hashes: [ENTRY_HASHES.json](f111_same_pattern_evidence/ENTRY_HASHES.json). Current source, not the pre-remediation stale process on port 8001, is the implementation authority for this static sweep.

## Scope

Reviewed exactly these retained candidate families, split into the explicit decision units below:

1. Procurement: Purchase Request create; Goods Receipt order selector.
2. Equipment: Maintenance Record; meter/reading, usage, fuel, downtime, plan/work-order, spare-link and operator qualification selectors.
3. Contracts: Contract create; contractual-record Contract choices.
4. Inventory: legacy Warehouse and Stock Transaction choices.
5. Expenses / Fixed Assets: expense allocation dimensions, recurring templates; Asset/AssetTransaction project/site/cost-center dimensions and requested WBS/CBS presence check.
6. Accounting: journal/opening dimensions and scoped-reader entry comparison.
7. Billing: shared commercial Contract/DocumentVersion choices, retention approved-clearance sources, payable ContractItem/Contract choices, approved Claim/Certificate sources and claim-settlement Treasury choices.
8. Documents: ordinary typed targets and the Field Observation target branch.
9. Workforce / Payroll: Employee and its position cascade, Training Requirement, Employee Training Record; payroll employment/rule/input dimensions.
10. Quality / Safety / Compliance: create Project/Site-related choices and all five routed `ScopedModelForm` subclasses.

No other module was added. Original resolved F-111 forms and the prior Expense/Estimate/Field Observation proofs were used as references only, not re-run. Equipment financial policy/handoff workflows, broader workforce/ESS, other financial consumers, workflow acceptance, broad authorization and UI/UX review are outside this sweep.

The retained same-pattern inventory and root-cause discussion are in [the remediation report](UIUX_F111_REMEDIATION_REPORT.md#remaining-same_pattern_review_required-candidates) and its Root Cause Addressed section. No separate root-cause contract was fabricated. The prior retest and Wave A/B histories are unchanged.

## Candidate Results

**42 decision units**; a unit is one selector surface, a field subset with a different visibility contract, an explicitly requested absent dimension, or the requested scoped-reader comparison. Shared constructors with identical gates are grouped explicitly; counts do not claim 42 independent pages or browser tests. Affected means a proven static capability -> constructor -> template path, with an out-of-scope qualifying record, will disclose metadata; it does not claim a newly executed exploit.

| Module | Surface | Membership supplied | Scope filtering | Classification | Evidence |
| --- | --- | --- | --- | --- | --- |
{table}

The form-membership column is distinct from membership validation at the HTTP gate. A permission decorator resolves trusted membership, but for object-scoped namespaces it asks only whether **any** effective scope exists. It does not narrow a field queryset. For namespaces outside that registry, the same gate requires an explicit organization grant; a role name, decorator name, or form class name alone was never used as proof.

Decisive source: `apps/organizations/decorators.py:18`, `apps/organizations/authorization.py:29,94,315,388,440`, `apps/organizations/form_scoping.py:22,41,65`. Effective grant dates/revocation, membership/user/tenant activity, tenant intersection and project/site semantics remain owned by those helpers.

## Confirmed Security Findings

**15 new findings: UIUX-F-113 through UIUX-F-127.** They are reconciled into the canonical register as `STATIC_CONFIRMED`, `runtime_status: NOT_EXECUTED`. Original F-111 was not reopened.

Severity is **MEDIUM** for plain Project/Site/catalogue metadata and **HIGH** for independently protected commercial/financial source references, expense allocation context or broad DMS version metadata. No successful posting, payment, privilege change, personal-file contents, item price, or full document download is claimed. The original F-111 severity is unchanged.

Only SP-019 groups multiple forms under one finding: they share the proven `_CommercialEvidenceForm._configure` seam. The clearance-source constructors are separate decision units because their inline filters are outside that helper; the create path is affected and the correction path is organization-gated. Other independent constructors/remediation seams remain separate findings.

{chr(10).join(details)}
## Runtime Confirmations

**None.** Static trace was conclusive for the 15 confirmed exposures and the safe/non-applicable units, so no broad browser run was justified. No completed Wave A/B or F-111 scenario was repeated.

One read-only preflight for SP-031 found that retained P-17 has `workforce_qualifications.manage` with A/B grants, lacks organization scope, and has **zero active TrainingRequirements available in the tenant**. [TRAINING_PREFLIGHT.json](f111_same_pattern_evidence/TRAINING_PREFLIGHT.json). No form/HTTP metadata assertion is claimed from that query, and no data or authority was prepared to force a result.

## SAFE Patterns

{safe}

Canonical safe reference mechanisms remain `scope_queryset`, `scoped_projects_for_form`, `scope_project_related_choices`, and `selected_form_project`, preserving their domain-specific semantics. Original F-111, Expense/Estimate and Field Observation references were not counted as newly reviewed candidate successes.

## NOT_APPLICABLE Decisions

These are bounded decisions about the current reachable metadata path. They do not certify the entire domain or prescribe that every future actor must have organization scope.

{na}

## NEEDS_RUNTIME_CONFIRMATION

**SP-031 — Employee Training Record requirement choices.** Minimum follow-up: reuse an existing limited-grant actor with `workforce_qualifications.manage` (P-17 already qualifies), and existing active A/B plus C/D project-associated TrainingRequirements. Establish the applicable catalogue visibility contract before treating a requirement's optional project applicability as exclusive visibility ownership; compare the actual rendered option label, identifier and UUID against an authorized and unauthorized parent. Include an existing cross-tenant requirement negative if available. None currently exists in the inspected active Development requirement data, so this sweep creates no fixtures. Tenant Employee/Skill/Position masters must not acquire an invented project-scope rule.

This unresolved unit does not weaken or erase the other static confirmations. No other unit is deferred merely because it lacks a browser test.

## Cross-Tenant Assessment

CROSS_TENANT_METADATA_EXPOSURE: **NOT_TESTED**

No cross-tenant exposure was confirmed. Candidate constructors retain tenant predicates (including parent-tenant predicates where applicable), but this static sweep does not promote that observation to a new cross-tenant runtime PASS. No critical-stop condition was encountered.

## Unauthorized Mutation

UNAUTHORIZED_MUTATION_OBSERVED: **NOT_TESTED**

No business POST or other business mutation was attempted. Mutation-service denial cannot repair an initial metadata leak; conversely, metadata disclosure does not prove an unauthorized business write.

## Scope Boundary

PRODUCT CODE CHANGED: NO  
ROLE CREATED: NO  
PERMISSION CREATED: NO  
SCOPE BROADENED: NO  
BUSINESS DATA CREATED: NO  
PRODUCTION ACTION: NO  
CEP-078 EXECUTION: NO  
CEP-079 EXECUTION: NO  
GIT WRITE: NO

No browser, session, credential, migration or fixture manipulation. Existing generated PDFs are preserved, remain untracked, and were neither deleted nor added to Git. Only this report, new static evidence and the authorized findings-register reconciliation were written. All pre-existing finding objects, F-111 status, earlier runtime evidence and other historical files are checked for preservation.

## Sweep Metrics

| Metric | Count |
| --- | ---: |
| CANDIDATES_REVIEWED | {len(CANDIDATES)} |
| SAFE_COUNT | {metrics[S]} |
| AFFECTED_CONFIRMED_COUNT | {metrics[A]} |
| NEEDS_RUNTIME_CONFIRMATION_COUNT | {metrics[R]} |
| NOT_APPLICABLE_COUNT | {metrics[N]} |

## Detailed Static Trace

The following annotations complete the view -> form -> field -> gate -> membership -> scope -> rendering/invalid-redisplay/cascade chain. Full relevant source excerpts, file hashes, symbols, verified line spans and templates are in [SOURCE_TRACE.json](f111_same_pattern_evidence/SOURCE_TRACE.json). The AST relationship map is navigation evidence, not an automatic security classifier. No graph rebuild was performed; source code controls over graph hints.

{chr(10).join(traces)}
## Final Decision

F111_PATTERN_SWEEP_FINDINGS_CONFIRMED
'''
(UIUX/'UIUX_F111_SAME_PATTERN_SECURITY_SWEEP.md').write_text(report,encoding='utf-8')
(OUT/'METRICS.json').write_text(json.dumps({'counts':dict(metrics),'candidates_reviewed':len(CANDIDATES),'new_findings':[{k:fi[k] for k in ['finding_id','surface_id','severity']} for fi in findings],'final_decision':'F111_PATTERN_SWEEP_FINDINGS_CONFIRMED'},indent=2),encoding='utf-8')
print('42 candidates: 4 SAFE, 15 AFFECTED_CONFIRMED, 1 NEEDS_RUNTIME_CONFIRMATION, 22 NOT_APPLICABLE.')
print('New finding IDs: UIUX-F-113 through UIUX-F-127. No runtime mutation or product edit.')


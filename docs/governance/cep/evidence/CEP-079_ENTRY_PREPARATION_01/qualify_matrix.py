"""Qualify the frozen 44-case STARTING STATES, never execute a UAT case."""
import csv
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from django.apps import apps
from django.db import connection, transaction
from apps.accounts.models import User
from apps.organizations.authorization import (
    effective_role_assignments, effective_scope_grants, membership_permission_codes,
    membership_has_scope,
)
from apps.organizations.models import Organization, OrganizationMembership
from apps.projects.models import Project

OUT = Path(__file__).parent
inputs = json.loads((OUT / "CANONICAL_INPUTS.json").read_text(encoding="utf-8"))
actors = {
    "manager": "account.demo-construction-01.owner",
    "project": "uiux.persona.project-manager",
    "accountant": "account.demo-construction-01.accountant",
    "treasurer": "account.demo-construction-01.accountant",
    "procurement": "cep078.synthetic.operations",
    "buyer": "uiux.wavec.buyer",
    "store": "cep078.synthetic.operations",
    "hr": "uiux.wavec.hr",
    "time": "uiux.wavec.time",
    "payroll": "uiux.wavec.payroll",
    "all": "cep078.synthetic.operations",
    "reporting": "uiux.audit.reporting",
    "project_controls": "cep078.synthetic.accessibility",
}

# Permission strings are existing registered codes, taken from the owning entry
# services. Persona names are business functions, not fabricated role codes.
# No role/permission assignment is made by this qualification.
# num, primary existing authority, minimum entry permissions, input models, exact
# disposable starting state / scope boundaries. Outputs may be created later by
# the UAT; absence of an output is not automatically a missing starting fixture.
specs = [
 (1,"manager","projects.view","projects.Project","Existing test login and authenticated Home; no UAT login performed"),
 (2,"manager","projects.view","projects.Project;projects.ProjectSite","Active tenant, project A and explicit organization scope"),
 (3,"reporting","reporting.metric_result.view;reporting.portfolio.view;budgets.view;project_cost.view","projects.BudgetVersion;accounting.JournalEntry","Existing accepted sources read-only; new projection refresh only during later UAT; no legacy reporting fallback"),
 (4,"manager","purchase_requests.approve","procurement.PurchaseRequest;workflows.WorkItem","New CEP079 submitted PR, owner is an actual candidate, creator is different; claim/action deferred"),
 (5,"reporting","reporting.reconciliation_run.view;reporting.project_closeout_case.view","reporting.ProjectCloseoutCase","Review truthful incomplete closeout evidence; no completeness/financial activation inferred"),
 (6,"manager","documents.view;documents.download","documents.Document;documents.DocumentVersion","Read-only source-linked project documents and retained audit; no confidential employee identity inference"),
 (7,"project","projects.view","projects.Project;projects.ProjectSite","Project A/B allowed, C and foreign tenant project denied; current explicit grants"),
 (8,"project_controls","budgets.view;project_cost.view;reporting.metric_result.view","projects.BudgetVersion;billing.ProgressRecord","Accepted budget/progress are read-only inputs to governed Project Controls metrics; no unmanaged legacy aggregates"),
 (9,"project","contracts.view;claims.view","contracts.Contract;billing.ProjectBaseline;billing.ProgressRecord","Contract/baseline inputs exist; populated claim and approved source configuration unavailable"),
 (10,"project","daily_reports.view;materials.view;purchase_orders.view","daily_reports.DailyReport;materials.Material","Read-only project A daily reports, materials and procurement; Site remains within Project"),
 (11,"project","employees.view;equipment.view;safety_incidents.view;quality_issues.view","workforce.Employee;equipment.Equipment;safety.SafetyIncident;quality.QualityIssue","Read source states, including legacy/unassessed; no invented Safety/Quality approval"),
 (12,"project_controls","project_cost.reconciliations_view","projects.BudgetVersion;projects.ProjectCostFact","IMB0039 required outcome/evidence unverified; incomplete source coverage must remain visible"),
 (13,"accountant","accounting.view","accounting.Account;accounting.FiscalYear;accounting.FiscalPeriod","Existing accounts/fiscal definitions read-only; synthetic period available for mutations"),
 (14,"accountant","accounting.journals_prepare;accounting.journals_submit","accounting.Account;accounting.FiscalPeriod","New journal target during UAT, existing posting policies; distinct owner checker; no source-owned journal bypass"),
 (15,"accountant","accounting.adjustments_prepare","accounting.JournalEntry","New CEP079 posted manual journal is the only allowed reversal/replacement target; accepted old journals untouched"),
 (16,"accountant","subledgers.obligations_recognize;subledgers.aging_run","subledgers.Obligation;subledgers.SupplierInvoiceMatch","New native AP obligation qualified; the AR branch requires an authoritative receivable source, not an invented obligation"),
 (17,"reporting","accounting.reconciliations_run;reporting.reconciliation_run.view;reporting.metric_result.view","accounting.JournalEntry;treasury.TreasuryMovement","Native source reconciliations retained; governed Reporting authority also required; unknown/missing ties are not zero"),
 (18,"accountant","accounting.periods_close","accounting.FiscalPeriod","New isolated CEP079 synthetic fiscal period; actual close/reopen deferred; old accepted periods untouched; requester and close/reopen authorities are distinct"),
 (19,"treasurer","treasury.view;treasury.statements_import;treasury.bank_reconciliations_run","treasury.TreasuryAccount","Bank statements require an ACTIVE BANK account with approved effective GL mapping; only active CASH exists"),
 (20,"treasurer","treasury.accounts_manage;treasury.movements_create;treasury.payment_requests_create;treasury.cheques_manage;treasury.advances_manage","treasury.TreasuryAccount;treasury.TreasuryMovement;treasury.TreasuryAdvance","New cash movement/advance sources qualified; cheque/bank portion lacks active bank context; no invented bank-to-GL mapping"),
 (21,"treasurer","subledgers.settlements_allocate;treasury.movements_create","subledgers.Obligation;treasury.TreasuryMovement","New AP obligation; a separate party/direction/amount-matched unallocated cash source is required; advance cash cannot be double-used"),
 (22,"treasurer","treasury.movements_reverse;treasury.cheques_manage;treasury.advances_reverse","treasury.TreasuryMovement;treasury.TreasuryAdvance;treasury.ChequeInstrument","Reverse only new CEP079 cash/advance originals; cleared cheque original and active bank context are missing"),
 (23,"treasurer","claims.view;subledgers.settlements_allocate","billing.ProgressClaim;subledgers.Obligation","New Billing/AR original and native cash source required; no legacy Payment writer"),
 (24,"procurement","purchase_requests.create;purchase_requests.submit","materials.Material;projects.Project","New PR target during later UAT, existing units/materials and project A; no accepted PR modified"),
 (25,"procurement","purchase_orders.create;purchase_orders.issue","procurement.PurchaseRequest","New CEP079 submitted PR plus actual independent owner candidate; PO target created later"),
 (26,"buyer","rfqs.view;rfq_quotes.capture;rfq_quotes.prepare_comparison;rfq_quotes.prepare_sourcing_award","procurement.RequestForQuotation;parties.BusinessParty","Existing RFQ, supplier, material source identities; separate registered custodian/opener/approver/award actors; source-specific authority must qualify current RFQ"),
 (27,"procurement","goods_receipts.create;goods_receipts.post;goods_receipts.void","procurement.PurchaseOrder","New CEP079 READY issued PO, with remaining quantity; new receipt target only"),
 (28,"accountant","supplier_invoices.prepare;supplier_invoices.approve;subledgers.obligations_recognize","procurement.GoodsReceipt;subledgers.SupplierInvoiceMatch","New posted GR and approved matched invoice/native AP fixture; owning AP authority is explicit, not a buyer-role inference"),
 (29,"procurement","materials.steward;parties.change;partner.profile_manage;partner.qualifications_prepare","materials.Material;parties.BusinessParty;partner_qualification.QualificationRequirement","Masters exist; Partner Qualification requires approved requirement/context inputs; no arbitrary criteria or weights invented"),
 (30,"store","warehouses.view;stock_balances.view","inventory.Warehouse;inventory.StockTransaction","New CEP079 warehouse and stock only; read balances; C/foreign scope comparator retained"),
 (31,"store","stock_transactions.create;stock_transactions.post","procurement.GoodsReceipt;inventory.Warehouse","New posted CEP079 HANDOFF receipt has no Inventory target; handoff/retry performed later, not now"),
 (32,"store","stock_transactions.create;stock_transactions.post;inventory_reservations.manage;inventory_transfers.prepare","inventory.StockTransaction;inventory.Warehouse","New positive stock and separate empty CEP079 destination; insufficient-stock target is explicit fictional quantity above available balance"),
 (33,"store","stock_transactions.reverse;inventory_counts.prepare;inventory_valuation.prepare","inventory.StockTransaction;subledgers.SupplierInvoiceMatch","New posted stock is disposable reversal/count target; valuation source unit/price is pinned new approved PO/invoice, no GL recognition inferred"),
 (34,"hr","employees.view;employees.create","workforce.Person;workforce.WorkRelationship;workforce.Employee","Person/current WorkRelationship inputs explicit; select ordinary employee/personnel path; department tree is not added to this frozen case"),
 (35,"time","attendance.capture;leave_mission.request;overtime.request","workforce.Employee;timekeeping.WorkCalendar;workforce.LeavePolicyVersion","Existing explicit test employee, calendar and configured Leave sources; frozen legacy flows only, no later ESS monetary activation"),
 (36,"time","timesheets.prepare;timesheets.view","workforce.Employee;projects.Activity;timekeeping.WorkCalendar","New timesheet target during UAT; known consistent Project/Site/Activity and explicit test employee; preview conserves minutes, not invented cost/rate"),
 (37,"payroll","payroll.prepare;payroll_results.view","payroll.PayrollPeriod;payroll.EmploymentPayConfiguration;payroll.PayrollRule;timekeeping.Timesheet","New OPEN CEP079 Payroll period and full-period approved synthetic Timesheet; existing approved native input producer and non-statutory rules; distinct reviewer/finalizer"),
 (38,"payroll","payroll.adjust;payslips.view","payroll.PayrollRun;payroll.Payslip","New finalized CEP079 non-statutory run/payslip is the correction/reversal target; old final runs retained unchanged"),
 (39,"manager","workflows.view;workflows.create;workflows.change_draft;workflows.publish","workflows.WorkflowTemplate;workflows.WorkflowDefinition","New declarative draft/version from existing registered template; no new step, command, rule or executable expression"),
 (40,"all","projects.view","workforce.Department","Cross-cutting representative form/RTL/keyboard inputs; exact six Workforce Close/Escape prerequisite cells currently FAIL"),
 (41,"all","projects.view","projects.Project;procurement.PurchaseRequest","Positive canonical actors plus existing scoped viewer A, denied C and foreign tenant; protected new PR maker/checker split; no denied action executed"),
 (42,"project","documents.upload;documents.view;documents.download","documents.Document;documents.DocumentVersion","Existing tenant/project category and safe disposable upload content; new target only; source-specific denied document comparator required"),
 (43,"project","equipment.view;fixed_assets.view;fixed_assets.candidate_prepare","equipment.Equipment;fixed_assets.FixedAssetClassVersion;fixed_assets.AssetBookPolicyVersion","Equipment sources exist; Fixed Asset positive candidate requires qualified class/book policy, monetary/capitalization references and explicit asset facts; no posting extension"),
 (44,"project","safety_incidents.view;quality_issues.view;compliance.view;partner.profile_manage","safety.SafetyIncident;quality.QualityIssue;compliance.InspectionTemplateVersion;partner_qualification.QualificationRequirement","Safety/Quality source states exist; published Compliance template and Partner Qualification requirements absent; Post-V1 performance scope excluded"),
]
assert len(specs) == 44 and {s[0] for s in specs} == set(range(1,45))

with transaction.atomic():
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION READ ONLY")
    org = Organization.objects.get(slug="demo-construction-01", status="active")
    project = Project.objects.get(organization=org, code="PRJ-01-01")
    project_c = Project.objects.get(organization=org, code="PRJ-01-03")
    foreign_project = Project.objects.get(organization__slug="demo-construction-02", code="PRJ-02-01")
    memberships = {key: OrganizationMembership.objects.select_related("user").get(organization=org,user__username=alias,status="active") for key,alias in actors.items()}
    checker = memberships["manager"]
    current_actor_data = []
    for alias in sorted(set(actors.values()) | {"uiux.wavec.custodian","uiux.wavec.opening-approver","uiux.persona.tenant-admin","uiux.audit.project"}):
        m = OrganizationMembership.objects.select_related("user").get(organization=org,user__username=alias,status="active")
        current_actor_data.append({"alias":alias,"membership":str(m.pk),"roles":list(effective_role_assignments(m).values_list("role__code",flat=True)),"grants":list(effective_scope_grants(m).values("scope_type","project_id","site_id")),"permissions":sorted(membership_permission_codes(m)),"credential_store_available":(Path(os.environ["LOCALAPPDATA"])/"BONIRA/UIUXRuntimeAudit/credentials"/(alias+".clixml")).exists()})
    (OUT/"QUALIFIED_ACTORS.json").write_text(json.dumps(current_actor_data,indent=2,default=str),encoding="utf-8")
    data = {}
    for _,_,_,labels,_ in specs:
        for label in labels.split(";"):
            if label in data:continue
            model=apps.get_model(label)
            fields={f.name for f in model._meta.fields}
            query=model.objects.filter(organization=org) if "organization" in fields else model.objects.all()
            names=[model._meta.pk.attname]+[f.attname for f in model._meta.fields if f.name in ("status","state","project","site","created_by","prepared_by","reviewed_by","posted_by","source_kind","effective_from","effective_to","starts_on","ends_on","code","is_active","review_status")]
            data[label]={"count":query.count(),"rows":list(query.values(*dict.fromkeys(names))[:100])}
    (OUT/"QUALIFIED_STARTING_DATA.json").write_text(json.dumps(data,indent=2,default=str),encoding="utf-8")
    rows=[]
    for num, actor_key, codes, labels, state in specs:
        source=inputs["scenarios"][num-1]
        assert source["UAT Scenario ID"]==f"UAT-CASE-{num:03}"
        m=memberships[actor_key]
        required=codes.split(";")
        missing=sorted(set(required)-membership_permission_codes(m))
        scoped=membership_has_scope(m,project=project) and m.user.is_active
        gaps=[]
        if missing:gaps.append({"classification":"AUTHORIZATION","requirement":"Existing canonical actor lacks registered required permissions", "missing":missing,"minimum_action":"Supply a qualified existing canonical role/actor or obtain an approved catalog/assignment decision; do not use the explicitly noncanonical uiux_runtime_reporting_test role or broaden existing roles here"})
        if not scoped:gaps.append({"classification":"AUTHORIZATION","requirement":"No effective Project A scope","minimum_action":"Qualified existing governed actor/scope required"})
        if num==12:gaps.append({"classification":"MISSING_EVIDENCE","requirement":"CEP040/IMB0039 exact AC/DoD and test/transaction/source-reconciliation/no-write evidence","minimum_action":"Recover authoritative execution proof; no reimplementation as evidence manufacture"})
        if num in (9,23):gaps.append({"classification":"BILLING_INPUTS","requirement":"Qualified approved claim source / ContractTermVersion / Billing configuration / effective regulatory provenance and accepted professional review","minimum_action":"Resolve exact Billing evidence item; create only canonical isolated claim/AR/cash starting states afterwards"})
        if num==16:gaps.append({"classification":"MISSING_FIXTURE","requirement":"Native AP is prepared; AR branch has no qualified receivable source","minimum_action":"Provide a disposable registered AR producer source; if sourced from Billing, use the same approved Billing inputs, never fabricate an AR obligation"})
        if num in (19,20,22):gaps.append({"classification":"MISSING_FIXTURE","requirement":"No ACTIVE BANK Treasury account / qualified effective bank-to-GL mapping / disposable bank/cheque context","minimum_action":"Provide approved isolated bank account/mapping starting context through canonical lifecycle; prepare cheque/statement sources without mapping-policy invention"})
        if num==18:gaps.append({"classification":"MISSING_FIXTURE","requirement":"Signed independent native reconciliation at the disposable period end, with required verified statements/control evidence; a new empty period alone is insufficient","minimum_action":"Qualify and retain native period-end reconciliation/statement inputs without treating unknown coverage as zero; use explicit separate close and reopen requester/approver pairs"})
        if num==21:
            cash_start=json.loads((OUT/"AP_CASH_START.json").read_text(encoding="utf-8"))
            if cash_start["result"]!="PREPARED":gaps.append({"classification":"MISSING_FIXTURE","requirement":"Separate matched unallocated AP cash source","minimum_action":"Prepare through native Treasury lifecycle; do not reuse advance cash"})
        if num in (29,44):gaps.append({"classification":"MISSING_FIXTURE_OR_BUSINESS_SOURCE","requirement":"No PartnerProfile / governed QualificationRequirement / qualified Partner source","minimum_action":"Supply approved qualification requirement/context and isolated partner fixture; no invented eligibility criteria, weights or Post-V1 scoring"})
        if num==40:gaps.append({"classification":"REQUIRED_VERIFICATION_FAIL","requirement":"Six exact Workforce cells FAIL close_focus and escape_focus; hard-refresh probe also FAIL","minimum_action":"Separately authorize the bounded asset/source-delivery or presentation correction after attribution, then rerun only these six cells"})
        if num==43:gaps.append({"classification":"MISSING_FIXTURE_OR_FINANCIAL_SOURCE","requirement":"No qualified FixedAssetClassVersion or AssetBookPolicyVersion; no positive asset fixture","minimum_action":"Supply approved class/book/capitalization/monetary source references and asset facts, then prepare isolated non-posting candidate; no fabricated depreciation or posting policy"})
        if num==44:gaps.append({"classification":"MISSING_FIXTURE_OR_BUSINESS_SOURCE","requirement":"No published Compliance InspectionTemplateVersion","minimum_action":"Supply an approved existing-semantic template and isolated Inspection/test records; do not invent checklist/risk criteria"})
        primary=actors[actor_key]
        approver="N/A for read-only starting-state use"
        if num in (4,14,15,18,20,21,22,24,25,26,27,28,29,32,33,35,36,37,38,42,43,44):
            approver=actors["manager"] if primary!=actors["manager"] else "Requester cep078.synthetic.operations; acting manager is independent checker"
        if num==26:approver="uiux.wavec.custodian (custody/admissibility), uiux.wavec.opening-approver (opening), uiux.wavec.buyer (opener/comparison), owner (RFQ/award); each object-specific grant/appointment must be bound by native lifecycle"
        if num==39:approver="Existing version validation/publication authority; no extra separation rule invented"
        if num==18:approver="Close requester accountant, closer tenant-admin; reopen requires explicit period-reopen permission on requester and a different approver from the closer. Existing owner/tenant-admin authorities must be bound to distinct steps; no permission added to accountant. Signed native reconciliation also required."
        if num in (3,5,8,17):approver="uiux.persona.tenant-admin: existing canonical reporting_reviewer, independent from both prepared Reporting authors; source-domain review permissions and object scope still intersect at actual action"
        row={"scenario_id":source["UAT Scenario ID"],"scenario_title":source["Scenario Title"],"required_persona":source["Scenario Actor"],"actor":primary,"canonical_roles":list(effective_role_assignments(m).values_list("role__code",flat=True)),"tenant":org.slug,"tenant_id":str(org.pk),"object_scope":"Project A "+str(project.pk)+"; organization scope only where owning service requires it; exact source scope intersects current grants","positive_authority_state":{"membership":"active","tenant":"active","user_active":m.user.is_active,"required_permissions":required,"missing_permissions":missing,"project_scope_verified":scoped},"negative_authority_state":{"actor":"uiux.audit.project","denied_project_C":str(project_c.pk),"foreign_tenant_project":str(foreign_project.pk),"not_executed":True},"independent_approver_or_separation":approver,"required_disposable_state":state,"suitable_existing_data":{label:{"count":data[label]["count"],"selection":"See exact retained/synthetic identifiers in QUALIFIED_STARTING_DATA and fixture manifests; old accepted sources read-only"} for label in labels.split(";")},"minimal_synthetic_data_needed":"Prepared identified namespace CEP079-PREP-01; later UAT creates its own target records. Outstanding input gaps are enumerated below, not silently substituted","readiness_result":"BLOCKED" if gaps else "READY_STARTING_CONTEXT_ONLY","blocking_requirements":gaps,"uat_execution_result":"NOT_EXECUTED","upstream_imb_ids":re.findall(r"IMB-\d+",source["Required IMB Implementation IDs"])}
        row["suitable_existing_data_exists"] = not any(g["classification"] in ("BILLING_INPUTS","MISSING_FIXTURE","MISSING_FIXTURE_OR_BUSINESS_SOURCE","MISSING_FIXTURE_OR_FINANCIAL_SOURCE") for g in gaps)
        row["minimal_synthetic_data_needed"] = {
            "prepared_namespace":"CEP079-PREP-01",
            "additional_starting_data_still_needed":[g["requirement"] for g in gaps if g["classification"] in ("BILLING_INPUTS","MISSING_FIXTURE","MISSING_FIXTURE_OR_BUSINESS_SOURCE","MISSING_FIXTURE_OR_FINANCIAL_SOURCE")],
            "source_manifests":["FIXTURES_CREATED.json","FINANCIAL_STARTING_STATES.json","REMAINING_STARTING_STATES.json","FOCUSED_FIXTURE_RETRY.json","OPEN_PAYROLL_START.json","AP_CASH_START.json"],
            "policy":"New target records during later authorized UAT; immutable/accepted old sources are read-only. Source-required policy/template/criterion content is not invented as fixture data.",
        }
        row["qualified_fixture_references"]={"project":str(project.pk),"actor_authority":"QUALIFIED_ACTORS.json","credential_check":"CREDENTIAL_QUALIFICATION.json"}
        if num in (6,42):row["qualified_fixture_references"]["documents"]="DOCUMENT_STARTING_DATA.json: owning-service-authorized, available file versions; foreign negative comparator and validated synthetic JPEG payload"
        if num in (4,25):
            request=apps.get_model("procurement.PurchaseRequest").objects.get(organization=org,request_number="CEP079-PREP-01-PR")
            row["qualified_fixture_references"]["request"]=str(request.pk)
            row["qualified_fixture_references"]["actual_work_items"]=list(apps.get_model("workflows.WorkItem").objects.filter(organization=org,instance__subject_id=request.pk,status="open").values_list("pk",flat=True))
        selections={15:("accounting.JournalEntry","source_key","CEP079-PREP-01-JOURNAL"),18:("accounting.FiscalYear","code","CEP079-SYNTHETIC-FY"),21:("treasury.TreasuryMovement","idempotency_key","CEP079-PREP-01-AP-CASH"),27:("procurement.PurchaseOrder","order_number","CEP079-PREP-01-READY"),28:("subledgers.SupplierInvoice","invoice_number","CEP079-PREP-01-INVOICE"),31:("procurement.GoodsReceipt","receipt_number","CEP079-PREP-01-HANDOFF"),32:("inventory.StockTransaction","transaction_number","CEP079-PREP-01-STOCK"),33:("inventory.StockTransaction","transaction_number","CEP079-PREP-01-STOCK"),37:("payroll.PayrollPeriod","code","CEP079-PREP-01-OPEN-PAY"),38:("payroll.PayrollRun","code","CEP079-PREP-01-PAY")}
        if num in selections:
            label,field,value=selections[num]
            row["qualified_fixture_references"]["synthetic_source"]={"model":label,"id":str(apps.get_model(label).objects.get(organization=org,**{field:value}).pk)}
        if num==32:row["qualified_fixture_references"]["destination_warehouse"]=str(apps.get_model("inventory.Warehouse").objects.get(organization=org,code="CEP079-PREP-01-DEST").pk)
        if num==37:row["qualified_fixture_references"]["approved_timesheet"]=json.loads((OUT/"OPEN_PAYROLL_START.json").read_text(encoding="utf-8"))["approved_timesheet_id"]
        rows.append(row)

    metadata={"at":datetime.now(timezone.utc).isoformat(),"kind":"ENTRY_PREPARATION_NOT_UAT_RESULTS","scope":"Frozen authoritative 44 cases, unchanged semantic rows; starting data and explicit authority only","source_mapping_sha256":"585a89893a69881afb0589a5173385ed2d3e860203a222700875a02a64744e45","no_role_hierarchy_or_persona_equals_role_inference":True,"role_definitions_permission_sets_and_authorization_semantics_unchanged":True,"explicit_fixture_role_scope_bindings":"ACTOR_PREPARATION.json: existing canonical roles, native dual-control/Platform Initial Grant services, synthetic aliases only; not a default role expansion","source_readiness_limit":"READY means qualified starting inputs/authority, never a promised PASS; source policy/currentness, object grants and workflow authority rechecked transactionally at actual execution","safe_data_policy":"Existing accepted business rows/master versions are read-only. Future mutating targets must use the identified new CEP079 namespace or newly created clearly isolated records. No reversal of accepted old financial/Payroll/stock sources. Synthetic role/scope changes are separately audited.","rows":rows}
(OUT/"44_CASE_READINESS_MATRIX.json").write_text(json.dumps(metadata,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
columns=["scenario_id","scenario_title","required_persona","actor","canonical_roles","tenant","object_scope","positive_authority_state","negative_authority_state","independent_approver_or_separation","required_disposable_state","suitable_existing_data","suitable_existing_data_exists","minimal_synthetic_data_needed","qualified_fixture_references","readiness_result","blocking_requirements","uat_execution_result","upstream_imb_ids"]
with (OUT/"44_CASE_READINESS_MATRIX.csv").open("w",newline="",encoding="utf-8-sig") as file:
    writer=csv.DictWriter(file,fieldnames=columns);writer.writeheader()
    for row in rows:writer.writerow({key:json.dumps(row[key],ensure_ascii=False,default=str) if isinstance(row[key],(dict,list)) else row[key] for key in columns})
print(json.dumps({"rows":len(rows),"ready_starting_context":sum(r["readiness_result"]=="READY_STARTING_CONTEXT_ONLY" for r in rows),"blocked":[r["scenario_id"] for r in rows if r["blocking_requirements"]],"missing_permission_rows":{r["scenario_id"]:r["positive_authority_state"]["missing_permissions"] for r in rows if r["positive_authority_state"]["missing_permissions"]}},ensure_ascii=True))

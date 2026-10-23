"""Bounded PD-WC-01..08 Development re-entry; evidence excludes credentials."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django
django.setup()
from django.db import connection
from django.db import transaction
from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationMembership, OrganizationRole, BusinessPermission
from apps.organizations.authorization import membership_permission_codes, effective_scope_grants, has_business_permission, is_platform_admin

OLD = runpy.run_path(str(OUT.parent / "wave_c_evidence/runtime.py"), run_name="support")
save = lambda name, data: (OUT / name).write_text(json.dumps(data, ensure_ascii=False, default=str, indent=2) + "\n", encoding="utf-8")

def ground():
    OLD["guard"]()
    assert not (OUT / "ENTRY.json").exists()
    save("ENTRY.json", {"branch": subprocess.check_output(["git", "branch", "--show-current"], text=True).strip(), "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(), "upstream": subprocess.check_output(["git", "rev-parse", "@{u}"], text=True).strip(), "status": subprocess.check_output(["git", "status", "--short"], text=True), "diff_stat": subprocess.check_output(["git", "diff", "--stat"], text=True), "diff_name_status": subprocess.check_output(["git", "diff", "--name-status"], text=True), "index_sha256": hashlib.sha256((ROOT / ".git/index").read_bytes()).hexdigest(), "authority": "Human attached Wave C Blocker Decision Pack PD-WC-01 through PD-WC-08", "database": {k: connection.settings_dict[k] for k in ("ENGINE", "HOST", "PORT", "NAME")}, "migration": "NO", "production": "UNTOUCHED", "cep078079": "NOT_EXECUTED", "git_writes": "NOT_EXECUTED"})
    paths = set(subprocess.check_output(["git", "ls-files"], text=True).splitlines())
    paths.update(str(p.relative_to(ROOT)).replace("\\", "/") for parent in ("docs/governance/uiux", "tests", "graphify-out", "protected_documents") for p in (ROOT / parent).rglob("*") if p.is_file() and OUT not in p.parents and "__pycache__" not in p.parts)
    save("FILES_BEFORE.json", {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(paths) if (ROOT/p).is_file()})
    save("RUNTIME_ENTRY.json", {"models": OLD["snapshot"](), "rows": OLD["row_hashes"]()})
    inventory()

def inventory():
    org = Organization.objects.get(slug="demo-construction-01")
    rows = []
    for m in OrganizationMembership.objects.filter(organization=org, status="active").select_related("user"):
        rows.append({"actor": m.user.username, "id": str(m.pk), "permissions": sorted(membership_permission_codes(m)), "scopes": list(effective_scope_grants(m).values("scope_type", "project_id", "site_id"))})
    save("AUTHORITY_INVENTORY.json", {"memberships": rows, "platform_admins": [u.username for u in User.objects.filter(is_active=True) if is_platform_admin(u)], "superusers": list(User.objects.filter(is_superuser=True, is_active=True).values_list("username", flat=True)), "catalog": list(BusinessPermission.objects.filter(is_active=True).values_list("code", flat=True))})
    print("Grounded Development; authority inventory saved; no secrets serialized")

ROLE_PLANS = {
    "buyer": ("RV-007", "Procurement Buyer", "project", ["rfqs.view", "rfq_quotes.view_metadata", "rfq_quotes.capture", "rfq_quotes.submit", "rfq_quotes.prepare_admissibility", "rfq_quotes.prepare_comparison", "rfq_quotes.evaluate_comparison", "rfq_quotes.prepare_sourcing_award"]),
    "hr": ("RV-015", "HR Administrator", "organization", ["employees.view", "employees.create", "departments.view", "departments.create", "positions.view", "positions.create", "work_teams.view", "work_teams.create"]),
    "time": ("RV-017", "Timekeeping Operator", "organization", ["attendance.view", "attendance.capture", "attendance.import", "time_calendars.manage", "leave_mission.request", "overtime.request", "timesheets.prepare", "timesheets.view"]),
    "payroll": ("RV-018", "Payroll Specialist", "organization", ["payroll_results.view", "payroll_configuration.view", "payroll_configuration.manage", "payroll.prepare", "payroll_audit.view", "payslips.view", "payroll_statutory_configuration.view", "payroll_statutory.prepare", "payroll_statutory_outputs.generate", "payroll_statutory_audit.view", "payroll_liability_handoff.prepare", "payroll_accounting_handoff.prepare", "payroll_payment_handoff.prepare", "payroll_project_cost_handoff.prepare", "payroll_handoff_reconciliation.prepare"]),
    "documents": ("RV-028", "Document Specialist", "project", ["documents.view", "documents.upload", "documents.download", "projects.view"]),
    "employment": ("RV-029", "Employment Manager", "organization", ["employment_records.manage", "employees.view", "documents.view"]),
    "employment-own": ("RV-029", "Employee Self-Service", "organization", ["employment_records.view_own"]),
    "commercial": ("RV-030", "Commercial Specialist", "project", ["tender_bids.view", "tender_bids.prepare", "tender_bids.transition", "contracts.view", "projects.view"]),
    "controls": ("RV-031", "Project Controls Analyst", "project", ["projects.view", "project_controls.view", "project_controls.compare", "project_controls.exceptions_view", "project_cost.reconciliations_view"]),
    "portal": ("RV-032", "Supplier Portal Manager", "project", ["supplier_portal.invitations_manage"]),
}

def store_credential(alias, password):
    program = "$d=[Console]::In.ReadToEnd()|ConvertFrom-Json; $p=Join-Path $env:LOCALAPPDATA 'BONIRA/UIUXRuntimeAudit/credentials'; [System.IO.Directory]::CreateDirectory($p)|Out-Null; $s=ConvertTo-SecureString $d.password -AsPlainText -Force; [pscredential]::new($d.alias,$s)|Export-Clixml -LiteralPath (Join-Path $p ($d.alias+'.clixml'))"
    subprocess.run([r"C:\Users\azera\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe", "-NoProfile", "-Command", program], input=json.dumps({"alias": alias, "password": password}), capture_output=True, text=True, check=True)

def roles():
    import secrets
    from apps.organizations.access_services import create_organization_role, assign_membership_role, grant_membership_scope
    from apps.organizations.services import create_organization_account
    from apps.accounts.services import initialize_personal_password
    from apps.projects.models import Project
    from django.core.exceptions import PermissionDenied
    OLD["guard"]()
    org = Organization.objects.get(slug="demo-construction-01")
    admin = User.objects.get(username="admin")
    owner = User.objects.get(username="account.demo-construction-01.owner")
    approver = OrganizationMembership.objects.get(organization=org, user=admin)
    project = Project.objects.get(organization=org, code="PRJ-01-01")
    # Fail before any mutation for a typo, inactive permission or unsupported catalog entry.
    catalog = set(BusinessPermission.objects.filter(is_active=True).values_list("code", flat=True))
    for _, _, _, codes in ROLE_PLANS.values():
        assert set(codes) <= catalog, set(codes)-catalog
    result = {}
    for key, (scenario, title, scope, codes) in ROLE_PLANS.items():
        role = OrganizationRole.objects.filter(organization=org, code="wave_c_" + key.replace("-", "_")).first()
        if role is None:
            role = create_organization_role(actor=admin, organization=org, code="wave_c_" + key.replace("-", "_"), name=title, description="Bounded Development Wave C specialist", permissions=codes, reason="PD-WC-01..08: " + scenario)
        assert set(role.permissions.values_list("code", flat=True)) == set(codes)
        alias = "uiux.wavec." + key
        row = {"scenario": scenario, "actor": alias, "role": str(role.pk), "code": role.code, "permissions": codes, "scope": scope, "project": str(project.pk) if scope == "project" else None}
        existing = User.objects.filter(username=alias).first()
        if existing:
            membership = OrganizationMembership.objects.get(organization=org, user=existing)
            assert set(membership_permission_codes(membership)) == set(codes)
            credential = Path(os.environ["LOCALAPPDATA"]) / "BONIRA/UIUXRuntimeAudit/credentials" / (alias + ".clixml")
            if not credential.exists():
                from apps.organizations.services import reset_organization_member_password
                password = secrets.token_urlsafe(28)
                with transaction.atomic():
                    reset_organization_member_password(organization=org, actor=owner, membership=membership, temporary_password=secrets.token_urlsafe(28))
                    initialize_personal_password(user=existing, new_password=password)
                    store_credential(alias, password)
                del password
            row.update(status="PROVISIONED", membership=str(membership.pk), assigner=owner.username, approver=admin.username)
        else:
            try:
                with transaction.atomic():
                    password = secrets.token_urlsafe(28)
                    user, membership = create_organization_account(organization=org, actor=owner, username=alias, temporary_password=secrets.token_urlsafe(28), role=role)
                    assignment = assign_membership_role(organization=org, actor=owner, membership_id=membership.pk, role=role, approver_membership_id=approver.pk, reason="PD-WC-01..08 bounded independent assignment " + scenario)
                    grant = grant_membership_scope(organization=org, actor=owner, membership_id=membership.pk, scope_type=scope, project=project if scope == "project" else None, approver_membership_id=approver.pk, reason="PD-WC-01 exact Development scenario scope " + scenario)
                    initialize_personal_password(user=user, new_password=password)
                    store_credential(alias, password)
                    row.update(status="PROVISIONED", membership=str(membership.pk), assignment=str(assignment.pk), grant=str(grant.pk), assigner=owner.username, approver=admin.username)
                del password
            except PermissionDenied as exc:
                row.update(status="BLOCKED_CANONICAL_DELEGATION", reason=str(exc), account_transaction="ROLLED_BACK", missing_assigner_permissions=sorted(set(codes) - membership_permission_codes(OrganizationMembership.objects.get(organization=org, user=owner))))
        result[key] = row
        save("ROLES.json", result)
    print({k: r["status"] for k, r in result.items()})

def policies():
    from datetime import date
    from apps.organizations.models import PlatformPolicyVersion, TenantPolicySelection
    from apps.organizations.policy_services import publish_initial_accounting_policy_versions, select_tenant_policy_version, apply_tenant_policy_selection
    from apps.organizations.policy_specs import initial_accounting_policy_parameters
    from apps.commercial.models import TenderBidActivation
    from apps.subledgers.services import _SOURCE_RESOLVERS
    OLD["guard"]()
    org = Organization.objects.get(slug="demo-construction-01")
    admin = User.objects.get(username="admin")
    tenant_admin = User.objects.get(username="uiux.persona.tenant-admin")
    info = {"tender_activations": list(TenderBidActivation.objects.filter(organization=org).values()), "obligation_source_kinds": sorted(_SOURCE_RESOLVERS), "accounting": {}}
    from django.utils import timezone
    from django.core.exceptions import ValidationError
    upcoming = list(PlatformPolicyVersion.objects.filter(policy__code__in=["accounting-money-precision", "accounting-rounding"], status="published").values("policy__code", "effective_from", "effective_to", "parameters"))
    info["existing_accounting_versions"] = upcoming
    if upcoming and all(v["effective_from"] > timezone.localdate() for v in upcoming):
        info["accounting_status"] = "BLOCKED_FUTURE_EFFECTIVE_DATE"
        info["reason"] = "Both published policies begin 2026-12-22. Current canonical selection rejects future versions. No permission to invent earlier accounting effective date or supersede published scheduling. Original activation attempt rolled back."
        save("POLICIES.json", info)
        save("POPULATED_STATEMENT.json", {"status": "BLOCKED", "missing": "Currently effective accounting-money-precision and accounting-rounding versions", "earliest_published_start": "2026-12-22", "transaction": "ROLLED_BACK", "new_journals": 0})
        print("Statement blocked by canonical future policy dates; no policy mutation")
        return
    with transaction.atomic():
        versions = {}
        for code in ("accounting-money-precision", "accounting-rounding"):
            v = PlatformPolicyVersion.objects.filter(policy__code=code, status="published").order_by("-version").first()
            if v:
                assert v.parameters == initial_accounting_policy_parameters(code)
                versions[code] = v
        if not versions:
            versions = publish_initial_accounting_policy_versions(actor=admin, effective_from=date(2026,10,22), reason="PD-WC-06 canonical code-owned initial accounting defaults; Development only")
        assert len(versions) == 2
        for code, v in versions.items():
            existing = TenantPolicySelection.objects.filter(organization=org, policy=v.policy, status="active").first()
            if existing:
                assert existing.policy_version_id == v.pk
                selected = existing
            else:
                selected = select_tenant_policy_version(organization=org, actor=tenant_admin, policy_version=v, reason="PD-WC-06 existing exact code-owned policy contract; Development statement fixture")
                apply_tenant_policy_selection(organization=org, actor=tenant_admin, selection=selected)
            info["accounting"][code] = {"version": str(v.pk), "parameters": v.parameters, "selection": str(selected.pk), "source": "apps/organizations/policy_specs.py ACCOUNTING_INITIAL_POLICY_PARAMETERS"}
    save("POLICIES.json", info)
    # Reuse the exact canonical, formerly blocked preparation without touching old evidence.
    save("FIXTURES.json", {"statements": {}})
    original_globals = OLD["populated_statement"].__globals__
    previous = original_globals["OUT"]
    try:
        original_globals["OUT"] = OUT
        OLD["populated_statement"]()
    finally:
        original_globals["OUT"] = previous

def documents():
    import struct
    import zlib
    from datetime import timedelta
    from django.utils import timezone
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.core.exceptions import PermissionDenied
    from apps.documents.models import Document
    from apps.documents.services import create_document, add_document_version, record_document_processing_assessment, get_document_version_for_download
    from apps.organizations.access_services import assign_platform_role, revoke_platform_role
    from apps.projects.models import Project
    OLD["guard"]()
    org = Organization.objects.get(slug="demo-construction-01")
    actor = User.objects.get(username="uiux.wavec.documents")
    superuser = User.objects.get(username="superuser")
    admin = User.objects.get(username="admin")
    project = Project.objects.get(organization=org, code="PRJ-01-01")
    assert not Document.objects.filter(organization=org, reference="WAVE-C-REENTRY-SCAN").exists()
    def png(pixel):
        def chunk(kind, payload):
            return struct.pack(">I",len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind+payload)&0xffffffff)
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR",struct.pack(">IIBBBBB",1,1,8,2,0,0,0)) + chunk(b"IDAT",zlib.compress(b"\x00"+pixel)) + chunk(b"IEND",b"")
    document = create_document(organization=org, actor=actor, document_type="general", title="Wave C benign synthetic scanner evidence", reference="WAVE-C-REENTRY-SCAN", target=project, upload=SimpleUploadedFile("wave-c-benign.png",png(b"\xff\xff\xff"),content_type="image/png"))
    versions = [document.current_version, add_document_version(document=document, actor=actor, upload=SimpleUploadedFile("wave-c-benign-v2.png",png(b"\xee\xee\xee"),content_type="image/png"))]
    record = {"document": str(document.pk), "versions": [], "mechanism": "Microsoft Defender MpCmdRun custom file scan; DisableRemediation", "assessment_service": "record_document_processing_assessment", "temporary_platform_duty": "NOT_ASSIGNED"}
    assignment = assign_platform_role(actor=superuser, approver=admin, target=actor, role="platform_operations", reason="PD-WC-07 minimum Development scanner-assessment duty only", ends_at=timezone.now()+timedelta(hours=1))
    record["temporary_platform_duty"] = str(assignment.pk)
    scanner = Path("C:/ProgramData/Microsoft/Windows Defender/Platform/4.18.26090.9-0/MpCmdRun.exe")
    try:
        for version in versions:
            denied = False
            try:
                get_document_version_for_download(document=document,version_id=str(version.pk),actor=actor)
            except PermissionDenied:
                denied = True
            assert denied
            scanned_hash = hashlib.sha256(Path(version.file.path).read_bytes()).hexdigest()
            assert scanned_hash == version.sha256
            proc = subprocess.run([str(scanner), "-Scan", "-ScanType", "3", "-File", version.file.path, "-DisableRemediation"], capture_output=True, text=True, timeout=55)
            item = {"version": str(version.pk), "sha256": scanned_hash, "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr, "pre_assessment_download_denied": denied}
            record["versions"].append(item)
            save("DOCUMENT_SCAN.json", record)
            if proc.returncode != 0 or "found no threats" not in proc.stdout.lower():
                record["status"] = "BLOCKED_SCANNER_VERDICT"
                break
            assert hashlib.sha256(Path(version.file.path).read_bytes()).hexdigest() == scanned_hash
            assessment = record_document_processing_assessment(version=version, actor=actor, verdict="clean", adapter_code="microsoft-defender-mpcmdrun", adapter_version="4.18.26090.9", details={"exit_code": proc.returncode, "stdout_sha256": hashlib.sha256(proc.stdout.encode()).hexdigest(), "synthetic": True})
            version = get_document_version_for_download(document=document,version_id=str(version.pk),actor=actor)
            item.update(assessment=str(assessment.pk),download_available=version.is_available)
        else:
            record["status"] = "SCANNED_AND_DOWNLOAD_VERIFIED"
    finally:
        revoke_platform_role(actor=superuser, approver=admin, assignment_id=assignment.pk, reason="PD-WC-07 scanner assessment finished; temporary duty removed")
        record["temporary_platform_duty"] = "REVOKED"
        save("DOCUMENT_SCAN.json", record)
    print(record["status"])

def domain_inventory():
    from django.apps import apps
    org = Organization.objects.get(slug="demo-construction-01")
    labels = ["payroll.PayrollPeriod", "payroll.PayrollRun", "payroll.EmploymentPayConfiguration", "payroll.PayrollRule", "billing.ProgressClaim", "billing.PayableCertificate", "subledgers.SupplierInvoice", "subledgers.SupplierInvoiceMatch", "subledgers.Obligation", "treasury.TreasuryMovement"]
    report = {}
    for label in labels:
        model = apps.get_model(label)
        qs = model.objects.filter(organization=org)
        fields = [f.name for f in model._meta.fields if f.name in ("id", "code", "status", "state", "effective_from", "effective_to", "starts_on", "ends_on", "source_kind", "source_key", "source_version", "posting_status", "amount")]
        report[label] = {"count": qs.count(), "rows": list(qs.values(*fields)[:30])}
    save("DOMAIN_INVENTORY.json",report)
    print({k:v["count"] for k,v in report.items()})

def refine_roles():
    from apps.organizations.access_services import revoke_membership_role, update_organization_role, assign_membership_role
    OLD["guard"]()
    org = Organization.objects.get(slug="demo-construction-01")
    owner = User.objects.get(username="account.demo-construction-01.owner")
    admin = User.objects.get(username="admin")
    approver = OrganizationMembership.objects.get(organization=org,user=admin)
    changes = {"hr":["workforce_skills.view","workforce_skills.manage","workforce_qualifications.view","workforce_qualifications.manage","employees.link_account"],"controls":["wbs_nodes.view","activities.view"]}
    evidence = json.loads((OUT/"ROLES.json").read_text(encoding="utf-8"))
    for key, extra in changes.items():
        role = OrganizationRole.objects.get(organization=org,code="wave_c_"+key)
        member = OrganizationMembership.objects.get(organization=org,user__username="uiux.wavec."+key)
        codes = sorted(set(role.permissions.values_list("code",flat=True))|set(extra))
        assert set(codes) <= membership_permission_codes(OrganizationMembership.objects.get(organization=org,user=owner))
        if set(role.permissions.values_list("code",flat=True)) != set(codes):
            with transaction.atomic():
                current = member.role_assignments.get(role=role,revoked_at__isnull=True)
                revoke_membership_role(organization=org,actor=owner,assignment_id=current.pk,approver_membership_id=approver.pk,reason="PD-WC exact dependent-view permissions; revoke before revised dual-controlled assignment")
                update_organization_role(actor=admin,role_id=role.pk,name=role.name,description=role.description,permissions=codes,reason="PD-WC exact required existing view/service dependencies")
                assigned = assign_membership_role(organization=org,actor=owner,membership_id=member.pk,role=role,approver_membership_id=approver.pk,reason="PD-WC revised least-privilege subset with independent approval")
                evidence[key].update(permissions=codes,assignment=str(assigned.pk))
    save("ROLES.json",evidence)

def fixtures():
    from datetime import date, datetime
    from zoneinfo import ZoneInfo
    from decimal import Decimal
    from django.core.exceptions import PermissionDenied, ValidationError
    from apps.workforce.services import create_department, create_position, create_work_team, create_employee
    from apps.timekeeping.services import create_work_calendar, capture_attendance
    from apps.payroll import services as payroll
    from apps.projects.models import Project
    OLD["guard"]()
    assert not (OUT / "DOMAIN_FIXTURES.json").exists()
    org = Organization.objects.get(slug="demo-construction-01")
    hr = User.objects.get(username="uiux.wavec.hr")
    time = User.objects.get(username="uiux.wavec.time")
    pay = User.objects.get(username="uiux.wavec.payroll")
    project = Project.objects.get(organization=org,code="PRJ-01-01")
    made = {}
    with transaction.atomic():
        department = create_department(organization=org,actor=hr,code="WAVE-C-HR",name="Wave C synthetic department")
        position = create_position(organization=org,actor=hr,code="WAVE-C-HR",title="Wave C synthetic position",department=department)
        team = create_work_team(organization=org,actor=hr,code="WAVE-C-HR",name="Wave C synthetic team",department=department)
        employee = create_employee(organization=org,actor=hr,employee_number="WAVE-C-HR",first_name="Wave C",last_name="Synthetic",department=department,position=position,work_team=team,hire_date=date(2026,10,22))
        made["hr"] = {"department":str(department.pk),"position":str(position.pk),"team":str(team.pk),"employee":str(employee.pk)}
        calendar = create_work_calendar(organization=org,actor=time,code="WAVE-C-TIME",name="Wave C synthetic calendar",effective_from=date(2026,10,22),working_weekdays=[1,2,3,4,5,6,7])
        attendance = capture_attendance(organization=org,actor=time,employee=employee,calendar=calendar,work_date=date(2026,10,22),check_in_at=datetime(2026,10,22,8,tzinfo=ZoneInfo(org.settings.timezone)),check_out_at=datetime(2026,10,22,9,tzinfo=ZoneInfo(org.settings.timezone)),project=project,source_reference="PD-WC synthetic 1-hour daily-operation fixture")
        made["time"] = {"calendar":str(calendar.pk),"attendance":str(attendance.pk)}
        # A synthetic non-statutory example is data, never a real compensation policy.
        configuration = payroll.create_employment_configuration(organization=org,actor=pay,employee=employee,pay_model="salaried",base_rate=Decimal("1"),rate_unit="hour",effective_from=date(2026,10,22),source_reference="PD-WC synthetic Development-only arithmetic example, not a real employment offer",evidence={"synthetic": True})
        payroll.activate_employment_configuration(organization=org,actor=pay,configuration=configuration)
        component = payroll.create_component(organization=org,actor=pay,code="WAVE-C-EXAMPLE",name="Synthetic non-statutory example",kind="earning",net_effect="add")
        rule = payroll.create_rule(organization=org,actor=pay,component=component,code="WAVE-C-EXAMPLE",name="Synthetic 1 IRR example",sequence=100,method="fixed_amount",fixed_amount=Decimal("1"),effective_from=date(2026,10,22),source_reference="PD-WC synthetic arithmetic fixture only",evidence={"synthetic":True})
        payroll.activate_rule(organization=org,actor=pay,rule=rule)
        period = payroll.create_period(organization=org,actor=pay,code="WAVE-C-EXAMPLE",name="Wave C synthetic period",starts_on=date(2026,10,22),ends_on=date(2026,10,22),cutoff_at=datetime(2026,10,22,23,tzinfo=ZoneInfo(org.settings.timezone)))
        run = payroll.create_run(organization=org,actor=pay,period=period,code="WAVE-C-EXAMPLE",idempotency_key="WAVE-C-REENTRY-RUN",employees=[employee])
        made["payroll"] = {"configuration":str(configuration.pk),"component":str(component.pk),"rule":str(rule.pk),"period":str(period.pk),"run":str(run.pk)}
    try:
        payroll.lock_run_inputs(organization=org,actor=pay,run=run)
        payroll.calculate_run(organization=org,actor=pay,run=run)
    except (PermissionDenied,ValidationError,ValueError) as exc:
        made["payroll"]["calculation_blocker"] = str(exc)
    save("DOMAIN_FIXTURES.json",made)
    print("Canonical HR, Timekeeping and synthetic non-statutory Payroll fixtures retained; calculation gate recorded")

def direct():
    from django.core.exceptions import PermissionDenied, ValidationError
    from apps.projects.models import Project
    from apps.projects.services import get_project_control_comparison, get_project_control_exceptions, get_project_cost_reconciliation
    from apps.workforce.services import get_organization_employees, create_employee, get_workforce_skills
    from apps.workforce.models import Employee, Department
    from apps.documents.models import Document
    from apps.documents.services import get_document_version_for_download
    from apps.timekeeping.services import create_work_calendar
    from apps.procurement.models import RequestForQuotationInvitation
    from apps.procurement.quote_services import capture_quote_revision, submit_quote_revision
    from apps.procurement.opening_services import request_quote_opening
    from apps.organizations.authorization import require_business_permission
    from datetime import date
    OLD["guard"]()
    org = Organization.objects.get(slug="demo-construction-01")
    other = Organization.objects.get(slug="demo-construction-02")
    actor = {key:User.objects.get(username="uiux.wavec."+key) for key in ("buyer","hr","time","payroll","documents","controls")}
    projects = {k:Project.objects.get(code=c) for k,c in [("A","PRJ-01-01"),("C","PRJ-01-03"),("X","PRJ-02-01")]}
    source = b"Wave C synthetic Development receiving evidence; no actual supplier pricing or business rule.\n"
    (OUT/"SEALED_SOURCE.txt").write_bytes(source)
    old = json.loads((OUT.parent/"wave_c_evidence/FIXTURES.json").read_text(encoding="utf-8"))
    invitation = RequestForQuotationInvitation.objects.get(pk=old["rfqs"]["A"]["invitation"])
    quote = capture_quote_revision(organization=org,actor=actor["buyer"],invitation=invitation,integrity_fingerprint=hashlib.sha256(source).hexdigest(),source_channel="manual_capture",source_reference="WAVE-C-SOURCE-01",idempotency_key="WAVE-C-REENTRY-CAPTURE")
    quote = submit_quote_revision(organization=org,actor=actor["buyer"],revision=quote,idempotency_key="WAVE-C-REENTRY-SUBMIT")
    save("PROCUREMENT.json",{"quote":str(quote.pk),"status":quote.status,"fingerprint":quote.integrity_fingerprint,"source":"SEALED_SOURCE.txt","remaining":"No canonical tenant assigner holds rfq_quotes.open / rfq_quotes.view_confidential; no protected opening bypass"})
    before = {"models":OLD["snapshot"](),"rows":OLD["row_hashes"]()}
    cases = []
    def case(name, command, denied=False):
        try:
            with transaction.atomic():
                result = command()
                if hasattr(result,"count") and not isinstance(result, (dict,list,str)):
                    result.count()
        except (PermissionDenied,ValidationError,ValueError) as exc:
            cases.append({"case":name,"result":"DENIED","expected":"DENIED" if denied else "SUCCESS","passed":denied,"reason":str(exc)})
        else:
            shape = {"is_none":result is None}
            if hasattr(result,"budget_id"):
                shape["budget_id"] = str(result.budget_id)
            if hasattr(result,"lines"):
                shape["line_count"] = len(result.lines)
            cases.append({"case":name,"result":"SUCCESS","expected":"DENIED" if denied else "SUCCESS","passed":not denied,"data_shape":shape})
    case("HR exact employee read",lambda:get_organization_employees(user=actor["hr"],organization=org))
    case("HR foundation read",lambda:get_workforce_skills(organization=org,actor=actor["hr"]))
    case("HR foreign tenant read",lambda:get_organization_employees(user=actor["hr"],organization=other),True)
    case("HR foreign related department write",lambda:create_employee(organization=org,actor=actor["hr"],employee_number="DENIED-NOT-CREATED",first_name="Denied",last_name="Fixture",department=Department.objects.filter(organization=other).first()),True)
    case("Unauthorized timekeeping write",lambda:create_work_calendar(organization=org,actor=actor["hr"],code="DENIED-NOT-CREATED",name="Denied",effective_from=date(2026,10,22),working_weekdays=[1]),True)
    for code in ("workforce_performance.view","workforce_labor_rates.view","employees.view"):
        case("Payroll excludes "+code,lambda code=code:require_business_permission(user=actor["payroll"],organization=org,permission=code,message="Denied by exact specialist boundary"),True)
    for key in ("A","C","X"):
        for name,func in [("comparison",get_project_control_comparison),("exceptions",get_project_control_exceptions),("reconciliation",get_project_cost_reconciliation)]:
            case("Controls "+name+" "+key,lambda func=func,key=key:func(organization=projects[key].organization,project=projects[key],actor=actor["controls"]),key!="A")
    docdata = json.loads((OUT/"DOCUMENT_SCAN.json").read_text(encoding="utf-8"))
    doc = Document.objects.get(pk=docdata["document"])
    for item in docdata["versions"]:
        case("Document scanned version download",lambda item=item:get_document_version_for_download(document=doc,version_id=item["version"],actor=actor["documents"]))
    case("Document unauthorized download",lambda:get_document_version_for_download(document=doc,version_id=docdata["versions"][0]["version"],actor=actor["hr"]),True)
    case("Procurement protected opening denied",lambda:request_quote_opening(organization=org,actor=actor["buyer"],quote_revision=quote,reason="PD-WC protected authority control",idempotency_key="DENIED-OPENING"),True)
    after = {"models":OLD["snapshot"](),"rows":OLD["row_hashes"]()}
    delta = {label:{"added":sorted(set(after["rows"][label])-set(oldrows)),"changed":[key for key,value in oldrows.items() if after["rows"][label].get(key)!=value]} for label,oldrows in before["rows"].items() if after["rows"][label]!=oldrows and label != "sessions.Session"}
    from apps.audit.models import AuditEvent
    audit_ids = delta.get("audit.AuditEvent",{}).get("added",[])
    audit_actions = list(AuditEvent.objects.filter(pk__in=audit_ids).values_list("action",flat=True))
    save("DIRECT_SERVICE.json",{"cases":cases,"all_expected":all(c["passed"] for c in cases),"snapshot_unchanged":before==after,"delta":delta,"audit_actions":audit_actions,"before_sha256":hashlib.sha256(json.dumps(before,sort_keys=True,default=str).encode()).hexdigest(),"after_sha256":hashlib.sha256(json.dumps(after,sort_keys=True,default=str).encode()).hexdigest()})
    print("Direct services:",len(cases),"controls;",sum(not c["passed"] for c in cases),"unexpected; no persisted delta:",before==after)

def linked_identity():
    from apps.accounts.services import update_personal_settings
    from apps.workforce.person_services import create_person, create_work_relationship
    from apps.workforce.models import Employee
    from datetime import date
    import importlib.util
    OLD["guard"]()
    assert not (OUT/"EMPLOYMENT_IDENTITY.json").exists()
    org = Organization.objects.get(slug="demo-construction-01")
    hr = User.objects.get(username="uiux.wavec.hr")
    user = User.objects.get(username="uiux.wavec.time")
    update_personal_settings(user=user,data={"first_name":"Wave C","last_name":"Linked synthetic employee","email":"","phone_number":"","profile_image":None})
    spec = importlib.util.spec_from_file_location("wave_http",OUT/"http_validation.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    employee = Employee.objects.filter(organization=org,user=user,employee_number="WAVE-C-LINKED").first()
    if employee is None:
        status,body,url = module.request(hr.username,"/workforce/employees/create/",{"source_type":"existing_account","user":str(user.pk),"employee_number":"WAVE-C-LINKED","hire_date":"1405/07/30"})
    else:
        from django.urls import reverse
        status,body,url = module.request(hr.username,reverse("workforce:employee_detail",args=[employee.pk]))
    assert status == 200 and "/create/" not in url, (status,url)
    employee = Employee.objects.get(organization=org,user=user,employee_number="WAVE-C-LINKED")
    assert employee.first_name == "Wave C" and employee.last_name == "Linked synthetic employee"
    OLD["guard"]()
    person = create_person(organization=org,actor=hr,first_name=employee.first_name,last_name=employee.last_name,user=user)
    relationship = create_work_relationship(organization=org,actor=hr,person=person,employee_number=employee.employee_number,effective_start=date(2026,10,22),legacy_employee=employee)
    save("EMPLOYMENT_IDENTITY.json",{"http_status":status,"final_path":url.removeprefix("http://127.0.0.1:8015"),"response_sha256":hashlib.sha256(body).hexdigest(),"user":str(user.pk),"employee":str(employee.pk),"person":str(person.pk),"relationship":str(relationship.pk),"resolution":"Explicit Employee.user AND explicit existing Person.user and WorkRelationship. No inferred identity.","own_history_authority":"BLOCKED: employment_records.view_own remains unassignable through existing delegation"})
    print("Known-account HTTP reuse and explicit Employee/User/Person/relationship linkage verified")

if __name__ == "__main__":
    globals()[sys.argv[1]]()

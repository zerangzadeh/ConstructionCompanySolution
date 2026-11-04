import os, sys, json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from datetime import timedelta

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django
django.setup()
from django.db import connections
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from psycopg import sql
from apps.documents.test_evidence_integration import EvidenceIntegrationTests
from apps.documents.services import add_document_link, add_document_version
from apps.safety.record_review import submit_safety_record
from apps.quality.record_review import submit_quality_record
from apps.daily_reports.field_services import attach_field_evidence, submit_field_observation
from apps.contracts.contractual_services import add_contractual_evidence, submit_contractual_record
from apps.billing import commercial_services as cs

SOURCE = "test_bonira_related_documents_phase1_20261104"
PREVIEW = "test_bonira_phase3_ux_" + uuid4().hex[:10]
conn = connections["default"]
original = conn.settings_dict["NAME"]
conn.settings_dict["NAME"] = SOURCE
with conn.cursor() as cursor:
    cursor.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(sql.Identifier(PREVIEW), sql.Identifier(SOURCE)))
conn.close()
conn.settings_dict["NAME"] = PREVIEW
out = Path(__file__).parent

try:
    with TemporaryDirectory(prefix="bonira-phase3-preview-") as temp, override_settings(MEDIA_ROOT=temp, DOCUMENT_PROTECTED_ROOT=temp, PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
        fx = EvidenceIntegrationTests()
        fx.setUp()
        try:
            commercial = fx.commercial()
            common = {"organization": fx.organization, "actor": fx.owner}
            document = fx._create_document(reference="UX-PINNED", title="گواهی کنترل کیفیت مصالح و گزارش بازبینی کارگاه برای آزمایش نمایش عنوان بلند سند")
            v1 = document.current_version
            fx.clean_version(v1)
            quarantine = fx._create_document(reference="UX-QUARANTINE", title="شاهد قرنطینه برای بررسی")
            expired = fx._create_document(reference="UX-EXPIRED", title="شاهد منقضی آزمایشی")
            project_b = fx.other_organization
            safety, quality, material, observation = fx.safety(), fx.quality(), fx.material(), fx.observation()
            from apps.contracts.contractual_services import create_contractual_record
            contractual = create_contractual_record(**common, contract=fx.contract, kind="claim", record_number="UX-CCR", title="درخواست قراردادی آزمایشی", description="نمونه بررسی رابط شواهد", idempotency_key="ux-contractual")
            add_document_link(document=document, actor=fx.owner, target=material)
            attach_field_evidence(**common, observation_id=observation.pk, document_version_id=v1.pk, operation_key=uuid4())
            for version, label in [(v1,"شاهد نسخه نخست"),(quarantine.current_version,"شاهد در انتظار بررسی"),(expired.current_version,"شاهد منقضی")]:
                add_contractual_evidence(**common, record=contractual, label=label, document_version=version)
            expired.access_expires_at=timezone.now()-timedelta(days=1)
            expired.save(update_fields=["access_expires_at"])
            from apps.safety.services import create_safety_incident
            from apps.quality.services import create_quality_issue
            safety_final=create_safety_incident(**common,project=fx.project,incident_number="UX-S-FINAL",occurred_at=timezone.now(),incident_type="near_miss",severity="high",description="بازبینی ارسال شده")
            quality_final=create_quality_issue(**common,project=fx.project,issue_number="UX-Q-FINAL",identified_at=timezone.now(),issue_type="nonconformance",severity="major",description="بازبینی ارسال شده")
            # Separate project witnesses remain eligible for review; the material pin
            # above adds an org-master context and is intentionally ineligible there.
            review_document=fx._create_document(reference="UX-REVIEW",title="شاهد کنترل بازبینی کارگاه")
            review_v1=review_document.current_version
            fx.clean_version(review_v1)
            for obj, submit, key in [(safety_final,submit_safety_record,"incident_id"),(quality_final,submit_quality_record,"issue_id")]:
                submit(**common, **{key: obj.pk}, reason="آزمون بازبینی", document_version_ids=[review_v1.pk,quarantine.current_version.pk])
            add_document_version(document=review_document, actor=fx.owner, upload=fx._pdf_upload(suffix=b"UX v2"))
            add_document_version(document=document, actor=fx.owner, upload=fx._pdf_upload(suffix=b"UX v2"))
            add_document_version(document=fx.evidence.document, actor=fx.owner, upload=fx._pdf_upload(suffix=b"UX commercial v2"))
            for kind,obj in commercial:
                operations={"guarantee":(cs.submit_guarantee,cs.decide_guarantee,"guarantee"),"compliance":(cs.submit_compliance_evidence,cs.decide_compliance_evidence,"evidence"),"release":(cs.submit_retention_release,cs.decide_retention_release,"release")}
                submit, decide, key=operations[kind]
                submit(**common,**{key:obj})
                decide(organization=fx.organization,actor=fx.manager,**{key:obj},approved=True,reason="تأیید مستقل آزمایشی")
            scope=[("safety",safety_final),("quality",quality_final),("material",material),("field_observation",observation),("contractual",contractual),*commercial]
            result={}
            for kind,obj in scope:
                panel=fx.panel(kind,obj)
                result[kind]={"detail":panel.source.url.split("#")[0],"register":panel.register_url,"view":panel.rows[0].view_url,"download":panel.rows[0].download_url}
            result["safety"]["register"]=fx.panel("safety",safety).register_url
            result["quality"]["register"]=fx.panel("quality",quality).register_url
            for kind,route in [("guarantee","guarantee_create"),("compliance","compliance_evidence_create"),("release","retention_release_create")]:
                result[kind]["create"]=reverse("billing:"+route)
            result["empty"]={"safety":fx.panel("safety",safety).source.url,"quality":fx.panel("quality",quality).source.url}
            from apps.organizations.models import OrganizationRole, MembershipRoleAssignment, MembershipScopeGrant, BusinessPermission
            from apps.accounts.models import User
            from apps.organizations.models import OrganizationMembership
            for login,codes in [("ux-reader",["documents.view","projects.view","safety_incidents.view","quality_issues.view","field_observations.view","materials.view","contractual_records.view","guarantees.view","compliance_evidence.view","retention_releases.view"]),("ux-restricted",["safety_incidents.view","quality_issues.view","field_observations.view","materials.view","contractual_records.view","guarantees.view","compliance_evidence.view","retention_releases.view"])]:
                user=User.objects.create_user(username=login,password="test-password")
                role=OrganizationRole.objects.create(organization=fx.organization,code=login,name="نقش آزمایشی")
                role.permissions.set(BusinessPermission.objects.filter(code__in=codes))
                mem=OrganizationMembership.objects.create(organization=fx.organization,user=user,status="active",role_definition=role)
                MembershipRoleAssignment.objects.create(organization=fx.organization,membership=mem,role=role,reason="Visual UAT")
                MembershipScopeGrant.objects.create(organization=fx.organization,membership=mem,scope_type="organization",reason="Visual UAT")
            (out/"preview-routes.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
            print("Isolated preview ready on 127.0.0.1:8013",flush=True)
            call_command("runserver","127.0.0.1:8013",use_reloader=False)
        finally:
            fx.doCleanups()
finally:
    conn.close()
    conn.settings_dict["NAME"]=SOURCE
    with conn.cursor() as cursor:
        cursor.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(PREVIEW)))
    conn.close()
    conn.settings_dict["NAME"]=original

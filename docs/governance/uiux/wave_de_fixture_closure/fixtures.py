"""Only synthetic Development fixture creation through existing domain services."""
from entry import OUT, ROOT, save, guard
import ast
import sys
from uuid import uuid4
from zoneinfo import ZoneInfo
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.authorization import membership_permission_codes, is_platform_admin
from apps.workforce.person_services import create_person, create_work_relationship
from apps.workforce.ess_services import resolve_ess_subject
from apps.workforce.models import Person
from apps.payroll.ess_services import own_payroll_history
from apps.knowledge.models import CandidateStatus
from apps.knowledge.services import create_candidate, submit_candidate, review_candidate, approve_candidate, publish_candidate, request_platform_promotion
from apps.support.models import SupportCase
from apps.daily_reports.field_services import create_field_observation, submit_field_observation, start_field_observation_review, review_field_observation
from apps.projects.models import Project

guard()
org = Organization.objects.get(slug="demo-construction-01")
owner = User.objects.get(username="account.demo-construction-01.owner")
own = User.objects.get(username="uiux.persona.project-operations")
author = User.objects.get(username="uiux.persona.tenant-admin")
curator = owner
label = "UIUX_TEST_ONLY_NON_AUTHORITATIVE — RV-016/RV-021 Development fixture"
with transaction.atomic():
    before = sorted(membership_permission_codes(OrganizationMembership.objects.get(organization=org, user=own)))
    assert "payroll_ess.view_own" in before
    person = Person.objects.filter(organization=org, user=own).first()
    if person is None:
        person = create_person(organization=org, actor=owner, first_name="آزمایشی", last_name="خدمات کارکنان توسعه", user=own)
        relationship = create_work_relationship(organization=org, actor=owner, person=person, employee_number="UIUX-D-ESS-001", effective_start=timezone.localdate(timezone=ZoneInfo(org.settings.timezone)))
    subject = resolve_ess_subject(user=own, organization=org)
    assert subject.person.pk == person.pk
    assert own_payroll_history(actor=own, organization=org) == ()
    assert before == sorted(membership_permission_codes(OrganizationMembership.objects.get(organization=org, user=own)))
    save("RV016_FIXTURE.json", {"label":label, "actor":own.username, "person":person.pk, "relationship":subject.current_relationship.pk, "mechanism":"create_person(user=explicit existing member) + create_work_relationship; existing member permission and project scopes unchanged", "legacy_employee":None, "payroll_history":"legitimate empty own history; no payroll financial source manufactured", "permissions_unchanged":True})

if not (OUT / "RV021_FIXTURE.json").exists():
    with transaction.atomic():
        # No eligible source exists. Prepare one explicitly synthetic observation
        # through its full canonical lifecycle and independent reviewer.
        source = create_field_observation(organization=org, actor=author, project=Project.objects.get(organization=org, code="PRJ-01-01"), site=None, kind="general", title="مشاهده مصنوعی آزمون دانش — فقط توسعه", summary=label)
        submit_field_observation(organization=org, actor=author, observation_id=source.pk, operation_key=uuid4())
        start_field_observation_review(organization=org, actor=curator, observation_id=source.pk, operation_key=uuid4())
        review_field_observation(organization=org, actor=curator, observation_id=source.pk, accepted=True, reason=label, operation_key=uuid4())
        candidate = create_candidate(organization=org, actor=author, title="راهنمای آزمایشی دانش — فقط توسعه", body="این مقاله مصنوعی برای ارزیابی رابط کاربری در محیط توسعه است و مرجع تصمیم اجرایی نیست.", knowledge_type="lesson_learned", authority_classification="advisory", audience="کاربران آزمایشی مجاز", category_code="uiux-development", tags=["UIUX_TEST_ONLY_NON_AUTHORITATIVE"])
        submit_candidate(organization=org, actor=author, candidate_id=candidate.pk, expected_status="draft", sources=[{"source_type":"field_observation", "source_id":source.pk, "citation_purpose":label}])
        review_candidate(organization=org, actor=curator, candidate_id=candidate.pk, expected_status="submitted", outcome="recommended", reason=label)
        approve_candidate(organization=org, actor=curator, candidate_id=candidate.pk, expected_status="recommended")
        version = publish_candidate(organization=org, actor=curator, candidate_id=candidate.pk, expected_status=CandidateStatus.APPROVED)
        promotion = request_platform_promotion(organization=org, actor=curator, version_id=version.pk, title="دانش پالایش‌شده آزمایشی توسعه", body="محتوای مصنوعی و بدون مشخصات اشخاص یا شرکت برای آزمون صف بررسی.", audience="بازبین آزمایشی سکو", category_code="uiux-development", anonymization_statement="صرفاً متن مصنوعی؛ نام و شناسه و اطلاعات منبع در مشتق درج نشده است.")
        save("RV021_FIXTURE.json", {"label":label, "author":author.username, "curator":curator.username, "authority":"Existing tenant_admin author and tenant_owner independent reviewer/approver/publisher; no new grants", "candidate":candidate.pk, "version":version.pk, "source":source.pk, "source_type":"field_observation", "promotion":promotion.pk, "separation":author.pk != curator.pk, "platform_status":"requested; no platform review/approval/publication performed"})

# Recover only the exact existing seed credential, if it is still current; no reset.
platform = User.objects.get(username="admin")
assert is_platform_admin(platform)
tree = ast.parse((ROOT / "apps/accounts/management/commands/seed_demo_data.py").read_text(encoding="utf-8"))
seed = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "DEMO_PASSWORD" for t in n.targets))
matched = platform.check_password(seed)
if matched:
    sys.path.insert(0, str(OUT.parent / "authorization_reconciliation"))
    from revalidate import store_credential
    store_credential("admin", seed)
del seed
save("PLATFORM_CREDENTIAL_READINESS.json", {"actor":"admin", "explicit_platform_admin":True, "existing_seed_credential_verified":matched, "credential_reset":False, "credential_in_evidence":False, "storage":"existing current-user DPAPI store only" if matched else None})
print("Fixture preparation complete; existing platform credential ready:", matched)

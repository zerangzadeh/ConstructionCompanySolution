"""Bounded MVP demonstration, using existing tenant/domain authorities.

No reset, global catalog editing, policy publication, passwords, or posting to
financial domains. Existing owned tenants are preserved, including UAT changes.
"""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.billing import services as billing
from apps.contracts import services as contracts
from apps.contracts.models import ContractTermVersion
from apps.daily_reports import services as reports
from apps.equipment import p8_services as equipment_operations
from apps.equipment import services as equipment
from apps.estimates import services as estimates
from apps.estimates.workflow import request_estimate_approval
from apps.expenses.services import create_expense, create_expense_category
from apps.inventory.services import create_warehouse
from apps.materials import services as materials
from apps.organizations.models import (
    MembershipRoleAssignment,
    MembershipScopeGrant,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import create_organization_with_owner
from apps.parties.services import assign_party_role, create_business_party
from apps.projects import services as projects
from apps.quality.services import create_quality_issue
from apps.safety.services import create_safety_incident
from apps.timekeeping import services as timekeeping
from apps.workforce.field_services import save_field_employee
from apps.workforce.services import assign_employee_to_project, create_work_team

DAY = date(2026, 11, 3)
START = datetime(2026, 11, 3, 8, tzinfo=ZoneInfo("Asia/Tehran"))
SLUG = "mvp08-synthetic-demo"
MARKER = "MVP-08 synthetic demonstration; no customer data"


def guard_environment() -> None:
    # A DEBUG flag or imported pytest module alone must never authorize seeding.
    if (
        settings.SETTINGS_MODULE != "config.settings.development"
        or not settings.DEBUG
        or connection.vendor != "postgresql"
        or str(connection.settings_dict["HOST"]).lower()
        not in {"localhost", "127.0.0.1", "::1"}
    ):
        raise CommandError("MVP demo requires local config.settings.development.")


def tenant_counts(organization: Organization) -> dict[str, int]:
    return {
        model._meta.label: model.objects.filter(organization=organization).count()
        for model in apps.get_models()
        if any(f.name == "organization" for f in model._meta.fields)
    }


class Command(BaseCommand):
    help = "Prepare owned, synthetic MVP demo tenants; preserve all existing state."

    def add_arguments(self, parser):
        parser.add_argument(
            "--rfq-duty-personas",
            action="store_true",
            help="Authorized five-account RFQ fixture extension in the retained UAT copy only.",
        )
        parser.add_argument(
            "--terms-source",
            required=True,
            help="Existing independently approved receivable term version UUID.",
        )

    def user(self, suffix: str, label: str) -> User:
        username = f"mvp08.{suffix}"
        user = User.objects.filter(username=username).first()
        email = f"{username}@example.test"
        if user:
            if user.email != email or user.is_superuser or user.is_staff:
                raise CommandError(f"Refusing unowned persona collision: {username}")
            return user
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=label,
            last_name="نمونه",
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])
        return user

    def member(self, organization, user, role_code, *, project=None, site=None):
        """Explicit native fixture bootstrap, confined to a newly owned tenant.

        Same seed convention as existing journey fixtures, retaining native role,
        scope, actor provenance and audit rather than trusting legacy role text.
        No permission catalog/default is edited and no custom broad role is made.
        """
        role = OrganizationRole.objects.get(
            organization__isnull=True,
            code=role_code,
            is_active=True,
        )
        membership = OrganizationMembership.objects.create(
            organization=organization,
            user=user,
            role=role_code,
            role_definition=role,
            status="active",
        )
        MembershipRoleAssignment.objects.create(
            organization=organization,
            membership=membership,
            role=role,
            reason=MARKER,
            source="demo_fixture",
        )
        MembershipScopeGrant.objects.create(
            organization=organization,
            membership=membership,
            scope_type="site" if site else "project" if project else "organization",
            project=project,
            site=site,
            reason=MARKER,
            source="demo_fixture",
        )
        for action in (
            AuditAction.MEMBERSHIP_ROLE_ASSIGNED,
            AuditAction.MEMBERSHIP_SCOPE_GRANTED,
        ):
            record_audit_event(
                action=action,
                organization=organization,
                actor=user,
                entity_type="organization_membership",
                entity_id=membership.pk,
                metadata={
                    "source": "demo_fixture",
                    "role": role_code,
                    "reason": MARKER,
                },
            )
        return membership

    def handle(self, *args, **options):
        guard_environment()
        if (
            options.get("rfq_duty_personas")
            and connection.settings_dict["NAME"] != "test_bonira_mvp08_demo_20261103"
        ):
            raise CommandError(
                "RFQ duty extension is restricted to the retained MVP-08 UAT copy."
            )
        result = self._seed(options)
        # Organization bootstrap schedules native starter workflows on commit.
        # Count only after those callbacks have completed, not inside the seed
        # transaction, so first-run evidence includes the complete resulting state.
        before = result.pop("_before")
        after = tenant_counts(Organization.objects.get(slug=SLUG))
        created = {
            label: count - before.get(label, 0) for label, count in after.items()
        }
        if any(count < 0 for count in created.values()):
            raise CommandError("Concurrent removal invalidated demo count evidence.")
        result["created"] = created if any(created.values()) else 0
        result["existing"] = before or 0
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))

    def _rfq_duty_personas(self, organization):
        if connection.settings_dict["NAME"] != "test_bonira_mvp08_demo_20261103":
            raise CommandError(
                "RFQ duty extension is restricted to the retained MVP-08 UAT copy."
            )
        project = organization.projects.get(code="MVP08-P01")
        definitions = (
            ("rfq-custodian", "مسئول نگهداری پیشنهاد", ("rfq_custodian",)),
            ("rfq-opening-approver", "بازبین مستقل گشایش", ("rfq_opening_approver",)),
            ("rfq-preparer", "تهیه‌کننده بررسی خرید", ("tenant_manager", "rfq_opener")),
            ("rfq-reviewer", "بازبین مستقل خرید", ("tenant_manager", "rfq_opener")),
            ("rfq-evaluator", "ارزیاب مستقل خرید", ("tenant_manager", "rfq_opener")),
        )
        for suffix, label, roles in definitions:
            actor = self.user(suffix, label)
            membership = organization.memberships.filter(user=actor).first()
            if membership is None:
                if actor.organization_memberships.exists():
                    raise CommandError(
                        "Refusing an existing cross-tenant duty-account collision."
                    )
                membership = self.member(organization, actor, roles[0], project=project)
                for code in roles[1:]:
                    assignment = MembershipRoleAssignment.objects.create(
                        organization=organization,
                        membership=membership,
                        role=OrganizationRole.objects.get(
                            organization=None, code=code, is_active=True
                        ),
                        reason="Explicit Human authorization of revised five-account MVP-08 RFQ fixture; existing personas unchanged.",
                        source="demo_fixture",
                    )
                    record_audit_event(
                        action=AuditAction.MEMBERSHIP_ROLE_ASSIGNED,
                        organization=organization,
                        actor=actor,
                        entity_type="organizations.MembershipRoleAssignment",
                        entity_id=assignment.pk,
                        metadata={
                            "source": "demo_fixture",
                            "role": code,
                            "reason": assignment.reason,
                        },
                    )
            assigned = set(
                membership.role_assignments.filter(revoked_at=None).values_list(
                    "role__code", flat=True
                )
            )
            scopes = list(
                membership.scope_grants.filter(revoked_at=None).values(
                    "scope_type", "project_id", "site_id"
                )
            )
            if assigned != set(roles) or scopes != [
                {"scope_type": "project", "project_id": project.pk, "site_id": None}
            ]:
                raise CommandError(
                    "Existing duty fixture authority differs; preserve it and investigate."
                )

    @transaction.atomic
    def _seed(self, options):
        # Serialize retries before checking either the tenant or persona namespace.
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [800820261103])
        try:
            source = ContractTermVersion.objects.select_related(
                "contract", "insurance_classification"
            ).get(pk=options["terms_source"], status="approved")
        except (ContractTermVersion.DoesNotExist, ValueError, ValidationError) as exc:
            raise CommandError(
                "Existing approved contract terms are required."
            ) from exc
        if (
            source.contract.direction != "receivable"
            or not source.insurance_classification_id
            or source.created_by_id == source.approved_by_id
        ):
            raise CommandError("Term source lacks independent receivable approval.")
        owner = self.user("admin", "مدیر شرکت")
        existing = Organization.objects.filter(slug=SLUG).first()
        if existing:
            if existing.legal_name != MARKER or existing.created_by_id != owner.pk:
                raise CommandError("Refusing unowned demo tenant collision.")
            counts = tenant_counts(existing)
            if not existing.projects.filter(code="MVP08-P01").exists():
                raise CommandError(
                    "Incomplete owned demo; explicit investigation required."
                )
            if options.get("rfq_duty_personas"):
                self._rfq_duty_personas(existing)
            return {
                "tenant": SLUG,
                "_before": counts,
                "preserved": "All lifecycle states, records, credentials and UAT edits",
            }
        if Organization.objects.filter(slug=SLUG + "-isolated").exists():
            raise CommandError("Refusing isolated-tenant namespace collision.")
        organization = create_organization_with_owner(
            owner=owner,
            name="شرکت ساختمانی سروستان — نمونه آموزشی",
            legal_name=MARKER,
            slug=SLUG,
            timezone_name="Asia/Tehran",
            currency="IRR",
        )
        owner_membership = organization.memberships.get(user=owner)
        MembershipRoleAssignment.objects.create(
            organization=organization,
            membership=owner_membership,
            role=OrganizationRole.objects.get(code="tenant_admin", organization=None),
            reason=MARKER,
            source="demo_fixture",
        )
        actor = self.user("operator", "مسئول عملیات")
        reviewer = self.user("reviewer", "بازبین مستقل")
        buyer = self.user("buyer", "مسئول خرید")
        evaluator = self.user("evaluator", "ارزیاب پیشنهاد")
        for user in (actor, reviewer, buyer, evaluator):
            self.member(organization, user, "tenant_manager")
        project = projects.create_project(
            organization=organization,
            actor=actor,
            code="MVP08-P01",
            name="مجتمع مسکونی سروستان — نمونه",
            status="active",
            start_date=date(2026, 10, 1),
            description=MARKER,
        )
        site = projects.create_project_site(
            organization=organization,
            actor=actor,
            project=project,
            code="MVP08-S01",
            name="کارگاه اصلی سروستان — نمونه",
        )
        create_warehouse(
            organization=organization,
            actor=actor,
            project=project,
            code="MVP08-WH01",
            name="انبار کارگاه سروستان — نمونه",
        )
        for suffix, label, role, scope in (
            ("site", "سرپرست کارگاه", "supervisor", site),
            ("restricted", "کاربر محدود", "member", site),
        ):
            self.member(
                organization,
                self.user(suffix, label),
                role,
                project=project,
                site=scope,
            )
        phase = projects.create_project_phase(
            organization=organization,
            actor=actor,
            site=site,
            name="اجرای سازه",
            code="MVP08-PH01",
            status="active",
        )
        wbs = projects.create_wbs_node(
            organization=organization,
            actor=actor,
            project=project,
            code="MVP08-W01",
            title="فونداسیون",
        )
        activity = projects.create_activity(
            organization=organization,
            actor=actor,
            project=project,
            code="MVP08-A01",
            name="بتن‌ریزی فونداسیون",
            phase=phase,
            site=site,
            wbs_node=wbs,
        )
        unit = materials.create_unit_of_measure(
            organization=organization,
            actor=actor,
            code="MVP08-M3",
            name="متر مکعب",
            symbol="m3",
            category="volume",
        )
        materials.create_material(
            organization=organization,
            actor=actor,
            code="MVP08-M01",
            name="بتن آماده نمونه",
            unit_of_measure=unit,
        )
        supplier = create_business_party(
            organization=organization,
            actor=actor,
            party_kind="company",
            display_name="تأمین مصالح سروستان — نمونه",
        )
        assign_party_role(
            organization=organization, actor=actor, party=supplier, role="supplier"
        )
        employer = create_business_party(
            organization=organization,
            actor=actor,
            party_kind="company",
            display_name="کارفرمای سروستان — نمونه",
        )
        team = create_work_team(
            organization=organization,
            actor=actor,
            code="MVP08-T01",
            name="اکیپ بتن‌ریزی نمونه",
        )
        employee = save_field_employee(
            organization=organization,
            actor=actor,
            employee_number="MVP08-WORK01",
            first_name="رضا",
            last_name="نمونه",
            national_id="",
            start_date=date(2026, 10, 1),
            work_team=team,
        )
        assign_employee_to_project(
            organization=organization,
            actor=actor,
            employee=employee,
            project=project,
            site=site,
            start_date=date(2026, 10, 1),
            role_title="بتن‌ریز نمونه",
        )
        report = reports.create_daily_report(
            organization=organization,
            actor=actor,
            project=project,
            site=site,
            phase=phase,
            reporting_date=DAY,
            work_performed="آماده‌سازی و بتن‌ریزی فونداسیون — داده آموزشی",
            labor_count=1,
        )
        reports.add_daily_activity(
            organization=organization,
            actor=actor,
            report_id=str(report.pk),
            activity=activity,
            description="بتن‌ریزی نمونه",
            quantity=Decimal(5),
            unit_of_measure=unit,
        )
        machine = equipment.create_equipment(
            organization=organization,
            actor=actor,
            code="MVP08-EQ01",
            name="پمپ بتن نمونه",
            category="پمپ بتن",
            ownership_type="owned",
        )
        deployment = equipment.assign_equipment(
            organization=organization,
            actor=actor,
            equipment=machine,
            project=project,
            site=site,
            start_date=date(2026, 10, 1),
            purpose="بتن‌ریزی فونداسیون نمونه",
        )
        equipment_operations.record_usage(
            organization=organization,
            actor=actor,
            equipment=machine,
            deployment=deployment,
            started_at=START,
            ended_at=START + timedelta(hours=2),
            runtime_hours=Decimal(2),
            source_key="MVP08-USAGE01",
            evidence_reference="گزارش روزانه نمونه",
        )
        calendar = timekeeping.create_work_calendar(
            organization=organization,
            actor=actor,
            code="MVP08-CAL01",
            name="تقویم کارگاه نمونه",
            effective_from=date(2026, 10, 1),
            working_weekdays=[1, 2, 3, 4, 5, 6],
        )
        timekeeping.capture_attendance(
            organization=organization,
            actor=actor,
            employee=employee,
            calendar=calendar,
            project=project,
            site=site,
            work_date=DAY,
            check_in_at=START,
            check_out_at=START + timedelta(hours=8),
            source_reference="MVP08-ATT01",
        )
        sheet = timekeeping.create_timesheet(
            organization=organization,
            actor=actor,
            employee=employee,
            period_start=DAY,
            period_end=DAY,
            declared_minutes=480,
        )
        timekeeping.add_timesheet_entry(
            organization=organization,
            actor=actor,
            timesheet=sheet,
            work_date=DAY,
            project=project,
            site=site,
            activity=activity,
            minutes=480,
            note="کارکرد نمونه؛ بدون اثر حقوق و دستمزد",
        )
        context = {
            "organization": organization,
            "actor": actor,
            "project": project,
            "site": site,
            "phase": phase,
            "activity": activity,
            "daily_report": report,
        }
        create_safety_incident(
            **context,
            incident_number="MVP08-HSE01",
            occurred_at=START,
            incident_type="near_miss",
            severity="low",
            description="نمونه آموزشی: رفع مانع مسیر عبور",
            immediate_action="مسیر عبور ایمن‌سازی شد",
        )
        create_quality_issue(
            **context,
            issue_number="MVP08-QC01",
            identified_at=START,
            issue_type="inspection",
            severity="minor",
            description="نمونه آموزشی: کنترل قالب پیش از بتن‌ریزی",
        )
        contract = contracts.create_contract(
            organization=organization,
            actor=actor,
            project=project,
            contract_number="MVP08-CTR01",
            title="اجرای سازه سروستان — نمونه",
            party=employer,
            counterparty_name=employer.display_name,
            direction="receivable",
            contract_value=Decimal(100000000),
        )
        contracts.add_contract_item(
            organization=organization,
            actor=actor,
            contract=contract,
            description="بتن‌ریزی فونداسیون",
            quantity=Decimal(10),
            unit_price=Decimal(10000000),
            unit_of_measure=unit,
        )
        estimate = estimates.create_estimate(
            organization=organization,
            actor=actor,
            project=project,
            contract=contract,
            phase=phase,
            estimate_number="MVP08-EST01",
            title="برآورد سازه سروستان — نمونه",
        )
        estimates.add_estimate_item(
            estimate=estimate,
            actor=actor,
            description="بتن‌ریزی فونداسیون",
            quantity=Decimal(10),
            unit_price=Decimal(10000000),
            unit_of_measure=unit,
        )
        request_estimate_approval(actor=actor, estimate=estimate)
        estimates.approve_estimate(estimate=estimate, actor=reviewer)
        contracts.transition_contract_status(
            organization=organization,
            actor=actor,
            contract=contract,
            status="active",
        )
        # Copy only existing approved commercial configuration, not guessed rates.
        fields = (
            "payment_due_days",
            "retention_rate",
            "retention_cap",
            "advance_recovery_rate",
            "advance_recovery_cap",
            "contractual_insurance_rate",
            "contractual_insurance_cap",
            "retention_release_requirement",
            "retention_release_cap",
            "insurance_classification",
        )
        term = contracts.create_contract_term_version(
            organization=organization,
            actor=actor,
            contract=contract,
            effective_from=date(2026, 11, 1),
            reason=f"{MARKER}; configured source {source.pk}",
            **{field: getattr(source, field) for field in fields},
        )
        contracts.approve_contract_term_version(
            organization=organization,
            actor=reviewer,
            term_version=term,
            reason="بازبینی مستقل شرایط نمونه برگرفته از تنظیمات موجود",
        )
        baseline = billing.create_project_baseline(
            organization=organization,
            actor=actor,
            project=project,
            contract=contract,
            effective_date=date(2026, 11, 1),
        )
        line = billing.add_baseline_item(
            organization=organization,
            actor=actor,
            baseline=baseline,
            line_key="MVP08-BOQ01",
            description="بتن‌ریزی فونداسیون",
            unit="متر مکعب",
            planned_quantity=Decimal(10),
            unit_rate=Decimal(10000000),
        )
        billing.request_project_baseline_approval(
            organization=organization,
            actor=actor,
            baseline=baseline,
        )
        billing.approve_project_baseline(
            organization=organization,
            actor=reviewer,
            baseline=baseline,
            reason="کنترل مستقل مبنای تجاری نمونه",
        )
        progress = billing.create_progress_record(
            organization=organization,
            actor=actor,
            baseline=baseline,
            baseline_item=line,
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 30),
            measured_on=DAY,
            source_type="daily_report",
            source_reference="MVP08-REPORT01",
            evidence="گزارش بتن‌ریزی نمونه کارگاه سروستان",
            period_quantity=Decimal(5),
            cumulative_quantity=Decimal(5),
        )
        billing.request_progress_verification(
            organization=organization,
            actor=actor,
            record=progress,
        )
        billing.verify_progress_record(
            organization=organization,
            actor=reviewer,
            record=progress,
            reason="کنترل مستقل اندازه‌گیری نمونه",
        )
        category = create_expense_category(
            organization=organization,
            actor=actor,
            code="MVP08-EXP01",
            name="هزینه‌های کارگاه نمونه",
        )
        create_expense(
            organization=organization,
            actor=actor,
            project=project,
            expense_category=category,
            description="ملزومات ایمنی نمونه",
            receipt_reference="MVP08-EXP01",
            amount=Decimal(2500000),
            incurred_on=DAY,
        )
        foreign_owner = self.user("foreign", "مدیر شرکت دوم")
        foreign = create_organization_with_owner(
            owner=foreign_owner,
            name="شرکت دوم مستقل — نمونه آموزشی",
            legal_name=MARKER,
            slug=SLUG + "-isolated",
            timezone_name="Asia/Tehran",
            currency="IRR",
        )
        # Owner governance is separate from explicitly assigned business authority.
        role = OrganizationRole.objects.get(code="tenant_manager", organization=None)
        membership = foreign.memberships.get(user=foreign_owner)
        MembershipRoleAssignment.objects.create(
            organization=foreign,
            membership=membership,
            role=role,
            reason=MARKER,
            source="demo_fixture",
        )
        projects.create_project(
            organization=foreign,
            actor=foreign_owner,
            code="MVP08-OTHER01",
            name="پروژه محرمانه شرکت دوم — نمونه",
        )
        return {
            "tenant": SLUG,
            "_before": {},
            "stable_references": [
                project.code,
                site.code,
                estimate.estimate_number,
                contract.contract_number,
                "MVP08-BOQ01",
            ],
            "terms_source": str(source.pk),
            "personas_have_passwords": False,
            "procurement_start": "Master data only; ordinary browser produces full chain",
        }

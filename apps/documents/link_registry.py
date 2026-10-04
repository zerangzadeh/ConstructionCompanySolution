"""Closed platform registry for domain-owned typed document links."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.apps import apps

from apps.organizations.models import BusinessPermissionCode

if TYPE_CHECKING:
    from django.db.models import Model


@dataclass(frozen=True, slots=True)
class DocumentLinkType:
    key: str
    owner: str
    model_label: str
    target_field: str
    view_permission: str
    project_lookup: str | None
    site_lookup: str | None = None
    legacy_compatible: bool = True

    @property
    def model(self) -> type["Model"]:
        return apps.get_model(self.model_label)


DOCUMENT_LINK_TYPES = (
    DocumentLinkType(
        key="material",
        owner="materials",
        model_label="materials.MaterialDocumentLink",
        target_field="material",
        view_permission=BusinessPermissionCode.MATERIALS_VIEW,
        project_lookup=None,
        legacy_compatible=False,
    ),
    DocumentLinkType(
        key="project",
        owner="projects",
        model_label="projects.ProjectDocumentLink",
        target_field="project",
        view_permission=BusinessPermissionCode.PROJECTS_VIEW,
        project_lookup="project_id",
    ),
    DocumentLinkType(
        key="contract",
        owner="contracts",
        model_label="contracts.ContractDocumentLink",
        target_field="contract",
        view_permission=BusinessPermissionCode.CONTRACTS_VIEW,
        project_lookup="contract__project_id",
    ),
    DocumentLinkType(
        key="estimate",
        owner="estimates",
        model_label="estimates.EstimateDocumentLink",
        target_field="estimate",
        view_permission=BusinessPermissionCode.ESTIMATES_VIEW,
        project_lookup="estimate__project_id",
    ),
    DocumentLinkType(
        key="expense",
        owner="expenses",
        model_label="expenses.ExpenseDocumentLink",
        target_field="expense",
        view_permission=BusinessPermissionCode.EXPENSES_VIEW,
        project_lookup="expense__project_id",
    ),
    DocumentLinkType(
        key="payment",
        owner="payments",
        model_label="payments.PaymentDocumentLink",
        target_field="payment",
        view_permission=BusinessPermissionCode.PAYMENTS_VIEW,
        project_lookup="payment__project_id",
    ),
    DocumentLinkType(
        key="daily_report",
        owner="daily_reports",
        model_label="daily_reports.DailyReportDocumentLink",
        target_field="daily_report",
        view_permission=BusinessPermissionCode.DAILY_REPORTS_VIEW,
        project_lookup="daily_report__project_id",
        site_lookup="daily_report__site_id",
    ),
    DocumentLinkType(
        key="employee_qualification",
        owner="workforce",
        model_label="workforce.EmployeeQualificationDocumentLink",
        target_field="qualification",
        view_permission=BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_VIEW,
        project_lookup=None,
        legacy_compatible=False,
    ),
    DocumentLinkType(
        key="employee_training",
        owner="workforce",
        model_label="workforce.EmployeeTrainingDocumentLink",
        target_field="training_record",
        view_permission=BusinessPermissionCode.WORKFORCE_QUALIFICATIONS_VIEW,
        project_lookup=None,
        legacy_compatible=False,
    ),
    DocumentLinkType(
        key="performance_evaluation",
        owner="workforce",
        model_label="workforce.PerformanceEvaluationDocumentLink",
        target_field="performance_evaluation",
        view_permission=BusinessPermissionCode.WORKFORCE_PERFORMANCE_VIEW,
        project_lookup=None,
        legacy_compatible=False,
    ),
)

_BY_KEY = {link_type.key: link_type for link_type in DOCUMENT_LINK_TYPES}


def registered_link_type(key: str) -> DocumentLinkType:
    try:
        return _BY_KEY[key]
    except KeyError as exc:
        raise ValueError("نوع لینک سند در رجیستری بسته ثبت نشده است.") from exc


def create_typed_link(
    *,
    target_type: str,
    target: Any,
    legacy_link: Any | None = None,
    organization: Any | None = None,
    document: Any | None = None,
    created_by: Any | None = None,
    document_version: Any | None = None,
) -> Any:
    link_type = registered_link_type(target_type)
    if legacy_link is not None:
        organization = legacy_link.organization
        document = legacy_link.document
        created_by = legacy_link.created_by
    if organization is None or document is None:
        raise ValueError("لینک سند به سازمان و سند نیاز دارد.")
    link_fields = {
        "organization": organization,
        "document": document,
        "created_by": created_by,
        link_type.target_field: target,
    }
    if legacy_link is not None:
        link_fields.update(id=legacy_link.pk, legacy_link_id=legacy_link.pk)
    # Version-aware typed evidence must not silently begin to point at a later
    # revision of the underlying DMS document.
    if any(
        field.name == "document_version" for field in link_type.model._meta.fields
    ):
        link_fields["document_version"] = document_version or document.current_version
    return link_type.model.objects.create(
        **link_fields,
    )


def typed_links_for_document(document: Any) -> list[Any]:
    links: list[Any] = []
    for link_type in DOCUMENT_LINK_TYPES:
        links.extend(
            link_type.model.objects.filter(document=document).select_related(
                link_type.target_field
            )
        )
    return links

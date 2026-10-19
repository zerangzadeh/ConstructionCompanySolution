from django.urls import path

from apps.workforce import certificate_views as certificates
from apps.workforce import personal_change_views as personal
from apps.workforce import views
from apps.workforce import ess_timekeeping_views as own_time
from apps.workforce.employment_views import employment_history

app_name = "workforce"

urlpatterns = [
    path("ess/timekeeping/",own_time.index,name="ess_timekeeping"),
    path("ess/timekeeping/<str:kind>/new/",own_time.create,name="ess_timekeeping_create"),
    path("ess/timekeeping/<str:kind>/<uuid:record_id>/",own_time.detail,name="ess_timekeeping_detail"),
    path("ess/timekeeping/<str:kind>/<uuid:record_id>/submit/",own_time.submit,name="ess_timekeeping_submit"),
    path("ess/timekeeping/<str:kind>/<uuid:record_id>/request/",own_time.edit_source,name="ess_timekeeping_edit_source"),
    path("ess/employment/", employment_history, name="employment_history"),
    path("ess/evidence/",certificates.evidence,name="own_evidence"),
    path("ess/certificates/",certificates.index,name="certificate_index"),
    path("ess/certificates/new/",certificates.create,name="certificate_create"),
    path("ess/certificates/<uuid:request_id>/",certificates.detail,name="certificate_detail"),
    path("ess/certificates/<uuid:request_id>/generate/",certificates.generate,name="certificate_generate"),
    path("ess/certificates/<uuid:request_id>/claim/<uuid:work_item_id>/",certificates.claim,name="certificate_claim"),
    path("ess/certificates/<uuid:request_id>/cancel/",certificates.cancel,name="certificate_cancel"),
    path("ess/requests/",personal.requests,name="ess_requests"),
    path("ess/requests/<str:source_type>/<uuid:source_id>/",personal.request_status,name="ess_request_status"),
    path("ess/changes/",personal.inbox,name="personal_change_inbox"),
    path("ess/changes/new/",personal.create,name="personal_change_create"),
    path("ess/changes/<uuid:request_id>/",personal.detail,name="personal_change_detail"),
    path("ess/changes/<uuid:request_id>/claim/<uuid:work_item_id>/",personal.claim,name="personal_change_claim"),
    path("ess/changes/<uuid:request_id>/cancel/",personal.cancel,name="personal_change_cancel"),
    path("", views.employee_list, name="employee_list"),
    path("ess/", views.ess_dashboard, name="ess_dashboard"),
    path("ess/profile/", views.ess_profile, name="ess_profile"),
    path(
        "ess/profile/<uuid:relationship_id>/",
        views.ess_profile,
        name="ess_profile_relationship",
    ),
    path("foundation/", views.workforce_foundation, name="foundation"),
    path("foundation/skills/create/", views.workforce_skill_create, name="skill_create"),
    path("foundation/competencies/create/", views.workforce_competency_create, name="competency_create"),
    path("foundation/employee-skills/create/", views.workforce_employee_skill_create, name="employee_skill_create"),
    path("foundation/qualifications/create/", views.workforce_qualification_create, name="qualification_create"),
    path("foundation/qualifications/<uuid:qualification_id>/revoke/", views.workforce_qualification_revoke, name="qualification_revoke"),
    path("foundation/training-requirements/create/", views.workforce_training_requirement_create, name="training_requirement_create"),
    path("foundation/training-records/create/", views.workforce_training_record_create, name="training_record_create"),
    path("foundation/performance/create/", views.workforce_performance_create, name="performance_create"),
    path("foundation/evidence/<str:target_type>/<uuid:target_id>/upload/", views.workforce_evidence_upload, name="evidence_upload"),
    path("foundation/labor-rates/create/", views.workforce_labor_rate_create, name="labor_rate_create"),
    path("employees/create/", views.employee_create, name="employee_create"),
    path(
        "employees/positions/",
        views.employee_positions,
        name="employee_positions",
    ),
    path(
        "employees/<uuid:employee_id>/", views.employee_detail, name="employee_detail"
    ),
    path(
        "employees/<uuid:employee_id>/profile-image/",
        views.employee_profile_image,
        name="employee_profile_image",
    ),
    path(
        "employees/<uuid:employee_id>/profile-image/update/",
        views.employee_profile_image_update,
        name="employee_profile_image_update",
    ),
    path(
        "employees/<uuid:employee_id>/status/",
        views.employee_status_change,
        name="employee_status_change",
    ),
    path(
        "employees/<uuid:employee_id>/account/link/",
        views.employee_account_link,
        name="employee_account_link",
    ),
    path(
        "employees/<uuid:employee_id>/account/unlink/",
        views.employee_account_unlink,
        name="employee_account_unlink",
    ),
    path(
        "employees/<uuid:employee_id>/positions/assign/",
        views.employee_position_assign,
        name="employee_position_assign",
    ),
    path(
        "employees/<uuid:employee_id>/positions/<uuid:assignment_id>/end/",
        views.employee_position_end,
        name="employee_position_end",
    ),
    path(
        "employees/<uuid:employee_id>/archive/",
        views.employee_archive,
        name="employee_archive",
    ),
    path("departments/", views.department_list, name="department_list"),
    path("departments/create/", views.department_create, name="department_create"),
    path(
        "departments/<uuid:department_id>/",
        views.department_detail,
        name="department_detail",
    ),
    path(
        "departments/<uuid:department_id>/edit/",
        views.department_update,
        name="department_update",
    ),
    path(
        "departments/<uuid:department_id>/archive/",
        views.department_archive,
        name="department_archive",
    ),
    path("positions/", views.position_list, name="position_list"),
    path("positions/create/", views.position_create, name="position_create"),
    path(
        "positions/<uuid:position_id>/",
        views.position_detail,
        name="position_detail",
    ),
    path(
        "positions/<uuid:position_id>/edit/",
        views.position_update,
        name="position_update",
    ),
    path(
        "positions/<uuid:position_id>/archive/",
        views.position_archive,
        name="position_archive",
    ),
    path("teams/", views.work_team_list, name="work_team_list"),
    path("teams/create/", views.work_team_create, name="work_team_create"),
    path(
        "teams/<uuid:team_id>/archive/",
        views.work_team_archive,
        name="work_team_archive",
    ),
    path("assignments/", views.assignment_list, name="assignment_list"),
    path("assignments/create/", views.assignment_create, name="assignment_create"),
    path("assignments/sites/", views.assignment_sites, name="assignment_sites"),
    path(
        "assignments/<uuid:assignment_id>/status/",
        views.assignment_status_change,
        name="assignment_status_change",
    ),
]

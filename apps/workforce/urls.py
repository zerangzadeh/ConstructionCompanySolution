from django.urls import path

from apps.workforce import views

app_name = "workforce"

urlpatterns = [
    path("", views.employee_list, name="employee_list"),
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

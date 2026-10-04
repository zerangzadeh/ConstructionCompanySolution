from django.urls import path

from . import views

app_name = "timekeeping"

urlpatterns = [
    path("", views.workbench, name="workbench"),
    path("calendars/new/", views.calendar_create, name="calendar_create"),
    path("holidays/new/", views.holiday_create, name="holiday_create"),
    path("shifts/new/", views.shift_create, name="shift_create"),
    path("shift-breaks/new/", views.shift_break_create, name="shift_break_create"),
    path("attendance/new/", views.attendance_create, name="attendance_create"),
    path("attendance/import/", views.attendance_import, name="attendance_import"),
    path(
        "attendance/<uuid:record_id>/finalize/",
        views.attendance_finalize,
        name="attendance_finalize",
    ),
    path(
        "attendance/<uuid:record_id>/corrections/new/",
        views.attendance_correction_create,
        name="attendance_correction_create",
    ),
    path(
        "attendance/corrections/<uuid:correction_id>/review/",
        views.attendance_correction_review,
        name="attendance_correction_review",
    ),
    path("leave-mission/new/", views.leave_mission_create, name="leave_mission_create"),
    path(
        "leave-mission/<uuid:request_id>/submit/",
        views.leave_mission_submit,
        name="leave_mission_submit",
    ),
    path(
        "leave-mission/<uuid:request_id>/review/",
        views.leave_mission_review,
        name="leave_mission_review",
    ),
    path("overtime/new/", views.overtime_create, name="overtime_create"),
    path(
        "overtime/<uuid:request_id>/submit/",
        views.overtime_submit,
        name="overtime_submit",
    ),
    path(
        "overtime/<uuid:request_id>/review/",
        views.overtime_review,
        name="overtime_review",
    ),
    path("timesheets/new/", views.timesheet_create, name="timesheet_create"),
    path(
        "timesheets/<uuid:timesheet_id>/",
        views.timesheet_detail,
        name="timesheet_detail",
    ),
    path(
        "timesheets/<uuid:timesheet_id>/submit/",
        views.timesheet_submit,
        name="timesheet_submit",
    ),
    path(
        "timesheets/<uuid:timesheet_id>/review/",
        views.timesheet_review,
        name="timesheet_review",
    ),
    path(
        "timesheets/<uuid:timesheet_id>/preview/",
        views.timesheet_preview,
        name="timesheet_preview",
    ),
]

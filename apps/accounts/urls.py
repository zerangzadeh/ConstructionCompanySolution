from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.UserLoginView.as_view(), name="login"),
    path(
        "password/reset/",
        views.PublicPasswordResetRequestView.as_view(),
        name="password_reset",
    ),
    path(
        "password/reset/done/",
        views.PublicPasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        views.PublicPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        views.PublicPasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path(
        "password/required/",
        views.required_password_change,
        name="required_password_change",
    ),
    path("connection-requests/", views.connection_requests, name="connection_requests"),
    path(
        "connection-requests/<uuid:request_id>/respond/",
        views.connection_request_respond,
        name="connection_request_respond",
    ),
    path("login-background/", views.login_background, name="login-background"),
    path("login-panel-image/", views.login_panel_image, name="login-panel-image"),
    path("settings/", views.personal_settings, name="settings"),
    path("profile-image/", views.profile_image, name="profile-image"),
    path("logout/", views.user_logout, name="logout"),
]

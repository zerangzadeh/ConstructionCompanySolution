from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.UserLoginView.as_view(), name="login"),
    path("login-background/", views.login_background, name="login-background"),
    path("login-panel-image/", views.login_panel_image, name="login-panel-image"),
    path("settings/", views.personal_settings, name="settings"),
    path("profile-image/", views.profile_image, name="profile-image"),
    path("logout/", views.user_logout, name="logout"),
]

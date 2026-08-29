from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from apps.accounts.forms import UserLoginForm


class UserLoginView(LoginView):
    """Authenticate users with the built-in Django authentication flow."""

    authentication_form = UserLoginForm
    template_name = "accounts/login.html"


@require_POST
def user_logout(request: HttpRequest) -> HttpResponse:
    """Log out the current user and clear the authentication session."""

    logout(request)
    return redirect("accounts:login")

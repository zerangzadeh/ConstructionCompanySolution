from django.shortcuts import redirect
from django.urls import Resolver404, resolve


class ForcePasswordChangeMiddleware:
    """Confine temporary-password sessions to password initialization or logout."""

    allowed_url_names = frozenset(
        {"accounts:required_password_change", "accounts:logout"}
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and user.must_change_password:
            try:
                match = resolve(request.path_info)
            except Resolver404:
                return redirect("accounts:required_password_change")
            if match.view_name not in self.allowed_url_names:
                return redirect("accounts:required_password_change")
        return self.get_response(request)

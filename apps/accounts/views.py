import logging
from smtplib import SMTPException

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetConfirmView
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseRedirect,
)
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.crypto import salted_hmac
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.views.generic import TemplateView

from apps.accounts.forms import (
    PersonalPasswordChangeForm,
    PersonalSettingsForm,
    PublicPasswordResetRequestForm,
    PublicPasswordResetSetForm,
    RequiredPasswordChangeForm,
    UserLoginForm,
)
from apps.accounts.models import LoginPageSettings
from apps.accounts.services import (
    change_personal_password,
    initialize_personal_password,
    update_personal_settings,
)
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.models import (
    AccountConnectionRequestStatus,
    OrganizationAccountConnectionRequest,
)
from apps.organizations.services import respond_to_account_connection_request

logger = logging.getLogger(__name__)


def _password_reset_throttle_key(*, category: str, value: str) -> str:
    """Return a cache key that never contains a raw email address or IP."""

    digest = salted_hmac(f"accounts.password_reset.{category}", value).hexdigest()
    return f"accounts:password-reset:{category}:{digest}"


def _password_reset_is_allowed(*, request: HttpRequest, email: str) -> bool:
    """Bound public recovery requests by both source and requested identity."""

    source = request.META.get("REMOTE_ADDR", "")
    duration = settings.PASSWORD_RESET_THROTTLE_SECONDS
    source_allowed = cache.add(
        _password_reset_throttle_key(category="source", value=source),
        True,
        duration,
    )
    identity_allowed = cache.add(
        _password_reset_throttle_key(category="identity", value=email.lower()),
        True,
        duration,
    )
    return source_allowed and identity_allowed


class UserLoginView(LoginView):
    """Authenticate users with the built-in Django authentication flow."""

    authentication_form = UserLoginForm
    redirect_authenticated_user = True
    template_name = "accounts/login.html"

    def get_success_url(self) -> str:
        if self.request.user.must_change_password:
            return reverse("accounts:required_password_change")
        return super().get_success_url()

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context["login_page_settings"] = (
            LoginPageSettings.objects.first() or LoginPageSettings()
        )
        return context


class PublicPasswordResetRequestView(TemplateView):
    """Start recovery without revealing whether an account can receive email."""

    template_name = "accounts/password_reset_form.html"
    form_class = PublicPasswordResetRequestForm
    success_url = reverse_lazy("accounts:password_reset_done")

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context.setdefault("form", self.form_class())
        return context

    def post(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        form = self.form_class(request.POST)
        if form.is_valid() and _password_reset_is_allowed(
            request=request,
            email=form.cleaned_data["email"],
        ):
            try:
                eligible_users = list(form.get_users(form.cleaned_data["email"]))
                if eligible_users:
                    record_audit_event(
                        action=AuditAction.USER_PASSWORD_RESET_REQUESTED,
                        entity_type="user",
                        entity_id=eligible_users[0].pk,
                        metadata={"channel": "email"},
                    )
                    form.save(
                        request=request,
                        use_https=request.is_secure(),
                        email_template_name="accounts/emails/password_reset_email.txt",
                        subject_template_name="accounts/emails/password_reset_subject.txt",
                    )
            except (OSError, SMTPException):
                logger.error("Password-reset email delivery failed.")
        return HttpResponseRedirect(self.success_url)


class PublicPasswordResetDoneView(TemplateView):
    """Show the same completion state for every recovery request."""

    template_name = "accounts/password_reset_done.html"


class PublicPasswordResetConfirmView(PasswordResetConfirmView):
    """Accept Django's signed recovery link and audit a successful reset."""

    form_class = PublicPasswordResetSetForm
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")

    def form_valid(self, form: PublicPasswordResetSetForm) -> HttpResponse:
        user = form.save()
        record_audit_event(
            action=AuditAction.USER_PASSWORD_RESET_COMPLETED,
            entity_type="user",
            entity_id=user.pk,
            actor=user,
            metadata={"channel": "email"},
        )
        return HttpResponseRedirect(self.get_success_url())


class PublicPasswordResetCompleteView(TemplateView):
    """Confirm that a verified recovery flow has completed."""

    template_name = "accounts/password_reset_complete.html"


@login_required
@require_http_methods(["GET", "POST"])
def required_password_change(request: HttpRequest) -> HttpResponse:
    """Require a personal password before allowing any application access."""

    if not request.user.must_change_password:
        return redirect("organizations:select")
    form = RequiredPasswordChangeForm(user=request.user, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        updated_user = initialize_personal_password(
            user=request.user, new_password=form.cleaned_data["new_password1"]
        )
        update_session_auth_hash(request, updated_user)
        messages.success(request, "گذرواژه شخصی شما تعیین شد.")
        return redirect("organizations:select")
    return render(request, "accounts/required_password_change.html", {"form": form})


@login_required
@require_GET
def connection_requests(request: HttpRequest) -> HttpResponse:
    pending_requests = OrganizationAccountConnectionRequest.objects.select_related(
        "organization", "role_definition"
    ).filter(
        target_user=request.user,
        status=AccountConnectionRequestStatus.PENDING,
    )
    return render(
        request,
        "accounts/connection_requests.html",
        {"connection_requests": pending_requests},
    )


@login_required
@require_POST
def connection_request_respond(request: HttpRequest, request_id: str) -> HttpResponse:
    request_record = OrganizationAccountConnectionRequest.objects.filter(
        pk=request_id, target_user=request.user
    ).first()
    if request_record is None:
        raise Http404
    try:
        respond_to_account_connection_request(
            target_user=request.user,
            request_record=request_record,
            accept=request.POST.get("decision") == "accept",
        )
    except (PermissionDenied, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "پاسخ شما ثبت شد.")
    return redirect("accounts:connection_requests")


@login_required
@require_http_methods(["GET", "POST"])
def personal_settings(request: HttpRequest) -> HttpResponse:
    """View and update settings belonging to the authenticated user only."""

    profile_form = PersonalSettingsForm(instance=request.user, prefix="profile")
    password_form = PersonalPasswordChangeForm(user=request.user, prefix="password")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "profile":
            profile_form = PersonalSettingsForm(
                request.POST,
                request.FILES,
                instance=request.user,
                prefix="profile",
            )
            if profile_form.is_valid():
                update_personal_settings(
                    user=request.user,
                    data=profile_form.cleaned_data,
                )
                messages.success(request, "تنظیمات شخصی شما ذخیره شد.")
                return redirect("accounts:settings")
        elif action == "password":
            password_form = PersonalPasswordChangeForm(
                user=request.user,
                data=request.POST,
                prefix="password",
            )
            if password_form.is_valid():
                try:
                    updated_user = change_personal_password(
                        user=request.user,
                        current_password=password_form.cleaned_data["old_password"],
                        new_password=password_form.cleaned_data["new_password1"],
                    )
                except ValidationError as exc:
                    password_form.add_error("old_password", exc)
                else:
                    update_session_auth_hash(request, updated_user)
                    messages.success(request, "گذرواژه شما با موفقیت تغییر کرد.")
                    return redirect("accounts:settings")

    return render(
        request,
        "accounts/settings.html",
        {"profile_form": profile_form, "password_form": password_form},
    )


@login_required
@require_GET
def profile_image(request: HttpRequest) -> FileResponse:
    """Serve only the authenticated user's current private profile image."""

    if not request.user.profile_image:
        raise Http404
    try:
        image = request.user.profile_image.open("rb")
    except (FileNotFoundError, OSError) as exc:
        raise Http404 from exc

    extension = "." + request.user.profile_image.name.lower().rsplit(".", 1)[-1]
    content_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(extension)
    if content_type is None:
        image.close()
        raise Http404
    response = FileResponse(image, content_type=content_type)
    response["Cache-Control"] = "private, max-age=300"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_GET
def login_background(request: HttpRequest) -> FileResponse:
    """Serve only the explicitly public background selected for the login page."""

    settings = LoginPageSettings.objects.first()
    if settings is None or not settings.background_image:
        raise Http404

    try:
        image = settings.background_image.open("rb")
    except (FileNotFoundError, OSError) as exc:
        raise Http404 from exc

    extension = "." + settings.background_image.name.lower().rsplit(".", maxsplit=1)[-1]
    content_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(extension)
    if content_type is None:
        image.close()
        raise Http404
    response = FileResponse(image, content_type=content_type)
    response["Cache-Control"] = "public, max-age=3600"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_GET
def login_panel_image(request: HttpRequest) -> FileResponse:
    """Serve only the explicitly public image selected for the login panel."""

    settings = LoginPageSettings.objects.first()
    if settings is None or not settings.panel_image:
        raise Http404

    try:
        image = settings.panel_image.open("rb")
    except (FileNotFoundError, OSError) as exc:
        raise Http404 from exc

    extension = "." + settings.panel_image.name.lower().rsplit(".", maxsplit=1)[-1]
    content_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(extension)
    if content_type is None:
        image.close()
        raise Http404
    response = FileResponse(image, content_type=content_type)
    response["Cache-Control"] = "public, max-age=3600"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_POST
def user_logout(request: HttpRequest) -> HttpResponse:
    """Log out the current user and clear the authentication session."""

    logout(request)
    return redirect("accounts:login")

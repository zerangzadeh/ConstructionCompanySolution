from django.apps import AppConfig


class RetiredPaymentsConfig(AppConfig):
    name = "core.retired_payments"
    label = "payments"
    verbose_name = "Legacy Payment migration history"

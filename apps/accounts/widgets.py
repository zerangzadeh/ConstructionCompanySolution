from django.forms.widgets import ClearableFileInput


class RtlClearableFileInput(ClearableFileInput):
    """Render stored image paths independently from surrounding RTL labels."""

    template_name = "accounts/widgets/clearable_file_input.html"

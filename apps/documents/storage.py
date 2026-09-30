"""P1 protected-filesystem adapter; production object storage remains gated."""

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class ProtectedDocumentStorage(FileSystemStorage):
    """Filesystem storage that never publishes a raw URL."""

    def __init__(self) -> None:
        super().__init__(base_url=None)

    @property
    def base_location(self) -> str:
        return str(settings.DOCUMENT_PROTECTED_ROOT)

    @property
    def location(self) -> str:
        return str(settings.DOCUMENT_PROTECTED_ROOT)

    def url(self, name: str) -> str:
        del name
        raise ValueError("فایل سند فقط از مسیر مجاز برنامه قابل دریافت است.")


document_storage = ProtectedDocumentStorage()

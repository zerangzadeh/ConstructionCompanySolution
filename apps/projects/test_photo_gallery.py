from tempfile import TemporaryDirectory

from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.daily_reports.models import DailyReport
from apps.documents.models import (
    DocumentProcessingAssessment,
    DocumentType,
    PhotoMetadata,
    PhotoSource,
)
from apps.documents.photo_services import create_photo, get_project_photos
from apps.documents.services import archive_document, create_document
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationSettings,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects.models import ProjectSiteDocumentLink
from apps.projects.services import create_project, create_project_site


class ProjectPhotoGalleryTests(TestCase):
    def setUp(self) -> None:
        self.media_directory = TemporaryDirectory()
        self.media_override = override_settings(
            MEDIA_ROOT=self.media_directory.name,
            DOCUMENT_PROTECTED_ROOT=self.media_directory.name,
        )
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.owner = User.objects.create_user(username="gallery-owner", password="pw")
        self.other_owner = User.objects.create_user(
            username="other-gallery-owner", password="pw"
        )
        self.organization = self._organization("Gallery Company", "gallery", self.owner)
        self.other_organization = self._organization(
            "Other Gallery Company", "other-gallery", self.other_owner
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="GAL-1",
            name="Gallery Project",
        )
        self.other_project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="GAL-2",
            name="Other Project",
        )
        self.site = create_project_site(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            code="SITE-1",
            name="Main Site",
        )
        self.other_site = create_project_site(
            organization=self.organization,
            project=self.other_project,
            actor=self.owner,
            code="SITE-2",
            name="Other Site",
        )

    @staticmethod
    def _organization(name: str, slug: str, owner: User) -> Organization:
        organization = Organization.objects.create(
            name=name,
            slug=slug,
            created_by=owner,
            updated_by=owner,
        )
        OrganizationSettings.objects.create(organization=organization)
        organization.memberships.create(
            user=owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        return organization

    @staticmethod
    def _image(name: str = "photo.png", suffix: bytes = b"") -> SimpleUploadedFile:
        return SimpleUploadedFile(
            name,
            b"\x89PNG\r\n\x1a\n" + suffix,
            content_type="image/png",
        )

    @staticmethod
    def _pdf(name: str = "document.pdf") -> SimpleUploadedFile:
        return SimpleUploadedFile(
            name, b"%PDF-1.7\nfile", content_type="application/pdf"
        )

    def _login(
        self, *, user: User | None = None, organization: Organization | None = None
    ) -> None:
        self.client.force_login(user or self.owner)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(
            (organization or self.organization).pk
        )
        session.save()

    def _photo(
        self,
        *,
        project=None,
        site=None,
        source: str = PhotoSource.UPLOAD,
        title: str = "Project image",
        name: str = "photo.png",
    ):
        project = project or self.project
        return create_photo(
            organization=self.organization,
            actor=self.owner,
            project=project,
            site=site,
            target=project,
            source=source,
            title=title,
            upload=self._image(name),
        )

    def _mark_clean(self, document) -> None:
        version = document.current_version
        DocumentProcessingAssessment.objects.create(
            organization=self.organization,
            version=version,
            sequence=1,
            verdict="clean",
            input_sha256=version.sha256,
            adapter_code="test-scanner",
            recorded_by=self.owner,
        )

    def test_create_photo_uses_document_version_and_metadata_only(self) -> None:
        document = self._photo(site=self.site, source=PhotoSource.CAMERA)

        self.assertEqual(document.document_type, DocumentType.PHOTO)
        self.assertEqual(document.versions.count(), 1)
        self.assertTrue(document.current_version.file.name.startswith("organizations/"))
        self.assertEqual(document.photo_metadata.source, PhotoSource.CAMERA)
        self.assertTrue(
            ProjectSiteDocumentLink.objects.filter(
                document=document,
                project_site=self.site,
                organization=self.organization,
            ).exists()
        )
        self.assertFalse(hasattr(document.photo_metadata, "file"))

    def test_site_must_belong_to_project_and_tenant(self) -> None:
        with self.assertRaises(PermissionDenied):
            self._photo(site=self.other_site)

        foreign_project = create_project(
            organization=self.other_organization,
            actor=self.other_owner,
            code="FOREIGN",
            name="Foreign",
        )
        foreign_site = create_project_site(
            organization=self.other_organization,
            project=foreign_project,
            actor=self.other_owner,
            code="FOREIGN-SITE",
            name="Foreign Site",
        )
        with self.assertRaises(PermissionDenied):
            self._photo(site=foreign_site)

    def test_gallery_is_authorized_rtl_scoped_and_excludes_non_photos(self) -> None:
        visible = self._photo(site=self.site, title="Visible photo")
        self._photo(project=self.other_project, title="Other project photo")
        create_document(
            organization=self.organization,
            actor=self.owner,
            document_type=DocumentType.GENERAL,
            title="Not a photo",
            upload=self._pdf(),
            target=self.project,
        )
        self._login()

        response = self.client.get(
            reverse("projects:gallery", kwargs={"project_id": self.project.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "گالری تصاویر پروژه")
        self.assertContains(response, "Visible photo")
        self.assertNotContains(response, "Other project photo")
        self.assertNotContains(response, "Not a photo")
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(
            response,
            reverse("projects:photo_add", kwargs={"project_id": self.project.pk}),
        )
        self.assertEqual(visible.document_type, DocumentType.PHOTO)

    def test_cross_tenant_gallery_and_private_preview_are_denied(self) -> None:
        document = self._photo()
        self._mark_clean(document)
        self._login(user=self.other_owner, organization=self.other_organization)

        gallery = self.client.get(
            reverse("projects:gallery", kwargs={"project_id": self.project.pk})
        )
        preview = self.client.get(
            reverse("documents:photo-preview", kwargs={"document_id": document.pk})
        )

        self.assertEqual(gallery.status_code, 403)
        self.assertEqual(preview.status_code, 403)

    def test_preview_requires_clean_active_photo_and_is_private_inline(self) -> None:
        document = self._photo()
        archived_document = self._photo(title="Archived photo", name="archived.png")
        archive_document(
            document=archived_document,
            actor=self.owner,
            reason="No longer active",
        )
        self._login()
        url = reverse("documents:photo-preview", kwargs={"document_id": document.pk})
        self.assertEqual(self.client.get(url).status_code, 403)
        archived_url = reverse(
            "documents:photo-preview", kwargs={"document_id": archived_document.pk}
        )
        self.assertEqual(self.client.get(archived_url).status_code, 403)

        self._mark_clean(document)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        for closer in response._resource_closers:
            closer()

    def test_camera_and_multi_upload_share_pipeline_with_partial_failure(self) -> None:
        self._login()
        add_url = reverse("projects:photo_add", kwargs={"project_id": self.project.pk})
        camera_response = self.client.post(
            add_url,
            {
                "source": PhotoSource.CAMERA,
                "title": "Camera image",
                "camera_file": self._image("camera.png", b"camera"),
            },
        )
        self.assertEqual(camera_response.status_code, 302)

        upload_response = self.client.post(
            add_url,
            {
                "source": PhotoSource.UPLOAD,
                "title": "Batch",
                "files": [
                    self._image("valid.png", b"valid"),
                    SimpleUploadedFile(
                        "fake.png", b"not-an-image", content_type="image/png"
                    ),
                ],
            },
        )
        self.assertEqual(upload_response.status_code, 302)
        sources = list(
            PhotoMetadata.objects.filter(organization=self.organization)
            .order_by("created_at")
            .values_list("source", flat=True)
        )
        self.assertEqual(sources, [PhotoSource.CAMERA, PhotoSource.UPLOAD])
        self.assertEqual(
            self.organization.documents.filter(document_type="photo").count(), 2
        )
        for document in self.organization.documents.filter(document_type="photo"):
            self.assertEqual(document.versions.count(), 1)

    def test_fake_extension_and_path_name_are_handled_safely(self) -> None:
        with self.assertRaisesMessage(ValueError, "محتوای فایل"):
            create_photo(
                organization=self.organization,
                actor=self.owner,
                project=self.project,
                target=self.project,
                source=PhotoSource.UPLOAD,
                upload=SimpleUploadedFile(
                    "fake.png", b"not-an-image", content_type="image/png"
                ),
            )
        document = create_photo(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            target=self.project,
            source=PhotoSource.UPLOAD,
            upload=self._image("../../safe.png", b"safe"),
        )
        self.assertNotIn("..", document.current_version.file.name)
        self.assertEqual(document.current_version.original_file_name, "safe.png")

    def test_daily_report_photo_appears_without_duplicate_binary(self) -> None:
        report = DailyReport.objects.create(
            organization=self.organization,
            project=self.project,
            site=self.site,
            reporting_date="2026-10-08",
            work_performed="Site work",
            created_by=self.owner,
            updated_by=self.owner,
        )
        document = create_document(
            organization=self.organization,
            actor=self.owner,
            document_type=DocumentType.PHOTO,
            title="Daily report image",
            upload=self._image("daily.png", b"daily"),
            target=report,
        )

        photos = get_project_photos(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
        )

        self.assertEqual([photo.document for photo in photos], [document])
        self.assertEqual(photos[0].site, self.site)
        self.assertEqual(document.versions.count(), 1)

    def test_project_detail_navigation_exposes_gallery_only_through_permission_context(
        self,
    ) -> None:
        self._login()
        response = self.client.get(
            reverse("projects:detail", kwargs={"project_id": self.project.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("projects:gallery", kwargs={"project_id": self.project.pk}),
        )

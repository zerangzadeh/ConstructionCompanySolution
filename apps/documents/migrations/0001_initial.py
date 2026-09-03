import apps.documents.models
import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0003_organizationinvitation"),
        ("payments", "0001_initial"),
        ("projects", "0003_projectphase"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectDocument",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "document_type",
                    models.CharField(
                        choices=[
                            ("general", "General"),
                            ("contract", "Contract"),
                            ("drawing", "Drawing"),
                            ("receipt", "Receipt"),
                            ("photo", "Photo"),
                            ("other", "Other"),
                        ],
                        default="general",
                        max_length=20,
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("original_file_name", models.CharField(max_length=255)),
                (
                    "file",
                    models.FileField(
                        upload_to=apps.documents.models.document_upload_path,
                    ),
                ),
                ("content_type", models.CharField(max_length=100)),
                ("file_size", models.PositiveBigIntegerField()),
                ("sha256", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                (
                    "archived_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="documents_archived",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="documents_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="project_documents",
                        to="organizations.organization",
                    ),
                ),
                (
                    "payment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="documents",
                        to="payments.payment",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="projects.project",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="projectdocument",
            index=models.Index(
                fields=["organization", "project", "created_at"],
                name="doc_org_project_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="projectdocument",
            index=models.Index(
                fields=["organization", "payment"],
                name="doc_org_payment_idx",
            ),
        ),
    ]

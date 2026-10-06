import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("knowledge", "0001_initial"),
        ("organizations", "0104_p9_s21_s24_knowledge_permissions"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="KnowledgePromotion",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="شناسه",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد"),
                ),
                ("sanitized_snapshot", models.JSONField()),
                ("snapshot_hash", models.CharField(max_length=64)),
                ("anonymization_statement", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("requested", "درخواست‌شده"),
                            ("recommended", "توصیه‌شده"),
                            ("rejected", "ردشده"),
                            ("approved", "تأییدشده"),
                            ("published", "منتشرشده"),
                        ],
                        db_index=True,
                        default="requested",
                        max_length=16,
                    ),
                ),
                ("review_reason", models.TextField(blank=True)),
                ("operation_key", models.UUIDField(default=uuid.uuid4)),
            ],
        ),
        migrations.CreateModel(
            name="KnowledgePromotionEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="شناسه",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد"),
                ),
                ("from_status", models.CharField(blank=True, max_length=16)),
                (
                    "to_status",
                    models.CharField(
                        choices=[
                            ("requested", "درخواست‌شده"),
                            ("recommended", "توصیه‌شده"),
                            ("rejected", "ردشده"),
                            ("approved", "تأییدشده"),
                            ("published", "منتشرشده"),
                        ],
                        max_length=16,
                    ),
                ),
                ("reason", models.TextField(blank=True)),
                ("operation_key", models.UUIDField(default=uuid.uuid4)),
            ],
        ),
        migrations.CreateModel(
            name="KnowledgePublicationEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name="شناسه",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد"),
                ),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("published", "انتشار"),
                            ("superseded", "جایگزینی"),
                            ("withdrawn", "پس‌گرفتن"),
                        ],
                        max_length=16,
                    ),
                ),
                ("reason", models.TextField(blank=True)),
                ("operation_key", models.UUIDField(default=uuid.uuid4)),
            ],
        ),
        migrations.AddField(
            model_name="knowledgecandidate",
            name="correction_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="knowledgecandidate",
            name="corrects_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="correction_candidates",
                to="knowledge.knowledgepublicationversion",
            ),
        ),
        migrations.AddField(
            model_name="knowledgerecurrenceevidence",
            name="correction_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="knowledgerecurrenceevidence",
            name="request_hash",
            field=models.CharField(default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="knowledgereuseevidence",
            name="status",
            field=models.CharField(
                choices=[
                    ("valid", "معتبر"),
                    ("reversal", "برگشت"),
                    ("replacement", "جایگزین"),
                ],
                default="valid",
                max_length=16,
            ),
        ),
        migrations.AddConstraint(
            model_name="knowledgepublicationversion",
            constraint=models.UniqueConstraint(
                condition=models.Q(("supersedes__isnull", False)),
                fields=("supersedes",),
                name="knowledge_publication_single_successor_uq",
            ),
        ),
        migrations.AddConstraint(
            model_name="knowledgerecurrenceevidence",
            constraint=models.UniqueConstraint(
                condition=models.Q(("replaces__isnull", False)),
                fields=("replaces",),
                name="knowledge_recurrence_single_correction_uq",
            ),
        ),
        migrations.AddConstraint(
            model_name="knowledgereuseevidence",
            constraint=models.UniqueConstraint(
                condition=models.Q(("reverses__isnull", False)),
                fields=("reverses",),
                name="knowledge_reuse_single_correction_uq",
            ),
        ),
        migrations.AddField(
            model_name="knowledgepromotion",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="knowledge_promotions_approved",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="knowledgepromotion",
            name="platform_candidate",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="promotion",
                to="knowledge.knowledgecandidate",
            ),
        ),
        migrations.AddField(
            model_name="knowledgepromotion",
            name="requested_by",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="knowledge_promotions_requested",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="knowledgepromotion",
            name="reviewed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="knowledge_promotions_reviewed",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="knowledgepromotion",
            name="source_organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="knowledge_promotion_requests",
                to="organizations.organization",
            ),
        ),
        migrations.AddField(
            model_name="knowledgepromotion",
            name="source_version",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="promotion_requests",
                to="knowledge.knowledgepublicationversion",
            ),
        ),
        migrations.AddField(
            model_name="knowledgepromotionevent",
            name="actor",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="knowledge_promotion_events",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="knowledgepromotionevent",
            name="promotion",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="events",
                to="knowledge.knowledgepromotion",
            ),
        ),
        migrations.AddField(
            model_name="knowledgepublicationevent",
            name="actor",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="knowledge_publication_events",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="knowledgepublicationevent",
            name="publication_version",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="lifecycle_events",
                to="knowledge.knowledgepublicationversion",
            ),
        ),
        migrations.AddField(
            model_name="knowledgepublicationevent",
            name="related_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="related_lifecycle_events",
                to="knowledge.knowledgepublicationversion",
            ),
        ),
        migrations.AddConstraint(
            model_name="knowledgepromotion",
            constraint=models.UniqueConstraint(
                fields=("source_organization", "requested_by", "operation_key"),
                name="knowledge_promotion_op_uq",
            ),
        ),
        migrations.AddConstraint(
            model_name="knowledgepromotion",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("status__in", ["requested", "recommended", "approved"])
                ),
                fields=("source_version",),
                name="knowledge_promotion_active_source_uq",
            ),
        ),
        migrations.AddConstraint(
            model_name="knowledgepromotionevent",
            constraint=models.UniqueConstraint(
                fields=("promotion", "actor", "operation_key"),
                name="knowledge_promotion_event_op_uq",
            ),
        ),
        migrations.AddConstraint(
            model_name="knowledgepublicationevent",
            constraint=models.UniqueConstraint(
                fields=("actor", "operation_key"),
                name="knowledge_publication_event_op_uq",
            ),
        ),
    ]

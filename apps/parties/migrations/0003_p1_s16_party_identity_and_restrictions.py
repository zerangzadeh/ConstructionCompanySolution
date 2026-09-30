import unicodedata
import uuid
from typing import ClassVar

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import F, Q
from django.utils import timezone


def normalize(value):
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def backfill_party_identity(apps, schema_editor):
    del schema_editor
    Party = apps.get_model("parties", "BusinessParty")
    Snapshot = apps.get_model("parties", "PartyIdentitySnapshot")
    identifiers = {}
    snapshots = []
    for party in Party.objects.order_by("organization_id", "pk").iterator():
        normalized_display_name = normalize(party.display_name)
        normalized_legal_name = normalize(party.legal_name)
        normalized_tax_identifier = normalize(party.tax_identifier)
        if normalized_tax_identifier:
            key = (party.organization_id, normalized_tax_identifier)
            if key in identifiers:
                raise RuntimeError(
                    "P1-S16 normalization found an ambiguous Tenant identifier "
                    f"collision between parties {identifiers[key]} and {party.pk}."
                )
            identifiers[key] = party.pk
        Party.objects.filter(pk=party.pk).update(
            normalized_display_name=normalized_display_name,
            normalized_legal_name=normalized_legal_name,
            normalized_tax_identifier=normalized_tax_identifier,
        )
        snapshots.append(
            Snapshot(
                id=uuid.uuid4(),
                organization_id=party.organization_id,
                party_id=party.pk,
                sequence=1,
                party_kind=party.party_kind,
                display_name=party.display_name,
                legal_name=party.legal_name,
                tax_identifier=party.tax_identifier,
                normalized_display_name=normalized_display_name,
                normalized_legal_name=normalized_legal_name,
                normalized_tax_identifier=normalized_tax_identifier,
                reason="migration_backfill",
                recorded_at=timezone.now(),
            )
        )
    Snapshot.objects.bulk_create(snapshots, batch_size=500)


def reverse_party_identity(apps, schema_editor):
    del schema_editor
    Restriction = apps.get_model("parties", "PartyRestriction")
    Party = apps.get_model("parties", "BusinessParty")
    if (
        Restriction.objects.exists()
        or Party.objects.filter(merged_into__isnull=False).exists()
    ):
        raise RuntimeError(
            "Unsafe P1-S16 rollback refused: restriction or merge history exists."
        )


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [
        ("organizations", "0038_p1_s16_party_governance_permissions"),
        ("parties", "0002_alter_businessparty_options_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations: ClassVar[list[migrations.operations.base.Operation]] = [
        migrations.AddField(
            model_name="businessparty",
            name="normalized_display_name",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                editable=False,
                max_length=255,
                verbose_name="نام نمایشی نرمال‌شده",
            ),
        ),
        migrations.AddField(
            model_name="businessparty",
            name="normalized_legal_name",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                editable=False,
                max_length=255,
                verbose_name="نام قانونی نرمال‌شده",
            ),
        ),
        migrations.AddField(
            model_name="businessparty",
            name="normalized_tax_identifier",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                editable=False,
                max_length=100,
                verbose_name="شناسه نرمال‌شده",
            ),
        ),
        migrations.AddField(
            model_name="businessparty",
            name="merge_reason",
            field=models.TextField(blank=True, verbose_name="دلیل ادغام"),
        ),
        migrations.AddField(
            model_name="businessparty",
            name="merged_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="زمان ثبت ادغام"
            ),
        ),
        migrations.AddField(
            model_name="businessparty",
            name="merged_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="business_party_merges_recorded",
                to=settings.AUTH_USER_MODEL,
                verbose_name="ثبت‌کننده ادغام",
            ),
        ),
        migrations.AddField(
            model_name="businessparty",
            name="merged_into",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="merged_sources",
                to="parties.businessparty",
                verbose_name="طرف تجاری مرجع پس از ادغام",
            ),
        ),
        migrations.CreateModel(
            name="PartyIdentitySnapshot",
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
                ("sequence", models.PositiveIntegerField(verbose_name="شماره نسخه")),
                (
                    "party_kind",
                    models.CharField(
                        choices=[("company", "شخص حقوقی"), ("individual", "شخص حقیقی")],
                        max_length=20,
                        verbose_name="نوع طرف تجاری",
                    ),
                ),
                (
                    "display_name",
                    models.CharField(max_length=255, verbose_name="نام نمایشی"),
                ),
                (
                    "legal_name",
                    models.CharField(
                        blank=True, max_length=255, verbose_name="نام قانونی"
                    ),
                ),
                (
                    "tax_identifier",
                    models.CharField(
                        blank=True, max_length=100, verbose_name="شناسه مالیاتی"
                    ),
                ),
                (
                    "normalized_display_name",
                    models.CharField(
                        max_length=255, verbose_name="نام نمایشی نرمال‌شده"
                    ),
                ),
                (
                    "normalized_legal_name",
                    models.CharField(
                        blank=True, max_length=255, verbose_name="نام قانونی نرمال‌شده"
                    ),
                ),
                (
                    "normalized_tax_identifier",
                    models.CharField(
                        blank=True, max_length=100, verbose_name="شناسه نرمال‌شده"
                    ),
                ),
                ("reason", models.TextField(verbose_name="دلیل ثبت")),
                (
                    "recorded_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="زمان ثبت"),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="party_identity_snapshots",
                        to="organizations.organization",
                        verbose_name="سازمان",
                    ),
                ),
                (
                    "party",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="identity_snapshots",
                        to="parties.businessparty",
                        verbose_name="طرف تجاری",
                    ),
                ),
                (
                    "recorded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="party_identity_snapshots_recorded",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="ثبت‌کننده",
                    ),
                ),
            ],
            options={
                "verbose_name": "نسخه هویت طرف تجاری",
                "verbose_name_plural": "نسخه‌های هویت طرف تجاری",
                "ordering": ["party", "sequence"],
            },
        ),
        migrations.CreateModel(
            name="PartyRestriction",
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
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, verbose_name="زمان آخرین به‌روزرسانی"
                    ),
                ),
                (
                    "scope",
                    models.CharField(
                        choices=[("tenant", "Tenant"), ("platform", "پلتفرم")],
                        max_length=20,
                        verbose_name="دامنه",
                    ),
                ),
                ("code", models.CharField(max_length=80, verbose_name="کد محدودیت")),
                (
                    "effect",
                    models.CharField(
                        choices=[
                            ("information_only", "صرفاً اطلاع‌رسانی"),
                            ("block_new_transactions", "مسدودسازی تراکنش جدید"),
                        ],
                        max_length=40,
                        verbose_name="اثر",
                    ),
                ),
                ("reason", models.TextField(verbose_name="دلیل")),
                ("effective_from", models.DateTimeField(verbose_name="شروع اثر")),
                (
                    "effective_until",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="پایان اثر"
                    ),
                ),
                (
                    "revoked_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="زمان لغو"
                    ),
                ),
                (
                    "revocation_reason",
                    models.TextField(blank=True, verbose_name="دلیل لغو"),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="party_restrictions_created",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="ایجادکننده",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="party_restrictions",
                        to="organizations.organization",
                        verbose_name="سازمان",
                    ),
                ),
                (
                    "party",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="restrictions",
                        to="parties.businessparty",
                        verbose_name="طرف تجاری",
                    ),
                ),
                (
                    "revoked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="party_restrictions_revoked",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="لغوکننده",
                    ),
                ),
            ],
            options={
                "verbose_name": "محدودیت طرف تجاری",
                "verbose_name_plural": "محدودیت‌های طرف تجاری",
                "ordering": ["party", "scope", "code", "-effective_from"],
            },
        ),
        migrations.RunPython(backfill_party_identity, reverse_party_identity),
        migrations.RemoveConstraint(
            model_name="businessparty",
            name="unique_party_tax_identifier_per_organization",
        ),
        migrations.AddConstraint(
            model_name="businessparty",
            constraint=models.UniqueConstraint(
                condition=~Q(normalized_tax_identifier="")
                & Q(merged_into__isnull=True),
                fields=("organization", "normalized_tax_identifier"),
                name="unique_party_normalized_identifier_per_org",
            ),
        ),
        migrations.AddConstraint(
            model_name="businessparty",
            constraint=models.CheckConstraint(
                condition=Q(
                    Q(
                        merged_at__isnull=True,
                        merged_by__isnull=True,
                        merged_into__isnull=True,
                        merge_reason="",
                    ),
                    Q(
                        merged_at__isnull=False,
                        merged_by__isnull=False,
                        merged_into__isnull=False,
                        merge_reason__gt="",
                    ),
                    _connector="OR",
                ),
                name="party_merge_evidence_complete",
            ),
        ),
        migrations.AddConstraint(
            model_name="businessparty",
            constraint=models.CheckConstraint(
                condition=~Q(id=F("merged_into")), name="party_cannot_merge_into_self"
            ),
        ),
        migrations.AddConstraint(
            model_name="partyidentitysnapshot",
            constraint=models.UniqueConstraint(
                fields=("party", "sequence"), name="unique_party_identity_sequence"
            ),
        ),
        migrations.AddIndex(
            model_name="partyrestriction",
            index=models.Index(
                fields=["organization", "party", "scope", "effect"],
                name="party_restriction_lookup_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="partyrestriction",
            constraint=models.CheckConstraint(
                condition=Q(effective_until__isnull=True)
                | Q(effective_until__gt=F("effective_from")),
                name="party_restriction_effective_interval",
            ),
        ),
        migrations.AddConstraint(
            model_name="partyrestriction",
            constraint=models.CheckConstraint(
                condition=Q(
                    Q(
                        revocation_reason="",
                        revoked_at__isnull=True,
                        revoked_by__isnull=True,
                    ),
                    Q(
                        revocation_reason__gt="",
                        revoked_at__isnull=False,
                        revoked_by__isnull=False,
                    ),
                    _connector="OR",
                ),
                name="party_restriction_revocation_evidence",
            ),
        ),
    ]

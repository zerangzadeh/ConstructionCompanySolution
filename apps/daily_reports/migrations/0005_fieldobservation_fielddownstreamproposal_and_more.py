import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('daily_reports', '0004_dailyreportdocumentlink'),
        ('documents', '0009_document_retention_classification_and_more'),
        ('organizations', '0099_p8_s24_s27_cost_asset_permissions'),
        ('projects', '0008_p4_s21_s25_schedule_change_controls'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FieldObservation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='شناسه')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='زمان ایجاد')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='زمان آخرین به\u200cروزرسانی')),
                ('kind', models.CharField(choices=[('general', 'مشاهده عمومی'), ('weather', 'وضعیت آب\u200cوهوا'), ('work_front', 'جبهه کاری'), ('visit', 'بازدید'), ('meeting', 'جلسه'), ('instruction', 'دستور کار ثبت\u200cشده')], max_length=30)),
                ('title', models.CharField(max_length=160)),
                ('summary', models.TextField(blank=True)),
                ('structured_payload', models.JSONField(blank=True, default=dict)),
                ('payload_schema_version', models.PositiveSmallIntegerField(default=1)),
                ('manual_context', models.CharField(blank=True, max_length=500)),
                ('captured_at', models.DateTimeField(blank=True, null=True)),
                ('captured_timezone_offset_minutes', models.SmallIntegerField(blank=True, null=True)),
                ('effective_at', models.DateTimeField(blank=True, null=True)),
                ('location_permission', models.CharField(choices=[('not_requested', 'درخواست\u200cنشده'), ('granted', 'مجاز'), ('denied', 'ردشده'), ('unavailable', 'در دسترس نیست')], default='not_requested', max_length=20)),
                ('latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('horizontal_accuracy_meters', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('location_captured_at', models.DateTimeField(blank=True, null=True)),
                ('location_mismatch_note', models.CharField(blank=True, max_length=500)),
                ('client_context', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('draft', 'پیش\u200cنویس'), ('submitted', 'ارسال\u200cشده'), ('in_review', 'در بررسی'), ('accepted', 'پذیرفته\u200cشده'), ('rejected', 'ردشده'), ('superseded', 'جایگزین\u200cشده')], db_index=True, default='draft', max_length=20)),
                ('revision', models.PositiveIntegerField(default=1)),
                ('canonical_hash', models.CharField(blank=True, max_length=64)),
                ('create_operation_key', models.UUIDField()),
                ('create_payload_hash', models.CharField(max_length=64)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('review_started_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('review_reason', models.TextField(blank=True)),
                ('correction_reason', models.TextField(blank=True)),
                ('activity', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='field_observations', to='projects.activity')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='field_observations_created', to=settings.AUTH_USER_MODEL)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='field_observations', to='organizations.organization')),
                ('phase', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='field_observations', to='projects.projectphase')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='field_observations', to='projects.project')),
                ('replaces', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='replacement_candidates', to='daily_reports.fieldobservation')),
                ('review_started_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='field_observations_review_started', to=settings.AUTH_USER_MODEL)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='field_observations_reviewed', to=settings.AUTH_USER_MODEL)),
                ('site', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='field_observations', to='projects.projectsite')),
                ('submitted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='field_observations_submitted', to=settings.AUTH_USER_MODEL)),
                ('submitted_membership', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='field_observations_submitted', to='organizations.organizationmembership')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='FieldDownstreamProposal',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='شناسه')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='زمان ایجاد')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='زمان آخرین به\u200cروزرسانی')),
                ('family', models.CharField(choices=[('progress', 'پیشنهاد پیشرفت فیزیکی'), ('time', 'پیشنهاد ثبت زمان'), ('equipment_usage', 'پیشنهاد کارکرد تجهیز'), ('material_consumption', 'پیشنهاد مصرف مصالح')], max_length=30)),
                ('effective_at', models.DateTimeField(blank=True, null=True)),
                ('lines', models.JSONField(default=list)),
                ('source_canonical_hash', models.CharField(max_length=64)),
                ('proposal_hash', models.CharField(blank=True, max_length=64)),
                ('status', models.CharField(choices=[('draft', 'پیش\u200cنویس'), ('submitted', 'ارسال\u200cشده'), ('accepted', 'پذیرفته\u200cشده برای تحویل'), ('rejected', 'ردشده')], default='draft', max_length=20)),
                ('create_operation_key', models.UUIDField()),
                ('create_payload_hash', models.CharField(max_length=64)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('review_reason', models.TextField(blank=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='field_proposals_created', to=settings.AUTH_USER_MODEL)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='field_proposals', to='organizations.organization')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='field_proposals', to='projects.project')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='field_proposals_reviewed', to=settings.AUTH_USER_MODEL)),
                ('site', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='field_proposals', to='projects.projectsite')),
                ('submitted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='field_proposals_submitted', to=settings.AUTH_USER_MODEL)),
                ('observation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='proposals', to='daily_reports.fieldobservation')),
            ],
        ),
        migrations.CreateModel(
            name='FieldObservationDraftRevision',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='شناسه')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='زمان ایجاد')),
                ('revision', models.PositiveIntegerField()),
                ('snapshot', models.JSONField()),
                ('payload_hash', models.CharField(max_length=64)),
                ('operation_key', models.UUIDField()),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('observation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='draft_revisions', to='daily_reports.fieldobservation')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='organizations.organization')),
            ],
            options={
                'ordering': ['revision'],
            },
        ),
        migrations.CreateModel(
            name='FieldObservationEvidenceLink',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='شناسه')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='زمان ایجاد')),
                ('legacy_link_id', models.UUIDField(blank=True, null=True, unique=True)),
                ('sha256', models.CharField(max_length=64)),
                ('operation_key', models.UUIDField()),
                ('payload_hash', models.CharField(max_length=64)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='documents.document')),
                ('document_version', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='field_observation_links', to='documents.documentversion')),
                ('field_observation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='evidence_links', to='daily_reports.fieldobservation')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='organizations.organization')),
            ],
            options={
                'ordering': ['created_at'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='FieldObservationTransition',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='شناسه')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='زمان ایجاد')),
                ('from_status', models.CharField(choices=[('draft', 'پیش\u200cنویس'), ('submitted', 'ارسال\u200cشده'), ('in_review', 'در بررسی'), ('accepted', 'پذیرفته\u200cشده'), ('rejected', 'ردشده'), ('superseded', 'جایگزین\u200cشده')], max_length=20)),
                ('to_status', models.CharField(choices=[('draft', 'پیش\u200cنویس'), ('submitted', 'ارسال\u200cشده'), ('in_review', 'در بررسی'), ('accepted', 'پذیرفته\u200cشده'), ('rejected', 'ردشده'), ('superseded', 'جایگزین\u200cشده')], max_length=20)),
                ('reason', models.TextField(blank=True)),
                ('canonical_hash', models.CharField(blank=True, max_length=64)),
                ('operation_key', models.UUIDField()),
                ('payload_hash', models.CharField(max_length=64)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('observation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transitions', to='daily_reports.fieldobservation')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='organizations.organization')),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='FieldProposalTransition',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, verbose_name='شناسه')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='زمان ایجاد')),
                ('from_status', models.CharField(choices=[('draft', 'پیش\u200cنویس'), ('submitted', 'ارسال\u200cشده'), ('accepted', 'پذیرفته\u200cشده برای تحویل'), ('rejected', 'ردشده')], max_length=20)),
                ('to_status', models.CharField(choices=[('draft', 'پیش\u200cنویس'), ('submitted', 'ارسال\u200cشده'), ('accepted', 'پذیرفته\u200cشده برای تحویل'), ('rejected', 'ردشده')], max_length=20)),
                ('reason', models.TextField(blank=True)),
                ('proposal_hash', models.CharField(blank=True, max_length=64)),
                ('operation_key', models.UUIDField()),
                ('payload_hash', models.CharField(max_length=64)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='organizations.organization')),
                ('proposal', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transitions', to='daily_reports.fielddownstreamproposal')),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='fieldobservation',
            index=models.Index(fields=['organization', 'project', 'site', 'status'], name='fieldobs_scope_status_idx'),
        ),
        migrations.AddIndex(
            model_name='fieldobservation',
            index=models.Index(fields=['organization', 'status', '-created_at'], name='fieldobs_org_status_idx'),
        ),
        migrations.AddConstraint(
            model_name='fieldobservation',
            constraint=models.UniqueConstraint(fields=('organization', 'created_by', 'create_operation_key'), name='fieldobs_create_operation_uq'),
        ),
        migrations.AddConstraint(
            model_name='fieldobservation',
            constraint=models.UniqueConstraint(condition=models.Q(('status', 'accepted')), fields=('replaces',), name='fieldobs_one_accepted_successor_uq'),
        ),
        migrations.AddConstraint(
            model_name='fieldobservation',
            constraint=models.CheckConstraint(condition=models.Q(('revision__gte', 1)), name='fieldobs_revision_positive'),
        ),
        migrations.AddIndex(
            model_name='fielddownstreamproposal',
            index=models.Index(fields=['organization', 'project', 'status'], name='fieldproposal_scope_status_idx'),
        ),
        migrations.AddConstraint(
            model_name='fielddownstreamproposal',
            constraint=models.UniqueConstraint(fields=('organization', 'created_by', 'create_operation_key'), name='fieldproposal_create_operation_uq'),
        ),
        migrations.AddConstraint(
            model_name='fieldobservationdraftrevision',
            constraint=models.UniqueConstraint(fields=('observation', 'revision'), name='fieldobs_draft_revision_uq'),
        ),
        migrations.AddConstraint(
            model_name='fieldobservationdraftrevision',
            constraint=models.UniqueConstraint(fields=('organization', 'actor', 'operation_key'), name='fieldobs_draft_operation_uq'),
        ),
        migrations.AddIndex(
            model_name='fieldobservationevidencelink',
            index=models.Index(fields=['organization', 'document'], name='fieldobsev_org_doc_idx'),
        ),
        migrations.AddConstraint(
            model_name='fieldobservationevidencelink',
            constraint=models.UniqueConstraint(fields=('field_observation', 'document_version'), name='fieldobs_evidence_version_uq'),
        ),
        migrations.AddConstraint(
            model_name='fieldobservationevidencelink',
            constraint=models.UniqueConstraint(fields=('organization', 'created_by', 'operation_key'), name='fieldobs_evidence_operation_uq'),
        ),
        migrations.AddConstraint(
            model_name='fieldobservationtransition',
            constraint=models.UniqueConstraint(fields=('organization', 'actor', 'to_status', 'operation_key'), name='fieldobs_transition_operation_uq'),
        ),
        migrations.AddConstraint(
            model_name='fieldproposaltransition',
            constraint=models.UniqueConstraint(fields=('organization', 'actor', 'to_status', 'operation_key'), name='fieldproposal_transition_operation_uq'),
        ),
    ]

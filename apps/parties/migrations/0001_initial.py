import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organizations", "0002_organizationsettings"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(name="BusinessParty", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("party_kind", models.CharField(choices=[("company", "Company"), ("individual", "Individual")], max_length=20)),
            ("display_name", models.CharField(max_length=255)), ("legal_name", models.CharField(blank=True, max_length=255)),
            ("tax_identifier", models.CharField(blank=True, max_length=100)), ("archived_at", models.DateTimeField(blank=True, null=True)),
            ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="business_parties_created", to=settings.AUTH_USER_MODEL)),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="business_parties", to="organizations.organization")),
            ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="business_parties_updated", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ["display_name"]}),
        migrations.CreateModel(name="PartyContact", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("contact_type", models.CharField(choices=[("email", "Email"), ("phone", "Phone"), ("mobile", "Mobile"), ("address", "Address"), ("other", "Other")], max_length=20)),
            ("value", models.CharField(max_length=255)), ("label", models.CharField(blank=True, max_length=100)),
            ("is_primary", models.BooleanField(default=False)), ("archived_at", models.DateTimeField(blank=True, null=True)),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="party_contacts", to="organizations.organization")),
            ("party", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="contacts", to="parties.businessparty")),
        ], options={"ordering": ["-is_primary", "contact_type", "value"]}),
        migrations.CreateModel(name="PartyRole", fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("role", models.CharField(choices=[("employer", "Employer"), ("client", "Client"), ("consultant", "Consultant"), ("supplier", "Supplier"), ("subcontractor", "Subcontractor"), ("other", "Other")], max_length=20)),
            ("is_active", models.BooleanField(default=True)),
            ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="party_roles", to="organizations.organization")),
            ("party", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="roles", to="parties.businessparty")),
        ], options={"ordering": ["role"]}),
        migrations.AddIndex(model_name="businessparty", index=models.Index(fields=["organization", "display_name"], name="party_org_name_idx")),
        migrations.AddIndex(model_name="businessparty", index=models.Index(fields=["organization", "archived_at"], name="party_org_archived_idx")),
        migrations.AddConstraint(model_name="businessparty", constraint=models.UniqueConstraint(condition=models.Q(("tax_identifier", ""), _negated=True), fields=("organization", "tax_identifier"), name="unique_party_tax_identifier_per_organization")),
        migrations.AddConstraint(model_name="partycontact", constraint=models.UniqueConstraint(fields=("organization", "party", "contact_type", "value"), name="unique_party_contact_value_per_organization")),
        migrations.AddConstraint(model_name="partycontact", constraint=models.UniqueConstraint(condition=models.Q(("archived_at__isnull", True), ("is_primary", True)), fields=("party",), name="unique_active_primary_contact_per_party")),
        migrations.AddConstraint(model_name="partyrole", constraint=models.UniqueConstraint(fields=("organization", "party", "role"), name="unique_party_role_per_organization")),
    ]

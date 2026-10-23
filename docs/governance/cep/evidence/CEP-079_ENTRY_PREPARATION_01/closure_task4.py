"""Read current domain-owner inputs; schema or test samples never approve policy."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from django.db import connection, transaction
from apps.organizations.models import Organization
from apps.partner_qualification.models import PartnerProfile, QualificationRequirement, PartnerQualification
from apps.fixed_assets.models import FixedAssetClassVersion, AssetBookPolicyVersion, FixedAsset
from apps.compliance.models import InspectionTemplate, InspectionTemplateVersion
from blocker_closure import write

with transaction.atomic():
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION READ ONLY")
    org = Organization.objects.get(slug="demo-construction-01", status="active")
    result = {"environment": "LOCAL_DEVELOPMENT_READ_ONLY", "models": {}}
    fields = {
        QualificationRequirement: ("id", "code", "version", "category_code", "source_reference", "source_version", "canonical_hash"),
        FixedAssetClassVersion: ("id", "code", "version", "status", "capitalization_policy_reference", "account_mapping_reference", "effective_from", "effective_to"),
        AssetBookPolicyVersion: ("id", "code", "version", "status", "effective_from", "effective_to", "monetary_policy_code", "monetary_policy_version"),
        InspectionTemplateVersion: ("id", "template_id", "version_number", "checklist", "outcome_rules", "source_references", "canonical_hash"),
    }
    for model in (PartnerProfile, QualificationRequirement, PartnerQualification, FixedAssetClassVersion, AssetBookPolicyVersion, FixedAsset, InspectionTemplate, InspectionTemplateVersion):
        queryset = model.objects.filter(organization=org)
        item = {"target_tenant_count": queryset.count(), "all_tenant_count": model.objects.count()}
        if model in fields:
            item["target_inputs"] = list(queryset.values(*fields[model]))
        result["models"][model._meta.label] = item
    result["mutation"] = "NONE_PENDING_APPROVED_INPUTS"
write("TASK4_GOVERNED_INPUT_DISCOVERY.json", result)
print(result)

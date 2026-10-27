"""Construct bounded schema1 parameters from retained sources and Human decisions."""

import hashlib
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
OLD = OUT.parent / "CEP-069_EXT0018_20261027"
REVIEW = OLD / "ADOPTED_EXPERT_REVIEW.md"
REF = REVIEW.relative_to(ROOT).as_posix()
intake = json.loads((OLD / "EXT0018_SOURCE_REVIEW_PACKAGE.json").read_text("utf-8"))
sources = {source["id"]: source for source in intake["sources"]}
for source in sources.values():
    for artifact in source["artifacts"]:
        assert (
            hashlib.sha256((OLD / artifact["path"]).read_bytes()).hexdigest()
            == artifact["sha256"]
        )


def source(
    reference, issued, published, effective, *, supersedes=None, prospective=False
):
    return {
        "reference": reference,
        "sha256": sources[reference]["artifacts"][0]["sha256"],
        "issued_on": issued,
        "published_on": published,
        "effective_on": effective,
        "supersedes": supersedes,
        "treatment": "PROSPECTIVE" if prospective else "RETROACTIVE",
        "correction_requirement": (
            "Preserve finalized earlier periods; unresolved benefit conditions fail closed."
            if prospective
            else "Reconcile affected processed periods through governed replacement/delta; never overwrite."
        ),
    }


annual = source("INTA-200-1005-S-1405", "2026-04-20", "2026-04-22", "2026-03-21")
sso = source("SSO-1000-1405-493", "2026-04-27", "2026-05-04", "2026-03-21")
amendment = source(
    "INTA-200-1405-59",
    "2026-10-19",
    "2026-10-21",
    "2026-10-19",
    supersedes="INTA-200-1403-39",
    prospective=True,
)
housing = {
    "reference": "HOUSING-9234-T65481-1405",
    "sha256": hashlib.sha256(
        (OUT / "HOUSING_1405.rendered.json").read_bytes()
    ).hexdigest(),
    "issued_on": "2026-05-05",
    "published_on": "2026-05-07",
    "effective_on": "2026-03-21",
    "supersedes": "SSO-1000-1405-493:paragraph4:9000000-IRR-observation",
    "treatment": "RETROACTIVE",
    "correction_requirement": "Housing entitlement 30000000 IRR monthly from 1405/01/01; retain 9000000 observation. Payroll owns replacement inputs; statutory engine never silently rewrites wages.",
}


def govern(parameters, records):
    parameters["statutory_governance"] = {
        "scope": "NON_PRODUCTION_QUALIFICATION",
        "population": "IR_LABOUR_ORDINARY_COMPULSORY",
        "insurance_profile": "IR_SSO_ORDINARY_EMPLOYEE_1405",
        "tax_year_start": "2026-03-21",
        "tax_year_end": "2027-03-20",
        "review_reference": REF,
        "review_sha256": hashlib.sha256(REVIEW.read_bytes()).hexdigest(),
        "sources": records,
        "parameter_sources": {
            key: [REF, records[0]["reference"]] for key in parameters
        },
    }
    return parameters


rounding = {
    "method": "ROUND_HALF_UP",
    "scale": 0,
    "stage": "FINAL_LIABILITY",
    "authority_type": "HUMAN_POLICY_WHERE_STATUTE_SILENT",
}
facts = intake["source_facts_for_review_only"]
exemption = Decimal(facts["tax"]["annual_exemption"]) * 1000000
tax = govern(
    {
        "component_mappings": [
            {"component_code": "BASE", "classification": "taxable", "basis_factor": "1"}
        ],
        "calculation_basis": "CUMULATIVE_YTD",
        "exemptions": [{"code": "ANNUAL-1405", "amount": str(exemption)}],
        "brackets": [
            {
                "lower": str(Decimal(row["lower"]) * 1000000 - exemption),
                "upper": None
                if row["upper"] is None
                else str(Decimal(row["upper"]) * 1000000 - exemption),
                "rate": row["percent"],
            }
            for row in facts["tax"]["bands"]
        ],
        "thresholds": {"floor": None, "ceiling": None},
        "rounding": deepcopy(rounding),
        "correction_mode": "source_version_governed",
    },
    [annual, amendment],
)
floor = Decimal(facts["insurance"]["daily_floor_IRR"])
insurance = govern(
    {
        "component_mappings": [
            {"component_code": code, "classification": "insurable", "basis_factor": "1"}
            for code in ("BASE", "HOUSING")
        ],
        "basis_mode": "insured_remuneration_and_days",
        "contribution_categories": [
            {"code": "SSO_EMPLOYEE", "payer": "employee", "rate": "7"},
            {"code": "SSO_EMPLOYER", "payer": "employer", "rate": "20"},
            {"code": "SSO_GOVERNMENT", "payer": "other", "rate": "3"},
            {"code": "UNEMPLOYMENT", "payer": "employer", "rate": "3"},
        ],
        "thresholds": {
            "floor": None,
            "ceiling": None,
            "daily_minimum": str(floor),
            "daily_maximum": str(
                floor * Decimal(facts["insurance"]["daily_ceiling_multiplier"])
            ),
        },
        "exemptions": [],
        "rounding": deepcopy(rounding),
        "correction_mode": "source_version_governed",
    },
    [sso, housing],
)
for name, value in (("TAX_PARAMETERS", tax), ("INSURANCE_PARAMETERS", insurance)):
    (OUT / (name + ".json")).write_text(
        json.dumps(value, indent=2) + "\n", encoding="utf-8"
    )
(OUT / "SOURCE_VERSION_DELTAS.json").write_text(
    json.dumps(
        {
            "housing": {
                **housing,
                "earlier_monthly_IRR": "9000000",
                "current_monthly_IRR": "30000000",
                "monthly_delta_IRR": "21000000",
                "official_url": "https://qavanin.ir/Law/TreeText/?IDS=608044749350627921",
                "metadata_note": "Portal execution metadata says 1405/02/15; operative text expressly makes entitlement effective from 1405/01/01. Issue/publication are separate.",
            },
            "tax_amendment": amendment,
            "component_boundary": "Only explicitly reviewed BASE remuneration for tax; BASE and HOUSING insured remuneration. Benefit tax conditions, other components and exceptional populations fail closed. No name/kind inference or statutory wage generation.",
            "historical_sources": "Original reviewed v1 package and artifact catalog unchanged; base-law hashes remain in original package adopted by Human review.",
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
print(
    "Retained hashes verified; two bounded parameter sets constructed; annual brackets never divided by 12."
)

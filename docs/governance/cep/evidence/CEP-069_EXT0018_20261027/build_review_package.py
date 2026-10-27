"""Build a review intake from retained official sources, never an activation payload."""

import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
sys.path.insert(0, str(ROOT))
from core.jalali import gregorian_to_jalali, jalali_to_gregorian


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(identity, issuer, number, adopted, published, effective, files, notes):
    retained = []
    for name in files:
        path = OUT / name
        content = path.read_text("utf-8") if path.suffix == ".txt" else ""
        assert "heading در ﺣﺎل" not in content, name
        retained.append(
            {"path": name, "sha256": sha(path), "bytes": path.stat().st_size}
        )
    return {
        "id": identity,
        "issuing_authority": issuer,
        "document_number": number,
        "version": "Official portal snapshot retrieved 2026-10-27; amendments as displayed",
        "adopted_on_jalali": adopted,
        "published_on_jalali": published,
        "effective_from_jalali": effective,
        "effective_to": None,
        "effective_from_gregorian": date(
            *jalali_to_gregorian(*map(int, effective.split("/")))
        ).isoformat()
        if effective
        else None,
        "effective_to_status": "Not supplied; no end date inferred",
        "retrieved_at_utc": datetime.fromtimestamp(
            (OUT / files[0]).stat().st_mtime, timezone.utc
        ).isoformat(),
        "retrieval_location": "https://qavanin.ir/ (government laws portal; normal browser)",
        "artifacts": retained,
        "applicability_notes": notes,
    }


sources = [
    source(
        "IR-BUDGET-1405",
        "Iranian Parliament; promulgated by President",
        "203337; Official Gazette23589",
        "1404/12/25",
        "1404/12/28 (Gazette);1405/01/27 (portal)",
        "1405/01/01",
        ["IR_BUDGET_1405.ax.txt", "IR_BUDGET_1405_METADATA.ax.txt"],
        "Budget enactment/effective-date authority. Portal text references images for tables; annual tax table separately retained from INTA circular. Portal consolidated version shows1405/04/10 amendment; not a reviewer currentness attestation.",
    ),
    source(
        "INTA-200-1005-S-1405",
        "Iranian National Tax Administration",
        "200/1005/ص",
        "1405/01/31",
        "1405/02/02",
        None,
        ["INTA_1405_CIRCULAR.ax.txt", "INTA_1405_METADATA.ax.txt"],
        "Annual1405 income exemption and salary tax bands, table1 rows1-1 and2-1. Effective-date metadata blank; underlying budget is effective1405/01/01. Do not turn annual bands into period/cumulative semantics without reviewed authority. Portal explicitly notes illegible pages4/5; no missing values reconstructed.",
    ),
    source(
        "LABOR-6682-1405",
        "Supreme Labour Council; Ministry of Cooperatives Labour and Social Welfare",
        "6682",
        "1404/12/24",
        "1405/02/09 (portal); issued1405/01/31",
        "1405/01/01",
        ["LABOR_1405_WAGE.ax.txt", "LABOR_1405_METADATA.ax.txt"],
        "Text paragraph1 states start of1405; metadata execution date blank. Wage floor, seniority and allowances are source facts, not automatically applicable to every employment class. Clauses5/6/8/9 retain conditional/exceptional applicability.",
    ),
    source(
        "SSO-1000-1405-493",
        "Social Security Organization; Managing Director",
        "1000/1405/493",
        "1405/02/07",
        "1405/02/14",
        "1405/01/01",
        ["SSO_1405_WAGE.ax.txt", "SSO_1405_METADATA.ax.txt"],
        "Daily insurance wage floor; paragraph13 sevenfold daily ceiling and29/30/31-day treatment. Paragraphs1/6/7/9/10/11/12 distinguish wage schedules, optional insurance, trades, drivers, construction workers and exemptions. Paragraph4 flags subsequent housing changes. Do not substitute contract-retention/Billing insurance for employee insurance.",
    ),
    source(
        "INTA-200-1405-59",
        "Iranian National Tax Administration",
        "200/1405/59",
        "1405/07/27",
        "1405/07/29",
        "1405/07/27",
        [
            "INTA_1405_EXEMPTION_AMENDMENT.ax.txt",
            "INTA_AMENDMENT_METADATA.ax.txt",
            "INTA_AMENDMENT_SCAN_INDEX.ax.txt",
            "INTA_AMENDMENT_ISSUED.gif",
        ],
        "Text says replacement from issue date; metadata execution date blank. Title cites prior200/1403/39; portal body transcribes200/1406/39. Original issued scan retained for reconciliation; no silent correction of portal evidence. Benefits subject to legally qualified ordinary limits; reviewer must address applicability and referenced prior circular.",
    ),
    source(
        "IR-SOCIAL-SECURITY-ACT-1354",
        "Iranian legislature; official consolidated government publication",
        "Social Security Act; portal15217005284570186428",
        "1354/04/03",
        None,
        None,
        ["SOCIAL_SECURITY_ACT.ax.txt"],
        "Article28 and note1 retain original and1355 contribution-share transition; current applicability, worker classes, other contributions and later changes require accepted review. Article38 is contract-retention authority and is not substituted for employee insurance.",
    ),
    source(
        "IR-UNEMPLOYMENT-INSURANCE-ACT-1369",
        "Iranian Parliament",
        "Unemployment Insurance Act; portal1010273200061683763",
        "1369/06/26",
        None,
        "1369/05/06",
        ["UNEMPLOYMENT_INSURANCE_ACT.ax.txt"],
        "Article5 provides3percent employer-paid contribution. Article1 exclusions and article13 stated commencement retained. No universal application to foreign nationals, optional insurance or other excluded classes is inferred.",
    ),
    source(
        "IR-ANNUAL-BUDGET-PROVISIONS-1404",
        "Iranian Parliament",
        "Annual Budget Provisions Act; portal1903819389959200956",
        "1404/09/30",
        None,
        None,
        ["ANNUAL_BUDGET_PROVISIONS_ACT.ax.txt"],
        "Article1 clauses1/2 are cited by annual tax table; retain annual exemption/bands and multi-source income authority. No monthly/YTD runtime formula inferred.",
    ),
    source(
        "IR-DIRECT-TAXES-ACT-1366",
        "Iranian Parliament; official government consolidated text",
        "Direct Taxes Act; portal892583840653829785",
        "1366/12/03",
        None,
        None,
        ["DIRECT_TAXES_ACT.ax.txt", "DIRECT_TAXES_ACT.rendered.json"],
        "Full rendered official text captured because accessibility representation abbreviates a long law. Articles82/83/84/85/86/91 provide salary-income definition, base, annual-budget reference, withholding and exemptions; current amendments/applicability and exact software mapping require accepted review. Original1366 rates are not substituted for1405 budget bands.",
    ),
]
for item, portal_id in zip(
    sources,
    [
        "17235897393895510166",
        "2617869460704551710",
        "3754395167104657494",
        "4409953025337624313",
        "13058438638422765313",
        "15217005284570186428",
        "1010273200061683763",
        "1903819389959200956",
        "892583840653829785",
    ],
    strict=True,
):
    item["source_url"] = "https://qavanin.ir/Law/TreeText/?IDS=" + portal_id
    for artifact in item["artifacts"]:
        if artifact["path"].endswith("METADATA.ax.txt"):
            artifact["retrieval_url"] = (
                "https://qavanin.ir/Law/Attribute/?IDS=" + portal_id
            )
        elif artifact["path"] == "INTA_AMENDMENT_SCAN_INDEX.ax.txt":
            artifact["retrieval_url"] = (
                "https://qavanin.ir/Law/ImageText/?IDS=" + portal_id
            )
        elif artifact["path"] == "INTA_AMENDMENT_ISSUED.gif":
            artifact["retrieval_url"] = (
                "https://qavanin.ir/resource/regulation/317863/eblagh/130133-1.gif"
            )
            artifact["retrieval_method"] = (
                "Normal browser image download; direct HTTPS returned a challenge"
            )
        else:
            artifact["retrieval_url"] = item["source_url"]

package = {
    "artifact_kind": "EXT-0018 review intake, not runtime import JSON",
    "evidence_format_version": 1,
    "package_id": "EXT0018-IR-1405-20261027-REVIEW-v1",
    "as_of_gregorian": "2026-10-27",
    "as_of_jalali": "/".join(map(str, gregorian_to_jalali(2026, 10, 27))),
    "governance": {
        "cep": "CEP-069",
        "imb": "IMB-0083",
        "pd": "PD-031",
        "spec": "SPEC-030",
        "recovery": "CANONICAL.json",
    },
    "sources": sources,
    "source_facts_for_review_only": {
        "tax": {
            "source": "INTA-200-1005-S-1405",
            "location": "table1 rows1-1 and2-1",
            "unit": "million IRR per year",
            "annual_exemption": "4800",
            "bands": [
                {"lower": "4800", "upper": "9600", "percent": "10"},
                {"lower": "9600", "upper": "12000", "percent": "15"},
                {"lower": "12000", "upper": "14400", "percent": "20"},
                {"lower": "14400", "upper": "16800", "percent": "25"},
                {"lower": "16800", "upper": None, "percent": "30"},
            ],
            "runtime_conversion": "NOT_PERFORMED; source annual taxable-income bands are not yet engine post-exemption period bands",
        },
        "insurance": {
            "source": "SSO-1000-1405-493",
            "daily_floor_IRR": "5541850",
            "daily_ceiling_multiplier": "7",
            "location": "paragraphs1 and13",
            "base_law_contribution_shares_for_review": {
                "source": "IR-SOCIAL-SECURITY-ACT-1354",
                "location": "article28 and note1",
                "insured_percent": "7",
                "employer_percent_from_1355": "20",
                "government_percent": "3",
            },
            "unemployment_contribution_for_review": {
                "source": "IR-UNEMPLOYMENT-INSURANCE-ACT-1369",
                "location": "article5; article1 exclusions",
                "percent": "3",
                "payer": "employer",
            },
            "runtime_contribution_categories": None,
            "shares_status": "Underlying article28 and unemployment article5 acquired. Current applicability and exceptions require qualification; no mapping of government share to runtime payer inferred",
        },
        "labor": {
            "source": "LABOR-6682-1405",
            "location": "paragraphs1-4",
            "daily_minimum_wage_IRR": "5541850",
            "daily_seniority_IRR": "166667",
            "monthly_household_allowance_IRR": "22000000",
            "monthly_marital_allowance_IRR": "5000000",
            "classification_and_exception_application": "REVIEW_REQUIRED",
        },
    },
    "runtime_schema_compatibility": {
        "existing_import_schema_version": 1,
        "required_envelope_keys": [
            "schema_version",
            "ytd_treatment",
            "retroactivity",
            "evidence_references",
        ],
        "policy_codes": ["payroll-tax-regulatory", "employee-insurance-regulatory"],
        "accepted_review_and_source_links_required_before_import": True,
        "runtime_policy_parameters": None,
        "importable": False,
        "reason": "No accepted Payroll review; no approved component/basis/share/YTD/rounding/retroactivity mapping. Nulls are intake gaps, never runtime defaults.",
    },
    "review": {
        "disposition": "PENDING_HUMAN_REVIEW",
        "reviewer_identity": None,
        "qualification_summary": None,
        "independence_statement": None,
        "review_scope": "1405 currentness/applicability and exact statutory-to-engine mapping as of1405/08/05",
        "reviewed_on": None,
        "evidence_reference": None,
    },
    "activation": {
        "status": "NOT_EXECUTED",
        "policy_version_id": None,
        "package_digest_at_activation": None,
        "actor": None,
        "audit_event": None,
        "scope": "No runtime import or activation; production separately gated",
    },
    "source_history": "Prior repository evidence and sealed canonical archives preserved. No published runtime versions exist to supersede. New review intake is independently versioned.",
}
encoded = json.dumps(
    package, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
).encode()
package["content_sha256_excluding_this_field"] = hashlib.sha256(encoded).hexdigest()
(OUT / "EXT0018_SOURCE_REVIEW_PACKAGE.json").write_text(
    json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)
runtime_paths = [
    "apps/payroll/models.py",
    "apps/payroll/source_package_services.py",
    "apps/payroll/statutory_services.py",
    "apps/payroll/test_cep052.py",
    "apps/payroll/test_p7_s23_s28_statutory_payroll.py",
    "apps/organizations/policy_services.py",
    "apps/organizations/policy_specs.py",
    "core/jalali.py",
]
(OUT / "IMPLEMENTATION_HASHES.json").write_text(
    json.dumps({p: sha(ROOT / p) for p in runtime_paths}, indent=2) + "\n",
    encoding="utf-8",
)
print(
    json.dumps(
        {
            "package": package["package_id"],
            "official_sources": len(sources),
            "digest": package["content_sha256_excluding_this_field"],
            "importable": False,
        }
    )
)

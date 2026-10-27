"""Read-only EXT-0018 discovery and canonical recovery; no statutory authoring."""

import csv
import hashlib
import io
import json
import re
import subprocess
import zipfile
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
ARCHIVES = Path(
    "E:/ERP_Construction_Documents/New Version/"
    "BONIRA_TRUE_LATEST_STATE_RECONSTRUCTION_20261013/Consolidated_Packages"
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write(name, data):
    (OUT / name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


registry = yaml.safe_load((ROOT / "CEP_EXECUTION_REGISTRY.yaml").read_text("utf-8"))
manifest = yaml.safe_load(
    (ROOT / "docs/governance/cep/CEP_PROMPT_MANIFEST.yaml").read_text("utf-8")
)
prompt_path = "docs/governance/cep/PROMPTS/CEP-069_EXECUTION_PROMPT.md"
prompt_hash = digest((ROOT / prompt_path).read_bytes())
assert prompt_hash == "41d138764cb8fcde81dfea26f6c6df82202c54e4da3a641b2b18382811f2ebba"
assert prompt_hash in json.dumps(manifest)
git = lambda *args: subprocess.check_output(
    ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
).strip()
write(
    "GROUNDING.json",
    {
        "client_date": "2026-10-27",
        "branch": git("branch", "--show-current"),
        "head": git("rev-parse", "HEAD"),
        "cached_origin_main": git("rev-parse", "origin/main"),
        "ahead_behind_cached": git(
            "rev-list", "--left-right", "--count", "HEAD...@{upstream}"
        ),
        "entry_tree": "CLEAN before this session's manifest edit",
        "current_diff": git("diff", "--name-status"),
        "prompt_sha256": prompt_hash,
        "prompt_manifest_match": True,
        "prerequisite": registry["ceps"]["CEP-052"]["execution"],
        "gate08": registry["gates"]["GATE-08"]["status"],
        "gate11": registry["gates"]["GATE-11"]["status"],
        "git_writes": "NOT_EXECUTED",
        "production_access": "NOT_EXECUTED",
    },
)

canonical = {}
expected = {
    "BONIRA_PRODUCT_DECISION_FREEZE": "1c11429f2e0cc16c61b585832537e5035d19d008bccefc4e94f6d18839047599",
    "BONIRA_REQUIRED_SPECIFICATION_COMPLETION": "cf45d1f6db5821084205e3cdf0553cd68c036855cd4c1d5bbe1ee28c7e6693be",
    "BONIRA_FINAL_IMPLEMENTATION_MASTER_BACKLOG": "7cc3d73c1673b8d50cec337ea030514248ae0115cfc3aef260e212ad0a04b6be",
    "BONIRA_CODEX_EXECUTION_PACKAGE_DESIGN": "15f8d71a3f3e14feed9e7162b81f74ad39b546df9aff3ec5b01e1a676deaf429",
    "BONIRA_IMPLEMENTATION_DEPENDENCY_GRAPH": "dc0d006be37dcf9f48051da7a878342e2397d0db3962d1b0ce50bfef539de5c6",
    "BONIRA_IMPLEMENTATION_ROADMAP": "54082de6f32d9a26805aaa3050f24a9863d73f840d827274f0cd3145988b6784",
}
for prefix, expected_hash in expected.items():
    path = next(ARCHIVES.glob(prefix + "*.zip"))
    actual = digest(path.read_bytes())
    assert actual == expected_hash, path.name
    item = {
        "path": str(path),
        "sha256": actual,
        "matches_retained_identity": True,
        "members": {},
    }
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            selected = []
            if name.endswith(".csv"):
                rows = csv.DictReader(
                    io.StringIO(archive.read(name).decode("utf-8-sig"))
                )
                for row in rows:
                    if any(
                        value == target
                        for value in row.values()
                        for target in (
                            "SPEC-030",
                            "IMB-0083",
                            "EXT-0018",
                            "GATE-11",
                            "CEP-069",
                        )
                    ):
                        selected.append(row)
            elif name.endswith("BONIRA_FINAL_PRODUCT_DECISION_REGISTER.md"):
                content = archive.read(name).decode("utf-8-sig")
                start = content.index("### `PD-031`")
                selected = [content[start : content.index("## 6.", start)].strip()]
            elif name.endswith(
                "BONIRA_PAYROLL_STATUTORY_SOURCE_PACKAGE_SPECIFICATION.md"
            ):
                selected = [archive.read(name).decode("utf-8-sig")]
            if selected:
                item["members"][name] = {
                    "sha256": digest(archive.read(name)),
                    "extract": selected,
                }
    canonical[path.name] = item
write("CANONICAL.json", canonical)

# Inventory retained text and every archive member name, without exposing content,
# credentials or personal data. A match is a discovery lead, never source approval.
roots = [
    ROOT / "docs",
    ROOT / "certification",
    ROOT / "scripts",
    Path("E:/ERP_Construction_Documents"),
    Path("E:/BONIRA_Operations"),
    Path("E:/BONIRA_Recovery"),
    Path("C:/Users/azera/.codex/attachments"),
]
terms = re.compile(
    r"statutor|payroll.tax|employee.insurance|EXT.?0018|PD-031|SPEC-030|مالیات|بیمه|دستمزد",
    re.IGNORECASE,
)
counts = Counter()
leads = []
archive_members = []
errors = []
for base in roots:
    if not base.exists():
        errors.append({"root": str(base), "error": "ROOT_NOT_PRESENT"})
        continue
    for path in base.rglob("*"):
        if not path.is_file() or OUT in path.parents:
            continue
        counts[str(base)] += 1
        try:
            if path.suffix.lower() == ".zip":
                with zipfile.ZipFile(path) as archive:
                    names = [n for n in archive.namelist() if terms.search(n)]
                    if names:
                        archive_members.append(
                            {
                                "path": str(path),
                                "sha256": digest(path.read_bytes()),
                                "members": names,
                            }
                        )
            if path.suffix.lower() in {
                ".md",
                ".txt",
                ".json",
                ".csv",
                ".yaml",
                ".yml",
                ".html",
            }:
                if path.stat().st_size > 8_000_000:
                    continue
                data = path.read_bytes()
                text = data.decode("utf-8-sig", errors="replace")
                matches = terms.findall(text)
                if matches:
                    leads.append(
                        {
                            "path": str(path),
                            "sha256": digest(data),
                            "matched_terms": sorted({m.lower() for m in matches}),
                        }
                    )
            elif terms.search(path.name):
                leads.append(
                    {
                        "path": str(path),
                        "kind": "BINARY_FILENAME_LEAD_ONLY",
                        "bytes": path.stat().st_size,
                    }
                )
        except (OSError, zipfile.BadZipFile, RuntimeError) as error:
            errors.append({"path": str(path), "error": type(error).__name__})
write(
    "DISCOVERY.json",
    {
        "counts": counts,
        "text_and_filename_leads": leads,
        "archive_member_leads": archive_members,
        "errors": errors,
        "limits": "Named retained project/evidence roots, not every disk or remote environment. Text over8MB excluded. Matches do not authenticate statutory content.",
    },
)
print(
    json.dumps(
        {
            "canonical_archives_verified": len(canonical),
            "inventory_files": sum(counts.values()),
            "leads": len(leads),
            "archives_with_leads": len(archive_members),
            "errors": len(errors),
        }
    )
)

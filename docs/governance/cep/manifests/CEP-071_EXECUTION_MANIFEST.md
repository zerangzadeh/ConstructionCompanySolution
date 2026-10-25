# CEP-071 execution manifest

2026-10-25; IMB0099; main566073b35f2f5bb8b08267b56856fb85b7a0fcf0.
Canonical prompt verified; no mandatory CEP prerequisite. EXT0021 production-only
permits non-production preparation, not certification. PD004/SPEC006 retain
UNSPECIFIED topology. [Entry/touch set](../evidence/FRONTIER_069_078_20261025/CEP071_ENTRY.json).

Before execution: touch Registry, this manifest, required report/AC/evidence/change
CSV files and CEP071 evidence in shared frontier directory. Product/settings,
schema, migrations, business data and UI unchanged. Isolated synthetic environment
imports existing production settings with dotenv disabled; no Django setup/DB
connection or production target. No cloud/process/static/media provider, host
count, SLA or activation authority invented. Production certification evidence
required by canonical AC remains unavailable and cannot be supplied by these tests.

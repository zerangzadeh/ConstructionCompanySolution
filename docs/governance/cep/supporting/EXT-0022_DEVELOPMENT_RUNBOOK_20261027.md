# EXT-0022 executable Development qualification

Authority: [Human approval](EXT-0022_HUMAN_APPROVAL_20261027.md).
OP-01..04 in [operations preparation](CEP-072_OPERATIONS_PREPARATION.md) are
approved for this target by that instruction. The Human Decision Authority owns
operation, incident escalation, runbook maintenance, revocation oversight and
activation/acceptance; Codex executes this session. Post-run technical PASS does
not impersonate a Human review or issue Human Sign-off.

Target: Windows Development, explicit `config.settings.development`, isolated
pytest PostgreSQL database whose name starts with `test_`, configured local
cache, ephemeral loopback-only WSGI HTTP process. No configured business database
is queried by the scenario. Synthetic tenants/actors carry existing registered
permissions and scope; their transactional fixtures roll back after execution.
No schema or migration action is part of this package.

Signals: the six established `core.operations.SIGNALS` only. Technical HTTP
status is never a financial/integration event or business readiness authority.
Cache GET reachability proves only the selected Development cache contract.

Sink: a fresh restricted child of `E:/BONIRA_Operations/EXT0022`, provisioned and
recursively verified using the existing Windows DACL implementation. Allowed
principals: current executor, Local System, local Administrators. No network
destination. Fixed-field HTTP telemetry and discrete failure alerts are linked
by server correlation UUID, written exclusively, flushed/fsynced and read back.
The sink and incident copy survive executor exit/restart. Retention metadata is
30 days from observation; no automatic purge or scheduled service is installed.
OP-04 requires owner-controlled review after that period; business/audit records
are outside diagnostic disposal. Future elapsed retention is unverified until due.

Execute from repository root with the existing `.venv-2` runtime:

```powershell
$env:BONIRA_OPERATIONS_EVIDENCE = '<absolute fresh package evidence directory>'
.venv-2/Scripts/python.exe -m pytest scripts/cep072_qualification_scenarios.py --reuse-db -q
```

1. OP-01: start only loopback WSGI with a synthetic scenario route. Trigger HTTP
   503, read back structured log and correlated alert, then recover to HTTP 200.
   Temporarily rename only this run's private sink to its checked sibling to
   exercise a genuine delivery failure, restore in `finally`, retain sanitized
   fallback and alert. The successful response remains successful. No business
   operation is replayed. Escalation authority is the Human Decision Authority;
   no response timer or acknowledgement is inferred from receipt.
2. OP-02: run actual read-only `operational_health` against the isolated test DB
   and cache. For the fault only, select a reserved unlistened loopback DB port.
   Confirm nonzero result, both dependency signals and NOT_VALIDATED Production
   readiness. Restore the original test connection configuration and re-probe.
   This is a configuration-only synthetic outage/recovery; no migration,
   database restore, production-equivalent deployment or finalized-history
   correction is performed. Existing approved deployment/recovery procedures
   govern any later action requiring those mechanisms.
3. OP-03: execute existing request/tenant-confirm/independent-platform-approve/
   use/revoke services with explicit current permission/scope fixtures. Reject
   self approval, premature approval, non-independent approval, wrong purpose,
   wrong scope and revoked use. Retain actual database audit action evidence.
   Create a short-lived grant through the service, wait until its real UTC
   expiry and prove denied use. No raw grant or timestamp mutation is needed.
4. OP-04: reopen the sink, compare hashes, verify every diagnostic's retention
   timestamp and DACLs, retain restricted incident identity/times/owner/actions/
   receipts/access-audit summary/resolution evidence. Stop HTTP and detach the
   session handler in `finally`; leave retained files intact.

Failure is a failed attempt, with output retained. Missing receipt is never
PASS. CEP-072 implementation qualification precedes its completion and gate
review; CEP-076 uses a fresh actual execution of the frozen scenario and product
sources after verified entry. No product/configuration mutation to force a
CEP-076 PASS is allowed. A defect would return to a separately recorded bounded
CEP-072 implementation action under the current Human remediation instruction.

# EXT-0020 Human approval — bounded Development qualification

Source: direct Human Decision Authority message in the current session,
2026-10-27. Verbatim decision follows. This is authority for its stated scope,
not an amendment to canonical CEP AC/DoD or a production-equivalence assertion.

> EXT-0020 — HUMAN DECISION APPROVED
>
> Approve the following common recovery policy for all four governed recovery classes for the current Development / Non-Production qualification scope:
>
> - **RPO:** 15 minutes
> - **RTO:** 60 minutes
> - **PITR:** Not required for the current Development qualification. Use complete-bundle recovery. PITR may be reconsidered separately for Production Readiness.
> - **Backup frequency:** Every 15 minutes
> - **Retention:** 30 days
> - **Restore-test frequency:** Every 30 days
> - **Recovery target/environment:** Use the existing isolated Windows / PostgreSQL 18.6 synthetic Development recovery environment as the current qualification target. Do not claim Production equivalence; retain equivalence gaps for later Production Readiness.
> - **Restore owner:** Human Decision Authority is accountable for this bounded non-production qualification; Codex is authorized as the technical executor for this session.
> - **Acceptance authority:** Human Decision Authority.
> - **Protected recovery target / key recovery:** Approve local synthetic-only recovery storage on the existing Development host, with verified restricted filesystem access and existing private Development secret sources. This does not establish encrypted-backup/key-custody qualification or Production storage readiness.
>
> No class-specific exceptions are approved at this stage.
>
> This approval applies only to EXT-0020 and the Development / Non-Production scope required to advance CEP-070 and, when eligible, CEP-074.
>
> It does not authorize Production backup/restore, Production deployment, cutover, Production key custody, final certification or Human Sign-off.
>
> Record this response as EXT-0020 authority.
>
> Proceed autonomously with:
>
> `complete CEP-070 remaining scope → verify AC/DoD → reconcile gates → execute CEP-074 when eligible`
>
> Implement and verify any Development-resolvable controls required by the approved objectives. Fix attributable defects and continue without further Human interruption unless a genuinely new Product/Domain/Production authority decision is required.
>
> No Git write unless separately authorized.

## Execution interpretation

The approved durations apply to all four canonical classes, with no exceptions.
Retention preserves recovery copies for at least the approved period; this
decision authorizes no purge or rewriting of document/audit retention policy.
The local qualification can prove its actual recovery results, scheduling and
retention controls. It cannot establish production equivalence, production
operation, 30 elapsed days of retention, or a future recurring run merely from
configuration. No unattended task outside this session is installed by inference.

CEP-074 remains subject to its canonical production-equivalent target and
mandatory CEP-070 outcome. Missing production equivalence is recorded separately
from the now-approved Development objectives and ownership.

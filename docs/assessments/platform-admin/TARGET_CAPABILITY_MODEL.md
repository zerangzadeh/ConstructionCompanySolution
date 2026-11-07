# Target Platform Admin capability model

Assessment date 2026-11-06. This is a proposed target for explicit implementation authorization. Current implementation and evidence are recorded in [the capability matrix](CAPABILITY_MATRIX.md). Priorities preserve the capability-level MVP and backend-active hidden domains.

## Product and authority principles

The platform control plane owns tenant establishment, bounded tenant lifecycle and platform governance. Tenant business services retain their existing permissions, membership, object scope, financial authority and finalized-history rules. A module's backend presence does not establish release readiness, licensing or statutory activation. Existing apps, models, migrations and domain handoffs remain preserved. [docs/architecture/PRODUCT_VISION_AND_MVP_RELEASE_STRATEGY.md:51](../../../docs/architecture/PRODUCT_VISION_AND_MVP_RELEASE_STRATEGY.md#L51) [docs/architecture/PRODUCT_VISION_AND_MVP_RELEASE_STRATEGY.md:65](../../../docs/architecture/PRODUCT_VISION_AND_MVP_RELEASE_STRATEGY.md#L65) [apps/organizations/authorization.py:110](../../../apps/organizations/authorization.py#L110)

Reuse Django Templates, Tailwind, the shared list/form/error components, registered permissions, independent platform duties, append-only audit and the current transaction/locking services. A platform duty should have an explicit capability contract rather than imply tenant membership. [apps/organizations/platform_grants.py:47](../../../apps/organizations/platform_grants.py#L47) [apps/organizations/permission_registry.py:19](../../../apps/organizations/permission_registry.py#L19) [templates/components/operational_list.html:1](../../../templates/components/operational_list.html#L1)

## Proposed information architecture

| Destination | Content and operator decisions | Priority and readiness boundary |
| --- | --- | --- |
| Platform overview | Counts by company lifecycle, onboarding exceptions, recent platform security events, qualified service-health signals and operator actions. Every metric names its source and cutoff. | P0 useful entry and safety exceptions. P1 richer analytics. |
| Companies | Searchable directory. Company detail with overview, onboarding/ownership, activity, configuration and permitted lifecycle actions. Explicit target company and reason/version controls. | P0, extending the existing directory and bounded services. |
| Access and governance | Separate platform operator assignments, tenant business-role definitions, explicit tenant assignments and protected-operation policies. Global permission edits show affected tenants/memberships and approval requirements. | P0. Platform-duty policy and Superuser boundary require Human decisions. |
| Security and audit | Read-only global privilege history, investigation filters and evidence references. Separate per-company activity and operational authentication signals. Privileged authentication/session controls with an approved recovery procedure. | P0 controls and investigations. P1 investigation ergonomics. |
| Operations | Dependency reachability, errors, deployment/migration status, backup/restore evidence and actionable alerts linked to an owned runbook. | P0 operational qualification. P1 UI. Worker views only after approved asynchronous workloads exist. |
| Configuration and release | Inventory of domain-owned policies and global configuration. Capability readiness and exposure policy are separate from per-tenant entitlements. | P1. Runtime toggles require approved semantics and preserve source-domain activation gates. |
| Support | Tenant diagnostics, case routing and a controlled access-request journey with tenant consent, independent approvals, exact purpose/scope, expiry and revocation. | P1, composing the existing hidden support capability. |
| Commercial administration | Fixed-plan/subscription records, licensing, entitlement versions, usage limits and external invoicing references, when approved. | P2 software. Establish customer-facing policy before sales. |
| Platform analytics | Defined activity/adoption/usage measures with privacy policy, cohorts and bounded tenant summaries. | P1 operational activity. P2 growth and commercial analytics. |

All entries above are proposed navigation labels. The deployed MVP navigation currently provides only the narrower set shown in the matrix.

## P0 — Secure MVP operation

- **Tenant establishment and ownership.** Attribute the initiating operator and owner separately, recheck authority in the transaction, expose recoverable onboarding outcomes and provide an approved lost-owner procedure. Existing role assignment and Initial Grant mechanics should supply the building blocks. S02/C01. [apps/organizations/services.py:798](../../../apps/organizations/services.py#L798) [apps/organizations/platform_grants.py:127](../../../apps/organizations/platform_grants.py#L127)
- **Privileged duties and sensitive changes.** Resolve normal-versus-bootstrap separation policy, qualify MFA/step-up or the actual external alternative, protect global system-role edits and govern setup-sensitive configuration. S01/S03/S04/S05. [apps/organizations/access_services.py:814](../../../apps/organizations/access_services.py#L814) [apps/organizations/access_services.py:268](../../../apps/organizations/access_services.py#L268)
- **Audit and operator certainty.** Supply a safe global security-event workspace, complete structured metadata validation, make company targets unmistakable, and expose the platform entry on supported viewports. S06/S07/U01/U02/U05. [apps/audit/services.py:35](../../../apps/audit/services.py#L35) [templates/base.html:687](../../../templates/base.html#L687)
- **Operational evidence.** Qualify the actual production auth, TLS, storage, alert and recovery boundary. Reconcile registry test failures and migration/environment discrepancies with their owners. A count widget or green dependency probe does not supply this evidence. C03/C09. [apps/support/management/commands/operational_health.py:36](../../../apps/support/management/commands/operational_health.py#L36) [core/production_operations.py:29](../../../core/production_operations.py#L29)

## P1 — Operational maturity

Build coherent onboarding/recovery/support journeys, a monitoring console using existing technical signals, domain-owned configuration navigation, safe role-catalog scale improvements and useful tenant activity summaries. Publish explicit capability-readiness metadata before adding per-tenant module controls. Cancellation/export/offboarding implementation depends on an approved tenant lifecycle and retention contract. C02/C03/C05/C06/C07/C08 and U03/U04/U06.

Existing support has purpose, scope, expiry, consent and independent confirmation semantics worth preserving. Platform Security and Platform Operations need a mapped, bounded contract before new menus are assigned to them. [apps/support/services.py:314](../../../apps/support/services.py#L314) [apps/support/services.py:352](../../../apps/support/services.py#L352) [apps/organizations/models.py:137](../../../apps/organizations/models.py#L137)

## P2 — Commercial SaaS expansion

Implement subscription, trial, entitlement, usage, licensing and growth tooling only after the corresponding business parameters and domain owners are approved. The present direction is one core plan with initial invoicing externally administered. Construction progress claims, Treasury cash authority and GL accounting must remain separate from SaaS commercial administration. Reuse their approved interfaces if later integrations are authorized. [docs/architecture/BUSINESS_MODEL.md:100](../../../docs/architecture/BUSINESS_MODEL.md#L100)

Full ERP exposure, automatic plan enforcement, subscription charging, new support impersonation and general-purpose background queues do not follow merely from adding an administrative screen. They require their own applicable contract, readiness evidence and Human decisions.

## Proposed capability contracts

| Contract | Required inputs and evidence | Acceptance boundary |
| --- | --- | --- |
| Company provisioning | Explicit initiator, intended owner, validated company identity, operation key, current platform authority, each provisioning outcome. | Retry preserves one logical company and a recoverable outcome. Owner and operator provenance remain distinguishable. |
| Lifecycle action | Target company, current version, allowed transition, reason, current platform authority and audit result. | State and audit commit together. Cancel/export/retention behaviors are defined before adding those transitions. |
| Platform-duty assignment | Actor, independent approver when required, recipient, duty, effective dates, reason and current authority. | A stale or ineligible approver cannot authorize a grant. No tenant membership is inferred. |
| Global role change | Intended permission diff, affected memberships, current version, protected classification, approval and rollback evidence. | Previewed, accepted and committed changes refer to the same approved version. |
| Support access | Tenant, requester, purpose, exact scope, expiry, tenant consent, independent approval and revocation. | Every consuming domain still authorizes its records and current access evidence. |
| Module entitlement | Tenant, versioned plan/entitlement, source readiness, release exposure and domain activation policy. | Availability never bypasses authentication, permissions, scope or financial/statutory gates. |

The table defines desired acceptance contracts for future packages. It does not amend current CEP Scope/AC/DoD or claim these contracts have already been implemented.

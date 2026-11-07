# Platform Admin capability and gap assessment

Assessment date 2026-11-06, Asia/Tehran.

BONIRA has a working, bounded Platform Admin control plane for company administration, business-role catalogs and policy governance. It has not yet established a complete production-ready platform operating model. The immediate gaps concern privileged governance, provisioning attribution/recovery, global security investigation and usable operator entry points. A subscription engine is not the next necessary implementation batch.

## What Platform Admin can actually do today

An account with an active independent Platform Admin duty can open the MVP company directory, inspect company activity summaries, open company creation and configuration forms, use the business-role catalog, manage protected-operation definitions and reach the specialized platform policy catalog. The directory supports search/status filters, membership counts and last recorded activity. Company services implement reasoned, version-checked suspension/reactivation and configuration updates with transactional audit. Their mutation tests were inspected, while this assessment exercised GET responses only. [apps/organizations/platform_views.py:31](../../../apps/organizations/platform_views.py#L31) [apps/organizations/platform_companies.py:104](../../../apps/organizations/platform_companies.py#L104) [apps/organizations/platform_companies.py:143](../../../apps/organizations/platform_companies.py#L143) [apps/organizations/test_platform_companies.py:184](../../../apps/organizations/test_platform_companies.py#L184)

During current read-only runtime checks, the account admin had active Platform Admin authority and received HTTP 200 for the directory, company detail/edit, creation, role catalog, protected-operation catalog and policy catalog. Existing non-platform and Superuser-without-platform-duty accounts received 403 for the sampled platform destinations. Anonymous requests redirected to login. The detailed response matrix is in [CAPABILITY_MATRIX.md](CAPABILITY_MATRIX.md#representative-runtime-evidence).

## What exists but is inaccessible or incomplete

Platform-duty assignment and revocation services exist, but there is no corresponding operational administrator-management page in the reviewed platform routes. These operations require Superuser authority. The visible role catalog edits OrganizationRole business definitions, including global and tenant roles, rather than PlatformRoleAssignment. The distinction is important for both usability and security. [apps/organizations/access_services.py:814](../../../apps/organizations/access_services.py#L814) [apps/organizations/access_services.py:887](../../../apps/organizations/access_services.py#L887) [apps/organizations/views.py:790](../../../apps/organizations/views.py#L790)

Support cases, tenant notifications, controlled support access, technical monitoring building blocks, login branding and global audit storage exist. Support and technical Django Admin screens remain MVP-hidden. Monitoring provides dependency probes and sanitized request signals, not a platform operations dashboard. Per-company activity does not include organization-null platform privilege events. [apps/support/urls.py:6](../../../apps/support/urls.py#L6) [apps/support/services.py:352](../../../apps/support/services.py#L352) [apps/support/management/commands/operational_health.py:26](../../../apps/support/management/commands/operational_health.py#L26) [apps/audit/admin.py:34](../../../apps/audit/admin.py#L34)

Company creation establishes an active company and existing owner's membership atomically. Workflow bootstrap follows through on-commit callbacks, with no persisted onboarding completion/retry model found. The success redirect goes to the initiating user's membership selector, where the new company may not appear. Owner transfer/recovery has underlying role/Initial Grant mechanics but lacks a complete operator journey. [apps/organizations/services.py:683](../../../apps/organizations/services.py#L683) [apps/organizations/views.py:247](../../../apps/organizations/views.py#L247) [apps/organizations/platform_grants.py:127](../../../apps/organizations/platform_grants.py#L127)

## What critical functionality is missing

- A consistent privileged-duty lifecycle with an explicit normal-versus-bootstrap separation policy and fresh authority checks. S01.
- Initiating-operator provenance and transaction-bound authorization in company creation, plus recoverable onboarding and owner continuity. S02/C01.
- A safe global security-audit investigation workspace usable in MVP. S07.
- Qualification of actual privileged authentication, session revocation, production monitoring and recovery controls. S05/C03.
- Protection and impact policy for global role changes and setup-sensitive fiscal/numbering configuration. S03/S04.
- A platform-aware landing page, supported mobile navigation and unambiguous company target context. U01/U02/U05.

The detailed conditions, confidence levels and source anchors are in [SECURITY_AND_ROLE_BOUNDARIES.md](SECURITY_AND_ROLE_BOUNDARIES.md) and [UIUX_FINDINGS.md](UIUX_FINDINGS.md).

## Security and tenant-isolation assessment

The sampled runtime requests did not demonstrate unrestricted cross-tenant business-data access. The shared authorization model requires tenant membership, business permission and object scope. New company-directory/lifecycle services provide explicit control-plane authority and do not create membership for the operator. That boundary should be preserved. This is a scoped observation rather than a complete endpoint-isolation certification. [apps/organizations/authorization.py:110](../../../apps/organizations/authorization.py#L110) [core/admin.py:55](../../../core/admin.py#L55) [apps/organizations/test_platform_companies.py:90](../../../apps/organizations/test_platform_companies.py#L90)

Confirmed source findings require attention. Platform-duty assignment accepts the same active Superuser as actor and approver, while revocation requires independent approval. Company creation checks the platform role before entering the atomic owner service and records the owner as creator/audit actor, losing the initiating admin's provenance. Global system-role permission edits apply immediately to existing assignments without an operator-submitted version or approval identity. These are privileged governance risks, not evidence of an observed external intrusion. [apps/organizations/access_services.py:814](../../../apps/organizations/access_services.py#L814) [apps/organizations/access_services.py:887](../../../apps/organizations/access_services.py#L887) [apps/organizations/services.py:798](../../../apps/organizations/services.py#L798) [apps/organizations/access_services.py:268](../../../apps/organizations/access_services.py#L268)

A pure-function synthetic check also confirmed that audit metadata validation rejects a direct sensitive key but accepts that key inside a list of dictionaries. No real credential or customer payload was used. S06 documents the condition and proposed regression coverage. [apps/audit/services.py:35](../../../apps/audit/services.py#L35)

## What should happen before onboarding real customers

Authorize the bounded B01 correction batch first, with a Human decision on the intended privileged approval policy. Complete the parallel policy decisions for global role changes, setup-sensitive settings and owner recovery. Qualify actual production identity, TLS/storage, alert and restore behavior. Provide global audit investigation and usable platform entry/navigation, then execute browser acceptance on disposable non-production fixtures. [PRIORITIZED_REMEDIATION_PLAN.md](PRIORITIZED_REMEDIATION_PLAN.md)

The assessment found one pending development migration, payroll.0010_cep069_reviewed_statutory_context, and three failed static registry architecture tests. Reconcile these with their owning scopes before relying on the environment as a release baseline. The migration does not itself authorize statutory activation. No production environment was assessed. [apps/payroll/migrations/0010_cep069_reviewed_statutory_context.py:11](../../../apps/payroll/migrations/0010_cep069_reviewed_statutory_context.py#L11) [apps/organizations/test_permission_registry.py:51](../../../apps/organizations/test_permission_registry.py#L51)

## What should be deferred until after MVP

A complete SaaS subscription/license/trial/payment system, broad tenant entitlements, growth/cohort analytics and worker administration are later expansion work. The inspected inventory did not contain a complete SaaS plan/subscription/quota implementation. Existing DocumentRetentionPolicy and procurement RFQ models are unrelated matches from a broad model-name scan and are not SaaS licensing. Current approved direction uses one core plan and externally administered initial invoicing, with unresolved commercial parameters. Decide the policy before building commercial automation. [docs/architecture/BUSINESS_MODEL.md:100](../../../docs/architecture/BUSINESS_MODEL.md#L100) [config/urls.py:12](../../../config/urls.py#L12) [apps/documents/models.py:675](../../../apps/documents/models.py#L675)

Controlled support workflows, operational monitoring UI and measured tenant activity are P1 work that can follow the P0 authority and operational prerequisites. Preserve all hidden backend modules, models, migrations and financial source-of-truth boundaries. [TARGET_CAPABILITY_MODEL.md](TARGET_CAPABILITY_MODEL.md)

## Verification and limitations

| Evidence | Result and limit |
| --- | --- |
| Repository grounding | main at 59f2fde64fc3684f09871b82a2b1945905c28aab, same local origin/main reference. No network fetch or Git mutation. There were 264 pre-existing modified/untracked entries, including platform code and unrelated UI changes. The assessment uses the current working tree. |
| Source review | Current routes, views, templates, services, models, authorization, configuration and relevant test sources were inspected. Product strategy and governance constrained recommendations rather than proving functionality. |
| Django runtime checks | GET-only request-pipeline checks, signed-cookie sessions held in memory and an explicitly read-only development database transaction. MVP profile and admin's active platform duty were confirmed. Existing tenant records were used only for read inspection. |
| Browser checks | Attempted discovery returned “Local browser use is disabled in Work settings.” Browser-based interaction, screenshots, actual responsive rendering and accessibility acceptance are unavailable. |
| Static test selection | PermissionRegistryArchitectureTests and ReconciledMatrixTests, run with bytecode/cache writes disabled. Result 5 passed, 3 failed, 28 subtests passed. These are database-independent tests, not a mutation or full regression suite. |
| Static test failures | Four duplicate Payroll model registrations, 77 namespace mismatches, and missing enforcement references across resources. Their detailed scope is in the security report. |
| Migration inventory | One pending Payroll migration in the configured development database. Read-only inspection only. |
| Pure audit-validator probe | Direct synthetic token key rejected, same key nested inside a list accepted. No record was persisted. |
| Deployment qualification | Production identity provider, perimeter limits, monitoring/alert delivery, backups, restores, live secrets and production tenant state were not inspected. |
| Assessment changes | Exactly the six requested Markdown reports under docs/assessments/platform-admin/. Application code, schemas, permissions, UI and existing tenant data were outside the assessment mutation scope. |

## Report set

1. [Current capability matrix](CAPABILITY_MATRIX.md)
2. [Security and role boundaries](SECURITY_AND_ROLE_BOUNDARIES.md)
3. [UI/UX findings and journeys](UIUX_FINDINGS.md)
4. [Target capability model](TARGET_CAPABILITY_MODEL.md)
5. [Prioritized remediation plan](PRIORITIZED_REMEDIATION_PLAN.md)
6. This executive summary

The assessment is complete. Recommended next implementation scope is B01. Implementation awaits explicit approval of a bounded package and its required policy decisions.

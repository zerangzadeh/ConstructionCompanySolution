# Security and role boundaries

Assessment date 2026-11-06. Evidence covers the current working tree identified in [the capability matrix](CAPABILITY_MATRIX.md). Severity describes impact if the condition is exercised. An inferred risk is distinguished from a confirmed code behavior.

## Authority boundaries

| Authority | Actual enforcement | Appropriate operational boundary |
| --- | --- | --- |
| Platform Admin | Independent, effective-dated PlatformRoleAssignment. is_platform_admin requires authenticated active user and current, unrevoked duty. New company services also require active registered platform_companies permission codes. | Tenant metadata, bounded lifecycle/configuration, role catalog and policy governance. Ordinary tenant business records still require explicit membership and applicable business/object authority. |
| Superuser | Separate Django technical authority. Assign/revoke platform-duty services require it. Runtime checks denied platform-company routes to an existing Superuser without platform duty. | Exceptional technical recovery under governance. Superuser status must not be presented as equivalent to Platform Admin. |
| Tenant Owner | Effective owner assignment on a membership, explicit tenant scope and last-owner protections. | Tenant ownership and governance. Owner is not automatically Tenant Admin or Platform Admin. |
| Tenant Admin | Membership-scoped role and delegated permission subset. Tenant custom-role administration requires this duty. | Local administration within the same tenant, authorized grant subset and object scope. |
| Tenant Business User | Active membership, union of current role permissions, tenant state, project/site grants and domain/workflow rules. | Authorized business operations within current tenant and object context. |
| Platform Support | No universal support impersonator was found. Platform Operations/Security duties exist, while support_operator and support_access_approver are tenant business-role profiles. Existing support access requires explicit permissions and consent. | A separate support operating model must be designed around the existing consent, purpose, scope and expiry contract. A label alone grants no tenant access. |

Sources for these boundaries are the role evaluator, tenant membership resolver, role catalog manager, support access service and default grant exclusions. [apps/organizations/authorization.py:130](../../../apps/organizations/authorization.py#L130) [apps/organizations/authorization.py:110](../../../apps/organizations/authorization.py#L110) [apps/organizations/access_services.py:176](../../../apps/organizations/access_services.py#L176) [apps/organizations/role_defaults.py:877](../../../apps/organizations/role_defaults.py#L877) [apps/support/services.py:352](../../../apps/support/services.py#L352)

## Verified controls worth preserving

- New company mutations lock and re-read the actor's platform duty and target company, compare updated_at, require a reason, and commit state and audit atomically. Cancelled, deleted and archived companies fail closed. Tests cover stale versions, rollback on audit failure and inactive/revoked/expired authority. These are inspected tests, not mutation runs during this assessment. [apps/organizations/platform_grants.py:47](../../../apps/organizations/platform_grants.py#L47) [apps/organizations/platform_companies.py:104](../../../apps/organizations/platform_companies.py#L104) [apps/organizations/test_platform_companies.py:303](../../../apps/organizations/test_platform_companies.py#L303) [apps/organizations/test_platform_companies.py:339](../../../apps/organizations/test_platform_companies.py#L339)
- Platform directory activity is a bounded projection of event time, action and actor. The queryset excludes metadata and change payloads, and the template supplies no business-record detail links. The target company is selected explicitly under platform authority without changing the active-tenant session. [apps/organizations/platform_companies.py:51](../../../apps/organizations/platform_companies.py#L51) [apps/organizations/templates/organizations/platform_company_detail.html:24](../../../apps/organizations/templates/organizations/platform_company_detail.html#L24) [apps/organizations/test_platform_companies.py:90](../../../apps/organizations/test_platform_companies.py#L90)
- Tenant-facing Admin inspection uses mapped business permission and tenant/object scope, while unmapped models fail closed. Audit records reject application-layer updates/deletes. These controls do not prove database-level tamper resistance or complete endpoint coverage. [core/admin.py:55](../../../core/admin.py#L55) [apps/audit/models.py:1683](../../../apps/audit/models.py#L1683)
- Production settings reject insecure DB TLS and insecure session/CSRF cookies. Password recovery uses identity/source throttling, and temporary-password sessions are confined to approved initialization paths. Actual production configuration and delivery were not verified. [config/settings/production.py:45](../../../config/settings/production.py#L45) [config/settings/production.py:54](../../../config/settings/production.py#L54) [apps/accounts/views.py:56](../../../apps/accounts/views.py#L56) [apps/accounts/middleware.py:5](../../../apps/accounts/middleware.py#L5)

## S01 — Platform-duty assignment and revocation have inconsistent approval checks

**High, P0. Confirmed code condition, with privilege-governance impact inferred.**

assign_platform_role checks active Superuser actor/approver and forbids assigning the role to either of them, but does not require actor and approver to differ. revoke_platform_role explicitly requires an independent approver. Assignment also trusts the passed actor/approver flags rather than using the locked fresh-authority pattern implemented for company mutations. No dedicated UI offers an operational explanation of this difference. Do not describe current platform-duty lifecycle as uniformly dual-controlled. [apps/organizations/access_services.py:814](../../../apps/organizations/access_services.py#L814) [apps/organizations/access_services.py:887](../../../apps/organizations/access_services.py#L887) [apps/organizations/platform_grants.py:47](../../../apps/organizations/platform_grants.py#L47)

Require an explicit Human decision on the intended bootstrap exception versus normal dual control, then implement the decided rule consistently and test same-actor, stale-user, inactive-user and concurrent revoke cases. The assessment does not classify the existing historical bootstrap behavior as a remotely exploitable endpoint.

## S02 — Company creation loses initiating actor attribution and checks authority before its transaction

**High, P0. Confirmed source behavior.**

create_organization_by_system_admin verifies Platform Admin before calling the atomic create_organization_with_owner service. The actor is not forwarded. Company created_by/updated_by, initial ownership evidence and ORGANIZATION_CREATED actor are set to the owner. The initiating admin therefore cannot be reconstructed from that event alone. There is no locked current-duty recheck inside the company-creation transaction comparable to the new lifecycle service. [apps/organizations/services.py:798](../../../apps/organizations/services.py#L798) [apps/organizations/services.py:683](../../../apps/organizations/services.py#L683) [apps/organizations/services.py:729](../../../apps/organizations/services.py#L729) [apps/organizations/services.py:771](../../../apps/organizations/services.py#L771)

Preserve owner identity as an explicit separate fact, carry the initiating actor through the transaction, record the two authorities accurately, and test revocation races. Handle workflow bootstrap/retry under C01. This is an auditability and race-risk finding, not a demonstrated unauthorized creation.

## S03 — Editing a live global role has immediate multi-tenant impact

**High, P0. Confirmed mutation path, inferred blast-radius risk.**

The platform catalog edits OrganizationRole permissions. update_organization_role permits an active Platform Admin to edit a system role, then replaces permissions on the existing role. Effective membership permissions consume those same assignments. The service records old/new permissions and a reason, but has no approval identity or submitted version argument. A role row lock serializes updates without detecting a stale operator form. Platform role-edit authority is legitimate, but its global effect needs explicit presentation and a protected change policy. [apps/organizations/access_services.py:268](../../../apps/organizations/access_services.py#L268) [apps/organizations/authorization.py:211](../../../apps/organizations/authorization.py#L211) [apps/organizations/templates/organizations/role_catalog.html:29](../../../apps/organizations/templates/organizations/role_catalog.html#L29)

Require blast-radius preview, current-version checks, consistent revalidation of privileged authority and an approved approval/rollback policy for global system-role changes. Distinguish this from granting tenant business-data access to an administrator.

## S04 — Financial/calendar configuration changes lack a visible data-dependent impact policy

**High, P0. Code-derived risk requiring business-policy confirmation.**

The platform settings form includes currency, fiscal-year start and numbering fields inherited from OrganizationSettingsForm. The shared persistence helper applies validated values. Reviewed validation checks supported currency and calendar validity, but no historical-use/posting dependency check was found in this path. Currency validation is bounded to the implemented supported base currency, which reduces but does not resolve fiscal/calendar and numbering policy questions. [apps/organizations/platform_forms.py:40](../../../apps/organizations/platform_forms.py#L40) [apps/organizations/forms.py:216](../../../apps/organizations/forms.py#L216) [apps/organizations/services.py:604](../../../apps/organizations/services.py#L604) [apps/organizations/models.py:2154](../../../apps/organizations/models.py#L2154)

Define which settings are setup-only, effective-dated, or changeable after operations begin. Implement that policy in the owning service, including concurrency and audit behavior. No ledger corruption was demonstrated.

## S05 — Privileged authentication hardening remains unverified

**High risk if local-password-only privileged access is deployed, P0 qualification.**

The inspected authentication implementation uses Django LoginView and AuthenticationForm. No integrated MFA, step-up challenge, operator session inventory or targeted session revocation facility was found in the inspected account routes, forms and settings. Password recovery throttling is not login throttling. An external identity gateway or perimeter limiter might supply controls, but none was verified. [apps/accounts/views.py:74](../../../apps/accounts/views.py#L74) [apps/accounts/forms.py:26](../../../apps/accounts/forms.py#L26) [apps/accounts/urls.py:7](../../../apps/accounts/urls.py#L7) [config/settings/base.py:66](../../../config/settings/base.py#L66)

Before live customer operation, verify the deployed privileged-authentication boundary. Reuse a trusted identity/MFA implementation where a gap exists, and define break-glass and session-revocation procedures. Do not implement custom cryptography.

## S06 — Audit metadata validation does not descend into lists

**Medium, P0 hardening. Confirmed pure-function behavior, no real secret disclosure observed.**

_validate_audit_metadata rejects sensitive dictionary keys and recurses into dictionary values, but not dictionaries nested in lists. A read-only synthetic probe rejected a direct token key and accepted the same key nested inside an items list. record_audit_event accepts arbitrary structured metadata and invokes this validator. [apps/audit/services.py:35](../../../apps/audit/services.py#L35) [apps/audit/services.py:46](../../../apps/audit/services.py#L46)

Validate supported nested containers consistently, with explicit limits and regression cases. Consider source-specific allowed schemas. Keep the current company-activity summary projection rather than rendering arbitrary metadata to work around investigation gaps.

## S07 — Global security audit has no accessible MVP investigation workspace

**High operational control gap, P0. Verified source and runtime boundary.**

Per-company activity filters by organization. Platform role assignment/revocation events are recorded without organization, so those events are absent from company detail. Django audit Admin deliberately exposes only organization-null records but /admin/ is MVP-hidden. The tenant audit route requires membership/context. A role-only Platform Admin therefore lacks a complete global privilege-investigation UI even though the evidence exists. [apps/organizations/platform_companies.py:51](../../../apps/organizations/platform_companies.py#L51) [apps/organizations/access_services.py:850](../../../apps/organizations/access_services.py#L850) [apps/audit/admin.py:34](../../../apps/audit/admin.py#L34) [apps/audit/views.py:17](../../../apps/audit/views.py#L17)

Add a read-only, explicitly permissioned platform security-event workspace. Keep tenant operational payloads, privileged authentication telemetry and global role audit distinct in source ownership and scope. Define required time/action/actor filters, lineage, retention and investigation access.

## Assessment limits and release evidence

Read-only runtime GET checks demonstrated role separation for the sampled routes, including Superuser without platform duty. They did not exercise protected writes, prove all application endpoint isolation, or test deployment defenses. Existing CSRF, cross-tenant, rollback and authority-expiry tests were inspected. [apps/organizations/test_platform_companies.py:139](../../../apps/organizations/test_platform_companies.py#L139) [apps/organizations/test_platform_companies.py:158](../../../apps/organizations/test_platform_companies.py#L158) [apps/organizations/test_cep001_security.py:34](../../../apps/organizations/test_cep001_security.py#L34)

The database-independent architecture selection ran during this assessment with 5 tests passing, 3 failing and 28 subtests passing. Failures concern four duplicate Payroll model registrations, 77 permission namespace mismatches, and missing enforcement references in multiple resources. The passing reconciliation checks do not erase those failures. One pending development migration was payroll.0010_cep069_reviewed_statutory_context. No migration was applied during this assessment. [apps/organizations/test_permission_registry.py:51](../../../apps/organizations/test_permission_registry.py#L51) [apps/organizations/test_platform_initial_grant.py:47](../../../apps/organizations/test_platform_initial_grant.py#L47) [apps/payroll/migrations/0010_cep069_reviewed_statutory_context.py:11](../../../apps/payroll/migrations/0010_cep069_reviewed_statutory_context.py#L11)

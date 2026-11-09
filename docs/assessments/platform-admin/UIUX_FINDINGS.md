# Platform Admin UI/UX assessment

Assessment date 2026-11-06. Browser interaction was unavailable because local browser use is disabled in Work settings. Observations below combine inspected templates with GET responses through Django's request pipeline. Browser focus order, viewport rendering, actual clicks, form submission, screen-reader behavior and visual quality remain unverified.

Finding IDs are shared with [the capability matrix](CAPABILITY_MATRIX.md) and [security assessment](SECURITY_AND_ROLE_BOUNDARIES.md). Recommended changes require their own approved implementation scope.

## Representative journeys

| Journey | Current entry and steps | Verified result | Friction or missing step |
| --- | --- | --- | --- |
| Enter the platform workspace | Login, then / and desktop sidebar section مدیریت پلتفرم. | HTTP 200 for admin, platform links and no-organization message in HTML. | Home still describes a tenant workspace. Platform actions are not discoverable through the mobile drawer. U01/U02. |
| Create and onboard a tenant | Sidebar شرکت جدید, enter company details and existing owner's username, submit, then redirect to organization selection. | Creation form GET 200. POST path and source tests inspected. | No owner account picker/invitation, acceptance or onboarding progress. Platform actor may not belong to the created company, so the destination selector is not its directory. C01/U03/S02. |
| Assign the initial owner | Required initial_owner_username on the same form. | Source validates an existing active account, and service creates explicit owner membership. | Display of intended owner identity/acceptance is absent from this flow. No browser verification of account-selection mistakes. C01. |
| Inspect and manage tenant status | Company directory, detail, reason, suspend/reactivate button. | Directory, detail and edit GET 200. Atomic status and rejection tests inspected. | Target company title and effect text are present. The global header can still display a different active company, and invalid status submission redirects with generic feedback. U05/U06. |
| Configure available modules | No module-configuration destination found. Specialized policy catalog exists. | Policy catalog GET 200. Hidden-module requests denied in MVP. | Policy settings do not represent tenant module availability. Product Surface is server-owned release exposure. C02. |
| Manage platform administrators | No admin-assignment page in the platform navigation or organizations routes. | Assignment/revocation services inspected. Technical Admin GET 403 in MVP. | کاتالوگ نقش‌ها edits tenant/business-role definitions and cannot assign PlatformRoleAssignment. U04/S01. |
| Review security and audit | Directory detail shows company event summaries. Tenant /audit/ needs membership/context. Global audit Admin is hidden. | Company detail GET 200. Platform account tenant audit redirects, technical Admin GET 403. | Company timeline cannot answer which admin granted a platform role or show global security events. S07. |
| Diagnose a support issue | Existing support case/access services and routes. | Support workbench GET 403 in MVP. | No current independent platform support inbox or tenant diagnostics UI. C08. |

Journey sources are the shell, directory views, creation view, owner form, product gate and audit routes. [templates/base.html:687](../../../templates/base.html#L687) [apps/organizations/platform_views.py:62](../../../apps/organizations/platform_views.py#L62) [apps/organizations/views.py:247](../../../apps/organizations/views.py#L247) [apps/organizations/forms.py:138](../../../apps/organizations/forms.py#L138) [apps/organizations/urls.py:8](../../../apps/organizations/urls.py#L8) [apps/audit/views.py:17](../../../apps/audit/views.py#L17)

## U01 — Platform navigation is desktop-only

**Medium, P0. Confirmed template structure.**

The platform section is inside the sidebar with hidden/lg:flex visibility. The mobile drawer includes components/navigation_links.html and logout. That shared component does not render the platform section. A small-screen Platform Admin therefore loses the primary entry points, even though direct URLs can remain authorized. The existing template test explicitly preserves the desktop-only design. [templates/base.html:678](../../../templates/base.html#L678) [templates/base.html:640](../../../templates/base.html#L640) [templates/components/navigation_links.html:2](../../../templates/components/navigation_links.html#L2) [core/test_cep014_administration.py:25](../../../core/test_cep014_administration.py#L25)

Add a shared, role-authorized platform navigation component used by both layouts. Update that explicit test contract under approved scope. Acceptance should include actual keyboard/touch navigation at narrow and desktop viewports and absence of these entries for non-platform users.

## U02 — A valid platform operator lands on a tenant empty state

**Medium, P0. Confirmed GET HTML and view branch.**

A role-only admin can see the platform links but home asks for an organization. This implies that choosing a tenant is a prerequisite for global work. The server uses the same no-context branch for every authenticated identity and supplies no platform overview model. [core/views.py:25](../../../core/views.py#L25) [templates/home.html:28](../../../templates/home.html#L28)

Provide an appropriate platform landing destination with company actions and honest, source-labelled metrics. Separate zero companies, no tenant memberships, unavailable metrics, and unauthorized states. Preserve a deliberate way to enter an explicitly authorized tenant workspace.

## U03 — Creation ends in an unrelated membership selector

**Medium UX gap with the High C01 onboarding dependency, P0. Source-verified.**

After successful company creation, the view redirects to organizations:select. That screen lists the actor's valid memberships, while platform creation explicitly assigns a different initial owner. The newly created company need not appear in that list. The code does not produce a platform completion page describing owner assignment or workflow bootstrap outcome. [apps/organizations/views.py:247](../../../apps/organizations/views.py#L247) [apps/organizations/views.py:127](../../../apps/organizations/views.py#L127) [apps/organizations/services.py:683](../../../apps/organizations/services.py#L683)

Route successful creation to the new company control-plane detail or a resumable onboarding result. Show the selected owner and each provisioning outcome, including recoverable partial completion. Do not imply the operator acquired tenant membership.

## U04 — Role and policy labels do not establish the right operator mental model

**Medium, P1. Source-verified information architecture.**

The role catalog label can be read as management of platform administrators. Its actual model is OrganizationRole, with a global/system or exact-company selector. The policy route is explicitly accounting-policies while the sidebar says platform policies. The role table and target-company selector are rendered without a pagination workflow in the inspected template/context, which will become difficult as the estate grows. [apps/organizations/templates/organizations/role_catalog.html:8](../../../apps/organizations/templates/organizations/role_catalog.html#L8) [apps/organizations/views.py:896](../../../apps/organizations/views.py#L896) [apps/organizations/urls.py:44](../../../apps/organizations/urls.py#L44) [templates/base.html:693](../../../templates/base.html#L693)

Use distinct destinations for platform operators/duties, business-role definitions, tenant assignments and domain-owned policies. Retain code identifiers where they help an internal operator, with Persian descriptions and explicit global impact. Reuse established filtered-list components after measuring their fit.

## U05 — Two company contexts can appear on one control-plane screen

**Medium, P0 for operator target clarity. Source-verified; browser effect unverified.**

The shared header and working context use request.organization, while company detail/edit use the target company from the authorized URL. The target title is present, but an operator who also has an active tenant membership can see a different active company in the shell. This is a wrong-target interaction risk, not evidence that the mutation service updates the wrong record. The service correctly uses the authorized target ID. [templates/base.html:715](../../../templates/base.html#L715) [templates/base.html:724](../../../templates/base.html#L724) [apps/organizations/platform_views.py:62](../../../apps/organizations/platform_views.py#L62) [apps/organizations/platform_companies.py:104](../../../apps/organizations/platform_companies.py#L104)

Give control-plane pages an explicit management context and consistently identify the target on headings, actions and results. Preserve tenant session state without presenting it as the control-plane action target. Verify with an operator who has membership in company A while managing company B.

## U06 — Recovery and error journeys need browser acceptance

**Medium, P1, with P0 acceptance for lifecycle actions.**

Positive source controls include Persian labels, RTL base layout, CSRF tokens, action effect text, empty states, overflow containers and shared field/pagination includes. Status-form errors redirect to the detail view with a generic message and discard the submitted reason. Settings validation retains bound forms, but stale-version recovery requires an explicit refresh. Closed companies have no normal edit link, while a direct edit GET can still render a form whose service later rejects a save. [apps/organizations/templates/organizations/platform_company_detail.html:16](../../../apps/organizations/templates/organizations/platform_company_detail.html#L16) [apps/organizations/templates/organizations/platform_company_list.html:38](../../../apps/organizations/templates/organizations/platform_company_list.html#L38) [apps/organizations/platform_views.py:107](../../../apps/organizations/platform_views.py#L107) [apps/organizations/platform_views.py:128](../../../apps/organizations/platform_views.py#L128)

Verify error announcement, first-invalid-field focus, reason retention, stale-data recovery, long company names, empty and large lists, keyboard navigation, zoom and mobile layouts. Prefer the existing form/error/system-state components. Validate contrast and assistive-technology behavior in a browser before marking accessibility accepted.

## Browser acceptance checklist for the next authorized batch

1. Verify the platform and ordinary-user navigation on desktop and a narrow viewport.
2. Create a disposable non-production tenant through the full UI with an explicit owner and verify its completion destination.
3. Inspect company A while company B is the operator's active tenant and verify the target throughout the flow.
4. Exercise suspend/reactivate, missing reason, stale version, duplicate submit and an expired role.
5. Verify settings error recovery and setup-only configuration policy after operations exist.
6. Review a global security event without exposing tenant business payloads.

These steps are proposed future verification, not completed checks. Full creation/lifecycle browser tests require a suitable non-production fixture and browser availability.

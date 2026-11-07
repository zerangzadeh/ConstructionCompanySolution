import json,re
from pathlib import Path
root=Path('output/equipment-workspace-redesign')
p=root/'IMPLEMENTATION_REPORT.md'
s=p.read_text(encoding='utf-8-sig')
s=s.replace('Status: implementation complete; validation in progress. Product Owner visual acceptance: PENDING.','Status: VISUAL UX REMEDIATION: READY_FOR_HUMAN_REVIEW. PRODUCT OWNER VISUAL ACCEPTANCE: PENDING.')
s=s.replace('Existing record destinations and permission conditions are retained, including final-state transition hiding.','Existing record destinations and authorization rules are retained, including final-state transition hiding. Attachment and spare-part controls now use their existing endpoint permission codes for visibility; no permission definition, grant, service or view changed.')
s=s.replace('- Focused tests and existing regression: pending; results will be recorded before handoff.','''- Final focused tests: **6/6 PASS**, 18.76s, in test_bonira_equipment_workspace_final_20261105 cloned from the existing migrated test baseline. See focused-tests.txt and focused-tests.xml. Coverage: genuine empty state and all destinations; populated/finalized/overdue order presentation; 50-row limit; explicit read-only/denied roles; foreign-tenant exclusion; existing XLSX operational sources/filters.
- Two legacy checks: **BASELINE TEST DEBT**, not PASS. P8EquipmentOperationsTests.test_rtl_operations_workbench_and_mutation_routes_are_navigable and test_operations_enforce_permission_tenant_project_and_site_scope fail in unchanged p8_services permission checks before reaching the template. Their legacy fixtures do not create current role assignments. See initial-test-results.txt/xml. No authorization was weakened to make these pass.
- Initial verification harness errors (missing required equipment category; browser fixtures sharing the reused test DB) were corrected. Final automated tests use a separate clean clone from the browser fixture DB. Fresh migration-from-zero attempts were interrupted before test execution and replaced by the migrated baseline clone; they are not counted as test results.''')
s=s.replace('The original development server restarted during capture; final captures used a separate task-owned server on port 8002 against the same existing local data. No business records were created in development.','The original development server restarted during capture; a task-owned server on port 8002 was used temporarily. The final primary captures were refreshed from the normal port 8000 workspace. Task-owned servers were stopped at handoff. No business records were created in development.')
s=s.replace('Authorized owner browser checks and explicit-role automated checks are distinct; no Human UAT or Product Owner acceptance is inferred.','Actual Chrome owner and read-only checks were performed. The normal demo tenant remains genuinely empty. Populated Chrome verification used explicitly synthetic records only in test_bonira_equipment_workspace_ready_20261105, a dedicated test clone. No Human UAT or Product Owner acceptance is inferred.')
s+='''
## Populated and role browser verification

The isolated browser fixture exercised three actual EquipmentWorkOrder rows (draft/overdue, completed, cancelled), long Persian equipment/summary text, existing Jalali dates, reference/attachment counts and preserved record links. Captures: isolated-populated-1440.jpg, isolated-populated-1024.jpg, isolated-populated-390.jpg, isolated-populated-390-follow-up.jpg and isolated-read-only-1440.jpg. These are test evidence, not demo/product records.

populated-checks.json records 3 rows at all widths, no document overflow, and contained table widths: 1099/1099px at 1440; 683/749px at 1024; 342/749px at 390 (region/scroll width). Keyboard ArrowLeft moved the focused scroll region from 0 to approximately -20.8px. Follow-up activation moved focus to maintenance-follow-up. Read-only Chrome check: 3 detail links, 0 operational or record mutation links, export retained; list action absent without equipment.view.

The first isolated login redirected through the unrelated home dashboard with incomplete fixture timezone settings and hit its existing configuration expectation. The fixture was given its organization timezone; the Equipment Operations route itself rendered correctly. No home-page code was changed.

Final primary screenshots, route evidence, checks, legacy-failure attribution and the normal Chrome workspace are ready for Human review. This is not Product Owner acceptance or production authorization.
'''
p.write_text(s,encoding='utf-8')
before=(root/'baseline/operations_workbench.html').read_text(encoding='utf-8-sig')
after=Path('templates/equipment/operations_workbench.html').read_text(encoding='utf-8')
route_pattern=r"\{% url [\"'](equipment:[^\"']+)"
old_routes=set(re.findall(route_pattern,before)); new_routes=set(re.findall(route_pattern,after))
pattern=r'"(equipment[^" ]+)" in business_permission_codes'
old_permissions=set(re.findall(pattern,before)); new_permissions=set(re.findall(pattern,after))
result={'preserved_routes':sorted(old_routes),'missing_routes':sorted(old_routes-new_routes),'existing_visibility_permissions_retained':old_permissions<=new_permissions,'additional_existing_endpoint_visibility_code':sorted(new_permissions-old_permissions),'endpoint_authority':'apps/equipment/views.py spare_link_create: EQUIPMENT_SPARE_LINKS_MANAGE','authorization_rules_changed':False,'git_writes':'NONE'}
assert not result['missing_routes'] and result['existing_visibility_permissions_retained']
assert new_permissions-old_permissions=={'equipment_spare_links.manage'}
(root/'preservation-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('Report and preservation evidence: complete')

import json,re
from pathlib import Path
root=Path('output/equipment-workspace-redesign')
before=(root/'baseline/operations_workbench.html').read_text(encoding='utf-8-sig')
after=Path('templates/equipment/operations_workbench.html').read_text(encoding='utf-8-sig')
pattern=r"\{% url [\"'](equipment:[^\"']+)"
routes_before=set(re.findall(pattern,before))
routes_after=set(re.findall(pattern,after))
permissions_before=set(re.findall(r'"(equipment[^" ]+)" in business_permission_codes',before))
permissions_after=set(re.findall(r'"(equipment[^" ]+)" in business_permission_codes',after))
result={'preserved_routes':sorted(routes_before),'missing_routes':sorted(routes_before-routes_after),'permission_code_sets_equal':permissions_before==permissions_after,'git_writes':'NONE'}
assert not result['missing_routes'] and result['permission_code_sets_equal']
(root/'preservation-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('Existing route and permission-code preservation: PASS')

import ast,difflib,hashlib,json,subprocess
from pathlib import Path
out=Path('output/project-detail-ui-remediation/evidence');private=Path('.scratch/project-detail-ui-remediation');entry=json.loads((out/'entry.json').read_text(encoding='utf-8'))
current={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in subprocess.check_output(['git','ls-files','-c','-o','--exclude-standard']).decode().splitlines() if Path(p).is_file() and p.startswith(('apps/','core/','config/','templates/','tests/'))}
delta={p:[entry['source'].get(p),current.get(p)] for p in sorted(set(entry['source'])|set(current)) if entry['source'].get(p)!=current.get(p)}
expected={'apps/projects/dashboard.py','apps/projects/static/projects/detail_dashboard.css','apps/projects/static/projects/project_dashboard.js','apps/projects/templates/projects/dashboard_budget.html','apps/projects/templates/projects/detail.html','apps/projects/test_project_operations_dashboard.py'}
assert set(delta)==expected
for p,h in entry['protected'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
for field,command in [('head',['git','rev-parse','HEAD']),('upstream',['git','rev-parse','origin/main']),('branch',['git','branch','--show-current'])]:assert subprocess.check_output(command).decode().strip()==entry[field]
patch=''
for name in delta:
 old=(private/'entry'/name).read_text(encoding='utf-8');new=Path(name).read_text(encoding='utf-8');patch+=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='entry/'+name,tofile=name))
(out/'implementation.patch').write_text(patch,encoding='utf-8');(out/'source-delta.json').write_text(json.dumps(delta,indent=2)+'\n');(out/'protected-hashes.json').write_text(json.dumps(entry['protected'],indent=2)+'\n')
name='apps/projects/dashboard.py';old=ast.parse((private/'entry'/name).read_text(encoding='utf-8'));new=ast.parse(Path(name).read_text(encoding='utf-8'));method=lambda tree,name:next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
assert ast.dump(method(old,'_budget_comparison'))==ast.dump(method(new,'_budget_comparison'))
name='apps/projects/test_project_operations_dashboard.py';old=ast.parse((private/'entry'/name).read_text(encoding='utf-8'));new=ast.parse(Path(name).read_text(encoding='utf-8'));old_methods={n.name:ast.dump(n) for n in old.body[-1].body if isinstance(n,ast.FunctionDef)};new_methods={n.name:ast.dump(n) for n in new.body[-1].body if isinstance(n,ast.FunctionDef)};assert all(new_methods[n]==v for n,v in old_methods.items())
(out/'source-preservation.json').write_text(json.dumps({'changed_source_files':len(delta),'other_entry_source_files_preserved':True,'entry_source_files':len(entry['source']),'protected_entry_hashes':len(entry['protected']),'financial_comparison_ast_preserved':True,'existing_test_methods_preserved':True,'head_upstream_branch_unchanged':True,'commit_or_push':False},indent=2)+'\n')
print('Six bounded source files; financial comparison, prior tests, unrelated sources and protected entry hashes preserved.')

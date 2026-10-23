"""Reconcile URL/gate evidence and verify the documentation-only sweep boundary."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import yaml

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).parent
UIUX=OUT.parent
trace=json.loads((OUT/'SOURCE_TRACE.json').read_text(encoding='utf8'))
scope_tree=ast.parse((ROOT/'apps/organizations/authorization.py').read_text(encoding='utf8'))
assignment=next(n for n in scope_tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='OBJECT_SCOPED_PERMISSION_NAMESPACES' for t in n.targets))
scoped=ast.literal_eval(assignment.value.args[0])
models=ast.parse((ROOT/'apps/organizations/models.py').read_text(encoding='utf8'))
cls=next(n for n in models.body if isinstance(n,ast.ClassDef) and n.name=='BusinessPermissionCode')
perms={}
for n in cls.body:
    if isinstance(n,ast.Assign):
        value=n.value.elts[0] if isinstance(n.value,ast.Tuple) else n.value
        if isinstance(value,ast.Constant) and isinstance(value.value,str):perms[n.targets[0].id]=value.value
gates={};routes={}
for c in trace['candidates']:
    for path,symbol in c['view_sources']:
        key=path+':'+symbol
        node=ast.parse(trace['source_anchors'][key]['excerpt']).body[0]
        rows=[]
        for d in node.decorator_list:
            if isinstance(d,ast.Call) and isinstance(d.func,ast.Name) and d.func.id=='organization_permission_required':
                name=d.args[0].attr;value=perms[name]
                rows.append(dict(symbol=name,permission=value,allow_any_scope=value.partition('.')[0] in scoped,requires_organization_grant=value.partition('.')[0] not in scoped))
        gates[key]=rows
        mod=path.split('/')[1]
        tree=ast.parse((ROOT/'apps'/mod/'urls.py').read_text(encoding='utf8'))
        for n in ast.walk(tree):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='path' and len(n.args)>1 and isinstance(n.args[0],ast.Constant) and isinstance(n.args[1],ast.Attribute) and n.args[1].attr==symbol:
                routes[key]='/'+mod.replace('_','-')+'/'+n.args[0].value
    c['entry_gates']={p+':'+s:gates[p+':'+s] for p,s in c['view_sources']}
    c['routes']=list(dict.fromkeys(routes[p+':'+s] for p,s in c['view_sources'] if p+':'+s in routes))
    if c['classification']=='AFFECTED_CONFIRMED':
        assert any(g['allow_any_scope'] for gs in c['entry_gates'].values() for g in gs),c['candidate_id']
        assert c['routes']
    else:
        c['severity']=None;c['exposed_metadata']=None

# Crucial nested reader gate: scope_queryset later in the service does not
# cancel the earlier organization-only require_business_permission call.
parent_key='apps/billing/commercial_services.py:_require'
parent_ast=ast.parse(trace['source_anchors'][parent_key]['excerpt'])
require_call=next(n for n in ast.walk(parent_ast) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='require_business_permission')
assert 'allow_any_scope' not in {k.arg for k in require_call.keywords}
for symbol in ['get_guarantees','get_compliance_evidence','get_retention_releases']:
    tree=ast.parse(trace['source_anchors']['apps/billing/commercial_services.py:'+symbol]['excerpt'])
    call=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='_require')
    assert any(k.arg=='project' and isinstance(k.value,ast.Constant) and k.value.value is None for k in call.keywords)
matrix=dict(object_scoped_namespaces=sorted(scoped),candidate_view_gates=gates,nested_commercial_reader_gate={'source':parent_key,'project_passed':None,'allow_any_scope':'omitted/default False','requires_organization_grant':True,'covered_candidates':['SP-021','SP-042']})
(OUT/'SCOPE_GATE_MATRIX.json').write_text(json.dumps(matrix,indent=2),encoding='utf8')
(OUT/'SOURCE_TRACE.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2),encoding='utf8')

regpath=UIUX/'UIUX_FINDINGS_REGISTER.yaml';text=regpath.read_text(encoding='utf8');old=yaml.safe_load(text)
for c in trace['candidates']:
    if c['classification']!='AFFECTED_CONFIRMED':continue
    marker='- finding_id: '+c['finding_id']+'\n'
    if marker+'  sweep_classification:' in text:continue
    fields=dict(sweep_classification='AFFECTED_CONFIRMED',finding_status='OPEN',route=c['routes'][0] if len(c['routes'])==1 else c['routes'])
    block='\n'.join('  '+line for line in yaml.safe_dump(fields,allow_unicode=True,sort_keys=False).splitlines())+'\n'
    assert text.count(marker)==1;text=text.replace(marker,marker+block,1)
new=yaml.safe_load(text);assert new['findings'][:112]==old['findings'][:112]
regpath.write_text(text,encoding='utf8')
report=UIUX/'UIUX_F111_SAME_PATTERN_SECURITY_SWEEP.md';body=report.read_text(encoding='utf8')
if 'SCOPE_GATE_MATRIX.json' not in body:
    body=body.replace('The form-membership column is distinct','Actual permission strings and object-scope/organization-only gate decisions, including the nested Billing reader gate, are in [SCOPE_GATE_MATRIX.json](f111_same_pattern_evidence/SCOPE_GATE_MATRIX.json). Routed URL paths are retained per candidate and new finding.\n\nThe form-membership column is distinct')
report.write_text(body,encoding='utf8')

entry=json.loads((OUT/'ENTRY_HASHES.json').read_text(encoding='utf8'))
product_changed=[p for p,h in entry['product'].items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
history_changed=[p for p,h in entry['history'].items() if Path(p).name!='UIUX_FINDINGS_REGISTER.yaml' and hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
assert not product_changed and not history_changed,(product_changed,history_changed)
assert next(f for f in new['findings'] if f['finding_id']=='UIUX-F-111')['runtime_status']=='RUNTIME_VERIFIED_RESOLVED'
assert len(new['findings'])==new['register_status']['finding_count']==127
assert len({f['finding_id'] for f in new['findings']})==127
assert new['register_status']['static_finding_count']==123
assert new['register_status']['severity_counts']==dict(Counter(f['severity'] for f in new['findings']))|{'CRITICAL':0,'LOW':0}
assert Counter(c['classification'] for c in trace['candidates'])=={'SAFE':4,'AFFECTED_CONFIRMED':15,'NOT_APPLICABLE':22,'NEEDS_RUNTIME_CONFIRMATION':1}
assert len(trace['candidates'])==42
assert {f['finding_id'] for f in new['findings'][112:]}=={f'UIUX-F-{n}' for n in range(113,128)}
assert all(f['runtime_status']=='NOT_EXECUTED' and f['sweep_classification']=='AFFECTED_CONFIRMED' for f in new['findings'][112:])
for anchor in trace['source_anchors'].values():
    data=(ROOT/anchor['path']).read_bytes()
    assert hashlib.sha256(data).hexdigest()==anchor['source_sha256']
    actual='\n'.join(data.decode('utf8').splitlines()[anchor['line']-1:anchor['end_line']])
    assert actual==anchor['excerpt']
for p,t in trace['templates'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==t['sha256']
for link in re.findall(r'\]\(([^)]+)\)',body):assert (UIUX/link.split('#')[0]).exists(),link
assert body.rstrip().endswith('F111_PATTERN_SWEEP_FINDINGS_CONFIRMED')
assert 'UIUX-F-128' not in body and '16 new findings' not in body
cleanup=json.loads((UIUX/'f111_remediation_evidence/cleanup_boundary.json').read_text(encoding='utf8'))
pdfs=[]
for p in cleanup['remaining_generated_files']:
    assert (ROOT/p).exists()
    assert subprocess.run(['git','ls-files','--error-unmatch',p],cwd=ROOT,capture_output=True).returncode!=0
    pdfs.append(dict(path=p,exists=True,tracked=False,deletion_attempted=False))
result=dict(product_code_hashes_unchanged=True,product_files_compared=len(entry['product']),historical_evidence_unchanged=True,historical_files_compared=len(entry['history'])-1,original_findings_preserved=True,original_f111_resolved=True,yaml_json_references_and_source_anchors='PASS',candidate_count=42,counts=dict(Counter(c['classification'] for c in trace['candidates'])),new_findings=15,new_finding_range='UIUX-F-113..UIUX-F-127',runtime_http_or_browser_tests=0,training_preflight='Read-only; no fixture changes; active requirements absent',pdf_status=pdfs,final_decision='F111_PATTERN_SWEEP_FINDINGS_CONFIRMED')
result['artifact_hashes']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='VERIFICATION.json'}
result['report_sha256']=hashlib.sha256(report.read_bytes()).hexdigest()
result['findings_register_sha256']=hashlib.sha256(regpath.read_bytes()).hexdigest()
(OUT/'VERIFICATION.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print('PASS: 42 classified units; 15 sequential static findings; original 112 findings/F-111 evidence preserved; all product source hashes unchanged; generated PDFs retained untracked.')

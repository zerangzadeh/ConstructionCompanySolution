import re,json,csv,subprocess,hashlib
from pathlib import Path
REG=Path("CEP_EXECUTION_REGISTRY.yaml")
def head():return subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
def blocks(s):
 matches=list(re.finditer(r"^  CEP-(\d{3}):\n",s,re.M))
 for i,m in enumerate(matches):
  end=matches[i+1].start() if i+1<len(matches) else s.index("\n",s.index("    updated_at:",m.start()))+1
  yield int(m[1]),m.start(),end,s[m.start():end]
def update(cep,transform):
 s=REG.read_text(); id=int(cep)
 for n,a,b,v in blocks(s):
  if n==id:s=s[:a]+transform(v)+s[b:];break
 REG.write_text(s)
def event(v,status,reason):
 m=re.search(r"    history:\n(.*?)(?=^    [a-z_]+:|\Z)",v,re.S|re.M)
 item="    - date: '2026-10-20'\n      status: "+status+"\n      reason: "+json.dumps(reason)+"\n"
 return v[:m.end()]+item+v[m.end():] if m else v+"    history:\n"+item
def complete(cep,total,baseline,reason,utv):
 def edit(v):
  v=re.sub(r"    dependency_status:.*","    dependency_status: SATISFIED_CANONICAL_REQUIREMENTS",v)
  v=re.sub(r"    eligibility_status:.*","    eligibility_status: SATISFIED_EXECUTION_COMPLETE",v)
  v=re.sub(r"    execution:\n.*?(?=    acceptance:)","    execution:\n      status: COMPLETE\n      lifecycle: CLOSED_VERIFIED\n      advisor_review: NOT_REQUIRED_CURRENT_GOVERNANCE\n",v,flags=re.S)
  v=re.sub(r"    acceptance:\n.*?(?=    dod:)",f"    acceptance:\n      passed: {total}\n      total: {total}\n      status: VERIFIED\n",v,flags=re.S)
  v=re.sub(r"    dod:.*","    dod: MET",v)
  v=re.sub(r"    blockers:.*?(?=    completion_report:)","    blockers: []\n    remaining_utv:\n"+"".join("    - "+json.dumps(x)+"\n" for x in utv),v,flags=re.S)
  v=re.sub(r"      evidence_presence:.*","      evidence_presence: VERIFIED_CURRENT_FOCUSED_AFFECTED_REGRESSION",v)
  v=re.sub(r"    last_execution:\n.*?(?=    updated_at:)",f"    last_execution:\n      branch: main\n      sha: {baseline}\n",v,flags=re.S)
  v=re.sub(r"    updated_at:.*","    updated_at: '2026-10-20'",v)
  v=re.sub(r"      category:.*","      category: COMPLETE",v,count=1)
  v=re.sub(r"      disposition:.*","      disposition: CURRENT_IMPLEMENTATION_VERIFIED",v,count=1)
  return event(v,"COMPLETE",reason)
 update(cep,edit)
 recalc()
def recalc():
 s=REG.read_text();records=[]
 for n,a,b,v in blocks(s):
  if n>79:continue
  status=re.search(r"    execution:\n      status: (.*)",v)[1]
  blocked=status=="NOT_STARTED" and bool(re.search(r"    blockers:\n    -",v))
  records.append((n,status,blocked))
 complete=sum(x[1]=="COMPLETE" for x in records);partial=sum(x[1]=="PARTIAL" for x in records);blocked=sum(x[2] for x in records);progress=sum(x[1]=="IN_PROGRESS" for x in records)
 for k,value in {"execution_state_complete":complete,"partial_current":partial,"blocked_current":blocked,"in_progress":progress,"not_started_other_current_governed":sum(x[1]=="NOT_STARTED" for x in records)-blocked}.items():
  s=re.sub(r"^  "+k+r":.*",f"  {k}: {value}",s,count=1,flags=re.M)
 v1=[x for x in records if x[0]<=68];counts={"COMPLETE":sum(x[1]=="COMPLETE" for x in v1),"PARTIAL":sum(x[1]=="PARTIAL" for x in v1),"BLOCKED":sum(x[2] for x in v1)}
 ready=sum(x[1]=="NOT_STARTED" and not x[2] for x in v1)
 if ready:counts["READY"]=ready
 s=re.sub(r"  v1_closure_counts:\n(?:    .*\n)+","  v1_closure_counts:\n"+"".join(f"    {k}: {v}\n" for k,v in counts.items()),s)
 REG.write_text(s);return counts
def checkpoint(cep,sha):
 def edit(v):
  v=re.sub(r"    git:\n.*?(?=    last_execution:)",f"    git:\n      committed: true\n      commit_sha: {sha}\n      pushed: true\n      merged_to_main: false\n      integrated_to_main: true\n      integration_method: DIRECT_COMMIT_TO_MAIN\n      remote_main_evidence: VERIFIED_LS_REMOTE\n",v,flags=re.S)
  return event(v,"GIT_INTEGRATED",f"Authorized direct main commit/push {sha}; remote verified; no merge or Production action.")
 update(cep,edit)
 s=REG.read_text();a=s.index("repository_state:\n");b=s.index("execution_frontier:\n",a);v=s[a:b]
 for key in ["last_reconciled_head","origin_main","integration_checkpoint"]:v=re.sub(r"  "+key+r":.*","  "+key+": "+sha,v)
 REG.write_text(s[:a]+v+s[b:])
def csvwrite(path,header,rows):
 with Path(path).open("w",newline="",encoding="utf-8") as f:
  w=csv.writer(f);w.writerow(header);w.writerows(rows)

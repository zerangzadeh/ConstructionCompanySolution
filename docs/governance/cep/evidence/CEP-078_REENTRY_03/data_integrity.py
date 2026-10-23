"""Attribute authorized synthetic append-only fixture delta against entry hashes."""
import hashlib,json,sys
from datetime import datetime
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
sys.path.insert(0,str(ROOT/'docs/governance/uiux/rv007_controlled_time'))
from support import guard,snapshot,REAL_NOW
from django.apps import apps
from django.db.models import Q
guard()
def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
entry=json.loads((OUT/'ENTRY.json').read_text(encoding='utf-8'))
baseline=json.loads((OUT/'DATA_BEFORE.json').read_text(encoding='utf-8'))
at=datetime.fromisoformat(entry['at'])
current=snapshot()
delta=[]
for label,rows in current.items():
    if digest(rows)==baseline[label]:continue
    model=apps.get_model(label)
    names={f.name for f in model._meta.concrete_fields}
    date_fields=names&{'created_at','date_joined','joined_at'}
    query=Q(pk__in=[])
    for name in date_fields:query |= Q(**{name+'__gte':at})
    new_ids={str(pk) for pk in model.objects.filter(query).values_list('pk',flat=True)}
    retained={key:value for key,value in rows.items() if key not in new_ids}
    delta.append({'model':label,'current_count':len(rows),'created_since_entry_ids':sorted(new_ids),'date_fields':sorted(date_fields),'prior_aggregate_matches_after_new_rows_removed':digest(retained)==baseline[label],'retained_count':len(retained)})
result={'at':REAL_NOW(),'entry_at':at,'models_compared':len(current),'unchanged_model_aggregates':len(current)-len(delta),'changed_models':delta,'unexplained_models':[r['model'] for r in delta if not r['prior_aggregate_matches_after_new_rows_removed']],'method':'Compare entry hash per model; for deltas remove only rows timestamped created since current entry and require exact original aggregate restoration. Timestamp classification is fixture-provenance review input, not blanket authorization. Sessions/last_login excluded as original helper.','result':'PASS_EXISTING_MODEL_AGGREGATES_PRESERVED_WITH_EXPLICIT_APPEND_ONLY_FIXTURES' if all(r['prior_aggregate_matches_after_new_rows_removed'] for r in delta) else 'PARTIAL_DELTA_ATTRIBUTION_REQUIRED'}
(OUT/'DATA_INTEGRITY.json').write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'result':result['result'],'unchanged':result['unchanged_model_aggregates'],'changed':len(delta),'unexplained':result['unexplained_models']}))

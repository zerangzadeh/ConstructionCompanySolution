import json,sys
from sweep import ROOT,DB,write
from django.test.utils import setup_test_environment
from fixtures import seed
setup_test_environment()
p=ROOT/sys.argv[1]
data=json.loads(p.read_text())
names=sys.argv[2:]
actors,sources,result=seed(names)
data['actors'].update({k:[str(u.pk) if u else None,str(o.pk) if o else None] for k,(u,o) in actors.items()})
data['sources'].update({k:[v._meta.label,str(v.pk)] for k,v in sources.items()})
data['results'].update(result)
p.write_text(json.dumps(data),encoding='utf-8')
write(DB+'-fixture-retry.json',result)
print(result)

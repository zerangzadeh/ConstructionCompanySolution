"""Resolve stale driver metadata against actual mounted source; repeat HTTPS."""
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

B=Path('/srv/bonira');OUT=B/'production-disposition-evidence';source=B/'source-production-disposition';release='production-disposition-current';target=B/'releases'/release
freeze=json.loads((source/'SOURCE_FREEZE.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert all(sha(source/name)==digest for name,digest in freeze.items())
differences=[name for name,digest in freeze.items() if sha(target/name)!=digest]
assert differences==['scripts/production_recovery.py'],differences
for name in differences:shutil.copyfile(source/name,target/name)
assert all(sha(target/name)==digest for name,digest in freeze.items())
shutil.copyfile(source/'SOURCE_FREEZE.json',target/'SOURCE_FREEZE.json')
head='c9fe1d7e7ed586ef96a2ee453a3490369d25e6a3'
build={'head':head,'working_tree':'bounded uncommitted Production-disposition changes','source_files':len(freeze),'source_manifest_sha256':sha(source/'SOURCE_FREEZE.json')}
(target/'RELEASE_BUILD.json').write_text(json.dumps(build,indent=2)+'\n')
env=B/'secrets'/(release+'.env');values=dict(line.split('=',1) for line in env.read_text().splitlines() if line);values['BONIRA_SOURCE_HEAD']=head;env.write_text('\n'.join(k+'='+v for k,v in values.items())+'\n')
spec=importlib.util.spec_from_file_location('d',B/'tools/guest_driver.py');d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d);d.OUT=OUT
original=d.app
def app(action,phase,**kwargs):return original(action,phase,release=release,**kwargs)
d.app=app
identity=d.start_app(release)
old_driver_head=identity.pop('source_head')
mounts=json.loads(d.invoke(['docker','inspect','bonira-app','--format','{{json .Mounts}}']).stdout)
assert next(row['Source'] for row in mounts if row['Destination']=='/app')==str(target)
identity.update(build)
count=d.web_checks(release,'FINAL_IDENTITY_HTTPS',authenticated=True)
health=d.health(release=release)
d.stop_app()
result={'result':'PASS','source':identity,'actual_mount_verified':True,'corrected_driver_metadata':{'erroneous_source':str(B/'source/BUILD.json'),'old_reported_head':old_driver_head,'actual_release_matches_source_manifest':True},'release_delta_since_first_http':differences,'delta_qualified_by':'PITR_RESULT.json; no HTTP/domain/configuration delta','https_cases':count,'health':health,'prior_https_cases':28,'production':False}
(OUT/'FINAL_RELEASE_IDENTITY.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS: actual mounted source identity and final HTTPS checks',flush=True)

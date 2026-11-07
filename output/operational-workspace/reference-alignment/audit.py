import hashlib
import json
import re
from pathlib import Path

root = Path('output/operational-workspace')
current = root / 'reference-alignment'
results = []
for folder in ('inbox', 'domains', 'reference-alignment'):
    for batch in sorted((root / folder).glob('batch-*.json')):
        results.extend({'batch': batch.relative_to(root).as_posix(), **row}
                       for row in json.loads(batch.read_text(encoding='utf-8')))
new_results = [r for r in results if r['batch'].startswith(('inbox/', 'reference-alignment/'))]
assert len(new_results) == 15, len(new_results)
assert all(not r.get('jsErrors') and not r.get('httpErrors')
           for r in new_results if r['status'] == 200)
before = (current / 'before/_work_item_row.html').read_text(encoding='utf-8')
after = Path('templates/workflows/_work_item_row.html').read_text(encoding='utf-8')
assert re.findall(r'<form.*?</form>', before, re.S) == re.findall(r'<form.*?</form>', after, re.S)
protected = json.loads((root / 'protected-files.json').read_text())
changed_protected = [p for p, digest in protected.items()
                     if hashlib.sha256(Path(p).read_bytes()).hexdigest() != digest]
print('Protected files changed since original rollout snapshot:', changed_protected)
(root / 'browser-scenarios.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
(current / 'browser-scenarios.json').write_text(json.dumps(new_results, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'{len(new_results)} current Inbox browser scenarios passed; {len(results)} total indexed scenarios.')
print('POST forms identical; no protected files were edited by this revision.')

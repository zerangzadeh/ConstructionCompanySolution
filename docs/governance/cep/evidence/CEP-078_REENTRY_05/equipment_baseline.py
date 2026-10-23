"""Compare unchanged legacy tests with pre-continuation form overlay; always restore."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
root=Path(__file__).resolve().parents[5]
out=Path(__file__).resolve().parent
path=root/'apps/equipment/forms.py'
final=path.read_bytes()
text=final.decode('utf-8')
baseline=text.replace('''        self.fields["workforce_qualification"].label_from_instance = (
            lambda qualification: (
                f"{qualification.employee.employee_number} — {qualification.title}"
            )
        )
        attach_parent_choice_ui(
            self, "workforce_qualification", "employee", "employee_id"
        )
''','').replace('''        ).select_related("equipment")
        self.fields["plan"].label_from_instance = (
            lambda plan: f"{plan.equipment.code} — {plan.name}"
        )
        attach_parent_choice_ui(self, "plan", "equipment", "equipment_id")
''','''        )
''')
assert baseline != text
entry=json.loads((out/'ENTRY.json').read_text(encoding='utf-8'))
# Match the entry hash despite the original file's retained CRLF line endings.
variants=[baseline.encode(),baseline.replace('\r\n','\n').replace('\n','\r\n').encode()]
original=next(x for x in variants if hashlib.sha256(x).hexdigest()==entry['product_hashes']['apps/equipment/forms.py'])
try:
    path.write_bytes(original)
    result=subprocess.run([str(root/'.venv/Scripts/python.exe'),'-X','utf8','manage.py','test','apps.equipment.test_p8_s18_s23.P8EquipmentOperationsTests','apps.equipment.tests.EquipmentPanelTests','--keepdb','--noinput'],cwd=root,capture_output=True)
    (out/'EQUIPMENT_BASELINE_TESTS.txt').write_bytes(result.stdout+result.stderr)
finally:
    path.write_bytes(final)
    assert path.read_bytes()==final
def outcomes(name):
    data=(out/name).read_text(encoding='utf-8')
    return re.findall(r'^(ERROR|FAIL): ([^\r\n]+)',data,re.M)
assert outcomes('EQUIPMENT_BASELINE_TESTS.txt')==outcomes('EQUIPMENT_AFFECTED_TESTS.txt')
(out/'EQUIPMENT_BASELINE_ATTRIBUTION.json').write_text(json.dumps({'result':'PASS_BASELINE_ATTRIBUTION','baseline_sha256':hashlib.sha256(original).hexdigest(),'matches_entry':True,'restored_final_sha256':hashlib.sha256(final).hexdigest(),'tests':11,'pass':1,'baseline_errors':9,'baseline_failures':1,'identical_failed_test_ids':outcomes('EQUIPMENT_BASELINE_TESTS.txt'),'no_test_or_authority_remediation':True},indent=2)+'\n',encoding='utf-8')
print('Exact entry overlay: same 9 errors + 1 failure; final form bytes restored')

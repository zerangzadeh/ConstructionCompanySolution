"""Narrow B04 negative, DMS, and projection witnesses in Chrome."""
from pathlib import Path
import os,hashlib
script=str(Path(__file__).with_name('b04_browser_retest.py')) if os.environ['B04_DB']=='b04_retest' else str(Path(__file__).with_name('b04_browser.py'))
exec(Path(script).read_text(encoding='utf-8').split('\nwith sync_playwright()')[0],globals())

with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chrome',headless=True,env={**os.environ,'TEMP':str(root),'TMP':str(root)})
    owner=login(browser,'b02-owner');reviewer=login(browser,'b02-b04-reviewer');reader=login(browser,'b02-b04-reader');wrong=login(browser,'b02-b04-sibling')
    for app,name,number in [('safety','SafetyIncident','incident_number'),('quality','QualityIssue','issue_number')]:
        obj=create(owner,app+':create',dict(project=ids['project'],site=ids['site'],description='آزمون شاهد دقیق B04',severity='low' if app=='safety' else 'minor',**{number:'B04-'+app+'-EVIDENCE',('occurred_at' if app=='safety' else 'identified_at'):'2026-11-10T09:30',('incident_type' if app=='safety' else 'issue_type'):'near_miss' if app=='safety' else 'defect'}),app,name,{number+'__iexact':'B04-'+app+'-EVIDENCE'})
        detail=reverse(app+':detail',args=[obj.pk]);visit(owner,detail)
        register=reverse('documents:evidence-register',args=[app,obj.pk])
        link=main(owner).locator(f'a[href="{register}"]');mark(app+':evidence',link.count()==1,actual_entry=register)
        if obj.review_status=='draft':
            link.click();owner.wait_for_load_state('load');f=form(owner)
            capture(owner,app+'-evidence-picker',True)
            values=f.evaluate('(f)=>Object.fromEntries(new FormData(f))')
            for key in ['foreign_version']:
                count=obj.review_revisions.count();status=post(owner,register,{**values,'versions':ids[key],'reason':'شاهد غیرمجاز'})
                obj.refresh_from_db();mark(app+':evidence',obj.review_status=='draft' and obj.review_revisions.count()==count,invalid=key,status=status)
            fill(f,versions=ids['v1'],reason='ارسال شاهد دقیق آزمون B04');click(f)
        obj.refresh_from_db();revision=obj.review_revisions.order_by('-sequence').first()
        pins=list(revision.evidence.values_list('document_version_id',flat=True)) if revision else []
        mark(app+':evidence',obj.review_status=='submitted' and pins==[__import__('uuid').UUID(ids['v1'])],state=obj.review_status,pins=pins,operational=obj.status)
        visit(reviewer,detail);capture(reviewer,app+'-submitted-review',True)
        controls=main(reviewer).locator('form').evaluate_all('(fs)=>fs.map(f=>new URL(f.action).pathname)')
        mark(app+':record-decision',False,blocked='No record approve/return/reject control or domain HTTP route in current MVP',forms=controls,review_status=obj.review_status,operational_status=obj.status)
        evidence=reverse('documents:evidence-detail',args=[app,obj.pk,ids['v1']]);visit(owner,detail)
        l=main(owner).locator(f'a[href="{evidence}"]')
        if l.count():l.first.click();owner.wait_for_load_state('load')
        mark(app+':evidence',urlsplit(owner.url).path==evidence,exact_link=evidence)
        capture(owner,app+'-exact-evidence',True)
    doc=get('documents','Document',pk=ids['doc']);visit(owner,reverse('documents:detail',args=[doc.pk]))
    if str(doc.current_version_id)==ids['v1']:
        f=form(owner,'/versions/add/');upload=root/'B04-version2.pdf';upload.write_bytes(b'%PDF-1.7\nB04 second synthetic version')
        f.locator('input[type=file]').set_input_files(upload);click(f)
    doc.refresh_from_db()
    url=reverse('documents:version-download',args=[doc.pk,ids['v1']]);r=owner.request.get(base+url);denied=reader.request.get(base+url)
    v=get('documents','DocumentVersion',pk=ids['v1'])
    # Source-owned pin continues to identify v1 after the real v2 upload.
    for app,name in [('safety','SafetyReviewEvidence'),('quality','QualityReviewEvidence')]:
        mark(app+':evidence',model(app,name).objects.filter(document_version_id=ids['v1']).exists() and str(doc.current_version_id)!=ids['v1'] and r.status==200 and hashlib.sha256(r.body()).hexdigest()==v.sha256 and denied.status in [403,404],current=doc.current_version_id,pin=ids['v1'],download=r.status,reader_download=denied.status)
    # Explicit form/capability limits, independent of HTTP 200.
    visit(owner,reverse('equipment:usage_create'));names=form(owner).locator('[name]').evaluate_all('(es)=>es.map(e=>e.name)')
    mark('equipment:usage-context',False,needs_po_review='Current usage form offers neither deployment nor operator; its new record is ineligible for cost allocation',fields=names)
    url=reverse('equipment:usage_create');before=model('equipment','EquipmentUsageLog').objects.count()
    payload={'equipment':ids['equipment'],'started_at':'2026-11-12T13:00','ended_at':'2026-11-12T15:00','runtime_hours':'20','source_key':'B04-runtime-overlap'}
    status=post(owner,url,payload)
    created=model('equipment','EquipmentUsageLog').objects.filter(source_key=payload['source_key']).first()
    mark('equipment:usage-interval',created is None,status=status,accepted_runtime=created.runtime_hours if created else None,overlaps_existing=True,created=model('equipment','EquipmentUsageLog').objects.count()-before)
    if db=='b04_retest':
        allocation=get('equipment','EquipmentCostAllocation',source_key='B04-allocation')
        reversal_url=reverse('equipment:cost_allocation_reverse',args=[allocation.pk])
        visit(owner,reversal_url);fill(form(owner),reason='برگشت مستقل B04');click(form(owner));allocation.refresh_from_db()
        reversals=model('equipment','EquipmentCostAllocation').objects.filter(correction_of=allocation)
        mark('equipment:cost_allocation_reverse',allocation.status=='reversed' and reversals.count()==1 and reversals.first().amount==-allocation.amount,state=allocation.status,reversal_amount=reversals.first().amount if reversals.exists() else None,original_amount=allocation.amount)
        n=model('audit','AuditEvent').objects.count();status=post(owner,reversal_url,{'reason':'برگشت مستقل B04'})
        mark('equipment:cost_allocation_reverse',reversals.count()==1 and model('audit','AuditEvent').objects.count()==n,replay_status=status)
        envelope=get('equipment','EquipmentCostSourceEnvelope',allocation=allocation)
        mark('equipment:cost_handoff_create',envelope.source_amount==allocation.amount,source_after_reversal=allocation.status,retained_snapshot=envelope.source_amount,envelope_status=envelope.status)
    # A sibling-site actor must not receive a source-backed allocation at EAST.
    visit(wrong,reverse('equipment:cost_workbench'));capture(wrong,'cost-sibling-scope',True)
    source=get('equipment','EquipmentCostAllocation',source_key='B04-allocation') if db=='b04_retest' else None
    if source:
        visible=int('B04-EQ-BASE' in text(wrong))+main(wrong).locator(f'a[href*="{source.pk}"]').count()+main(wrong).locator(f'form[action*="{source.pk}"]').count()
        mark('equipment:cost-scope',visible==0,source_site=source.site_id,actor_scope=ids['sibling'],visible_source_actions=visible)
    for route in ['accounting:dashboard','treasury:dashboard']:
        try:status=owner.request.get(base+reverse(route)).status
        except Exception:continue
        mark('mvp-financial-boundary',status in [403,404],target_route=route,status=status)
    for app,name in [('accounting','JournalEntry'),('treasury','TreasuryMovement'),('treasury','PaymentRequest'),('projects','ProjectCostFact')]:
        mark('financial-side-effects',model(app,name).objects.count()==0,model=app+'.'+name,count=model(app,name).objects.count())
    import csv
    from django.urls import get_resolver
    from uuid import uuid4
    values={'equipment_id':ids['equipment']}
    for key,app,name,lookup in [
        ('assignment_id','equipment','EquipmentAssignment',{'equipment__code':'B04-EQ-UI'}),
        ('record_id','equipment','MaintenanceRecord',{'record_number':'B04-M1'}),
        ('work_order_id','equipment','EquipmentWorkOrder',{'number':'B04-WO1'}),
        ('policy_id','equipment','EquipmentCostPolicyVersion',{'code':'B04-POL'}),
        ('allocation_id','equipment','EquipmentCostAllocation',{'source_key':'B04-allocation'}),
        ('envelope_id','equipment','EquipmentCostSourceEnvelope',{}),
        ('expense_id','expenses','Expense',{'source_reference':'B04-INV1'}),
        ('category_id','expenses','ExpenseCategory',{'code':'b04-cat'}),
        ('template_id','expenses','RecurringExpenseTemplate',{'source_reference_prefix':'B04-REC'}),
        ('incident_id','safety','SafetyIncident',{'incident_number':'B04-SAFETY'}),
        ('issue_id','quality','QualityIssue',{'issue_number':'B04-QUALITY'}),
    ]:
        obj=model(app,name).objects.filter(**lookup).first();values[key]=str(obj.pk) if obj else str(uuid4())
    values['action']='review'
    rows=[r for r in csv.DictReader(Path('docs/validation/comprehensive-product/TEST_EXECUTION_MATRIX_MVP.csv').open(encoding='utf-8-sig')) if r['Batch']=='B04']
    before=model('audit','AuditEvent').objects.count()
    for row in rows:
        route=row['Route_Name'];namespace,name=route.split(':')
        params=get_resolver().namespace_dict[namespace][1].reverse_dict.getlist(name)[0][0][0][1]
        url=reverse(route,kwargs={k:values[k] for k in params})
        if row['Method']!='GET' and not name.endswith(('list','detail')) and name not in ['recurrences']:
            status=post(reader,url)
            mark('restricted:'+route,status in [403,404],status=status)
    mark('restricted-no-audit-writes',model('audit','AuditEvent').objects.count()==before,before=before,after=model('audit','AuditEvent').objects.count())
    browser.close()
save()

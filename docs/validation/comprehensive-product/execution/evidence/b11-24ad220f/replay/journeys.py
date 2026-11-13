"""Representative cross-module clicks and bounded browser acceptance cases."""
import sys
import os
import re
import traceback
from urllib.parse import parse_qs, urlsplit

from sweep import Browser, host, load_fixtures, sessions, write, sync_playwright, reverse, model_first
from django.db import connection, transaction
from playwright.sync_api import expect

def href(page, path, region='main', match_query=False):
    url=urlsplit(path)
    locator=page.locator(f'{region} a[href]')
    positions=locator.evaluate_all("""(all,u) => all.map((a,i)=>[a,i]).filter(([a])=>{const x=new URL(a.href,location.href);return x.pathname===u[0] && (!u[1] || x.search===u[1]) && a.getClientRects().length>0;}).map(([,i])=>i)""",[url.path,'?'+url.query if match_query and url.query else ''])
    assert positions, f'No rendered link to {url.path} from {urlsplit(page.url).path}'
    return locator.nth(positions[0])

def click(page,path,region='main',match_query=False):
    link=href(page,path,region,match_query)
    label=link.inner_text().strip()
    with page.expect_navigation(wait_until='domcontentloaded',timeout=25000) as nav:
        link.click(timeout=25000,no_wait_after=True)
    assert nav.value is None or nav.value.status==200
    assert urlsplit(page.url).path==urlsplit(path).path
    return {'href':urlsplit(page.url).path,'label':label,
            'query_keys':list(parse_qs(urlsplit(page.url).query))}

def submit(page,form,expected=(302,),reason=None):
    if reason is not None:
        form.locator('[name=reason]').fill(reason)
    button=form.locator('button[type=submit],button:not([type])').last
    with page.expect_response(lambda r:r.request.method=='POST',timeout=25000) as posted:
        button.click(timeout=25000,no_wait_after=True)
    status=posted.value.status
    assert status in expected,status
    page.wait_for_load_state('domcontentloaded')
    return status

def main():
    actors,s=load_fixtures()
    proc,origin,log=host()
    out={}
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='chrome',headless=True)
            run=Browser(browser,origin,actors,sessions(actors))
            def check(name,fn):
                if os.environ.get('B11_JOURNEYS') and not re.search(os.environ['B11_JOURNEYS'],name): return
                try:
                    detail=fn()
                    out[name]={'outcome':'PASS' if detail.get('project_context_handoff_verified') is not False else 'PARTIAL','detail':detail}
                except Exception as exc:
                    traceback.print_exc()
                    out[name]={'outcome':'UNVERIFIED','observation':str(exc).splitlines()[0][:300]}
                print(name,out[name],flush=True)
                write(os.environ.get('B11_JOURNEY_OUTPUT','journeys.json'),out)

            def project(site=False):
                pr=s['field-main-project']
                ps=s['field-main-site']
                page,response=run.get('field','/organizations/')
                assert response.status==200
                # Select the visible active company's real context before following app navigation.
                entry=urlsplit(page.url).path
                switch=page.locator(f"main form[action='{reverse('organizations:switch')}']").filter(has=page.locator(f"[value='{pr.organization_id}']"))
                switched=False
                if switch.count():
                    submit(page,switch.first)
                    switched=True
                if urlsplit(page.url).path!='/':
                    page,_=run.get('field','/')
                steps=[click(page,'/projects/',region='body')]
                steps.append(click(page,reverse('projects:detail',args=[pr.pk])))
                if site:
                    steps.append(click(page,reverse('projects:site_list',args=[pr.pk])))
                    steps.append(click(page,reverse('projects:site_detail',args=[pr.pk,ps.pk])))
                    assert ps.name in page.locator('main').inner_text()
                    page.go_back(wait_until='domcontentloaded')
                    assert urlsplit(page.url).path==reverse('projects:site_list',args=[pr.pk])
                else:
                    steps.append(click(page,reverse('daily_reports:list')))
                    assert str(pr.pk) in parse_qs(urlsplit(page.url).query).get('project_filter',[])
                    steps.append(click(page,reverse('daily_reports:detail',args=[s['field-report'].pk])))
                return {'company_entry':entry,'explicit_switch':switched,'steps':steps,'terminal_widths':run.bounds(page)}
            check('company-project-site',lambda:project(True))
            check('project-daily-reports',project)

            def workforce():
                employee=s['field-employee']
                page,_=run.get('field',reverse('workforce:field_list'))
                steps=[click(page,reverse('workforce:field_detail',args=[employee.pk])),click(page,reverse('timekeeping:workbench'))]
                assert str(employee.pk) in [v for values in parse_qs(urlsplit(page.url).query).values() for v in values]
                path=reverse('timekeeping:record_detail',args=['attendance',s['field-attendance'].pk])
                steps.append(click(page,path))
                assert page.locator('main').inner_text()
                return {'steps':steps,'employee_context':True,'terminal_widths':run.bounds(page)}
            check('workforce-timekeeping',workforce)

            def equipment():
                pr=s['field-main-project']
                eq=s['field-equipment']
                page,_=run.get('field',reverse('projects:detail',args=[pr.pk]))
                direct=run.link(page,reverse('equipment:list'))
                operations=reverse('equipment:operations_workbench')
                if run.link(page,reverse('equipment:list'),'body'):
                    steps=[click(page,reverse('equipment:list'),region='body'),click(page,reverse('equipment:detail',args=[eq.pk]))]
                else:
                    return {'direct_project_link':False,'visible_equipment_in_sidebar':run.link(page,operations,'body'),'project_context_handoff_verified':False}
                ops=reverse('equipment:operations_workbench')
                if not run.link(page,ops):
                    steps.append(click(page,ops,region='body'))
                else:
                    steps.append(click(page,ops))
                return {'direct_project_link':bool(direct),'steps':steps,'terminal_widths':run.bounds(page)}
            check('project-equipment-operations',equipment)

            def review(app):
                obj=s[app]
                page,_=run.get('hse-reviewer',reverse(app+':list'))
                source=reverse(app+':detail',args=[obj.pk])
                decision=reverse(app+':record_decision',args=[obj.pk])
                steps=[click(page,source),click(page,decision)]
                form=page.locator('main form').filter(has=page.locator('[name=reason]')).first
                form.locator('[name=outcome]').select_option('approved')
                status=submit(page,form,reason='بررسی مستقل آزمایشی بنیرا')
                expect(page).to_have_url(origin+source)
                obj.refresh_from_db()
                assert obj.review_status=='approved' and obj.review_revisions.count()==2
                assert obj.status=='reported'
                return {'steps':steps,'post':status,'review_status':obj.review_status,'operational_status':obj.status,
                        'persisted_revisions':obj.review_revisions.count(),'terminal_widths':run.bounds(page)}
            check('safety-independent-review',lambda:review('safety'))
            check('quality-independent-review',lambda:review('quality'))

            def billing():
                contract=s['billing-contract']
                baseline=s['billing-baseline']
                page,_=run.get('billing',reverse('contracts:detail',args=[contract.pk]))
                listing=reverse('billing:baseline_list')
                dest=reverse('billing:baseline_detail',args=[baseline.pk])
                steps=[]
                if run.link(page,dest):
                    steps.append(click(page,dest))
                else:
                    quantities=reverse('contracts:detail',args=[contract.pk])+'?tab=quantities'
                    nav=page.get_by_role('link',name='مقادیر و بهای قرارداد',exact=True).first
                    if nav.count():
                        link=nav.get_attribute('href')
                        steps.append(click(page,link,match_query=True))
                        basis=page.get_by_role('link',name='مبنای متره و صورت‌وضعیت',exact=True).first
                        if basis.count():
                            steps.append(click(page,basis.get_attribute('href'),match_query=True))
                        if run.link(page,dest):
                            steps.append(click(page,dest))
                        else:
                            steps.extend([click(page,listing,region='body'),click(page,dest)])
                    else:
                        steps.extend([click(page,listing),click(page,dest)])
                steps.append(click(page,reverse('billing:claim_create')))
                params=parse_qs(urlsplit(page.url).query)
                assert str(baseline.pk) in params.get('baseline',[])
                return {'steps':steps,'baseline_context':True,'terminal_widths':run.bounds(page)}
            check('contract-baseline-progress-claim',billing)

            def receipt():
                obj=s['receipt'];stock=s['stock']
                page,_=run.get('ops',reverse('procurement:receipt_list'))
                rpath=reverse('procurement:receipt_detail',args=[obj.pk])
                spath=reverse('inventory:transaction_detail',args=[stock.pk])
                steps=[click(page,rpath),click(page,spath)]
                assert stock.goods_receipt_item.goods_receipt_id==obj.pk
                page.go_back(wait_until='domcontentloaded')
                assert urlsplit(page.url).path==rpath
                return {'steps':steps,'pinned_postgres_source':True,'browser_back':rpath}
            check('procurement-inventory',receipt)

            def inbound():
                obj=s['transfer']
                page,_=run.get('inventory-receiver',reverse('inventory:warehouse_list'))
                listing=reverse('inventory:custody_workbench',query={'tab':'inbound'})
                detail=reverse('inventory:transfer_detail',args=[obj.pk],query={'tab':'inbound'})
                steps=[click(page,listing,match_query=True),click(page,detail,match_query=True)]
                assert obj.transfer_number in page.locator('main').inner_text()
                limited=run.request('inventory-sibling',detail)
                foreign=run.request('inventory-foreign',detail)
                assert limited.status in (403,404) and foreign.status in (403,404)
                return {'steps':steps,'sibling':limited.status,'foreign':foreign.status,'terminal_widths':run.bounds(page)}
            check('inventory-inbound-transfers',inbound)

            def documents():
                obj=s['dms-project'];doc=s['document']
                source=reverse('projects:detail',args=[obj.pk])
                page,_=run.get('docs',source)
                dest=reverse('documents:detail',args=[doc.pk])
                steps=[click(page,dest),click(page,source)]
                assert obj.name in page.locator('main').inner_text()
                assert run.request('docs-foreign',dest).status in (403,404)
                return {'steps':steps,'source_return':source}
            check('business-record-related-documents',documents)

            def workflow():
                item=s['work-item'];source=s['workflow-request']
                listing=reverse('workflows:workbench')
                detail=reverse('procurement:request_detail',args=[source.pk])
                page,_=run.get('workflow',listing)
                steps=[click(page,detail)]
                page.go_back(wait_until='domcontentloaded')
                assert urlsplit(page.url).path==listing
                row=page.locator(f'#work-item-{item.pk}')
                action=lambda route: row.locator(f"form[action='{reverse(route,args=[item.pk])}']")
                for name,state in [('claim','claimed'),('release','open'),('claim','claimed')]:
                    row.locator('summary').first.press('Enter')
                    submit(page,action('workflows:work_item_'+name))
                    expect(page).to_have_url(origin+listing)
                    item.refresh_from_db()
                    assert item.status==state
                row.locator('summary').first.press('Enter')
                approve=action('workflows:work_item_action').filter(has=page.locator('[name=outcome][value=approved]'))
                submit(page,approve)
                source.refresh_from_db();item.refresh_from_db()
                assert item.status=='completed' and source.status=='approved'
                return {'steps':steps,'return':listing,'item':item.status,'source':source.status,'claim_release_claim':True}
            check('workflow-inbox-source-decision',workflow)

            def platform():
                start=reverse('organizations:platform_dashboard')
                page,_=run.get('platform',start)
                paths=[reverse('organizations:'+r) for r in ('platform_company_list','platform_users','platform_role_catalog')]
                steps=[]
                for path in paths:
                    steps.append(click(page,path,region='body'))
                    page.go_back(wait_until='domcontentloaded')
                company_path=reverse('organizations:platform_company_detail',args=[s['company'].pk])
                steps.append(click(page,paths[0],region='body'))
                steps.append(click(page,company_path))
                assert run.request('tenant',company_path).status in (302,403,404)
                return {'steps':steps,'terminal_widths':run.bounds(page)}
            check('platform-companies-users-roles',platform)

            def mobile():
                page,_=run.get('field','/')
                hidden=('/accounting/','/treasury/','/payroll/','/financials/','/subledgers/','/admin/')
                selector='a[href]'
                def links(region):
                    return set(page.locator(f'{region} {selector}').evaluate_all("es => es.map(e=>new URL(e.href,location.href).pathname)"))
                desktop=links('aside.erp-sidebar')
                page.set_viewport_size({'width':390,'height':844})
                drawer=page.locator('[data-mobile-nav]')
                summary=drawer.locator(':scope > summary')
                summary.focus()
                summary.press('Enter')
                expect(drawer).to_have_attribute('open','')
                narrow=links('.erp-mobile-nav__panel')
                summary.press('Escape')
                expect(summary).to_be_focused()
                assert drawer.get_attribute('open') is None
                assert not any(u.startswith(hidden) for u in desktop|narrow)
                direct={u:run.request('field',u).status for u in hidden[:-1]}
                assert all(v in (403,404) for v in direct.values())
                common={'/projects/','/daily-reports/','/timekeeping/','/workforce/field/','/equipment/'}
                return {'desktop_destinations':len(desktop),'mobile_destinations':len(narrow),'both_include':sorted(common&desktop&narrow),
                        'desktop_only':sorted(desktop-narrow),'mobile_only':sorted(narrow-desktop),'escape_returns_focus':True,'hidden_direct':direct}
            check('mobile-keyboard-and-hidden-surface',mobile)

            def form_validation():
                page,_=run.get('field',reverse('projects:site_create',args=[s['field-main-project'].pk]))
                form=page.locator('main form[method=post]').first
                code=form.locator('[name=code]')
                code.fill('B11-RETAIN')
                form.evaluate("f => f.noValidate = true")
                status=submit(page,form,expected=(200,400))
                expect(page.locator('main [name=code]')).to_have_value('B11-RETAIN')
                assert not model_first(s['field-main-project'].organization,'projects.ProjectSite',code='B11-RETAIN')
                return {'http':status,'retained':'B11-RETAIN','persisted':False,'viewport':run.bounds(page)}
            check('contextual-form-invalid-retention',form_validation)
            def search():
                p=s['field-main-project']
                page,response=run.get('field',reverse('global_search',query={'q':p.name}))
                assert response.status==200
                main=page.locator('main')
                assert p.name in main.inner_text()
                path=reverse('projects:detail',args=[p.pk])
                steps=[click(page,path)]
                page,response=run.get('field',reverse('global_search',query={'q':'B11-UNMATCHED-SYNTHETIC'}))
                assert response.status==200 and not run.link(page,path)
                return {'steps':steps,'nonmatch_excludes_prior_result':True,'terminal_widths':run.bounds(page)}
            check('global-search-match-and-empty',search)

            def pointer_contextual():
                from apps.documents.models import DocumentLink
                obj=s['dms-project']
                from apps.documents.test_evidence_integration import EvidenceIntegrationTests
                from b09_seed import upload
                from apps.documents.services import create_document
                owner,organization=actors['docs']
                existing=create_document(organization=organization,actor=owner,title='سند آزمون B11-POINTER',document_type='general',upload=upload(),target=s['dms-contract'])
                source=reverse('projects:detail',args=[obj.pk])
                link=reverse('documents:contextual-link',args=['project',obj.pk])
                page,_=run.get('docs',source)
                start=click(page,link)
                form=page.locator('main form[method=post]').first
                combo=form.get_by_role('combobox')
                if combo.count()>1:
                    combo=combo.last
                form.locator('.ts-control').last.click(timeout=12000)
                # Existing selectable document is a separate synthetic source.
                search=form.locator('.ts-control input').last
                if search.count():
                    search.fill('B11-POINTER')
                else:
                    combo.fill('B11-POINTER')
                option=page.locator('.ts-dropdown [data-selectable]').filter(has_text='B11-POINTER').first
                option.click(timeout=15000)
                before=DocumentLink.objects.filter(project=obj).count()
                status=submit(page,form)
                expect(page).to_have_url(origin+source+'#related-documents')
                assert DocumentLink.objects.filter(project=obj).count()==before+1
                return {'entry':start,'source':source,'pointer_submit':status,'one_new_link':True}
            check('contextual-document-pointer',pointer_contextual)

            def auth_invalid():
                page,_=run.get('anonymous',reverse('accounts:login'))
                form=page.locator('main form').first
                form.locator('[name=username]').fill('b11-invalid-user')
                form.locator('[name=password]').fill('invalid-synthetic-password')
                status=submit(page,form,expected=(200,400))
                assert 'b11-invalid-user'==form.locator('[name=username]').input_value()
                assert page.locator('main').get_by_text('ورود',exact=False).count()
                assert urlsplit(page.url).path==reverse('accounts:login')
                return {'status':status,'identity_input_retained':True,'stayed_on_login':True,'viewport':run.bounds(page)}
            check('login-invalid-retention',auth_invalid)
            browser.close()
    finally:
        proc.terminate(); proc.wait(timeout=15); log.close()

if __name__=='__main__':main()







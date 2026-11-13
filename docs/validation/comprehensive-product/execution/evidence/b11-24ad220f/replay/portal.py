"""Isolated supplier portal display regression in Google Chrome."""
import argparse
from pathlib import Path
from zoneinfo import ZoneInfo
from django.utils import timezone
from sweep import Browser, host, load_fixtures, sessions, write, sync_playwright, reverse, OUT
from core.jalali import format_jalali

def main():
    args=argparse.ArgumentParser()
    args.add_argument('phase',choices=['before','after'])
    phase=args.parse_args().phase
    actors,s=load_fixtures()
    grant=s['portal-grant']
    receipt=s['portal-receipt']
    invitation=s['invitation']
    org=grant.organization
    setting=org.settings
    if setting.timezone!='Asia/Tehran':
        setting.timezone='Asia/Tehran'
        setting.save(update_fields=['timezone'])
    prior={'receipt':receipt.created_at,'close':invitation.rfq_version.closing_at,'receipt_version':receipt.quote_revision_id}
    with timezone.override(ZoneInfo('Asia/Tehran')):
        close=format_jalali(prior['close'],include_time=True)
        when=format_jalali(prior['receipt'],include_time=True)
    proc,origin,log=host()
    result={}
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='chrome',headless=True)
            run=Browser(browser,origin,actors,sessions(actors))
            specs=[
                ('context','supplier','procurement:portal_context',grant.pk,close),
                ('receipt','supplier','procurement:portal_receipt',receipt.pk,when),
                ('invitation','rfq','procurement:portal_invitation_manage',invitation.pk,None),
            ]
            for name,actor,route,pk,expected in specs:
                path=reverse(route,args=[pk])
                page,response=run.get(actor,path)
                widths=run.bounds(page)
                content=page.locator('main').inner_text()
                date_check=expected in content.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹','0123456789')) if expected else None
                receipt_visible=str(receipt.pk) in content
                result[name]={'path':path,'role':actor,'status':response.status,'expected_local_jalali':expected,
                    'local_jalali_rendered':date_check,'receipt_uuid_visible':receipt_visible,'layouts':widths}
                if actor=='supplier':
                    result[name]['wrong_principal']=run.request('rfq-foreign',path).status
                if name!='invitation':
                    pth=OUT/f'portal-{phase}-{name}-390.png'
                    page.screenshot(path=pth,animations='disabled')
            receipt.refresh_from_db(); invitation.refresh_from_db()
            result['unchanged_source']=prior=={'receipt':receipt.created_at,'close':invitation.rfq_version.closing_at,'receipt_version':receipt.quote_revision_id}
            if phase=='after':
                for name in ('context','receipt'):
                    x=result[name]
                    assert x['status']==200 and x['wrong_principal']==404 and x['local_jalali_rendered'] and (name!='receipt' or x['receipt_uuid_visible'])
                    assert all(o['scrollWidth']<=o['width']+1 and o['dir']=='rtl' for o in x['layouts'])
                assert result['unchanged_source']
            browser.close()
    finally:
        proc.terminate();proc.wait(timeout=15);log.close()
        write('portal-'+phase+'.json',result)
if __name__=='__main__':main()


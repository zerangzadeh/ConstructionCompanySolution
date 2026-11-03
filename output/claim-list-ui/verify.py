"""UI-only verification; all data lives in this runner's disposable PostgreSQL DB."""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
os.environ['BONIRA_BROWSER_LOCAL_ONLY'] = '1'
import django
django.setup()
from django.db import connections
from django.core.management import call_command
from apps.billing.test_claim_list import ClaimsListBrowserTests as ExistingBrowserChecks
connections['default'].settings_dict['TEST']['NAME'] = 'test_bonira_claim_list_clone_20261101'

class ClaimListVisualChecks(ExistingBrowserChecks):
    browser_evidence_directory = ROOT / 'output/claim-list-ui/browser'

    def _fixture_teardown(self):
        for alias in self._databases_names(include_mirrors=False):
            if connections[alias].settings_dict['NAME'] != 'test_bonira_claim_list_clone_20261101':
                raise RuntimeError('Dedicated disposable database required')
            call_command('flush', database=alias, interactive=False, verbosity=0,
                         allow_cascade=True, inhibit_post_migrate=True)
        connections['default'].creation.deserialize_db_from_string(self.seed_contents)

    def test_requested_viewports(self):
        self.rows()
        from decimal import Decimal
        from apps.billing.models import ProgressClaim
        self.project.name = "مجتمع مسکونی باغستان — پروژه نمونه سازه و تأسیسات"
        self.project.save(update_fields=['name'])
        ProgressClaim.objects.filter(organization=self.organization).update(
            gross_amount=Decimal('621878131688'), adjustment_amount=Decimal('21823556477'),
            net_amount=Decimal('600054575211'))
        geometry = "document.documentElement.scrollWidth<=innerWidth+1 && document.documentElement.dir==='rtl'"
        scenarios=[]
        for width in (1440,1024,390):
            for scope,path in [('contract',self.scoped),('general',self.url)]:
                scenarios.append(dict(name=f'{scope}-{width}',path=path,width=width,mobile=width<640,status=200,screenshot=True,noJsErrors=True,noHttpErrors=True,steps=[
                    dict(inspect=geometry,description='RTL and no page overflow'),
                    dict(inspect="document.querySelector('[name=status]').getBoundingClientRect().height>=40 && document.querySelector('[data-filter-apply]').getBoundingClientRect().height>=40",description='Filters stay visible and usable at all widths'),
                    dict(inspect="[...document.querySelectorAll('.erp-list-amount bdi')].every(e=>getComputedStyle(e).color===getComputedStyle(document.querySelector('.claim-net bdi')).color)",description='All financial values use neutral ink'),
                    dict(inspect="document.querySelectorAll('thead th').length==="+('8' if scope=='contract' else '9'),description='Context column only in general list'),
                    dict(inspect="!!document.querySelector('.claim-page-header [data-xlsx-export]')",description='Export in page header'),
                ]))
        scenarios.append(dict(name='filter-submit-390',path=self.scoped,width=390,mobile=True,status=200,screenshot=True,steps=[
            dict(fill={'status':'approved'},formSelector='#list-filter-bar',clickSelector='[data-filter-apply]',afterPath=self.url),
            dict(inspect="new URLSearchParams(location.search).get('status')==='approved' && !!new URLSearchParams(location.search).get('contract')",description='Real status filter retains contract'),
            dict(inspect=geometry,description='Filtered mobile fits'),
        ]))
        self.browser(self.owner,scenarios)

if __name__=='__main__':
    import pytest
    raise SystemExit(pytest.main([__file__+'::ClaimListVisualChecks::test_requested_viewports','--reuse-db','-q','--tb=short']))

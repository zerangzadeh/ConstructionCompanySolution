from sweep import *
from django.db import transaction
from apps.procurement.test_mvp04c import AwardPOJourneyTests
from apps.accounts.models import User
from apps.organizations.models import Organization
from b09_seed import persona
from apps.organizations.models import BusinessPermission
class ExplicitAwardFixture(AwardPOJourneyTests):
 def _make_actor(self,username):
  return persona(self,username,list(BusinessPermission.objects.filter(is_active=True).values_list('code',flat=True)))
actors,s=load_fixtures()
with transaction.atomic():
 for slug in ('procurement-co','other-procurement-co'):
  Organization.objects.filter(slug=slug).update(slug='b11-award-prior-'+slug)
 for user in User.objects.filter(username__in=['procurement-owner','procurement-member','procurement-viewer','procurement-outsider','admissibility-preparer','admissibility-approver']):
  user.username='b11-award-prior-'+user.username;user.save(update_fields=['username'])
 f=ExplicitAwardFixture();f.client=Client();f.setUp();award=f.award()
 f._protected_override.disable()
actors['award']=(f.preparer,f.organization)
proc,origin,log=host();out={}
try:
 with sync_playwright() as p:
  b=p.chromium.launch(channel='chrome',headless=True);run=Browser(b,origin,actors,sessions(actors))
  page,r=run.get('award',f.source_url(award));assert r.status==200
  out={'status':r.status,'path':urlsplit(page.url).path,'actor':'award preparer with explicit grants','widths':run.bounds(page),'controls':page.locator('main').aria_snapshot(),'business_scope':'UI source selection only. Prior B06 governs award calculation and downstream lineage.'}
  assert all(x['scrollWidth']<=x['width']+1 and x['dir']=='rtl' for x in out['widths'])
  b.close()
finally:
 proc.terminate();proc.wait(timeout=15);log.close();write('award-source-ui.json',out)

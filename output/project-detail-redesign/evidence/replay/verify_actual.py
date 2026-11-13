import os,json
from pathlib import Path
os.environ['DJANGO_SETTINGS_MODULE']='config.settings.development'
import django
django.setup()
from django.conf import settings
from django.db import connection,transaction
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import resolve
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.contrib.messages.storage.fallback import FallbackStorage
from apps.projects.models import Project
from apps.organizations.authorization import has_business_permission
from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.middleware import OrganizationMiddleware
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.daily_reports.services import get_organization_daily_reports
from core.product_surface import route_exposed
path='/projects/58f517da-2139-45ac-8b7b-4f3d3a3d26e8/'
assert settings.SETTINGS_MODULE=='config.settings.development' and settings.DEBUG
assert settings.DATABASES['default']['HOST']=='127.0.0.1' and str(settings.DATABASES['default']['PORT'])=='5432' and settings.DATABASES['default']['NAME']=='construction_erp'
with transaction.atomic():
 with connection.cursor() as c:c.execute('SET TRANSACTION READ ONLY')
 project=Project.objects.select_related('organization').get(pk='58f517da-2139-45ac-8b7b-4f3d3a3d26e8')
 actor=None
 for member in project.organization.memberships.filter(status='active',user__is_active=True).select_related('user'):
  if all(has_business_permission(user=member.user,organization=project.organization,permission=code,project=project) for code in [P.PROJECTS_VIEW,P.DAILY_REPORTS_VIEW]):
   actor=member.user;break
 assert actor is not None,'No existing authorized member for read-only verification'
 request=RequestFactory().get(path,HTTP_HOST='127.0.0.1:8000')
 request.user=actor;request.session=SessionStore();request.session[ACTIVE_ORGANIZATION_SESSION_KEY]=str(project.organization_id)
 request._messages=FallbackStorage(request);request.resolver_match=resolve(path)
 assert request.resolver_match.view_name=='projects:detail' and route_exposed('projects:detail')
 with CaptureQueriesContext(connection) as queries:
  response=OrganizationMiddleware(lambda req:request.resolver_match.func(req,**request.resolver_match.kwargs))(request)
 assert response.status_code==200,response.status_code
 assert project.name in response.content.decode()
 assert not any(x in response.content for x in [b'ProgrammingError',b'Traceback'])
 join_queried=any('previous_revision_id' in q['sql'] for q in queries.captured_queries)
 assert join_queried,'Exact Daily Report revision query was not exercised'
 result={'path':path,'project_view_status':response.status_code,'daily_report_revision_query_exercised':join_queried,'authorization':'Existing active member checked for projects.view and daily_reports.view. No grants or identity links changed.','verification':'Full project view and template rendered through OrganizationMiddleware inside a read-only database transaction with an unsaved in-memory session. No login, user, session or business writes.','queries':len(queries)}
Path('.scratch/project-detail-redesign/actual-project-readonly.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))

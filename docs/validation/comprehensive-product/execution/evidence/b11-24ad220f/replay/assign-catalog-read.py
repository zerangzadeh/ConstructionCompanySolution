from sweep import *
from apps.organizations.models import BusinessPermission,OrganizationRole
actors,_=load_fixtures()
u,org=actors['role-reader']
role=OrganizationRole.objects.get(organization=org,code=u.username)
role.permissions.add(BusinessPermission.objects.get(code='authorization_roles.view'))

from browser import *
from apps.organizations.test_platform_console import PlatformConsoleTests
assert db=='project_redesign_retest'
PlatformConsoleTests.setUpTestData()
cfg['actors']['platform']=str(PlatformConsoleTests.admin.pk);cfg['company']=str(PlatformConsoleTests.company.pk)
(root/'fixtures.json').write_text(json.dumps(cfg,indent=2),encoding='utf-8')
print('Protected-page synthetic Platform fixture ready.')

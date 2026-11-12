
from django.conf import settings
from django.core.management import call_command
import apps.documents.presentation as document_presentation
import apps.projects.dashboard as project_dashboard
for module,name in (
    (document_presentation,"apps/documents/presentation.py"),
    (project_dashboard,"apps/projects/dashboard.py"),
):
    path=private/"entry"/name
    exec(compile(path.read_bytes(),str(path),"exec"),module.__dict__)
templates=private/"entry_templates"
target=templates/"projects/detail.html"
target.parent.mkdir(parents=True,exist_ok=True)
target.write_bytes((private/"entry/apps/projects/templates/projects/detail.html").read_bytes())
settings.TEMPLATES[0]["DIRS"]=[templates,*settings.TEMPLATES[0]["DIRS"]]
call_command("test","apps.documents.test_related_documents.RelatedDocumentsTests.test_business_templates_have_one_navigation_and_one_read_only_section",keepdb=True,interactive=False,verbosity=2)

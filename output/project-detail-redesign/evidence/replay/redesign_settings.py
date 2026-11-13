import os
from pathlib import Path
from config.settings.base import *
private=Path(__file__).resolve().parent
name=os.environ.get('REDESIGN_DB','project_redesign_original')
assert name in {'project_redesign_base','project_redesign_original','project_redesign_retest'}
DATABASES={'default':{'ENGINE':'django.db.backends.postgresql','NAME':name,'USER':'b11_local','PASSWORD':'','HOST':'127.0.0.1','PORT':(private/'port.txt').read_text().strip(),'OPTIONS':{'sslmode':'disable'},'TEST':{'NAME':'test_project_redesign'}}}
SECRET_KEY=(private/'secret.txt').read_text().strip()
DEBUG=False
ALLOWED_HOSTS=['127.0.0.1','testserver','localhost']
PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']
MEDIA_ROOT=private/name/'media'
DOCUMENT_PROTECTED_ROOT=private/name/'protected'
EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
PRODUCT_SURFACE_PROFILE='MVP'

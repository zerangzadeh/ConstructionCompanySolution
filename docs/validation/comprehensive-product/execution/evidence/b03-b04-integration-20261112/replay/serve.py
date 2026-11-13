from common import root, guard
from django.core.management import call_command
guard()
call_command('runserver', '127.0.0.1:'+(root/'web-port.txt').read_text(), use_reloader=False, insecure_serving=True)

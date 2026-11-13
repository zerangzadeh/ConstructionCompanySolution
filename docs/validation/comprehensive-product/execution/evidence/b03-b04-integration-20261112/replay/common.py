import os
from pathlib import Path
import django
django.setup()
from django.db import connection
from django.conf import settings
root = Path(__file__).resolve().parent
db = 'integration_frozen'
assert settings.BASE_DIR.resolve() == root/'source'
def guard(readonly=False):
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(),inet_server_port(),current_setting('data_directory')")
        name, port, directory = cursor.fetchone()
        assert name == db and str(port) == (root/'db-port.txt').read_text()
        assert Path(directory).resolve() == root/'pg'
        if readonly:
            cursor.execute('SET default_transaction_read_only=on')
    return name, port

"""Loopback-only temporary Development server with test-only application clock."""
from support import *
from unittest.mock import patch
from django.core.management import execute_from_command_line
guard()
with patch("django.utils.timezone.now", side_effect=controlled_now):
    execute_from_command_line(["manage.py", "runserver", "127.0.0.1:8017", "--noreload"])

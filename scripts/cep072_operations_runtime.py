"""Bounded EXT-0022 Windows Development sink activation; no background service."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path

from core.operations import DevelopmentOperationsHandler, DevelopmentOperationsSink
from scripts.cep070_recovery_controls import create_private_store, verify_private_tree


def provision_sink() -> tuple[DevelopmentOperationsSink, dict]:
    directory = create_private_store(Path("E:/BONIRA_Operations/EXT0022"))
    return DevelopmentOperationsSink(directory), verify_private_tree(directory)


@contextmanager
def activate(sink: DevelopmentOperationsSink):
    """Attach only for this explicitly approved executor, retaining files on exit."""
    verify_private_tree(sink.directory)
    logger = logging.getLogger("bonira.request")
    handler = DevelopmentOperationsHandler(sink)
    logger.addHandler(handler)
    try:
        yield sink
    finally:
        logger.removeHandler(handler)
        handler.close()
        verify_private_tree(sink.directory)

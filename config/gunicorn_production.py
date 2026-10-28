"""Explicit Production diagnostics binding for the approved synchronous WSGI service."""

import logging
import os
from pathlib import Path


def post_worker_init(worker: object) -> None:
    from django.conf import settings

    from core.production_operations import (
        ProductionOperationsHandler,
        ProductionOperationsSink,
        install_authentication_observer,
    )

    if settings.DEBUG or settings.SETTINGS_MODULE != "config.settings.production":
        raise RuntimeError(
            "The Production service requires secure Production settings."
        )
    sink = ProductionOperationsSink(
        Path(os.environ["BONIRA_OPERATIONS_SINK"]),
        environment=os.environ["BONIRA_OPERATIONS_ENVIRONMENT"],
    )
    logging.getLogger("bonira.request").addHandler(ProductionOperationsHandler(sink))
    install_authentication_observer(sink)

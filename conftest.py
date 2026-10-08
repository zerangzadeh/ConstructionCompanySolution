"""Repository-wide pytest configuration."""

import pytest
from django.test import TransactionTestCase

# Migration-seeded workflow, authorization, and platform master catalogues are
# part of the test baseline.  Mixing ordinary TransactionTestCase classes with
# classes that opt into Django's serialized rollback leaves post_migrate rows in
# place before the next baseline deserialize.  Apply one policy to the entire
# transactional suite so every class starts from the same seeded snapshot and
# every teardown inhibits post_migrate before the next deserialize.
TransactionTestCase.serialized_rollback = True


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Give function-style transactional tests the same seeded baseline."""
    for item in items:
        marker = item.get_closest_marker("django_db")
        if marker is None or not marker.kwargs.get("transaction", False):
            continue
        marker.kwargs["serialized_rollback"] = True

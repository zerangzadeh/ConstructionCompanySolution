from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import TransactionTestCase

from apps.accounts.models import User
from apps.organizations.services import create_organization_with_owner
from apps.workforce.person_services import create_person


class NationalIdConcurrencyTests(TransactionTestCase):
    def test_concurrent_person_and_user_ids_cannot_commit_a_contradiction(self):
        owner = User.objects.create_user(username="mvp02-race-owner")
        organization = create_organization_with_owner(
            owner=owner, name="شرکت آزمایش هم‌زمانی", slug="mvp02-race"
        )
        person = create_person(
            organization=organization,
            actor=owner,
            first_name="نیروی",
            last_name="آزمایشی",
            user=owner,
        )
        barrier = Barrier(2)

        def change(model, pk, value):
            close_old_connections()
            try:
                instance = model.objects.get(pk=pk)
                barrier.wait(timeout=10)
                instance.national_id = value
                try:
                    instance.save()
                except ValidationError:
                    return "conflict"
                return "saved"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            user_result = pool.submit(change, User, owner.pk, "0013543679")
            person_result = pool.submit(change, type(person), person.pk, "1234567891")
            results = [user_result.result(timeout=30), person_result.result(timeout=30)]
        self.assertCountEqual(results, ["saved", "conflict"])
        owner.refresh_from_db()
        person.refresh_from_db()
        self.assertFalse(
            owner.national_id
            and person.national_id
            and owner.national_id != person.national_id
        )

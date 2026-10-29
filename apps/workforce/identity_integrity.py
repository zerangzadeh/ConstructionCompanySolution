"""National-ID integrity over explicit identity links; never infer a link."""

from contextlib import contextmanager

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Q


def normalize_national_id(value: str | None) -> str | None:
    return (value or "").strip().translate(
        str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    ) or None


def _conflict() -> None:
    raise ValidationError({"national_id": "کد ملی با هویت متصل‌شده سازگار نیست."})


def validate_person_identity(person) -> None:
    from apps.accounts.models import User
    from apps.workforce.models import Person, WorkRelationship

    user_ids = set(
        WorkRelationship.objects.filter(person_id=person.pk)
        .exclude(legacy_employee__user_id=None)
        .values_list("legacy_employee__user_id", flat=True)
    )
    if person.user_id:
        user_ids.add(person.user_id)
    if len(user_ids) > 1:
        _conflict()
    if (
        user_ids
        and Person.objects.filter(
            Q(user_id__in=user_ids)
            | Q(work_relationships__legacy_employee__user_id__in=user_ids),
            organization_id=person.organization_id,
        )
        .exclude(pk=person.pk)
        .exists()
    ):
        _conflict()
    for user in User.objects.filter(pk__in=user_ids):
        if (
            person.national_id
            and user.national_id
            and person.national_id != user.national_id
        ):
            _conflict()
        if (
            user.national_id
            and Person.objects.filter(
                organization_id=person.organization_id, national_id=user.national_id
            )
            .exclude(pk=person.pk)
            .exists()
        ):
            _conflict()
    if (
        person.national_id
        and Person.objects.filter(
            Q(user__national_id=person.national_id)
            | Q(
                work_relationships__legacy_employee__user__national_id=person.national_id
            ),
            organization_id=person.organization_id,
        )
        .exclude(pk=person.pk)
        .exists()
    ):
        _conflict()


def validate_employee_identity(employee) -> None:
    from apps.accounts.models import User
    from apps.workforce.models import Person, WorkRelationship

    if not employee.user_id:
        return
    user = User.objects.get(pk=employee.user_id)
    for relation in WorkRelationship.objects.filter(
        legacy_employee_id=employee.pk
    ).select_related("person"):
        person = relation.person
        if person.user_id and person.user_id != user.pk:
            raise ValidationError({"user": "حساب با هویت نیروی کار سازگار نیست."})
        if (
            Person.objects.filter(
                Q(user_id=user.pk)
                | Q(work_relationships__legacy_employee__user_id=user.pk),
                organization_id=employee.organization_id,
            )
            .exclude(pk=person.pk)
            .exists()
        ):
            raise ValidationError({"user": "این حساب به هویت دیگری متصل است."})
        if (
            person.national_id
            and user.national_id
            and person.national_id != user.national_id
        ):
            raise ValidationError(
                {"user": "کد ملی حساب با هویت نیروی کار سازگار نیست."}
            )
        if (
            user.national_id
            and Person.objects.filter(
                organization_id=employee.organization_id, national_id=user.national_id
            )
            .exclude(pk=person.pk)
            .exists()
        ):
            raise ValidationError({"user": "این کد ملی برای هویت دیگری ثبت شده است."})


def validate_user_national_id(user) -> None:
    from django.db.models import Q

    from apps.workforce.models import Person

    if not user.national_id:
        return
    people = Person.objects.filter(
        Q(user_id=user.pk) | Q(work_relationships__legacy_employee__user_id=user.pk)
    ).distinct()
    for person in people:
        if person.national_id and person.national_id != user.national_id:
            _conflict()
        if (
            Person.objects.filter(
                organization_id=person.organization_id, national_id=user.national_id
            )
            .exclude(pk=person.pk)
            .exists()
        ):
            _conflict()


@contextmanager
def identity_write_lock():
    """Serialize link/ID changes against authentication-ID edits."""
    with transaction.atomic():
        # A cross-table invariant has no single unique index. Serialize the short
        # identity write boundary, including previously unlinked national IDs.
        # PostgreSQL transaction locks release on commit/rollback and require no
        # new table, background process, or persistent lock lifecycle.
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [1942070216])
        yield

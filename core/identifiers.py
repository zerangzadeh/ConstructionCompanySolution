"""Database-agnostic canonicalization for business identifiers."""


def canonicalize_lower_identifier(value: str) -> str:
    """Strip surrounding whitespace and store a lowercase identifier."""

    return value.strip().lower()


def canonicalize_upper_identifier(value: str) -> str:
    """Strip surrounding whitespace and store an uppercase identifier."""

    return value.strip().upper()

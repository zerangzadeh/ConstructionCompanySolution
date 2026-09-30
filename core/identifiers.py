"""Database-agnostic canonicalization for business identifiers."""

import unicodedata


def canonicalize_lower_identifier(value: str) -> str:
    """Strip surrounding whitespace and store a lowercase identifier."""

    return value.strip().lower()


def canonicalize_upper_identifier(value: str) -> str:
    """Strip surrounding whitespace and store an uppercase identifier."""

    return value.strip().upper()


def canonicalize_party_identity_value(value: str) -> str:
    """Normalize party match evidence without changing the recorded source value."""

    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.split()).casefold()

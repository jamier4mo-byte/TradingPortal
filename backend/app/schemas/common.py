"""Shared field types."""

from typing import Annotated

from pydantic import AfterValidator, StringConstraints


def _email(value: str) -> str:
    value = value.strip().lower()
    local, sep, domain = value.partition("@")
    if not sep or not local or "." not in domain or " " in value:
        raise ValueError("Enter a valid email address.")
    return value


# Looser than EmailStr on purpose: test and LAN domains like name@example.test are fine.
Email = Annotated[str, StringConstraints(min_length=3, max_length=255), AfterValidator(_email)]

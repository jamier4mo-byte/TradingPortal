from fastapi import HTTPException

from ..services.keys import KeyError_
from ..services.passkeys import PasskeyError
from ..services.tags import TagError
from ..services.users import AuthError

ServiceError = AuthError | KeyError_ | TagError | PasskeyError


def http(exc: ServiceError) -> HTTPException:
    return HTTPException(exc.status, exc.message)

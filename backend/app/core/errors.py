from fastapi import HTTPException, status


class ApiError(HTTPException):
    """HTTPException with a stable machine-readable `code` for clients."""

    def __init__(self, status_code: int, code: str, message: str | None = None, **extra):
        super().__init__(status_code=status_code, detail={"code": code, "message": message or code, **extra})


def bad_request(code: str, message: str | None = None, **extra) -> ApiError:
    return ApiError(status.HTTP_400_BAD_REQUEST, code, message, **extra)


def unauthorized(code: str = "unauthorized", message: str | None = None) -> ApiError:
    return ApiError(status.HTTP_401_UNAUTHORIZED, code, message)


def forbidden(code: str = "forbidden", message: str | None = None) -> ApiError:
    return ApiError(status.HTTP_403_FORBIDDEN, code, message)


def not_found(code: str = "not_found", message: str | None = None) -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, code, message)


def conflict(code: str, message: str | None = None, **extra) -> ApiError:
    return ApiError(status.HTTP_409_CONFLICT, code, message, **extra)


def too_many(code: str = "rate_limited", message: str | None = None, **extra) -> ApiError:
    return ApiError(status.HTTP_429_TOO_MANY_REQUESTS, code, message, **extra)

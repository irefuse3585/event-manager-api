# app/utils/exceptions.py

from fastapi import HTTPException, status


class ConflictError(HTTPException):
    """
    Raised when an action would create a resource conflict, e.g. duplicate user.
    Returns HTTP 409.
    """

    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class UnauthorizedError(HTTPException):
    """
    Raised when credentials are invalid or missing.
    Returns HTTP 401.
    """

    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class ForbiddenError(HTTPException):
    """
    Raised when the user is authenticated but does not have permission.
    Returns HTTP 403.
    """

    def __init__(self, detail: str = "Forbidden"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class NotFoundError(HTTPException):
    """
    Raised when a requested resource is not found.
    Returns HTTP 404.
    """

    def __init__(self, detail: str = "Not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

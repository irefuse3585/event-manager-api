# app/utils/response.py

from typing import Any

import msgpack
from fastapi import Request
from fastapi.responses import JSONResponse, Response


class MessagePackResponse(Response):
    """
    Custom Response class for MessagePack serialization.
    Sets the correct Content-Type for MessagePack.
    """

    media_type = "application/x-msgpack"

    def render(self, content: Any) -> bytes:  # <-- Тут Any, не any
        # Use msgpack to serialize the content
        return msgpack.packb(content, use_bin_type=True)


def auto_response(
    request: Request, data: Any, status_code: int = 200
):  # <-- Тут Any, не any
    """
    Return either a JSON or MessagePack response depending on the Accept header.
    Converts Pydantic models to dict automatically.
    """
    # If data is a Pydantic model, convert to dict
    if hasattr(data, "dict"):
        data = data.dict()
    accept = request.headers.get("accept", "")
    # If client requests MessagePack, use MessagePackResponse
    if "application/x-msgpack" in accept:
        return MessagePackResponse(content=data, status_code=status_code)
    # Default to JSONResponse
    return JSONResponse(content=data, status_code=status_code)

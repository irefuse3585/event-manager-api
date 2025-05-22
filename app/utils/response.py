# app/utils/response.py

import logging
from typing import Any

import msgpack
from fastapi import Request
from fastapi.responses import JSONResponse, Response

# Initialize logger for this module
logger = logging.getLogger(__name__)


class MessagePackResponse(Response):
    """
    Custom Response class for MessagePack serialization.
    Sets the correct Content-Type for MessagePack.
    """

    media_type = "application/x-msgpack"

    def render(self, content: Any) -> bytes:
        """
        Serialize the response content using msgpack.
        Logs any serialization errors.
        """
        try:
            return msgpack.packb(content, use_bin_type=True)
        except Exception as exc:
            logger.error(
                "Failed to serialize content to MessagePack: %s", exc, exc_info=True
            )
            raise


def auto_response(request: Request, data: Any, status_code: int = 200):
    """
    Return either a JSON or MessagePack response depending on the Accept header.
    Converts Pydantic models to dict automatically.
    Logs usage of MessagePack.
    """
    # If data is a Pydantic model, convert to dict
    if hasattr(data, "dict"):
        data = data.dict()
    accept = request.headers.get("accept", "")
    if "application/x-msgpack" in accept:
        logger.info("Returning response in MessagePack format (Accept: %s)", accept)
        return MessagePackResponse(content=data, status_code=status_code)
    # Default to JSONResponse
    return JSONResponse(content=data, status_code=status_code)

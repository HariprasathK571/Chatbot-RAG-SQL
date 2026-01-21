import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # attach to request state
        request.state.request_id = request_id

        # log request start
        logger.info(
            f"Request started method={request.method} path={request.url.path}",
            extra={"request_id": request_id},
        )

        response = await call_next(request)

        # add request id to response header
        response.headers["X-Request-ID"] = request_id

        # log request end
        logger.info(
            f"Request finished status_code={response.status_code}",
            extra={"request_id": request_id},
        )

        return response

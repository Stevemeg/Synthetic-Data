import re
from time import perf_counter
from uuid import uuid4

from ..core.logging import log_event, request_id_context
from ..core.metrics import HTTP_LATENCY, HTTP_REQUESTS
from .errors import error_response


class RequestMiddleware:
    """Bound the full request body, including streamed/chunked multipart uploads."""

    def __init__(self, app, max_bytes: int, production: bool = False):
        self.app = app
        self.max_bytes = max_bytes
        self.production = production

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        proposed = headers.get(b"x-request-id", b"").decode("ascii", errors="ignore")
        request_id = proposed if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", proposed) else uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        context = request_id_context.set(request_id)
        start = perf_counter()
        status = 500

        async def correlated_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message["headers"] = [
                    *[
                        (k, v)
                        for k, v in message.get("headers", [])
                        if k.lower()
                        not in {b"x-request-id", b"x-content-type-options", b"cache-control"}
                    ],
                    (b"x-request-id", request_id.encode()),
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"cache-control", b"no-store"),
                ]
                message["headers"].append(
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()")
                )
                if self.production:
                    message["headers"].extend(
                        [
                            (
                                b"content-security-policy",
                                b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
                            ),
                            (b"strict-transport-security", b"max-age=31536000"),
                        ]
                    )
            await send(message)

        try:
            body = bytearray()
            more = True
            while more:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > self.max_bytes:
                    return await error_response(
                        request_id,
                        "UPLOAD_TOO_LARGE",
                        "Request exceeds configured upload limit",
                        413,
                    )(scope, receive, correlated_send)
                more = message.get("more_body", False)
            sent = False

            async def replay():
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            await self.app(scope, replay, correlated_send)
        finally:
            elapsed = perf_counter() - start
            route = getattr(scope.get("route"), "path", "unmatched")
            method = scope.get("method", "OTHER")
            if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
                method = "OTHER"
            HTTP_REQUESTS.labels(route, method, str(status)).inc()
            HTTP_LATENCY.labels(route, method).observe(elapsed)
            principal = scope.get("state", {}).get("principal")
            log_event(
                "http_request",
                status=status,
                duration=round(elapsed, 4),
                user_id=str(principal.user_id) if principal and principal.user_id else None,
                organization_id=str(principal.organization_id) if principal else None,
            )
            request_id_context.reset(context)

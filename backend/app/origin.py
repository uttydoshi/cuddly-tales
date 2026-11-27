"""Only accept requests that came through CloudFront.

The Lambda Function URL is public, so CloudFront adds a secret header to every
request it forwards. Requests without it are refused. Locally no secret is set
and every request is allowed.

Written as plain ASGI middleware (not @app.middleware) so streamed responses
pass straight through.
"""

import hmac
from collections.abc import Callable

from starlette.types import ASGIApp, Receive, Scope, Send

HEADER = b"x-origin-verify"


def is_allowed(given: str | None, expected: str | None) -> bool:
    if expected is None:
        return True
    return given is not None and hmac.compare_digest(given, expected)


class CloudFrontOnly:
    def __init__(self, app: ASGIApp, expected_secret: Callable[[], str | None]) -> None:
        self.app = app
        self.expected_secret = expected_secret

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            given = dict(scope["headers"]).get(HEADER)
            if not is_allowed(given.decode() if given else None, self.expected_secret()):
                await send({"type": "http.response.start", "status": 403,
                            "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": b'{"detail":"Forbidden"}'})
                return
        await self.app(scope, receive, send)

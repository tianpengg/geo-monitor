from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from internal.protocol import MAX_BODY_BYTES


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > MAX_BODY_BYTES:
                return await JSONResponse({"detail": "请求过大"}, status_code=413)(
                    scope, receive, send
                )
            if not message.get("more_body"):
                break
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


async def invalid_request(request: Request, exc: RequestValidationError):
    # Pydantic's default errors include input values, including raw IPs/passwords.
    return JSONResponse(
        {
            "detail": "请求字段、格式或范围无效",
            "errors": [{"loc": error["loc"], "type": error["type"]} for error in exc.errors()],
        },
        status_code=422,
    )

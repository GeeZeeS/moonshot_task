from __future__ import annotations

import json
from dataclasses import dataclass, field
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings
from app.core.logging import log_event, sanitize_headers, truncate_text


@dataclass
class ResponseLogState:
    preview_limit: int
    status_code: int | None = None
    size: int = 0
    preview: bytearray = field(default_factory=bytearray)

    def append(self, chunk: bytes) -> None:
        self.size += len(chunk)
        if len(self.preview) >= self.preview_limit:
            return

        remaining = self.preview_limit - len(self.preview)
        self.preview.extend(chunk[:remaining])

    def preview_text(self) -> str:
        return self.preview.decode("utf-8", errors="replace")


class RequestResponseLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        body = await self._read_body(receive)
        request_id = self._extract_request_id(headers, body)
        scope.setdefault("state", {})["request_id"] = request_id

        self._log_request(scope, headers, body, request_id)
        response_state = ResponseLogState(preview_limit=settings.log_body_preview_chars)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_state.status_code = int(message["status"])
                _headers = MutableHeaders(scope=message)
                _headers["x-request-id"] = request_id
                await send(message)
                return

            if message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                response_state.append(chunk)

                if not message.get("more_body", False):
                    log_event(
                        "http.response",
                        requestId=request_id,
                        statusCode=response_state.status_code,
                        bodySize=response_state.size,
                        bodyPreview=truncate_text(
                            response_state.preview_text(),
                            response_state.preview_limit,
                        ),
                    )
            await send(message)

        try:
            await self.app(scope, self._replay_body(body), send_wrapper)
        except Exception:
            log_event("http.response", requestId=request_id, statusCode=500)
            raise

    @classmethod
    def _extract_request_id(cls, headers: Headers, body: bytes) -> str:
        request_id = headers.get("x-request-id")
        if request_id:
            return request_id

        try:
            parsed_body = json.loads(body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            parsed_body = {}

        if isinstance(parsed_body, dict):
            body_request_id = parsed_body.get("requestId")
            if isinstance(body_request_id, str) and body_request_id:
                return body_request_id
        return str(uuid4())

    @classmethod
    async def _read_body(cls, receive: Receive) -> bytes:
        chunks = bytearray()
        more_body = True

        while more_body:
            message = await receive()
            if message["type"] != "http.request":
                continue
            chunks.extend(message.get("body", b""))
            more_body = message.get("more_body", False)

        return bytes(chunks)

    @classmethod
    def _replay_body(cls, body: bytes) -> Receive:
        consumed = False

        async def replay_receive() -> Message:
            nonlocal consumed
            if consumed:
                return {"type": "http.request", "body": b"", "more_body": False}

            consumed = True
            return {"type": "http.request", "body": body, "more_body": False}

        return replay_receive

    @classmethod
    def _log_request(
        cls, scope: Scope, headers: Headers, body: bytes, request_id: str
    ) -> None:
        log_event(
            "http.request",
            requestId=request_id,
            method=scope["method"],
            path=scope["path"],
            headers=sanitize_headers(dict(headers.items())),
            bodySize=len(body),
            bodyPreview=truncate_text(
                body.decode("utf-8", errors="replace"),
                settings.log_body_preview_chars,
            ),
        )

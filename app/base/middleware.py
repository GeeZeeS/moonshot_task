from __future__ import annotations

import json
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.base.config import settings
from app.base.logging import log_event, sanitize_headers, truncate_text


class RequestResponseLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        body = await self._read_body(receive)
        headers = Headers(scope=scope)
        request_id = self._extract_request_id(headers, body)
        scope.setdefault("state", {})["request_id"] = request_id

        self._log_request(scope, headers, body, request_id)
        response_state = self._create_response_state()

        async def send_wrapper(message: Message) -> None:
            self._observe_response_message(message, request_id, response_state)
            await send(message)

        try:
            await self.app(scope, self._replay_body(body), send_wrapper)
        except Exception:
            log_event("http.response", requestId=request_id, statusCode=500)
            raise

    async def _read_body(self, receive: Receive) -> bytes:
        chunks = bytearray()
        more_body = True

        while more_body:
            message = await receive()
            if message["type"] != "http.request":
                continue
            chunks.extend(message.get("body", b""))
            more_body = message.get("more_body", False)

        return bytes(chunks)

    def _replay_body(self, body: bytes) -> Receive:
        consumed = False

        async def replay_receive() -> Message:
            nonlocal consumed
            if consumed:
                return {"type": "http.request", "body": b"", "more_body": False}

            consumed = True
            return {"type": "http.request", "body": body, "more_body": False}

        return replay_receive

    def _log_request(
        self, scope: Scope, headers: Headers, body: bytes, request_id: str
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

    def _create_response_state(self) -> dict[str, int | bytearray | None]:
        return {
            "status_code": None,
            "preview_limit": settings.log_body_preview_chars,
            "preview": bytearray(),
            "size": 0,
        }

    def _observe_response_message(
        self,
        message: Message,
        request_id: str,
        response_state: dict[str, int | bytearray | None],
    ) -> None:
        if message["type"] == "http.response.start":
            self._handle_response_start(message, request_id, response_state)
            return

        if message["type"] == "http.response.body":
            self._handle_response_body(message, request_id, response_state)

    def _handle_response_start(
        self,
        message: Message,
        request_id: str,
        response_state: dict[str, int | bytearray | None],
    ) -> None:
        response_state["status_code"] = int(message["status"])
        headers = MutableHeaders(scope=message)
        headers["x-request-id"] = request_id

    def _handle_response_body(
        self,
        message: Message,
        request_id: str,
        response_state: dict[str, int | bytearray | None],
    ) -> None:
        chunk = message.get("body", b"")
        response_state["size"] = int(response_state["size"] or 0) + len(chunk)

        preview = response_state["preview"]
        preview_limit = int(response_state["preview_limit"] or 0)
        if isinstance(preview, bytearray) and len(preview) < preview_limit:
            remaining = preview_limit - len(preview)
            preview.extend(chunk[:remaining])

        if not message.get("more_body", False):
            self._log_response(request_id, response_state)

    def _log_response(
        self, request_id: str, response_state: dict[str, int | bytearray | None]
    ) -> None:
        preview = response_state["preview"]
        preview_text = ""
        if isinstance(preview, bytearray):
            preview_text = preview.decode("utf-8", errors="replace")

        log_event(
            "http.response",
            requestId=request_id,
            statusCode=response_state["status_code"],
            bodySize=response_state["size"],
            bodyPreview=truncate_text(
                preview_text,
                int(response_state["preview_limit"] or 0),
            ),
        )

    def _extract_request_id(self, headers: Headers, body: bytes) -> str:
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

from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.errors import ProxyError
from app.core.middleware import RequestResponseLoggingMiddleware
from app.providers import OpenLigaProvider, SportsProvider
from app.proxy.routers import proxy_router
from app.proxy.schemas import ErrorResponse
from app.proxy.utils.decision_mapper import DecisionMapper


def build_provider() -> SportsProvider:
    if settings.provider_name == "openliga":
        return OpenLigaProvider()
    raise RuntimeError(f"Unsupported provider configuration: {settings.provider_name}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(
    title="Moonshot Proxy",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(RequestResponseLoggingMiddleware)

provider = build_provider()
decision_mapper = DecisionMapper(provider)
app.state.decision_mapper = decision_mapper
app.include_router(proxy_router)


@app.exception_handler(ProxyError)
async def proxy_error_handler(request: Request, exc: ProxyError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or str(uuid4())
    payload = ErrorResponse(
        error=exc.message,
        code=exc.code,
        requestId=request_id,
        details=exc.details,
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or str(uuid4())
    payload = ErrorResponse(
        error="Payload validation failed",
        code="PAYLOAD_VALIDATION_ERROR",
        requestId=request_id,
        details=[error["msg"] for error in exc.errors()],
    )
    return JSONResponse(status_code=400, content=payload.model_dump())

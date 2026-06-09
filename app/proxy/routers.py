from uuid import uuid4

from fastapi import APIRouter, Request

from app.proxy.schemas import ProxyRequest
from app.proxy.utils.decision_mapper import DecisionMapper

proxy_router = APIRouter(
    prefix="/proxy",
)


@proxy_router.post("/execute")
async def execute_proxy(request: Request, proxy_request: ProxyRequest):
    decision_mapper: DecisionMapper = request.app.state.decision_mapper
    request_id = (
        getattr(request.state, "request_id", None)
        or proxy_request.requestId
        or str(uuid4())
    )
    request.state.request_id = request_id
    result = await decision_mapper.execute(
        request_id=request_id,
        operation_type=proxy_request.operationType,
        payload=proxy_request.payload,
    )
    return result

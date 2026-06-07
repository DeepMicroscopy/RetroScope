"""Action routes for hardware commands."""

from __future__ import annotations

from concurrent.futures import TimeoutError as FutureTimeoutError

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from retroscope.api.context import get_api_context
from retroscope.api.models import ActionResponse

router = APIRouter()


@router.post(
    "/actions/autofocus",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_409_CONFLICT: {"model": ActionResponse},
        status.HTTP_504_GATEWAY_TIMEOUT: {"model": ActionResponse},
    },
)
def start_autofocus(request: Request) -> JSONResponse:
    context = get_api_context(request)

    def _start() -> ActionResponse:
        autofocus = context.autofocus_svc
        busy = bool(getattr(autofocus, "busy", False))
        cancelling = bool(getattr(autofocus, "cancelling", False))
        if busy or cancelling:
            return ActionResponse(
                action="autofocus",
                state="busy",
                busy=busy,
                cancelling=cancelling,
                message="Autofocus is already running",
            )

        autofocus.start_autofocus()
        return ActionResponse(
            action="autofocus",
            state="started",
            busy=True,
            cancelling=False,
            message="Autofocus started",
        )

    try:
        result = context.dispatcher.call(_start)
    except FutureTimeoutError:
        result = ActionResponse(
            action="autofocus",
            state="timeout",
            busy=False,
            cancelling=False,
            message="Timed out waiting for the Qt main thread",
        )
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content=jsonable_encoder(result),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    response_status = (
        status.HTTP_202_ACCEPTED
        if result.state == "started"
        else status.HTTP_409_CONFLICT
    )
    return JSONResponse(
        status_code=response_status,
        content=jsonable_encoder(result),
    )

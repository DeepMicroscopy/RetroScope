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


@router.post(
    "/actions/capture",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_409_CONFLICT: {"model": ActionResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ActionResponse},
        status.HTTP_504_GATEWAY_TIMEOUT: {"model": ActionResponse},
    },
)
def trigger_capture(request: Request) -> JSONResponse:
    context = get_api_context(request)

    def _start() -> ActionResponse:
        camera = context.camera_svc
        busy = bool(getattr(camera, "capture_busy", False))
        if busy:
            return ActionResponse(
                action="capture",
                state="busy",
                busy=True,
                cancelling=False,
                message="Capture is already running",
            )

        started = camera.capture_snapshot()
        if started is False:
            busy_now = bool(getattr(camera, "capture_busy", False))
            if not busy_now:
                return ActionResponse(
                    action="capture",
                    state="failed",
                    busy=False,
                    cancelling=False,
                    message="Capture could not be started",
                )
            return ActionResponse(
                action="capture",
                state="busy",
                busy=True,
                cancelling=False,
                message="Capture is already running",
            )
        return ActionResponse(
            action="capture",
            state="started",
            busy=True,
            cancelling=False,
            message="Capture started",
        )

    try:
        result = context.dispatcher.call(_start)
    except FutureTimeoutError:
        result = ActionResponse(
            action="capture",
            state="timeout",
            busy=False,
            cancelling=False,
            message="Timed out",
        )
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content=jsonable_encoder(result),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if result.state == "started":
        response_status = status.HTTP_202_ACCEPTED
    elif result.state == "busy":
        response_status = status.HTTP_409_CONFLICT
    else:
        response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    return JSONResponse(
        status_code=response_status,
        content=jsonable_encoder(result),
    )

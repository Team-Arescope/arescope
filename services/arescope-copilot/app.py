"""Arescope Copilot ASGI application; production binds to loopback only."""

from __future__ import annotations

from contextlib import asynccontextmanager
import hmac
import json
import sqlite3
import time
from typing import Callable, Literal, TypeVar

import anyio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from copilot_core import (
    AUDIO_LIMIT, AUDIO_TYPES, Config, CopilotRouter, JSON_LIMIT, SettingsStore,
    TEXT_LIMIT, UpstreamFailure, VersionConflict, VOICE_PROFILES, normalize_origin,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Settings(StrictModel):
    voice: Literal["male", "female"]
    volume: float = Field(ge=0, le=1)
    hud_enabled: bool
    hud_follow_mode: Literal["hard", "smooth"]


class SettingsUpdate(StrictModel):
    version: int = Field(ge=1)
    settings: Settings


class SettingsAck(StrictModel):
    version: int = Field(ge=1)


class TextRequest(StrictModel):
    text: str = Field(min_length=1, max_length=TEXT_LIMIT)

    @field_validator("text")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text must not be blank.")
        return value


class ChatRequest(TextRequest):
    context: str | None = Field(default=None, max_length=TEXT_LIMIT)


class SpeechRequest(TextRequest):
    voice: Literal["male", "female"]


class OriginGuard:
    """Origin enforcement and Bearer-friendly CORS without buffering SSE."""

    def __init__(self, app, config_provider: Callable[[], Config]):
        self.app = app
        self.config_provider = config_provider

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        origins = [value for key, value in scope["headers"] if key.lower() == b"origin"]
        origin = None
        if origins:
            try:
                if len(origins) != 1:
                    raise ValueError
                origin = origins[0].decode("ascii")
                canonical = normalize_origin(origin)
                if canonical not in self.config_provider().allowed_origins:
                    raise ValueError
            except (ValueError, UnicodeError):
                return await JSONResponse({"detail": "Origin is not allowed."}, status_code=403)(scope, receive, send)
        headers = {key.lower(): value for key, value in scope["headers"]}
        if origin and scope["method"] == "OPTIONS" and b"access-control-request-method" in headers:
            requested_method = headers[b"access-control-request-method"].decode("latin-1").upper()
            requested_headers = {
                value.strip().lower()
                for value in headers.get(b"access-control-request-headers", b"").decode("latin-1").split(",")
                if value.strip()
            }
            if requested_method not in {"GET", "PUT", "POST"} or not requested_headers <= {"authorization", "content-type"}:
                return await JSONResponse({"detail": "CORS request is not allowed."}, status_code=403)(scope, receive, send)
            return await Response(status_code=204, headers={
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "GET, PUT, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Authorization, Content-Type",
                "Access-Control-Max-Age": "600", "Vary": "Origin",
            })(scope, receive, send)

        async def guarded_send(message):
            if message["type"] == "http.response.start":
                message = dict(message)
                response_headers = list(message.get("headers", []))
                response_headers.append((b"cache-control", b"no-store"))
                if origin:
                    response_headers.extend([
                        (b"access-control-allow-origin", origin.encode("ascii")),
                        (b"vary", b"Origin"),
                    ])
                message["headers"] = response_headers
            await send(message)

        await self.app(scope, receive, guarded_send)


async def limited_body(request: Request, limit: int) -> bytes:
    lengths = request.headers.getlist("content-length")
    if lengths:
        try:
            if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
                raise ValueError
            length = int(lengths[0])
        except ValueError:
            raise HTTPException(400, "Invalid Content-Length.") from None
        if length > limit:
            raise HTTPException(413, "Request body is too large.")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > limit:
            raise HTTPException(413, "Request body is too large.")
        body.extend(chunk)
    return bytes(body)


Model = TypeVar("Model", bound=BaseModel)


async def json_body(request: Request, model: type[Model]) -> Model:
    body = await limited_body(request, JSON_LIMIT)
    try:
        return model.model_validate_json(body)
    except ValidationError:
        raise HTTPException(422, "Invalid request fields or JSON.") from None


def authorize(request: Request, role: Literal["panel", "device", "either"]) -> None:
    values = request.headers.getlist("authorization")
    value = values[0] if len(values) == 1 else ""
    scheme, _, token = value.partition(" ")
    supplied = token.encode("utf-8") if scheme.lower() == "bearer" else b""
    config = request.app.state.config
    # Evaluate both comparisons for every request, including role-specific routes.
    panel = hmac.compare_digest(supplied, config.panel_token.encode("utf-8"))
    device = hmac.compare_digest(supplied, config.device_token.encode("utf-8"))
    permitted = panel if role == "panel" else device if role == "device" else panel or device
    if not permitted:
        raise HTTPException(401, "Unauthorized.", headers={"WWW-Authenticate": "Bearer"})


def create_app(
    config: Config | None = None,
    *,
    upstream_transport: httpx.AsyncBaseTransport | None = None,
    clock: Callable[[], float] = time.time,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        runtime_config = Config.from_env() if config is None else config
        runtime_config.validate()
        application.state.config = runtime_config
        store = SettingsStore(runtime_config.settings_db, clock)
        await anyio.to_thread.run_sync(store.initialize)
        application.state.store = store
        async with httpx.AsyncClient(
            transport=upstream_transport, trust_env=False, follow_redirects=False,
        ) as client:
            application.state.router = CopilotRouter(runtime_config, client)
            yield

    application = FastAPI(title="Arescope Copilot", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    application.add_middleware(OriginGuard, config_provider=lambda: application.state.config)

    @application.exception_handler(VersionConflict)
    async def conflict(_request, _error):
        return JSONResponse({"detail": "Settings version conflict; read the current settings and retry."}, status_code=409)

    @application.exception_handler(sqlite3.Error)
    async def storage_error(_request, _error):
        return JSONResponse({"detail": "Settings storage is unavailable."}, status_code=503)

    @application.get("/healthz")
    async def health():
        return {"ok": True}

    @application.get("/api/copilot/status")
    async def status(request: Request):
        authorize(request, "panel")
        return {
            "router_configured": request.app.state.config.router_configured,
            "voice_profiles": VOICE_PROFILES,
            "features": ["llm", "asr", "tts"],
        }

    @application.get("/api/copilot/settings")
    async def get_settings(request: Request):
        authorize(request, "either")
        return await anyio.to_thread.run_sync(request.app.state.store.get)

    @application.put("/api/copilot/settings")
    async def put_settings(request: Request):
        authorize(request, "panel")
        payload = await json_body(request, SettingsUpdate)
        return await anyio.to_thread.run_sync(
            request.app.state.store.update, payload.version, payload.settings.model_dump(),
        )

    @application.post("/api/copilot/settings/ack")
    async def ack_settings(request: Request):
        authorize(request, "device")
        payload = await json_body(request, SettingsAck)
        return await anyio.to_thread.run_sync(request.app.state.store.ack, payload.version)

    @application.post("/api/copilot/transcribe")
    async def transcribe(request: Request):
        authorize(request, "either")
        media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if media_type not in AUDIO_TYPES:
            raise HTTPException(415, "Unsupported audio media type.")
        body = await limited_body(request, AUDIO_LIMIT)
        if not body:
            raise HTTPException(400, "Audio body is empty.")
        try:
            return await request.app.state.router.transcribe(body, media_type)
        except UpstreamFailure:
            raise HTTPException(502, "Transcription is unavailable.") from None

    @application.post("/api/copilot/chat")
    async def chat(request: Request):
        authorize(request, "either")
        payload = await json_body(request, ChatRequest)

        async def events():
            stream = request.app.state.router.chat(payload.text, payload.context)
            try:
                async for event in stream:
                    yield "data: " + json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n\n"
            finally:
                await stream.aclose()

        return StreamingResponse(events(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})

    @application.post("/api/copilot/speech")
    async def speech(request: Request):
        authorize(request, "either")
        payload = await json_body(request, SpeechRequest)
        try:
            audio = await request.app.state.router.speech(payload.text, payload.voice)
        except UpstreamFailure:
            raise HTTPException(502, "Speech synthesis is unavailable.") from None
        return Response(content=audio, media_type="audio/mpeg")

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=18975)

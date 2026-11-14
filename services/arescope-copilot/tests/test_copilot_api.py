"""Contract tests: no live providers, credentials, or external database writes."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
from pathlib import Path
import sqlite3
import stat
import time

from fastapi.testclient import TestClient
import httpx
import pytest

from app import create_app
import copilot_core as core
from copilot_core import (
    AUDIO_LIMIT, ASR_MODEL, CHAT_MODELS, Config, DEFAULT_SETTINGS, JSON_LIMIT,
    SettingsStore, SPEECH_MODEL, TEXT_LIMIT,
)


PANEL = "test-panel-" + "p" * 32
DEVICE = "test-device-" + "d" * 32
KEY = "test-upstream-key"
AUTH = {"panel": {"Authorization": f"Bearer {PANEL}"}, "device": {"Authorization": f"Bearer {DEVICE}"}}


def frame(content=None, *, finish=None, newline="\n") -> bytes:
    delta = {} if content is None else {"content": content}
    payload = {"choices": [{"delta": delta, "finish_reason": finish}]}
    return ("data: " + json.dumps(payload, ensure_ascii=False) + newline + newline).encode("utf-8")


class Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks, delay=0):
        self.chunks = list(chunks)
        self.delay = delay
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            if self.delay:
                await asyncio.sleep(self.delay)
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk

    async def aclose(self):
        self.closed = True


def upstream_sse(chunks):
    stream = chunks if isinstance(chunks, Chunks) else Chunks(chunks)
    return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, stream=stream)


def events(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


class Harness:
    def __init__(self, path):
        self.requests = []
        self.now = 1_000.0
        self.handler = self.default_handler
        self.config = Config(PANEL, DEVICE, KEY, "http://router.test/v1", path)

    def default_handler(self, request):
        if request.url.path.endswith("/audio/transcriptions"):
            return httpx.Response(200, json={"text": "Проверь маршрут."})
        if request.url.path.endswith("/audio/speech"):
            return httpx.Response(200, content=b"ID3mock-mp3", headers={"Content-Type": "audio/mpeg"})
        if request.url.path.endswith("/chat/completions"):
            return upstream_sse([frame("Проверь "), frame("маршрут."), b"data: [DONE]\n\n"])
        raise AssertionError(f"Unexpected upstream route: {request.url}")

    async def dispatch(self, request):
        self.requests.append(request)
        assert request.headers["Authorization"] == f"Bearer {KEY}"
        assert PANEL not in str(request.headers) and DEVICE not in str(request.headers)
        return self.handler(request)

    def app(self, config=None):
        return create_app(
            self.config if config is None else config,
            upstream_transport=httpx.MockTransport(self.dispatch), clock=lambda: self.now,
        )


@pytest.fixture
def harness(tmp_path):
    return Harness(tmp_path / "settings.sqlite3")


@pytest.fixture
def client(harness):
    with TestClient(harness.app()) as test_client:
        yield test_client


def test_health_status_and_removed_endpoint(client, harness):
    assert client.get("/healthz").json() == {"ok": True}
    result = client.get("/api/copilot/status", headers=AUTH["panel"])
    assert result.status_code == 200
    assert result.json() == {
        "router_configured": True,
        "voice_profiles": {"male": "Deep_Voice_Man", "female": "Calm_Woman"},
        "features": ["llm", "asr", "tts"],
    }
    assert KEY not in result.text and PANEL not in result.text and DEVICE not in result.text
    assert result.headers["cache-control"] == "no-store"
    for method in ("GET", "POST", "PUT", "DELETE"):
        assert client.request(method, "/api/copilot/decision").status_code == 404
    assert harness.requests == []


@pytest.mark.parametrize("method,path,payload", [
    ("GET", "/api/copilot/status", None),
    ("GET", "/api/copilot/settings", None),
    ("PUT", "/api/copilot/settings", {"version": 1, "settings": DEFAULT_SETTINGS}),
    ("POST", "/api/copilot/settings/ack", {"version": 1}),
    ("POST", "/api/copilot/transcribe", None),
    ("POST", "/api/copilot/chat", {"text": "Помоги"}),
    ("POST", "/api/copilot/speech", {"text": "Помоги", "voice": "male"}),
])
@pytest.mark.parametrize("authorization", [None, "Basic abc", "Bearer wrong", "Bearer", "Bearer "])
def test_every_protected_route_rejects_missing_or_bad_auth(client, harness, method, path, payload, authorization):
    headers = {} if authorization is None else {"Authorization": authorization}
    response = client.request(method, path, headers=headers, json=payload)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert harness.requests == []


@pytest.mark.parametrize("role", ["panel", "device"])
def test_either_role_routes(client, role):
    headers = AUTH[role]
    assert client.get("/api/copilot/settings", headers=headers).status_code == 200
    assert client.post("/api/copilot/transcribe", headers={**headers, "Content-Type": "audio/wav"}, content=b"RIFF").status_code == 200
    assert events(client.post("/api/copilot/chat", headers=headers, json={"text": "Помоги"}))[-1]["type"] == "complete"
    assert client.post("/api/copilot/speech", headers=headers, json={"text": "Помоги", "voice": "male"}).status_code == 200


def test_role_separation(client, harness):
    assert client.get("/api/copilot/status", headers=AUTH["device"]).status_code == 401
    assert client.put("/api/copilot/settings", headers=AUTH["device"], json={"version": 1, "settings": DEFAULT_SETTINGS}).status_code == 401
    assert client.post("/api/copilot/settings/ack", headers=AUTH["panel"], json={"version": 1}).status_code == 401
    assert harness.requests == []


def test_duplicate_auth_headers_are_rejected(client):
    headers = [("Authorization", f"Bearer {PANEL}"), ("Authorization", f"Bearer {DEVICE}")]
    assert client.get("/api/copilot/settings", headers=headers).status_code == 401


@pytest.mark.parametrize("panel,device", [
    ("", DEVICE), (PANEL, ""), ("a" * 23, DEVICE), (PANEL, "b" * 23),
    (PANEL, PANEL), ("a" * 24 + "\n", DEVICE), ("ю" * 24, DEVICE),
])
def test_invalid_tokens_refuse_startup_before_db_creation(harness, panel, device):
    config = replace(harness.config, panel_token=panel, device_token=device)
    with pytest.raises(ValueError), TestClient(harness.app(config)):
        pass
    assert not config.settings_db.exists()


def test_environment_defaults_and_allowlist(tmp_path):
    env = {"ARESCOPE_COPILOT_TOKEN": PANEL, "ARESCOPE_DEVICE_TOKEN": DEVICE}
    config = Config.from_env(env)
    assert config.router_url == "http://127.0.0.1:20128/v1"
    assert config.settings_db == Path("~/.local/share/arescope-copilot/settings.sqlite3").expanduser()
    assert not config.router_configured
    assert config.allowed_origins == frozenset()
    env.update({
        "ARESCOPE_SETTINGS_DB": str(tmp_path / "custom.sqlite3"),
        "OMNIROUTE_API_KEY": KEY,
        "ARESCOPE_ROUTER_URL": "https://router.test/v1/",
        "ARESCOPE_ALLOWED_ORIGINS": "https://panel.test, http://localhost:3000,",
    })
    config = Config.from_env(env)
    assert config.router_url == "https://router.test/v1"
    assert config.router_configured
    assert config.allowed_origins == {"https://panel.test", "http://localhost:3000"}
    with pytest.raises(ValueError):
        Config.from_env({})


@pytest.mark.parametrize("origin", [
    "*", "null", "file://panel.test", "ftp://panel.test", "https://panel.test/path",
    "https://user:pass@panel.test", "https://panel.test?q=1", "https://panel.test#x",
    "https://panel.test:invalid", "https://panel.test,ftp://evil.test",
])
def test_invalid_origin_config_is_rejected(origin):
    with pytest.raises(ValueError):
        Config.from_env({"ARESCOPE_COPILOT_TOKEN": PANEL, "ARESCOPE_DEVICE_TOKEN": DEVICE, "ARESCOPE_ALLOWED_ORIGINS": origin})


@pytest.mark.parametrize("url", ["", "file:///v1", "http://", "http://user:pass@router/v1", "http://router:bad/v1", "http://router/v1?secret=1"])
def test_invalid_router_url_refuses_startup(harness, url):
    with pytest.raises(ValueError), TestClient(harness.app(replace(harness.config, router_url=url))):
        pass


def test_missing_router_key_keeps_settings_available(harness):
    config = replace(harness.config, router_key="")
    with TestClient(harness.app(config)) as client:
        assert client.get("/api/copilot/status", headers=AUTH["panel"]).json()["router_configured"] is False
        assert client.get("/api/copilot/settings", headers=AUTH["device"]).status_code == 200
        assert client.post("/api/copilot/transcribe", headers={**AUTH["device"], "Content-Type": "audio/wav"}, content=b"RIFF").status_code == 502
        assert client.post("/api/copilot/speech", headers=AUTH["device"], json={"text": "Помоги", "voice": "male"}).status_code == 502
        assert events(client.post("/api/copilot/chat", headers=AUTH["device"], json={"text": "Помоги"}))[0]["type"] == "error"
    assert harness.requests == []


def test_origin_allowlist_and_preflight(harness):
    config = replace(harness.config, allowed_origins=frozenset({"https://panel.test", "http://localhost:3000"}))
    with TestClient(harness.app(config)) as client:
        for origin in ("https://panel.test", "https://PANEL.test:443", "http://localhost:3000"):
            response = client.get("/api/copilot/settings", headers={**AUTH["panel"], "Origin": origin})
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == origin
            assert response.headers["vary"] == "Origin"
        response = client.options("/api/copilot/settings", headers={
            "Origin": "https://panel.test", "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "authorization, content-type",
        })
        assert response.status_code == 204
        assert response.headers["access-control-allow-headers"] == "Authorization, Content-Type"
        assert client.get("/api/copilot/settings", headers=AUTH["panel"]).status_code == 200
        for origin in ("null", "file://panel.test", "http://panel.test", "https://evil.test", "https://panel.test.evil.test", "https://panel.test/path"):
            assert client.get("/healthz", headers={"Origin": origin}).status_code == 403
        assert client.get("/healthz", headers=[("Origin", "https://panel.test"), ("Origin", "https://evil.test")]).status_code == 403
        assert client.options("/api/copilot/settings", headers={"Origin": "https://panel.test", "Access-Control-Request-Method": "DELETE"}).status_code == 403
        assert client.options("/api/copilot/settings", headers={"Origin": "https://panel.test", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "X-Evil"}).status_code == 403
        response = client.get("/api/copilot/status", headers={"Origin": "https://panel.test"})
        assert response.status_code == 401
        assert response.headers["access-control-allow-origin"] == "https://panel.test"


def test_empty_origin_allowlist_rejects_browser(client):
    assert client.get("/healthz", headers={"Origin": "https://panel.test"}).status_code == 403


def test_settings_version_ack_expiry_and_persistence(client, harness):
    initial = client.get("/api/copilot/settings", headers=AUTH["panel"]).json()
    assert initial == {"version": 1, "settings": DEFAULT_SETTINGS, "device_applied": False, "acked_at": None}
    changed = {"voice": "female", "volume": 0.25, "hud_enabled": False, "hud_follow_mode": "hard"}
    payload = {"version": 1, "settings": changed}
    result = client.put("/api/copilot/settings", headers=AUTH["panel"], json=payload)
    assert result.status_code == 200
    assert result.json() == {"version": 2, "settings": changed, "device_applied": False, "acked_at": None}
    assert client.put("/api/copilot/settings", headers=AUTH["panel"], json=payload).status_code == 409
    assert client.post("/api/copilot/settings/ack", headers=AUTH["device"], json={"version": 1}).status_code == 409
    result = client.post("/api/copilot/settings/ack", headers=AUTH["device"], json={"version": 2})
    assert result.json()["device_applied"] is True
    assert result.json()["acked_at"] == 1_000.0
    harness.now += 30
    assert client.get("/api/copilot/settings", headers=AUTH["device"]).json()["device_applied"] is True
    harness.now += 0.001
    expired = client.get("/api/copilot/settings", headers=AUTH["device"]).json()
    assert expired["device_applied"] is False and expired["acked_at"] == 1_000.0
    assert client.post("/api/copilot/settings/ack", headers=AUTH["device"], json={"version": 2}).json()["device_applied"] is True
    with TestClient(harness.app()) as restarted:
        result = restarted.get("/api/copilot/settings", headers=AUTH["panel"]).json()
        assert result["settings"] == changed and result["version"] == 2
        assert result["device_applied"] is True
    result = client.put("/api/copilot/settings", headers=AUTH["panel"], json={"version": 2, "settings": DEFAULT_SETTINGS}).json()
    assert result["version"] == 3 and result["device_applied"] is False and result["acked_at"] is None


def test_ack_does_not_apply_after_clock_moves_backwards(client, harness):
    client.post("/api/copilot/settings/ack", headers=AUTH["device"], json={"version": 1})
    harness.now -= 1
    assert client.get("/api/copilot/settings", headers=AUTH["panel"]).json()["device_applied"] is False


def test_settings_concurrent_writers_have_one_winner(client):
    def write(_):
        return client.put("/api/copilot/settings", headers=AUTH["panel"], json={"version": 1, "settings": DEFAULT_SETTINGS}).status_code

    with ThreadPoolExecutor(max_workers=4) as executor:
        statuses = list(executor.map(write, range(4)))
    assert sorted(statuses) == [200, 409, 409, 409]


@pytest.mark.parametrize("field,value", [
    ("voice", "other"), ("voice", None), ("volume", -0.01), ("volume", 1.01),
    ("volume", "0.5"), ("volume", True), ("hud_enabled", 1),
    ("hud_follow_mode", "other"), ("unexpected", True),
])
def test_settings_reject_invalid_fields(client, field, value):
    settings = {**DEFAULT_SETTINGS, field: value}
    assert client.put("/api/copilot/settings", headers=AUTH["panel"], json={"version": 1, "settings": settings}).status_code == 422


@pytest.mark.parametrize("version", [True, 0, -1, 1.5, "1", None])
def test_settings_versions_are_strict(client, version):
    assert client.put("/api/copilot/settings", headers=AUTH["panel"], json={"version": version, "settings": DEFAULT_SETTINGS}).status_code == 422
    assert client.post("/api/copilot/settings/ack", headers=AUTH["device"], json={"version": version}).status_code == 422


def test_settings_missing_fields_and_nonfinite_volume(client):
    assert client.put("/api/copilot/settings", headers=AUTH["panel"], json={"version": 1, "settings": {"voice": "male"}}).status_code == 422
    assert client.post("/api/copilot/settings/ack", headers=AUTH["device"], json={"version": 1, "extra": 1}).status_code == 422
    body = json.dumps({"version": 1, "settings": {**DEFAULT_SETTINGS, "volume": float("nan")}})
    assert client.put("/api/copilot/settings", headers=AUTH["panel"], content=body).status_code == 422


def test_sqlite_timeout_and_storage_errors(client, harness, monkeypatch):
    original = core.sqlite3.connect
    timeouts = []

    def connect(*args, **kwargs):
        timeouts.append(kwargs.get("timeout"))
        return original(*args, **kwargs)

    monkeypatch.setattr(core.sqlite3, "connect", connect)
    assert client.get("/api/copilot/settings", headers=AUTH["device"]).status_code == 200
    assert timeouts == [5.0]

    def broken_get():
        raise sqlite3.OperationalError("sensitive filesystem location")

    monkeypatch.setattr(client.app.state.store, "get", broken_get)
    result = client.get("/api/copilot/settings", headers=AUTH["device"])
    assert result.status_code == 503 and "sensitive" not in result.text


@pytest.mark.skipif(os.name == "nt", reason="POSIX 0600 permissions are not represented by Windows stat.")
def test_sqlite_private_mode(harness):
    harness.config.settings_db.write_bytes(b"")
    harness.config.settings_db.chmod(0o666)
    store = SettingsStore(harness.config.settings_db)
    store.initialize()
    assert stat.S_IMODE(harness.config.settings_db.stat().st_mode) == 0o600


@pytest.mark.parametrize("media_type", list(core.AUDIO_TYPES))
def test_transcribe_models_multipart_and_media_types(client, harness, media_type):
    audio = b"RIFFmock-audio"
    response = client.post("/api/copilot/transcribe", headers={**AUTH["device"], "Content-Type": media_type + "; charset=binary"}, content=audio)
    assert response.json() == {"text": "Проверь маршрут.", "model": ASR_MODEL}
    request = harness.requests[-1]
    assert request.url.path == "/v1/audio/transcriptions"
    assert request.headers["Content-Type"].startswith("multipart/form-data; boundary=")
    assert ASR_MODEL.encode() in request.content and audio in request.content
    assert core.AUDIO_TYPES[media_type].encode() in request.content
    assert request.extensions["timeout"] == {"connect": 10.0, "read": 60.0, "write": 60.0, "pool": 60.0}


def test_transcribe_request_limits(client, harness):
    endpoint = "/api/copilot/transcribe"
    assert client.post(endpoint, headers=AUTH["device"], content=b"x").status_code == 415
    assert client.post(endpoint, headers={**AUTH["device"], "Content-Type": "application/octet-stream"}, content=b"x").status_code == 415
    headers = {**AUTH["device"], "Content-Type": "audio/wav"}
    assert client.post(endpoint, headers=headers, content=b"").status_code == 400
    assert client.post(endpoint, headers=headers, content=b"x" * (AUDIO_LIMIT + 1)).status_code == 413
    assert client.post(endpoint, headers=headers, content=iter([b"x" * AUDIO_LIMIT, b"x"])).status_code == 413
    assert harness.requests == []
    assert client.post(endpoint, headers=headers, content=b"x" * AUDIO_LIMIT).status_code == 200


@pytest.mark.parametrize("payload", [{"text": ""}, {"text": " \n "}, {"text": "a" * (TEXT_LIMIT + 1)}, {"text": None}, {"text": 1}, [], {}])
def test_transcribe_rejects_bad_upstream_text(client, harness, payload):
    harness.handler = lambda request: httpx.Response(200, json=payload)
    assert client.post("/api/copilot/transcribe", headers={**AUTH["device"], "Content-Type": "audio/wav"}, content=b"RIFF").status_code == 502


@pytest.mark.parametrize("status", [401, 402, 403, 429, 500])
def test_transcribe_upstream_http_errors(client, harness, status):
    harness.handler = lambda request: httpx.Response(status, content=b"sensitive provider error")
    response = client.post("/api/copilot/transcribe", headers={**AUTH["device"], "Content-Type": "audio/wav"}, content=b"RIFF")
    assert response.status_code == 502 and "sensitive" not in response.text


def test_transcribe_output_cap_and_malformed_json(client, harness):
    for body in (b"not JSON", b"\xff", b"x" * (1024 * 1024 + 1)):
        harness.handler = lambda request, body=body: httpx.Response(200, stream=Chunks([body]))
        assert client.post("/api/copilot/transcribe", headers={**AUTH["device"], "Content-Type": "audio/wav"}, content=b"RIFF").status_code == 502
    harness.handler = lambda request: httpx.Response(200, json={"text": "x" * TEXT_LIMIT})
    assert client.post("/api/copilot/transcribe", headers={**AUTH["device"], "Content-Type": "audio/wav"}, content=b"RIFF").status_code == 200


def test_chat_utf8_chunks_crlf_and_rover_operator_prompt(client, harness):
    wire = b": keepalive\r\n\r\n" + frame(newline="\r\n") + frame("Остановись ", newline="\r\n") + frame("и проверь карту.", newline="\r\n") + b"data: [DONE]\r\n\r\n"
    stream = Chunks([bytes([byte]) for byte in wire])
    harness.handler = lambda request: upstream_sse(stream)
    context = "Guardian: warning, wheel_slip; карта низкой уверенности, путь отката не проверен."
    response = client.post("/api/copilot/chat", headers=AUTH["device"], json={"text": "Как восстановить движение ровера?", "context": context})
    result = events(response)
    assert result == [
        {"type": "text", "text": "Остановись ", "model": CHAT_MODELS[0]},
        {"type": "text", "text": "и проверь карту.", "model": CHAT_MODELS[0]},
        {"type": "complete", "text": "Остановись и проверь карту.", "model": CHAT_MODELS[0]},
    ]
    assert response.headers["x-accel-buffering"] == "no" and stream.closed
    payload = json.loads(harness.requests[-1].content)
    assert payload["model"] == CHAT_MODELS[0] and payload["stream"] is True
    assert [message["role"] for message in payload["messages"]] == ["system", "user"]
    assert "1–3" in payload["messages"][0]["content"]
    assert "Никогда не выдумывай" in payload["messages"][0]["content"]
    assert "Безопасность" in payload["messages"][0]["content"]
    prompt = payload["messages"][0]["content"]
    for requirement in ("Mars Rover Mission Control", "полевого инженера", "Guardian", "Slow Loop",
                        "hold-out", "F1", "ложные тревоги", "одобрения оператора",
                        "dust", "glare", "low_texture", "wheel_slip", "sensor_drop",
                        "разреженная атмосфера", "проверки проходимости", "недоверенные данные"):
        assert requirement in prompt
    assert "астронавта" not in prompt
    assert context in payload["messages"][1]["content"]
    assert harness.requests[-1].extensions["timeout"] == {"connect": 10.0, "read": 90.0, "write": 90.0, "pool": 90.0}


def test_chat_falls_back_in_exact_order_only_before_delta(client, harness):
    assert CHAT_MODELS == (
        "agy/gemini-4-hydrogen-low", "cx/gpt-6-luna", "th/muse-ember", "th/glm-5.3-flash",
    )
    def handler(request):
        model = json.loads(request.content)["model"]
        if model == CHAT_MODELS[0]:
            return httpx.Response(503)
        if model == CHAT_MODELS[1]:
            return upstream_sse([frame(), httpx.ReadError("interrupted before text")])
        if model == CHAT_MODELS[2]:
            return upstream_sse([b"data: [DONE]\n\n"])
        return upstream_sse([frame("Проверь связь."), b"data: [DONE]\n\n"])

    harness.handler = handler
    result = events(client.post("/api/copilot/chat", headers=AUTH["device"], json={"text": "Помоги"}))
    assert [json.loads(request.content)["model"] for request in harness.requests] == list(CHAT_MODELS)
    assert [event["type"] for event in result] == ["text", "complete"]
    assert all(event["model"] == CHAT_MODELS[-1] for event in result)


@pytest.mark.parametrize("tail", [
    [], [httpx.ReadError("secret upstream detail")], [b"data: invalid\n\n"],
    [b'data: {"error":{"message":"sensitive"}}\n\n'],
    [frame(finish="length")], [b"data: unfinished"],
])
def test_chat_after_delta_aborts_without_switch_or_complete(client, harness, tail):
    stream = Chunks([frame("Начало."), *tail])
    harness.handler = lambda request: upstream_sse(stream)
    result = events(client.post("/api/copilot/chat", headers=AUTH["device"], json={"text": "Помоги"}))
    assert [event["type"] for event in result] == ["text", "error"]
    assert len(harness.requests) == 1 and stream.closed
    assert "secret" not in json.dumps(result) and "sensitive" not in json.dumps(result)


@pytest.mark.parametrize("status", [401, 402, 403])
def test_chat_auth_and_billing_failures_are_sse_errors(client, harness, status):
    harness.handler = lambda request: httpx.Response(status, content=b"sensitive")
    result = events(client.post("/api/copilot/chat", headers=AUTH["panel"], json={"text": "Помоги"}))
    assert result == [{"type": "error", "message": f"Upstream router returned HTTP {status}."}]
    assert len(harness.requests) == 1


def test_chat_all_models_fail_without_text(client, harness):
    harness.handler = lambda request: httpx.Response(500)
    result = events(client.post("/api/copilot/chat", headers=AUTH["device"], json={"text": "Помоги"}))
    assert result[0]["type"] == "error" and len(result) == 1
    assert len(harness.requests) == len(CHAT_MODELS)


def test_chat_finish_reason_and_usage_frames(client, harness):
    harness.handler = lambda request: upstream_sse([
        b'data: {"choices":[],"usage":{"total_tokens":1}}\n\n',
        frame("Готово."), frame(finish="stop"),
    ])
    result = events(client.post("/api/copilot/chat", headers=AUTH["device"], json={"text": "Помоги"}))
    assert result[-1] == {"type": "complete", "text": "Готово.", "model": CHAT_MODELS[0]}


@pytest.mark.parametrize("chunks", [
    [b"data: " + b"x" * core.SSE_BUFFER_LIMIT],
    [b": comment\n" * 110_000],
    [b": ok\n\n" * 100_000] * 7,
])
def test_chat_enforces_buffer_and_upstream_byte_caps(client, harness, chunks):
    harness.handler = lambda request: upstream_sse([frame("Начало."), *chunks])
    result = events(client.post("/api/copilot/chat", headers=AUTH["device"], json={"text": "Помоги"}))
    assert [event["type"] for event in result] == ["text", "error"]
    assert "limit" in result[-1]["message"]
    assert len(harness.requests) == 1


def test_chat_output_text_limit(client, harness):
    harness.handler = lambda request: upstream_sse([frame("x" * TEXT_LIMIT), frame("x"), b"data: [DONE]\n\n"])
    result = events(client.post("/api/copilot/chat", headers=AUTH["device"], json={"text": "Помоги"}))
    assert [event["type"] for event in result] == ["text", "error"]
    assert len(result[0]["text"]) == TEXT_LIMIT and len(harness.requests) == 1


@pytest.mark.parametrize("chunk", [
    b'data: {"choices":[{"delta":{"content":123}}]}\n\n',
    b'data: {"choices":[null]}\n\n', b'data: {"choices":"bad"}\n\n',
    b'data: {"choices":[{"delta":null}]}\n\n', b'data: [1]\n\n',
    b'data: \xff\n\n',
])
def test_chat_malformed_upstream_can_fallback_before_delta(client, harness, chunk):
    def handler(request):
        if len(harness.requests) == 1:
            return upstream_sse([chunk])
        return upstream_sse([frame("Готово."), b"data: [DONE]\n\n"])

    harness.handler = handler
    result = events(client.post("/api/copilot/chat", headers=AUTH["device"], json={"text": "Помоги"}))
    assert result[-1]["type"] == "complete" and result[-1]["model"] == CHAT_MODELS[1]
    assert len(harness.requests) == 2


def test_chat_wrong_content_type_falls_back_before_delta(client, harness):
    harness.handler = lambda request: httpx.Response(200, json={"choices": []})
    result = events(client.post("/api/copilot/chat", headers=AUTH["device"], json={"text": "Помоги"}))
    assert result == [{"type": "error", "message": "Upstream chat did not return an SSE stream."}]
    assert len(harness.requests) == 4


@pytest.mark.parametrize("payload", [
    {}, {"text": ""}, {"text": " \n "}, {"text": 12}, {"text": True},
    {"text": "x" * (TEXT_LIMIT + 1)}, {"text": "x", "context": "x" * (TEXT_LIMIT + 1)},
    {"text": "x", "context": 123}, {"text": "x", "unexpected": True},
])
def test_chat_input_validation(client, harness, payload):
    assert client.post("/api/copilot/chat", headers=AUTH["device"], json=payload).status_code == 422
    assert harness.requests == []


def test_chat_exact_input_limits(client):
    response = client.post("/api/copilot/chat", headers=AUTH["device"], json={"text": "x" * TEXT_LIMIT, "context": "y" * TEXT_LIMIT})
    assert events(response)[-1]["type"] == "complete"


@pytest.mark.parametrize("voice,upstream_voice", [("male", "Deep_Voice_Man"), ("female", "Calm_Woman")])
def test_speech_voice_model_options_and_audio(client, harness, voice, upstream_voice):
    response = client.post("/api/copilot/speech", headers=AUTH["device"], json={"text": "Проверь связь.", "voice": voice})
    assert response.status_code == 200 and response.content == b"ID3mock-mp3"
    assert response.headers["content-type"] == "audio/mpeg"
    request = harness.requests[-1]
    assert request.url.path == "/v1/audio/speech"
    assert json.loads(request.content) == {
        "model": SPEECH_MODEL, "input": "Проверь связь.", "voice": upstream_voice,
        "response_format": "mp3", "speed": 0.95, "volume": 1, "pitch": 0, "normalization": "basic",
    }
    assert request.extensions["timeout"] == {"connect": 10.0, "read": 90.0, "write": 90.0, "pool": 90.0}


@pytest.mark.parametrize("payload", [
    {}, {"text": "x"}, {"text": "", "voice": "male"}, {"text": " \n ", "voice": "female"},
    {"text": 1, "voice": "male"}, {"text": "x", "voice": "other"},
    {"text": "x" * (TEXT_LIMIT + 1), "voice": "male"}, {"text": "x", "voice": "male", "extra": 1},
])
def test_speech_input_validation(client, harness, payload):
    assert client.post("/api/copilot/speech", headers=AUTH["device"], json=payload).status_code == 422
    assert harness.requests == []


@pytest.mark.parametrize("status,media_type,body", [
    (500, "audio/mpeg", b"failed"), (401, "audio/mpeg", b"failed"),
    (200, "audio/mpeg", b""), (200, "application/json", b'{"error":"failed"}'),
    (200, "audio/mpeg", b"x" * (AUDIO_LIMIT + 1)),
])
def test_speech_upstream_failures(client, harness, status, media_type, body):
    stream = Chunks([body])
    harness.handler = lambda request: httpx.Response(status, headers={"Content-Type": media_type}, stream=stream)
    assert client.post("/api/copilot/speech", headers=AUTH["device"], json={"text": "Помоги", "voice": "male"}).status_code == 502
    assert stream.closed


def test_speech_exact_output_and_text_limits(client, harness):
    audio = b"x" * AUDIO_LIMIT
    harness.handler = lambda request: httpx.Response(200, headers={"Content-Type": "audio/mpeg"}, stream=Chunks([audio]))
    response = client.post("/api/copilot/speech", headers=AUTH["device"], json={"text": "x" * TEXT_LIMIT, "voice": "female"})
    assert response.status_code == 200 and response.content == audio


@pytest.mark.parametrize("path,payload", [
    ("/api/copilot/chat", {"text": "x"}),
    ("/api/copilot/speech", {"text": "x", "voice": "male"}),
    ("/api/copilot/settings/ack", {"version": 1}),
    ("/api/copilot/settings", {"version": 1, "settings": DEFAULT_SETTINGS}),
])
def test_json_body_limits_including_chunked_and_exact_boundary(client, harness, path, payload):
    role = "panel" if path == "/api/copilot/settings" else "device"
    method = "PUT" if path == "/api/copilot/settings" else "POST"
    headers = {**AUTH[role], "Content-Type": "application/json"}
    encoded = json.dumps(payload).encode()
    for content in (b"x" * (JSON_LIMIT + 1), iter([b"x" * JSON_LIMIT, b"x"])):
        assert client.request(method, path, headers=headers, content=content).status_code == 413
    assert harness.requests == []
    response = client.request(method, path, headers=headers, content=encoded + b" " * (JSON_LIMIT - len(encoded)))
    assert response.status_code == 200


@pytest.mark.parametrize("body", [b"", b"not json", b"{", b"[]", b"null", b"\xff"])
def test_invalid_json_is_422(client, body):
    assert client.post("/api/copilot/chat", headers=AUTH["device"], content=body).status_code == 422


@pytest.mark.parametrize("length", ["-1", "not-a-number", "1,1"])
def test_invalid_content_length(client, length):
    assert client.post("/api/copilot/chat", headers={**AUTH["device"], "Content-Length": length}, content=b"{}").status_code == 400


@pytest.mark.parametrize("route", ["transcribe", "speech", "chat"])
def test_upstream_transport_failures(client, harness, route):
    def handler(request):
        raise httpx.ConnectTimeout("sensitive upstream information")

    harness.handler = handler
    if route == "transcribe":
        response = client.post("/api/copilot/transcribe", headers={**AUTH["device"], "Content-Type": "audio/wav"}, content=b"RIFF")
    else:
        payload = {"text": "Помоги"}
        if route == "speech":
            payload["voice"] = "male"
        response = client.post(f"/api/copilot/{route}", headers=AUTH["device"], json=payload)
    if route == "chat":
        assert events(response)[-1]["type"] == "error"
        assert len(harness.requests) == 4
    else:
        assert response.status_code == 502
    assert "sensitive" not in response.text


@pytest.mark.parametrize("route", ["transcribe", "speech", "chat"])
def test_total_deadline_enforced_during_streaming(client, harness, monkeypatch, route):
    timeout_name = {"transcribe": "ASR_TIMEOUT", "speech": "SPEECH_TIMEOUT", "chat": "CHAT_TIMEOUT"}[route]
    monkeypatch.setattr(core, timeout_name, 0.05)
    body = frame("Поздно") if route == "chat" else b"late"
    stream = Chunks([body], delay=0.2)
    media_type = "text/event-stream" if route == "chat" else "audio/mpeg"
    harness.handler = lambda request: httpx.Response(200, headers={"Content-Type": media_type}, stream=stream)
    started = time.monotonic()
    if route == "transcribe":
        response = client.post("/api/copilot/transcribe", headers={**AUTH["device"], "Content-Type": "audio/wav"}, content=b"RIFF")
    else:
        payload = {"text": "Помоги", **({"voice": "male"} if route == "speech" else {})}
        response = client.post(f"/api/copilot/{route}", headers=AUTH["device"], json=payload)
    assert time.monotonic() - started < 1.0
    if route == "chat":
        assert events(response)[-1]["type"] == "error" and len(harness.requests) == 1
    else:
        assert response.status_code == 502
    assert stream.closed

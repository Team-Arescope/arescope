#!/usr/bin/env python3
"""Python 3.11+ production smoke check; run with sudo and the LAB venv Python.

Defaults read /etc/arescope-{lab,copilot}.env. --source-dir is the LAB directory.
--exercise creates/deletes one synthetic session; --ai checks chat, TTS and ASR.
Limits: 240s overall plus bounded cleanup, 15s/request (AI 90s), 128 assets,
8 MiB/asset, 2 MiB/response, 4 MiB/WS message and 64 pushed messages.
Only JSON metadata is printed; environment values are never evaluated.
"""
import argparse
import asyncio
import hashlib
from html.parser import HTMLParser
import json
import logging
from pathlib import Path
import re
import sys
from urllib.parse import quote, unquote, urljoin, urlsplit
import uuid
RESULTS, CURRENT = [], "configuration"

class CheckFailed(Exception):
    pass

def check(name, ok=True, **details):
    global CURRENT
    CURRENT = name
    RESULTS.append(dict(name=name, status="ok" if ok else "fail", **details))
    if not ok:
        raise CheckFailed

def failure(exc):
    if not isinstance(exc, CheckFailed):
        RESULTS.append(dict(name=CURRENT, status="fail", exception=type(exc).__name__))

def read_bounded(path, cap):
    with Path(path).open("rb") as stream:
        data = stream.read(cap + 1)
    if len(data) > cap:
        raise ValueError
    return data

def load_env(path):
    """Single-line KEY=value, optionally fully quoted; no shell/escape expansion."""
    values = {}
    for line in read_bounded(path, 65536).decode("utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        key, separator, value = line.partition("=")
        value = value.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key.strip()) or "\\" in value:
            raise ValueError
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError
            value = value[1:-1]
        values[key.strip()] = value
    return values
class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.references = set()

    def handle_starttag(self, tag, attrs):
        self.references.update(value for key, value in attrs if key in {"src", "href"} and value)

async def run(args):
    global CURRENT
    base = args.base_url.rstrip("/")
    parts = urlsplit(base)
    check("base_configuration", parts.scheme == "https" and bool(parts.hostname) and
          parts.username is None and parts.password is None and not parts.query and
          not parts.fragment and parts.path == "" and not any(c.isspace() for c in base))
    lab, copilot = load_env(args.lab_env), load_env(args.copilot_env)
    producer, viewer = (lab[key] for key in ("ARESCOPE_LIVE_PRODUCER_TOKEN", "ARESCOPE_LIVE_VIEWER_TOKEN"))
    panel, device = (copilot[key] for key in ("ARESCOPE_COPILOT_TOKEN", "ARESCOPE_DEVICE_TOKEN"))
    check("role_configuration", producer != viewer and panel != device and all(
        len(token) >= 24 and all(33 <= ord(c) <= 126 for c in token) for token in (producer, viewer, panel, device)))
    invalid = "invalid-smoke-" + uuid.uuid4().hex
    source = Path(args.source_dir).resolve() if args.source_dir else None
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=10) as client:
        async def http(name, path, token="", method="GET", expected=200, cap=2*1024**2,
                       raw=False, mime=None, seconds=15, **kwargs):
            global CURRENT
            CURRENT = name
            headers = {"Cache-Control": "no-cache", **kwargs.pop("headers", {})}
            if token:
                headers["Authorization"] = "Bearer " + token
            if path.startswith("/api/copilot/"):
                headers.setdefault("Origin", base)
            async with asyncio.timeout(seconds):
                async with client.stream(method, base + path, headers=headers, timeout=seconds, **kwargs) as response:
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(body) + len(chunk) > cap:
                            raise ValueError
                        body.extend(chunk)
                    check(name, response.status_code == expected, http_status=response.status_code, bytes=len(body))
                    if mime:
                        check(name + "_media", response.headers.get("content-type", "").split(";")[0] == mime)
                    if path.startswith("/api/copilot/") and expected == 200:
                        check(name + "_origin", response.headers.get("access-control-allow-origin") == base)
                    return bytes(body) if raw or expected != 200 else json.loads(body)
        def asset(name, body, path):
            digest, mismatch = hashlib.sha256(body).hexdigest(), False
            if source:
                local = (source / unquote(path).lstrip("/")).resolve()
                check(name + "_source_path", local.is_relative_to(source / "static"))
                mismatch = digest != hashlib.sha256(read_bounded(local, 8*1024**2)).hexdigest()
            check(name + "_content", bool(body) and not mismatch, bytes=len(body),
                  sha256=digest, hash_mismatch=mismatch)
        async with asyncio.timeout(240):
            root = await http("root", "/", raw=True, mime="text/html")
            asset("root", root, "/static/index.html")
            page = Assets()
            page.feed(root.decode("utf-8"))
            assets = set()
            for reference in page.references:
                url = urlsplit(urljoin(base + "/", reference))
                if url.path.startswith("/static/"):
                    check("static_origin", (url.scheme, url.netloc) == (parts.scheme, parts.netloc))
                    assets.add(url.path + ("?" + url.query if url.query else ""))
            check("static_inventory", 0 < len(assets) <= 128, count=len(assets))
            for index, path in enumerate(sorted(assets)):
                body = await http(f"asset_{index}", path, raw=True, cap=8*1024**2)
                asset(f"asset_{index}", body, urlsplit(path).path)
            paths = ("/api/live/latest", "/api/live/stats", "/api/guardian/status",
                     "/api/guardian/model", "/api/guardian/incidents")
            for index, path in enumerate(paths):
                for role, token in (("anonymous", ""), ("invalid", invalid), ("producer", producer)):
                    await http(f"lab_denies_{role}_{index}", path, token, expected=401)
            for role, token in (("anonymous", ""), ("invalid", invalid), ("viewer", viewer)):
                await http("lab_write_denies_" + role, "/api/live/frame", token, "POST", expected=401, json={})
            guardian = await http("guardian_status", paths[2], viewer)
            model = await http("guardian_model", paths[3], viewer)
            incidents = await http("guardian_incidents", paths[4] + "?limit=1", viewer)
            stats = await http("storage_before", paths[1], viewer)
            check("guardian_contract", bool(model.get("prototypes")) and bool(model.get("featureNames")) and
                  bool(model.get("modelVersion")) and model["modelVersion"] == guardian.get("modelVersion") and
                  model == guardian.get("activeModel") and isinstance(incidents.get("incidents"), list))
            errors = stats.get("storage_errors")
            check("storage_errors", type(errors) is int and errors == 0)
            for index, path in enumerate(("/api/copilot/status", "/api/copilot/settings")):
                for role, token in (("anonymous", ""), ("invalid", invalid)):
                    await http(f"copilot_denies_{role}_{index}", path, token, expected=401)
            await http("copilot_status_denies_device", "/api/copilot/status", device, expected=401)
            await http("copilot_write_denies_device", "/api/copilot/settings", device, "PUT", expected=401, json={})
            await http("copilot_ack_denies_panel", "/api/copilot/settings/ack", panel, "POST", expected=401, json={})
            await http("copilot_denies_origin", "/api/copilot/settings", panel, expected=403,
                       headers={"Origin": "https://smoke.invalid"})
            status = await http("copilot_status", "/api/copilot/status", panel)
            check("copilot_features", status.get("router_configured") is True and
                  {"llm", "asr", "tts"} <= set(status.get("features", [])))
            for role, token in (("panel", panel), ("device", device)):
                settings = await http("copilot_settings_" + role, "/api/copilot/settings", token)
                check("copilot_settings_contract_" + role, type(settings.get("version")) is int and
                      settings["version"] >= 1 and settings.get("settings", {}).get("voice") in {"male", "female"} and
                      type(settings.get("device_applied")) is bool)
            ws_base = "wss://" + parts.netloc + "/api/live/stream?token="
            for role, token in (("anonymous", ""), ("invalid", invalid), ("producer", producer)):
                CURRENT = "wss_denies_" + role
                async with asyncio.timeout(15):
                    async with connect(ws_base + quote(token, safe=""), proxy=None, open_timeout=10,
                                       close_timeout=2, max_size=4*1024**2, max_queue=4) as ws:
                        try:
                            await ws.recv()
                        except ConnectionClosed as exc:
                            check(CURRENT, exc.rcvd is not None and exc.rcvd.code == 4401)
                        else:
                            check(CURRENT, False)
            CURRENT = "wss_snapshot"
            async with connect(ws_base + quote(viewer, safe=""), proxy=None, open_timeout=10,
                               close_timeout=2, max_size=4*1024**2, max_queue=4) as ws:
                snapshot = json.loads(await asyncio.wait_for(ws.recv(), 10))
                check("wss_snapshot", snapshot.get("source") == "live-quest" and isinstance(snapshot.get("rooms"), list))
                if args.exercise:
                    name, sid = "smoke-" + uuid.uuid4().hex, None
                    points = [[0, 0, 0], [0.1, 0, 0], [0, 0.1, 0]]
                    try:
                        reply = await http("exercise_ingest", "/api/live/frame", producer, "POST", json=dict(
                            room=name, carrierId=name, carrierType="rover", source="simulated-rover", points=points,
                            telemetry=dict(pointCount=1200, fps=30, lumaContrast=0.58, slipRatio=0.03, linkOk=True)))
                        sid = reply.get("sessionId")
                        check("exercise_stored", type(sid) is int and sid > 0 and reply.get("stored") is True)
                        async with asyncio.timeout(10):
                            for _ in range(64):
                                pushed = json.loads(await ws.recv())
                                if pushed.get("carrierId") == name:
                                    check("exercise_push", pushed.get("room") == name and pushed.get("points") == points)
                                    break
                            else:
                                check("exercise_push", False)
                        record = await http("exercise_session", f"/api/live/sessions/{sid}", viewer)
                        check("exercise_owned", record["session"]["room"] == name and
                              record["frame"]["carrierId"] == name and record["frame"]["points"] == points)
                        ply = await http("exercise_ply", f"/api/live/sessions/{sid}/export.ply", viewer, raw=True)
                        check("exercise_ply_content", ply.startswith(b"ply\nformat ascii 1.0\n") and b"element vertex 3\n" in ply)
                    finally:
                        previous = CURRENT
                        try:
                            if type(sid) is not int or sid <= 0:
                                sessions = await http("cleanup_discover", "/api/live/sessions?limit=100", viewer)
                                sid = next((s["id"] for s in sessions["sessions"] if s.get("room") == name), None)
                            if type(sid) is int and sid > 0:
                                record = await http("cleanup_verify", f"/api/live/sessions/{sid}", viewer)
                                check("cleanup_owned", record["session"]["room"] == name and
                                      (record["frame"] is None or record["frame"].get("carrierId") == name))
                                await http("cleanup_delete", f"/api/live/sessions/{sid}", producer, "DELETE")
                                await http("cleanup_absent", f"/api/live/sessions/{sid}", viewer, expected=404)
                        except Exception as exc:
                            failure(exc)
                        CURRENT = previous
            after = await http("storage_after", paths[1], viewer)
            check("storage_no_increase", type(after.get("storage_errors")) is int and after["storage_errors"] == errors)
            if args.ai:
                marker = "smoke-" + uuid.uuid4().hex[:12]
                wire = await http("ai_chat", "/api/copilot/chat", device, "POST", raw=True,
                                  mime="text/event-stream", cap=131072, seconds=90, json=dict(
                                      text="Ответь по-русски одним коротким предложением. Повтори без изменений идентификатор проверки и storage_errors=число из контекста.",
                                      context=f"Синтетическая проверка {marker}; storage_errors={errors}; Guardian={model['modelVersion']}."))
                events = [json.loads(line[5:].strip()) for line in wire.decode("utf-8").splitlines() if line.startswith("data:")]
                text = events[-1].get("text", "") if events else ""
                check("ai_complete", bool(events) and events[-1].get("type") == "complete" and
                      all(e.get("type") == "text" for e in events[:-1]) and 0 < len(text) <= 1000 and
                      text == "".join(e.get("text", "") for e in events[:-1]) and marker in text and
                      f"storage_errors={errors}" in text and bool(re.search("[А-Яа-яЁё]", text)), bytes=len(text.encode("utf-8")))
                audio = await http("ai_tts", "/api/copilot/speech", device, "POST", raw=True,
                                   mime="audio/mpeg", seconds=90, json={"text": text, "voice": "male"})
                check("ai_tts_bytes", len(audio) > 128, bytes=len(audio))
                transcript = await http("ai_asr", "/api/copilot/transcribe", device, "POST", seconds=65,
                                        headers={"Content-Type": "audio/mpeg"}, content=audio)
                check("ai_asr_text", isinstance(transcript.get("text"), str) and
                      bool(transcript["text"].strip()), characters=len(transcript.get("text", "")))
if __name__ == "__main__":
    logging.disable(sys.maxsize)  # Before imports/connections: WS debug logs include credential queries.
    try:
        import httpx
        from websockets.asyncio.client import connect
        from websockets.exceptions import ConnectionClosed
        parser = argparse.ArgumentParser(description=__doc__)
        parser.error = lambda message: (_ for _ in ()).throw(ValueError())
        parser.add_argument("--lab-env", default="/etc/arescope-lab.env")
        parser.add_argument("--copilot-env", default="/etc/arescope-copilot.env")
        parser.add_argument("--base-url", default="https://arescope.mrfenek.eu.cc")
        parser.add_argument("--source-dir")
        parser.add_argument("--exercise", action="store_true")
        parser.add_argument("--ai", action="store_true")
        asyncio.run(run(parser.parse_args()))
    except (Exception, KeyboardInterrupt) as exc:
        failure(exc)
    print(json.dumps(dict(ok=all(r["status"] == "ok" for r in RESULTS), results=RESULTS), separators=(",", ":")))
    sys.exit(0 if RESULTS and all(r["status"] == "ok" for r in RESULTS) else 1)

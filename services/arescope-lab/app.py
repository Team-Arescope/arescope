"""Arescope LAB: one Uvicorn worker owns the live fanout and session cache."""

import asyncio
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import gzip
import hmac
import json
import logging
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
import time
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from arsm import InvalidMesh, parse_arsm

ROOT = Path(__file__).resolve().parent
LIVE_TTL_SECONDS = 30
WS_IDLE_SECONDS = 20
WS_QUEUE_SIZE = 32


class StreamQueryFilter(logging.Filter):
    """Uvicorn logs WebSocket handshakes on its error logger, even without access logs."""

    def filter(self, record):
        message = record.getMessage()
        record.msg = re.sub(r"(/api/live/stream)\?[^\s\"']+", r"\1?[redacted]", message)
        record.args = ()
        return True


for _logger in ("uvicorn.access", "uvicorn.error"):
    logging.getLogger(_logger).addFilter(StreamQueryFilter())


@dataclass
class Settings:
    producer_token: str = field(default_factory=lambda: os.getenv("ARESCOPE_LIVE_PRODUCER_TOKEN", ""))
    viewer_token: str = field(default_factory=lambda: os.getenv("ARESCOPE_LIVE_VIEWER_TOKEN", ""))
    db: Path = field(default_factory=lambda: Path(os.getenv("ARESCOPE_LIVE_DB", "/var/lib/arescope-lab/live.sqlite3")))
    mesh_dir: Path = field(default_factory=lambda: Path(os.getenv("ARESCOPE_MESH_DIR", "/var/lib/arescope-lab/meshes")))
    log_dir: Path = field(default_factory=lambda: Path(os.getenv("ARESCOPE_LOG_DIR", "/var/lib/arescope-lab/logs")))
    session_gap: float = field(default_factory=lambda: float(os.getenv("ARESCOPE_SESSION_GAP", "60")))
    retention_days: float = field(default_factory=lambda: float(os.getenv("ARESCOPE_RETENTION_DAYS", "7")))
    max_db_bytes: int = field(default_factory=lambda: int(os.getenv("ARESCOPE_MAX_DB_BYTES", "209715200")))
    min_history_interval: float = field(default_factory=lambda: float(os.getenv("ARESCOPE_MIN_HISTORY_INTERVAL", "0.25")))
    max_frames_per_session: int = field(default_factory=lambda: int(os.getenv("ARESCOPE_MAX_FRAMES_PER_SESSION", "2000")))
    max_export_points: int = field(default_factory=lambda: min(400_000, int(os.getenv("ARESCOPE_MAX_EXPORT_POINTS", "400000"))))
    max_mesh_bytes: int = field(default_factory=lambda: int(os.getenv("ARESCOPE_MAX_MESH_BYTES", "33554432")))
    max_log_bytes: int = field(default_factory=lambda: int(os.getenv("ARESCOPE_MAX_LOG_BYTES", "8388608")))

    def check(self):
        if not self.producer_token.strip() or not self.viewer_token.strip():
            raise ValueError("Producer and viewer tokens must both be configured")
        if hmac.compare_digest(self.producer_token.encode(), self.viewer_token.encode()):
            raise ValueError("Producer and viewer tokens must be distinct")
        for name in ("session_gap", "retention_days", "max_db_bytes", "max_frames_per_session",
                     "max_export_points", "max_mesh_bytes", "max_log_bytes"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite")
        if not math.isfinite(self.min_history_interval) or self.min_history_interval < 0:
            raise ValueError("min_history_interval must be nonnegative and finite")


def token_matches(actual: str, expected: str) -> bool:
    # Bytes also support non-ASCII secrets without compare_digest's str restriction.
    return bool(expected.strip() and actual) and hmac.compare_digest(actual.encode(), expected.encode())


def summary(row):
    return {"id": row["id"], "room": row["room"], "startedAt": row["started_at"],
            "endedAt": row["ended_at"], "frameCount": row["frame_count"],
            "maxPoints": row["max_points"], "hasMesh": bool(row["has_mesh"]),
            "meshBytes": row["mesh_bytes"]}


class Store:
    def __init__(self, settings):
        self.settings = settings
        self.lock = threading.RLock()
        self.rooms = {}
        self.last_prune = None

    @contextmanager
    def connect(self):
        self.settings.db.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.settings.db, timeout=0.5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with conn:
                self.ensure_schema(conn)
                yield conn
        finally:
            conn.close()

    @staticmethod
    def ensure_schema(db):
        db.execute("""CREATE TABLE IF NOT EXISTS sessions(
            id INTEGER PRIMARY KEY AUTOINCREMENT, room TEXT NOT NULL,
            started_at REAL NOT NULL, ended_at REAL NOT NULL,
            frame_count INTEGER NOT NULL DEFAULT 0, max_points INTEGER NOT NULL DEFAULT 0,
            has_mesh INTEGER NOT NULL DEFAULT 0, mesh_bytes INTEGER NOT NULL DEFAULT 0)""")
        db.execute("""CREATE TABLE IF NOT EXISTS frames(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            received_at REAL NOT NULL, yaw REAL, point_count INTEGER NOT NULL, payload BLOB NOT NULL)""")
        db.execute("CREATE INDEX IF NOT EXISTS frames_session_received ON frames(session_id, received_at)")
        db.execute("CREATE INDEX IF NOT EXISTS sessions_started ON sessions(started_at DESC)")

    def prune(self, db, now, force=False):
        if not force and self.last_prune is not None and now - self.last_prune < 3600:
            return
        db.execute("DELETE FROM sessions WHERE started_at < ?", (now - self.settings.retention_days * 86400,))
        total = db.execute("SELECT COALESCE(SUM(length(payload)),0) FROM frames").fetchone()[0]
        oldest = db.execute("""SELECT s.id, COALESCE(SUM(length(f.payload)),0) AS bytes
            FROM sessions s LEFT JOIN frames f ON f.session_id=s.id
            GROUP BY s.id ORDER BY s.started_at, s.id""").fetchall()
        for row in oldest:
            if total <= self.settings.max_db_bytes:
                break
            db.execute("DELETE FROM sessions WHERE id=?", (row["id"],))
            total -= row["bytes"]
        # Set only after the enclosing transaction commits (see append).

    def append(self, frame):
        now, room = frame["receivedAt"], frame["room"]
        with self.lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cached = self.rooms.get(room)
            row = None
            if cached and now - cached[1] <= self.settings.session_gap:
                row = db.execute("SELECT * FROM sessions WHERE id=?", (cached[0],)).fetchone()
            if row is None:
                sid = db.execute("INSERT INTO sessions(room,started_at,ended_at) VALUES(?,?,?)",
                                 (room, now, now)).lastrowid
                count, last_stored = 0, float("-inf")
            else:
                sid, count, last_stored = row["id"], row["frame_count"], cached[2]
            throttled = now - last_stored < self.settings.min_history_interval
            stored = count < self.settings.max_frames_per_session and not throttled
            if stored:
                payload = gzip.compress(json.dumps(frame["points"], separators=(",", ":"), allow_nan=False).encode(), compresslevel=6)
                db.execute("INSERT INTO frames(session_id,received_at,yaw,point_count,payload) VALUES(?,?,?,?,?)",
                           (sid, now, frame["yawDeg"], frame["pointCount"], payload))
                db.execute("UPDATE sessions SET ended_at=?, frame_count=frame_count+1, max_points=MAX(max_points,?) WHERE id=?",
                           (now, frame["pointCount"], sid))
                last_stored = now
            due = self.last_prune is None or now - self.last_prune >= 3600
            self.prune(db, now)
            db.commit()
            self.rooms[room] = (sid, now, last_stored)
            if due:
                self.last_prune = now
            return sid, stored, throttled

    def list_sessions(self, limit):
        with self.lock, self.connect() as db:
            rows = db.execute("SELECT * FROM sessions ORDER BY started_at DESC,id DESC LIMIT ?", (limit,)).fetchall()
            total = db.execute("SELECT count(*) FROM sessions").fetchone()[0]
            size = db.execute("SELECT COALESCE(SUM(length(payload)),0) FROM frames").fetchone()[0]
            return {"sessions": [summary(r) for r in rows], "total": total, "storedBytes": size,
                    "retentionDays": self.settings.retention_days, "maxBytes": self.settings.max_db_bytes}

    def session(self, sid):
        with self.lock, self.connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
            if row is None:
                raise HTTPException(404, "Session not found")
            f = db.execute("SELECT * FROM frames WHERE session_id=? ORDER BY received_at DESC,id DESC LIMIT 1", (sid,)).fetchone()
            frame = None if f is None else {"source": "archived-quest", "room": row["room"], "sessionId": sid,
                "receivedAt": f["received_at"], "yawDeg": f["yaw"], "pointCount": f["point_count"],
                "points": json.loads(gzip.decompress(f["payload"]))}
            return {"session": summary(row), "frame": frame}

    def delete(self, sid):
        with self.lock, self.connect() as db:
            if not db.execute("DELETE FROM sessions WHERE id=?", (sid,)).rowcount:
                raise HTTPException(404, "Session not found")
            db.commit()
            for room, cached in list(self.rooms.items()):
                if cached[0] == sid:
                    del self.rooms[room]
            # Mesh files and logs have a separate ops retention policy.
            (self.settings.mesh_dir / f"{sid}.arsm").unlink(missing_ok=True)

    def stats(self):
        with self.lock, self.connect() as db:
            sessions = db.execute("SELECT count(*) FROM sessions").fetchone()[0]
            frames, payload = db.execute("SELECT count(*), COALESCE(SUM(length(payload)),0) FROM frames").fetchone()
            pages = db.execute("PRAGMA page_count").fetchone()[0]
            page_size = db.execute("PRAGMA page_size").fetchone()[0]
            return {"dbBytes": pages * page_size, "payloadBytes": payload, "sessionCount": sessions, "frameCount": frames}

    def ply(self, sid, mode):
        with self.lock, self.connect() as db:
            if db.execute("SELECT id FROM sessions WHERE id=?", (sid,)).fetchone() is None:
                raise HTTPException(404, "Session not found")
            sql = "SELECT payload FROM frames WHERE session_id=? ORDER BY received_at DESC,id DESC"
            rows = db.execute(sql + (" LIMIT 1" if mode == "last" else ""), (sid,))
            points, seen = [], set()
            for row in rows:
                for point in json.loads(gzip.decompress(row[0])):
                    cell = tuple(round(v, 2) for v in point)
                    if mode == "merged" and cell in seen:
                        continue
                    seen.add(cell)
                    points.append(point)
                    if len(points) >= self.settings.max_export_points:
                        break
                if len(points) >= self.settings.max_export_points:
                    break
        header = f"ply\nformat ascii 1.0\nelement vertex {len(points)}\nproperty float x\nproperty float y\nproperty float z\nend_header\n"
        return (header + "".join(" ".join(format(x, ".9g") for x in p) + "\n" for p in points)).encode("ascii")

    def save_mesh(self, sid, body):
        with self.lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT id FROM sessions WHERE id=?", (sid,)).fetchone() is None:
                raise HTTPException(404, "Session not found")
            directory = self.settings.mesh_dir
            directory.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix=f".{sid}-", dir=directory)
            try:
                with os.fdopen(fd, "wb") as file:
                    file.write(body)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(name, directory / f"{sid}.arsm")
                db.execute("UPDATE sessions SET has_mesh=1,mesh_bytes=? WHERE id=?", (len(body), sid))
            finally:
                Path(name).unlink(missing_ok=True)


class LiveState:
    def __init__(self):
        self.frames = {}
        self.subscribers = set()
        self.ingest = 0
        self.storage_errors = 0

    def snapshot(self, now):
        for room, frame in list(self.frames.items()):
            if now - frame["receivedAt"] > LIVE_TTL_SECONDS:
                del self.frames[room]
        return {"source": "live-quest", "rooms": list(self.frames.values())}

    def broadcast(self, frame):
        for queue in tuple(self.subscribers):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(frame)


async def read_limited(request, maximum):
    length = request.headers.get("content-length")
    if length:
        try:
            if int(length) > maximum:
                raise HTTPException(413, "Body exceeds size limit")
        except ValueError:
            raise HTTPException(422, "Invalid content length") from None
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > maximum:
            raise HTTPException(413, "Body exceeds size limit")
        body.extend(chunk)
    return bytes(body)


def validate_frame(body):
    try:
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError
        points = data["points"]
        if not isinstance(points, list) or len(points) > 4096:
            raise ValueError
        for p in points:
            if not isinstance(p, list) or len(p) != 3 or any(
                isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in p
            ):
                raise ValueError
        room = data.get("room") or "default"
        if not isinstance(room, str):
            raise ValueError
        yaw = data.get("yawDeg")
        if yaw is not None and (isinstance(yaw, bool) or not isinstance(yaw, (int, float)) or not math.isfinite(yaw)):
            raise ValueError
        return room[:64], yaw, points
    except (ValueError, KeyError, TypeError, OverflowError, RecursionError):
        raise HTTPException(422, "Expected room, optional yawDeg and at most 4096 finite xyz points") from None


def create_app(settings=None, clock=time.time):
    cfg = settings or Settings()
    store, live = Store(cfg), LiveState()

    @asynccontextmanager
    async def lifespan(application):
        cfg.check()
        try:
            await run_in_threadpool(store.stats)
        except (sqlite3.Error, OSError):
            live.storage_errors += 1
        yield

    app = FastAPI(title="Arescope LAB", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings, app.state.store, app.state.live = cfg, store, live

    def auth(expected_role):
        def dependency(request: Request):
            scheme, _, token = request.headers.get("authorization", "").partition(" ")
            expected = cfg.producer_token if expected_role == "producer" else cfg.viewer_token
            distinct = not (cfg.producer_token and cfg.viewer_token and
                            hmac.compare_digest(cfg.producer_token.encode(), cfg.viewer_token.encode()))
            if scheme.lower() != "bearer" or not distinct or not token_matches(token, expected):
                raise HTTPException(401, "Unauthorized", headers={"WWW-Authenticate": "Bearer"})
        return dependency

    producer, viewer = auth("producer"), auth("viewer")

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; "
            "img-src 'self' blob: data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(sqlite3.Error)
    @app.exception_handler(OSError)
    async def storage_unavailable(request, exc):
        live.storage_errors += 1
        return Response('{"detail":"Storage temporarily unavailable"}', status_code=503, media_type="application/json")

    @app.get("/healthz")
    def health():
        return {"ok": True, "service": "arescope-lab"}

    @app.get("/")
    def index():
        return FileResponse(ROOT / "static/index.html", headers={"Cache-Control": "no-cache"})

    @app.post("/api/live/frame", dependencies=[Depends(producer)])
    async def frame(request: Request):
        room, yaw, points = validate_frame(await read_limited(request, 2 * 1024 * 1024))
        now = clock()
        current = {"source": "live-quest", "room": room, "yawDeg": yaw, "points": points,
                   "pointCount": len(points), "receivedAt": now}
        live.ingest += 1
        # Publish before touching disk: a locked/failed DB cannot hold up viewers.
        live.snapshot(now)
        live.frames[room] = current
        live.broadcast(current)
        sid, stored, throttled = None, False, False
        try:
            sid, stored, throttled = await run_in_threadpool(store.append, current)
        except (sqlite3.Error, OSError):
            live.storage_errors += 1
        return {"ok": True, "room": room, "pointCount": len(points), "viewers": len(live.subscribers),
                "sessionId": sid, "stored": stored, "throttled": throttled}

    @app.get("/api/live/latest", dependencies=[Depends(viewer)])
    def latest():
        return live.snapshot(clock())

    @app.websocket("/api/live/stream")
    async def stream(ws: WebSocket):
        distinct = not hmac.compare_digest(cfg.producer_token.encode(), cfg.viewer_token.encode())
        if not distinct or not token_matches(ws.query_params.get("token", ""), cfg.viewer_token):
            # Complete the upgrade so real browsers receive the custom 4401 code;
            # closing before accept would become an HTTP 403 handshake response.
            await ws.accept()
            await ws.close(code=4401)
            return
        await ws.accept()
        queue = asyncio.Queue(maxsize=WS_QUEUE_SIZE)
        live.subscribers.add(queue)

        async def send():
            await ws.send_json(live.snapshot(clock()))
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), WS_IDLE_SECONDS)
                except asyncio.TimeoutError:
                    live.snapshot(clock())
                    message = {"type": "ping", "at": clock()}
                await ws.send_json(message)

        async def receive():
            while True:
                if (await ws.receive())["type"] == "websocket.disconnect":
                    return

        tasks = [asyncio.create_task(send()), asyncio.create_task(receive())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            live.subscribers.discard(queue)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    @app.get("/api/live/sessions", dependencies=[Depends(viewer)])
    def sessions(limit: int = 20):
        return store.list_sessions(max(1, min(limit, 100)))

    @app.get("/api/live/sessions/{id}", dependencies=[Depends(viewer)])
    def session(id: int):
        return store.session(id)

    @app.delete("/api/live/sessions/{id}", dependencies=[Depends(producer)])
    def delete_session(id: int):
        store.delete(id)
        return {"ok": True, "deleted": id}

    @app.get("/api/live/stats", dependencies=[Depends(viewer)])
    def stats():
        return {**store.stats(), "retentionDays": cfg.retention_days, "maxBytes": cfg.max_db_bytes,
                "sessionGap": cfg.session_gap, "minHistoryInterval": cfg.min_history_interval,
                "maxFramesPerSession": cfg.max_frames_per_session, "maxExportPoints": cfg.max_export_points,
                "maxMeshBytes": cfg.max_mesh_bytes, "maxLogBytes": cfg.max_log_bytes,
                "liveTtlSeconds": LIVE_TTL_SECONDS, "ingest": live.ingest, "storage_errors": live.storage_errors,
                "activeRooms": [f["room"] for f in live.snapshot(clock())["rooms"]]}

    @app.get("/api/live/sessions/{id}/export.ply", dependencies=[Depends(viewer)])
    def export(id: int, frame: Literal["merged", "last"] = "merged"):
        return Response(store.ply(id, frame), media_type="application/octet-stream",
                        headers={"Content-Disposition": f'attachment; filename="arescope-{id}-{frame}.ply"'})

    @app.post("/api/live/mesh", dependencies=[Depends(producer)])
    async def upload_mesh(request: Request, session: int = Query(...)):
        body = await read_limited(request, cfg.max_mesh_bytes)
        try:
            info = await run_in_threadpool(parse_arsm, body)
        except InvalidMesh as exc:
            raise HTTPException(422, str(exc)) from None
        await run_in_threadpool(store.save_mesh, session, body)
        return {"ok": True, "sessionId": session, "bytes": len(body), "version": info.version,
                "vertexCount": info.vertex_count, "indexCount": info.index_count}

    @app.get("/api/live/sessions/{id}/mesh", dependencies=[Depends(viewer)])
    def mesh(id: int):
        record = store.session(id)["session"]
        path = cfg.mesh_dir / f"{id}.arsm"
        if not record["hasMesh"] or not path.is_file() or path.is_symlink():
            raise HTTPException(404, "Mesh not found")
        return FileResponse(path, media_type="application/octet-stream", filename=f"{id}.arsm")

    @app.post("/api/live/log", dependencies=[Depends(producer)])
    async def upload_log(request: Request, source: str = "device"):
        body = await read_limited(request, cfg.max_log_bytes)
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(422, "Log must be UTF-8") from None
        if not text.strip():
            raise HTTPException(422, "Log must not be empty")
        source = re.sub(r"[^A-Za-z0-9_-]", "", source)[:40] or "device"

        def save_log():
            cfg.log_dir.mkdir(parents=True, exist_ok=True)
            at = datetime.fromtimestamp(clock(), timezone.utc)
            # Preserve the wire filename format and avoid overwriting same-second uploads.
            while True:
                filename = f'{at:%Y%m%d-%H%M%S}-{source}.log'
                try:
                    with (cfg.log_dir / filename).open("xb") as file:
                        file.write(body)
                    return filename
                except FileExistsError:
                    at += timedelta(seconds=1)

        filename = await run_in_threadpool(save_log)
        return {"ok": True, "file": filename, "bytes": len(body)}

    @app.get("/api/live/logs", dependencies=[Depends(viewer)])
    def logs(limit: int = 20):
        files = sorted((p for p in cfg.log_dir.glob("*.log") if p.is_file() and not p.is_symlink()),
                       key=lambda p: p.name, reverse=True)
        result = []
        for path in files:
            if not re.fullmatch(r"\d{8}-\d{6}-[A-Za-z0-9_-]{1,40}\.log", path.name):
                continue
            try:
                at = datetime.strptime(path.name[:15], "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
                size = path.stat().st_size
            except (ValueError, FileNotFoundError):
                continue
            result.append({"file": path.name, "bytes": size, "at": at.isoformat()})
            if len(result) >= max(1, min(limit, 200)):
                break
        return {"logs": result}

    @app.get("/api/live/logs/{filename}", dependencies=[Depends(viewer)])
    def log(filename: str):
        if not re.fullmatch(r"\d{8}-\d{6}-[A-Za-z0-9_-]{1,40}\.log", filename):
            raise HTTPException(404, "Log not found")
        path = cfg.log_dir / filename
        if not path.is_file() or path.is_symlink():
            raise HTTPException(404, "Log not found")
        return FileResponse(path, media_type="text/plain", headers={"Cache-Control": "no-store"})

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return app


app = create_app()
LIVE_FRAMES = app.state.live.frames

if __name__ == "__main__":
    import sys
    if "--check-config" in sys.argv:
        Settings().check()
        print("Configuration valid; producer and viewer roles are distinct")
    else:
        import uvicorn
        uvicorn.run("app:app", host="127.0.0.1", port=18965, workers=1)

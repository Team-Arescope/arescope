"""Legacy SQLite migration contracts using only temporary, local databases."""

from __future__ import annotations

from contextlib import closing
import json
import sqlite3

import pytest

import copilot_core as core
from copilot_core import DEFAULT_SETTINGS, SettingsStore, VersionConflict


CUSTOM_SETTINGS = {
    "voice": "female",
    "volume": 0.25,
    "hud_enabled": False,
    "hud_follow_mode": "hard",
}


def create_legacy(path, *, version=0, payload=json.dumps(DEFAULT_SETTINGS)):
    with closing(sqlite3.connect(path)) as db:
        db.execute(
            """CREATE TABLE settings (
                id INTEGER PRIMARY KEY,
                version INTEGER NOT NULL,
                payload TEXT NOT NULL
            )"""
        )
        db.execute(
            "INSERT INTO settings (id, version, payload) VALUES (1, ?, ?)",
            (version, payload),
        )
        db.commit()


def database_state(path):
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        return list(db.iterdump()), db.execute("PRAGMA table_info(settings)").fetchall()


@pytest.mark.parametrize("version", [0, 23, 2**63 - 1])
@pytest.mark.parametrize("settings", [DEFAULT_SETTINGS, CUSTOM_SETTINGS])
def test_legacy_migration_preserves_settings_and_version_on_reinitialize(tmp_path, version, settings):
    path = tmp_path / "settings.sqlite3"
    create_legacy(path, version=version, payload=json.dumps(settings))
    store = SettingsStore(path)
    expected = {
        "version": max(1, version), "settings": settings,
        "device_applied": False, "acked_at": None,
    }

    store.initialize()
    assert store.get() == expected
    with closing(sqlite3.connect(path)) as db:
        assert [row[1] for row in db.execute("PRAGMA table_info(settings)")] == [
            "id", "version", "voice", "volume", "hud_enabled", "hud_follow_mode",
            "ack_version", "acked_at",
        ]
        assert db.execute("SELECT ack_version, acked_at FROM settings").fetchall() == [(None, None)]
        assert db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall() == [("settings",)]
    state = database_state(path)

    store.initialize()
    assert store.get() == expected
    restarted = SettingsStore(path)
    restarted.initialize()
    assert restarted.get() == expected
    assert database_state(path) == state


@pytest.mark.parametrize("volume", [0, 1])
def test_legacy_migration_accepts_integer_volume_boundaries(tmp_path, volume):
    path = tmp_path / "settings.sqlite3"
    settings = {**CUSTOM_SETTINGS, "volume": volume}
    create_legacy(path, payload=json.dumps(settings))
    store = SettingsStore(path)
    store.initialize()
    assert store.get()["settings"] == settings


@pytest.mark.parametrize("version", [0, 23])
def test_migrated_store_supports_updates_acknowledgments_and_restarts(tmp_path, version):
    path = tmp_path / "settings.sqlite3"
    create_legacy(path, version=version)
    store = SettingsStore(path, clock=lambda: 1_000.0)
    store.initialize()
    version = max(1, version)

    with pytest.raises(VersionConflict):
        store.ack(version - 1)
    with pytest.raises(VersionConflict):
        store.update(version - 1, CUSTOM_SETTINGS)
    updated = store.update(version, CUSTOM_SETTINGS)
    assert updated == {
        "version": version + 1, "settings": CUSTOM_SETTINGS,
        "device_applied": False, "acked_at": None,
    }
    acknowledged = store.ack(version + 1)
    assert acknowledged == {**updated, "device_applied": True, "acked_at": 1_000.0}

    store.initialize()
    assert store.get() == acknowledged
    restarted = SettingsStore(path, clock=lambda: 1_000.0)
    restarted.initialize()
    assert restarted.get() == acknowledged
    reset_ack = restarted.update(version + 1, DEFAULT_SETTINGS)
    assert reset_ack == {
        "version": version + 2, "settings": DEFAULT_SETTINGS,
        "device_applied": False, "acked_at": None,
    }


INVALID_FIELDS = [
    ("voice", value) for value in ("other", None, True, 1, [], {})
] + [
    ("volume", value) for value in (
        -0.01, 1.01, "0.5", True, False, None, [], {},
        float("nan"), float("inf"), float("-inf"),
    )
] + [
    ("hud_enabled", value) for value in (0, 1, "true", None, [], {})
] + [
    ("hud_follow_mode", value) for value in ("other", None, True, 1, [], {})
]
INVALID_PAYLOADS = [
    "", "{", "null", "[]", "true", "1", '"settings"', "{}",
    json.dumps({**DEFAULT_SETTINGS, "unexpected": True}),
    '{"voice":"female","voice":"male","volume":1.0,"hud_enabled":true,"hud_follow_mode":"smooth"}',
    json.dumps(DEFAULT_SETTINGS).encode(),
] + [
    json.dumps({key: value for key, value in DEFAULT_SETTINGS.items() if key != missing})
    for missing in DEFAULT_SETTINGS
] + [
    json.dumps({**DEFAULT_SETTINGS, field: value}) for field, value in INVALID_FIELDS
]


@pytest.mark.parametrize("payload", INVALID_PAYLOADS)
def test_malformed_legacy_payload_leaves_database_and_schema_untouched(tmp_path, payload):
    path = tmp_path / "settings.sqlite3"
    create_legacy(path, version=23, payload=payload)
    state = database_state(path)
    contents = path.read_bytes()

    for _ in range(2):
        with pytest.raises(ValueError):
            SettingsStore(path).initialize()
        assert database_state(path) == state
        assert path.read_bytes() == contents


@pytest.mark.parametrize("version", [-1, 0.5, "invalid"])
def test_invalid_legacy_version_leaves_database_untouched(tmp_path, version):
    path = tmp_path / "settings.sqlite3"
    create_legacy(path, version=version)
    state = database_state(path)
    contents = path.read_bytes()
    with pytest.raises(ValueError, match="version"):
        SettingsStore(path).initialize()
    assert database_state(path) == state
    assert path.read_bytes() == contents


@pytest.mark.parametrize("row_ids", [[], [2], [1, 2]])
def test_invalid_legacy_rows_leave_database_untouched(tmp_path, row_ids):
    path = tmp_path / "settings.sqlite3"
    create_legacy(path)
    with closing(sqlite3.connect(path)) as db:
        db.execute("DELETE FROM settings")
        db.executemany(
            "INSERT INTO settings (id, version, payload) VALUES (?, 0, ?)",
            [(row_id, json.dumps(DEFAULT_SETTINGS)) for row_id in row_ids],
        )
        db.commit()
    state = database_state(path)
    with pytest.raises(ValueError, match="exactly one row with id 1"):
        SettingsStore(path).initialize()
    assert database_state(path) == state


@pytest.mark.parametrize("statement", ["CREATE TABLE IF NOT EXISTS settings", "DROP TABLE settings_legacy"])
def test_migration_storage_failure_rolls_back_ddl_and_data(tmp_path, monkeypatch, statement):
    path = tmp_path / "settings.sqlite3"
    create_legacy(path, version=23, payload=json.dumps(CUSTOM_SETTINGS))
    state = database_state(path)
    contents = path.read_bytes()
    original_connect = sqlite3.connect

    class FailingConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql.lstrip().startswith(statement):
                assert self.in_transaction
                assert super().execute("SELECT COUNT(*) FROM settings_legacy").fetchone()[0] == 1
                raise sqlite3.OperationalError("injected migration storage failure")
            return super().execute(sql, parameters)

    def connect(*args, **kwargs):
        return original_connect(*args, **kwargs, factory=FailingConnection)

    with monkeypatch.context() as patch:
        patch.setattr(core.sqlite3, "connect", connect)
        with pytest.raises(sqlite3.OperationalError, match="injected migration storage failure"):
            SettingsStore(path).initialize()
    assert database_state(path) == state
    assert path.read_bytes() == contents

    # Retrying after a transient failure must migrate the original settings.
    store = SettingsStore(path)
    store.initialize()
    assert store.get() == {
        "version": 23, "settings": CUSTOM_SETTINGS,
        "device_applied": False, "acked_at": None,
    }


def test_unrecognized_schema_is_rejected_without_reset(tmp_path):
    path = tmp_path / "settings.sqlite3"
    create_legacy(path)
    with closing(sqlite3.connect(path)) as db:
        db.execute("ALTER TABLE settings ADD COLUMN unexpected TEXT")
        db.commit()
    state = database_state(path)
    with pytest.raises(ValueError, match="Unsupported settings database schema"):
        SettingsStore(path).initialize()
    assert database_state(path) == state

from __future__ import annotations

import subprocess
from pathlib import Path

import filecheck.db_persistence as db_persistence
import filecheck.portable_everything as portable
from filecheck.everything import EverythingStatus


def _status() -> EverythingStatus:
    return EverythingStatus(
        es_path="es.exe",
        es_version="1.1.0.37",
        everything_version="1.4.1.1032",
        instance="FileCheck",
    )


def test_start_instance_uses_explicit_db_and_headless_startup(tmp_path: Path, monkeypatch) -> None:
    ini = tmp_path / "Everything.ini"
    ini.write_text("[Everything]\nrun_in_background=1\n", encoding="utf-8")
    exe = tmp_path / "Everything.exe"
    exe.write_bytes(b"x")
    db = tmp_path / "Everything-FileCheck.db"
    launched: list[list[str]] = []

    class DummyPopen:
        def __init__(self, command, **kwargs):
            del kwargs
            launched.append(list(command))

    monkeypatch.setattr(portable, "find_everything_exe", lambda value=None: exe)
    monkeypatch.setattr(portable, "everything_ini_path", lambda: ini)
    monkeypatch.setattr(db_persistence, "database_path", lambda: db)
    monkeypatch.setattr(db_persistence.subprocess, "Popen", DummyPopen)
    monkeypatch.setattr(db_persistence, "get_status", lambda es=None, instance=None: _status())

    status = db_persistence.start_instance()

    assert status.instance == "FileCheck"
    assert len(launched) == 1
    command = launched[0]
    assert command[command.index("-db") + 1] == str(db)
    assert command[command.index("-config") + 1] == str(ini)
    assert "-startup" in command


def test_flush_database_uses_es_ipc_save_db(tmp_path: Path, monkeypatch) -> None:
    es = tmp_path / "es.exe"
    es.write_bytes(b"x")
    db = tmp_path / "Everything-FileCheck.db"
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        del kwargs
        calls.append(list(command))
        db.write_bytes(b"database")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(db_persistence, "find_es", lambda value=None: es)
    monkeypatch.setattr(db_persistence, "database_path", lambda: db)
    monkeypatch.setattr(db_persistence.subprocess, "run", fake_run)

    result = db_persistence._flush_database_to_disk(es=str(es), wait_seconds=1)

    assert result == db
    assert calls == [[str(es), "-argv", "-instance", "FileCheck", "-save-db"]]

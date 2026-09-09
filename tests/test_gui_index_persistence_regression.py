from __future__ import annotations

from pathlib import Path

import pytest

import filecheck.db_persistence as db_persistence
import filecheck.portable_everything as portable
from filecheck.everything import EverythingStatus
from filecheck.gui import index_service


def _status() -> EverythingStatus:
    return EverythingStatus(
        es_path="es.exe",
        es_version="1.1.0.37",
        everything_version="1.4.1.1032",
        instance="FileCheck",
    )


def test_gui_configure_installs_named_database_hooks(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "Everything-FileCheck.db"
    db.write_bytes(b"db")

    def fake_original(selected_roots, backup_root, **kwargs):
        del selected_roots, backup_root, kwargs
        assert portable.everything_db_path is db_persistence.database_path
        assert portable.start_instance is db_persistence.start_instance
        assert portable.stop_instance is db_persistence.stop_instance
        return portable.PortableIndexResult(
            status=_status(),
            config_path=tmp_path / "Everything.ini",
            database_path=db_persistence.database_path(),
            selected_roots=("C:\\",),
            excluded_roots=("D:\\backup",),
            ntfs_roots=("C:\\",),
            folder_roots=(),
        )

    monkeypatch.setattr(db_persistence, "database_path", lambda: db)
    monkeypatch.setattr(db_persistence, "_ORIGINAL_CONFIGURE_AND_REINDEX", fake_original)
    monkeypatch.setattr(db_persistence, "_flush_database_to_disk", lambda *args, **kwargs: db)
    monkeypatch.setattr(db_persistence, "_remove_legacy_empty_db_directory", lambda: None)
    monkeypatch.setattr(db_persistence, "_remove_legacy_wrong_db_file_after_success", lambda value: None)

    result = db_persistence.configure_and_reindex(["C:\\"], "D:\\backup")
    assert result.database_path == db


def test_failed_rebuild_invalidates_ready_state(tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / "index-config.json"
    state.write_text('{"schema_version": 1}', encoding="utf-8")

    monkeypatch.setattr(portable, "index_state_path", lambda: state)
    monkeypatch.setattr(db_persistence, "_remove_legacy_empty_db_directory", lambda: None)

    def fail(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("simulated rebuild failure")

    monkeypatch.setattr(db_persistence, "_ORIGINAL_CONFIGURE_AND_REINDEX", fail)

    with pytest.raises(RuntimeError, match="simulated"):
        db_persistence.configure_and_reindex(["C:\\"], "D:\\backup")

    assert not state.exists()


def test_index_health_rejects_old_unnamed_database(tmp_path: Path, monkeypatch) -> None:
    expected = tmp_path / "Everything-FileCheck.db"
    legacy = tmp_path / "Everything.db"
    legacy.write_bytes(b"legacy")
    monkeypatch.setattr(db_persistence, "database_path", lambda: expected)

    ready, path, issue = index_service._database_health({"database_path": str(legacy)})

    assert ready is False
    assert path == str(legacy)
    assert "当前要求 Everything-FileCheck.db" in issue


def test_index_health_accepts_nonempty_named_database(tmp_path: Path, monkeypatch) -> None:
    expected = tmp_path / "Everything-FileCheck.db"
    expected.write_bytes(b"durable")
    monkeypatch.setattr(db_persistence, "database_path", lambda: expected)

    ready, path, issue = index_service._database_health({"database_path": str(expected)})

    assert ready is True
    assert path == str(expected)
    assert issue == ""

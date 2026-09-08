from __future__ import annotations

import stat
from pathlib import Path

import pytest

from filecheck.backup import create_backup
from filecheck import deletion_runtime


def test_missing_after_preflight_becomes_already_absent(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")
    backup = create_backup([source], tmp_path / "backup")

    summary = deletion_runtime.preflight_migration(backup)
    assert summary["files"] == 1
    source.unlink()

    _, state = deletion_runtime.remove_verified_sources(backup, preflight=False)
    assert state["status"] == "completed"
    assert state["already_absent"] == 1
    assert state["deleted"] == 0
    assert state["failed"] == 0


def test_delete_after_preflight_does_not_hash_source_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"payload" * 100)
    backup = create_backup([source], tmp_path / "backup")
    deletion_runtime.preflight_migration(backup)

    def fail_hash(_path):
        raise AssertionError("source SHA-256 must not run again after confirmation")

    monkeypatch.setattr(deletion_runtime, "sha256_file", fail_hash)
    _, state = deletion_runtime.remove_verified_sources(backup, preflight=False)
    assert state["deleted"] == 1
    assert not source.exists()


def test_readonly_is_cleared_before_first_delete_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "readonly.txt"
    source.write_text("payload", encoding="utf-8")
    source.chmod(source.stat().st_mode & ~stat.S_IWRITE)

    real_unlink = Path.unlink
    calls = {"count": 0}

    def assert_writable_then_unlink(path: Path, *args, **kwargs):
        calls["count"] += 1
        assert path.stat().st_mode & stat.S_IWRITE
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", assert_writable_then_unlink)
    deletion_runtime._unlink_ignoring_readonly(source)
    assert calls["count"] == 1
    assert not source.exists()


def test_failed_delete_restores_readonly_attribute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "readonly.txt"
    source.write_text("payload", encoding="utf-8")
    source.chmod(source.stat().st_mode & ~stat.S_IWRITE)

    def fail_unlink(_path: Path, *args, **kwargs):
        raise PermissionError(5, "Access is denied", str(_path))

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with pytest.raises(PermissionError):
        deletion_runtime._unlink_ignoring_readonly(source)

    assert source.exists()
    assert not (source.stat().st_mode & stat.S_IWRITE)


def test_changed_after_preflight_is_not_deleted(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")
    backup = create_backup([source], tmp_path / "backup")
    deletion_runtime.preflight_migration(backup)

    source.write_text("changed", encoding="utf-8")
    _, state = deletion_runtime.remove_verified_sources(backup, preflight=False)
    assert state["failed"] == 1
    assert source.exists()

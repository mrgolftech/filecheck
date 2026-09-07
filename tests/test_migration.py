from __future__ import annotations

import json
from pathlib import Path

import pytest

from filecheck.backup import BackupError, create_backup, restore_backup, verify_backup
from filecheck.migration import (
    MigrationError,
    preflight_migration,
    remove_verified_sources,
    resume_migration,
)
from filecheck.util import sha256_file


def _make_files(root: Path, count: int = 6) -> dict[str, str]:
    expected: dict[str, str] = {}
    for index in range(count):
        path = root / f"组 {index % 3}" / f"同名-{index % 2}.txt"
        # Ensure unique source paths while intentionally repeating basenames.
        path = path.parent / f"{index:04d}-{path.name}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"payload-{index}-中文", encoding="utf-8")
        expected[str(path.resolve())] = sha256_file(path)
    return expected


@pytest.mark.parametrize("zip_mode", [False, True])
def test_bulk_migration_roundtrip_and_restore(tmp_path: Path, zip_mode: bool) -> None:
    source = tmp_path / "source"
    source.mkdir()
    expected = _make_files(source, 12)

    backup = create_backup([source], tmp_path / "backup", zip_mode=zip_mode)
    summary = preflight_migration(backup)
    assert summary["files"] == len(expected)

    state_file, state = remove_verified_sources(backup, preflight=False, checkpoint_every=3)
    assert state_file.is_file()
    assert state["status"] == "completed"
    assert state["deleted"] == len(expected)
    assert state["failed"] == 0
    assert all(not Path(raw).exists() for raw in expected)

    # Source removal must not alter backup validity.
    verify_backup(backup)
    restored = restore_backup(backup)
    assert sum(row["state"] == "restored" for row in restored) == len(expected)
    for raw, digest in expected.items():
        assert sha256_file(Path(raw)) == digest


@pytest.mark.parametrize("zip_mode", [False, True])
def test_changed_source_aborts_entire_removal_before_first_delete(tmp_path: Path, zip_mode: bool) -> None:
    source = tmp_path / "source"
    source.mkdir()
    expected = _make_files(source, 5)
    backup = create_backup([source], tmp_path / "backup", zip_mode=zip_mode)

    changed = Path(next(iter(expected)))
    changed.write_text("changed after backup", encoding="utf-8")

    with pytest.raises(MigrationError, match="未删除任何源文件"):
        remove_verified_sources(backup)

    # Batch preflight is fail-closed: even unchanged siblings remain in place.
    assert all(Path(raw).exists() for raw in expected)


def test_corrupt_backup_blocks_source_removal(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    expected = _make_files(source, 4)
    backup = create_backup([source], tmp_path / "backup")
    manifest = verify_backup(backup)
    stored = backup / Path(manifest["items"][0]["backup_path"])
    stored.write_bytes(b"corrupt")

    with pytest.raises(BackupError):
        remove_verified_sources(backup)
    assert all(Path(raw).exists() for raw in expected)


def test_partial_remove_is_checkpointed_and_resumable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    expected = _make_files(source, 7)
    backup = create_backup([source], tmp_path / "backup")
    locked = Path(list(expected)[3])

    real_unlink = Path.unlink

    def maybe_locked(path: Path, *args, **kwargs):
        if path == locked:
            raise PermissionError("simulated Windows file lock")
        return real_unlink(path, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "unlink", maybe_locked)
        state_file, state = remove_verified_sources(backup, checkpoint_every=1)

    assert state["status"] == "partial"
    assert state["failed"] == 1
    assert locked.exists()
    assert sum(Path(raw).exists() for raw in expected) == 1

    state_file, resumed = resume_migration(state_file, checkpoint_every=1)
    assert resumed["status"] == "completed"
    assert resumed["failed"] == 0
    assert resumed["deleted"] == len(expected)
    assert all(not Path(raw).exists() for raw in expected)

    # Completed migration remains fully restorable.
    restore_backup(backup)
    for raw, digest in expected.items():
        assert sha256_file(Path(raw)) == digest


def test_resume_treats_missing_pending_source_as_already_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    expected = _make_files(source, 3)
    backup = create_backup([source], tmp_path / "backup")
    locked = Path(list(expected)[0])

    real_unlink = Path.unlink

    def maybe_locked(path: Path, *args, **kwargs):
        if path == locked:
            raise PermissionError("locked")
        return real_unlink(path, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "unlink", maybe_locked)
        state_file, state = remove_verified_sources(backup, checkpoint_every=1)
    assert state["failed"] == 1

    # Simulate that the previously failed path was removed manually before resume.
    locked.unlink()
    _, resumed = resume_migration(state_file)
    assert resumed["status"] == "completed"
    assert resumed["already_absent"] == 1


def test_tampered_migration_state_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    expected = _make_files(source, 2)
    backup = create_backup([source], tmp_path / "backup")
    locked = Path(next(iter(expected)))
    real_unlink = Path.unlink

    def maybe_locked(path: Path, *args, **kwargs):
        if path == locked:
            raise PermissionError("locked")
        return real_unlink(path, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "unlink", maybe_locked)
        state_file, _ = remove_verified_sources(backup, checkpoint_every=1)

    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["items"][0]["source_path"] = str((tmp_path / "not-in-manifest.txt").resolve())
    state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(MigrationError, match="不属于备份|文件集合不一致"):
        resume_migration(state_file)


def test_bulk_migration_250_files_stress(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    expected = _make_files(source, 250)
    backup = create_backup([source], tmp_path / "backup")

    _, state = remove_verified_sources(backup, checkpoint_every=25)
    assert state["status"] == "completed"
    assert state["deleted"] == 250
    assert all(not Path(raw).exists() for raw in expected)

    restore_backup(backup)
    assert all(sha256_file(Path(raw)) == digest for raw, digest in expected.items())


def test_completed_source_that_reappears_is_not_deleted_on_resume(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    expected = _make_files(source, 1)
    source_file = Path(next(iter(expected)))
    original_bytes = source_file.read_bytes()
    backup = create_backup([source], tmp_path / "backup")

    state_file, state = remove_verified_sources(backup)
    assert state["status"] == "completed"
    assert not source_file.exists()

    # Simulate an application recreating the same path after migration. Even if
    # bytes happen to be identical, resume must not assume it is the old file.
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_bytes(original_bytes)
    _, resumed = resume_migration(state_file)

    assert source_file.exists()
    assert resumed["status"] == "partial"
    assert resumed["failed"] == 1
    assert resumed["items"][0]["state"] == "reappeared"


def test_state_file_cannot_be_written_inside_directory_backup(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    expected = _make_files(source, 2)
    backup = create_backup([source], tmp_path / "backup")

    with pytest.raises(MigrationError, match="备份批次目录内部"):
        remove_verified_sources(backup, state_path=backup / "migration-state.json")

    assert all(Path(raw).exists() for raw in expected)

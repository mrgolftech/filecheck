from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import filecheck.backup as backup_mod
from filecheck.backup import BackupError, create_backup, verify_backup


def test_insufficient_destination_space_rejected_before_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"x" * 1024)
    destination = tmp_path / "backup"

    monkeypatch.setattr(
        backup_mod.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=100, used=100, free=0),
    )

    with pytest.raises(BackupError, match="可用空间不足"):
        create_backup([source], destination)

    assert destination.exists()
    assert list(destination.iterdir()) == []


def test_failed_copy_is_never_published_as_valid_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("content", encoding="utf-8")
    destination = tmp_path / "backup"
    seen_target: list[Path] = []

    def fail_copy(src: Path, target: Path):
        seen_target.append(target)
        raise OSError("simulated media disconnect")

    monkeypatch.setattr(backup_mod, "_atomic_copy_to_backup", fail_copy)

    with pytest.raises(OSError, match="media disconnect"):
        create_backup([source], destination)

    assert seen_target
    assert any(
        part.startswith(".FC-") and part.endswith(".incomplete")
        for part in seen_target[0].parts
    )
    assert not list(destination.glob("FC-*"))
    assert not list(destination.glob(".FC-*.incomplete"))


def test_zip_failure_does_not_leave_final_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("content", encoding="utf-8")
    destination = tmp_path / "backup"

    def fail_zip(staging: Path, archive: Path) -> None:
        archive.write_bytes(b"partial zip")
        raise OSError("simulated destination failure")

    monkeypatch.setattr(backup_mod, "_create_zip_from_staging", fail_zip)

    with pytest.raises(OSError, match="destination failure"):
        create_backup([source], destination, zip_mode=True)

    assert not list(destination.glob("FC-*.zip"))
    assert not list(destination.glob("FC-*"))
    assert not list(destination.glob(".FC-*.incomplete"))


def test_backup_payload_is_fsynced_before_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("durable", encoding="utf-8")
    destination = tmp_path / "backup"
    calls: list[int] = []
    real_fsync = backup_mod.os.fsync

    def counting_fsync(fd: int) -> None:
        calls.append(fd)
        real_fsync(fd)

    monkeypatch.setattr(backup_mod.os, "fsync", counting_fsync)
    result = create_backup([source], destination)

    verify_backup(result)
    assert calls

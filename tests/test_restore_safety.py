from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import filecheck.backup as backup_mod
from filecheck.backup import BackupError, create_backup, restore_backup, verify_backup


def test_whole_backup_is_verified_before_any_target_write(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    first = source / "01-first.txt"
    second = source / "02-second.txt"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    backup = create_backup([source], tmp_path / "backup")
    manifest = verify_backup(backup)
    second_item = next(item for item in manifest["items"] if item["source_path"].endswith("02-second.txt"))
    stored_second = backup / Path(second_item["backup_path"])
    stored_second.write_bytes(b"BROKEN")

    shutil.rmtree(source)
    with pytest.raises(BackupError):
        restore_backup(backup)

    # A later corrupt item must prevent even an earlier valid item from being restored.
    assert not first.exists()
    assert not second.exists()


def test_overwrite_does_not_touch_existing_target_if_temp_copy_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"good backup content")
    backup = create_backup([source], tmp_path / "backup")

    source.write_bytes(b"important existing content")
    real_copy2 = shutil.copy2

    def failing_copy(src, dst, *args, **kwargs):
        Path(dst).write_bytes(b"partial restored temp")
        raise OSError("simulated copy failure")

    monkeypatch.setattr(backup_mod.shutil, "copy2", failing_copy)
    with pytest.raises(OSError, match="simulated copy failure"):
        restore_backup(backup, conflict="overwrite")

    assert source.read_bytes() == b"important existing content"
    assert list(source.parent.glob(".*.filecheck-restore-*.part")) == []
    monkeypatch.setattr(backup_mod.shutil, "copy2", real_copy2)


def test_basic_mtime_is_restored(tmp_path: Path) -> None:
    source = tmp_path / "mtime.txt"
    source.write_bytes(b"mtime")
    original_mtime_ns = 1_700_000_000_123_456_700
    source.touch()
    try:
        import os

        os.utime(source, ns=(original_mtime_ns, original_mtime_ns))
    except OSError:
        pytest.skip("filesystem does not support requested mtime precision")

    backup = create_backup([source], tmp_path / "backup", zip_mode=True)
    source.unlink()
    restore_backup(backup)

    # Filesystems may round timestamp precision; content integrity remains exact.
    assert abs(source.stat().st_mtime_ns - original_mtime_ns) <= 2_000_000_000

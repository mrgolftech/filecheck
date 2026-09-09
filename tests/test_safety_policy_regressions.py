from __future__ import annotations

import json
from pathlib import Path

import pytest

import filecheck.backup as backup_mod
from filecheck import portable_everything as portable
from filecheck.backup import (
    BackupError,
    create_backup,
    find_containing_backup_batch,
    is_filecheck_backup_batch,
    read_backup_manifest,
)


def _stored_path(batch: Path) -> Path:
    manifest = read_backup_manifest(batch)
    return batch.joinpath(*str(manifest["items"][0]["backup_path"]).split("/"))


def test_renamed_legacy_backup_remains_protected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Keep this regression independent from the separate Win7 path-length gate.
    monkeypatch.setattr(backup_mod, "_is_windows", lambda: False)

    source = tmp_path / "workspace" / "机密旧文件.txt"
    source.parent.mkdir(parents=True)
    source.write_text("payload", encoding="utf-8")
    batch = create_backup([source], tmp_path / "old-backups")

    # Simulate v0.2.1 and earlier: no persistent marker, then the user renames
    # the outer batch directory to something that no longer equals batch_id.
    (batch / ".filecheck-backup").unlink()
    renamed = batch.with_name("FC-2")
    batch.rename(renamed)
    stored = _stored_path(renamed)

    assert is_filecheck_backup_batch(renamed)
    assert find_containing_backup_batch(stored) == renamed.resolve()

    with pytest.raises(BackupError, match="历史备份"):
        create_backup([stored], tmp_path / "new-backups")


def test_corrupt_marker_cannot_downgrade_valid_backup(tmp_path: Path) -> None:
    source = tmp_path / "workspace" / "报告.txt"
    source.parent.mkdir(parents=True)
    source.write_text("payload", encoding="utf-8")
    batch = create_backup([source], tmp_path / "backups")

    (batch / ".filecheck-backup").write_text("{not-json", encoding="utf-8")

    assert is_filecheck_backup_batch(batch)
    assert find_containing_backup_batch(_stored_path(batch)) == batch.resolve()


def test_renamed_ordinary_directory_with_invalid_manifest_is_not_protected(tmp_path: Path) -> None:
    fake = tmp_path / "FC-2"
    (fake / "files").mkdir(parents=True)
    (fake / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "batch_id": "FC-20260909-113220-a07f8670",
                "mode": "directory",
                "items": [
                    {
                        "source_path": "relative.txt",
                        "backup_path": "files/D/relative.txt",
                        "size": 0,
                        "sha256": "0" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert not is_filecheck_backup_batch(fake)


def test_everything_ini_indexes_hidden_and_system_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "everything"
    monkeypatch.setattr(portable, "portable_root", lambda: root)

    ini = portable._write_ini(
        ["C:\\"],
        ["C:\\FileCheckBackup"],
        ntfs_roots=["C:\\"],
        folder_roots=[],
    )
    text = ini.read_text(encoding="utf-8")

    assert "exclude_hidden_files_and_folders=0" in text
    assert "exclude_system_files_and_folders=0" in text
    assert "exclude_hidden_files_and_folders=1" not in text
    assert "exclude_system_files_and_folders=1" not in text


def test_old_index_policy_requires_rebuild_before_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "everything"
    root.mkdir(parents=True)
    monkeypatch.setattr(portable, "portable_root", lambda: root)

    (root / "index-config.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "selected_roots": ["C:\\"],
                "excluded_roots": [],
            }
        ),
        encoding="utf-8",
    )

    relaxed = portable.load_index_state(required=False)
    assert relaxed is not None
    assert relaxed["index_policy_upgrade_required"] is True

    with pytest.raises(portable.PortableEverythingError, match="隐藏文件.*System"):
        portable.load_index_state(required=True)


def test_current_index_policy_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "everything"
    root.mkdir(parents=True)
    monkeypatch.setattr(portable, "portable_root", lambda: root)

    (root / "index-config.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "index_policy_version": portable._INDEX_POLICY_VERSION,
                "selected_roots": ["C:\\"],
                "excluded_roots": [],
            }
        ),
        encoding="utf-8",
    )

    state = portable.load_index_state(required=True)
    assert state is not None
    assert state["index_policy_upgrade_required"] is False

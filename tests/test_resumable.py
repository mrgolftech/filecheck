from __future__ import annotations

from pathlib import Path

import pytest

import filecheck.resumable as resumable
from filecheck.backup import BackupError, read_backup_manifest, verify_backup


def _use_test_appdata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))


def test_copy_failure_keeps_state_and_resumes_without_recopying_valid_payloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_test_appdata(tmp_path, monkeypatch)
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    a = source_dir / "a.txt"
    b = source_dir / "b.txt"
    c = source_dir / "c.txt"
    a.write_text("A", encoding="utf-8")
    b.write_text("B", encoding="utf-8")
    c.write_text("C", encoding="utf-8")

    destination = tmp_path / "backup"
    real_copy = resumable._atomic_copy_to_backup
    failed_once = {"value": False}

    def flaky_copy(source: Path, target: Path):
        if resumable._display_path_from_io(source).endswith("b.txt") and not failed_once["value"]:
            failed_once["value"] = True
            raise OSError("simulated transient path failure")
        return real_copy(source, target)

    monkeypatch.setattr(resumable, "_atomic_copy_to_backup", flaky_copy)
    batch_id = "FC-20260907-RESUME01"

    with pytest.raises(BackupError, match="批量复制未完整完成"):
        resumable.create_resumable_backup(
            [a, b, c],
            destination,
            batch_id=batch_id,
        )

    state_path = resumable.operation_state_path(batch_id)
    state = resumable.load_operation_state(state_path)
    assert state["copied"] == 2
    assert state["failed"] == 1
    assert state["status"] == "copy_failed"
    assert (destination / f".{batch_id}.incomplete").is_dir()

    monkeypatch.setattr(resumable, "_atomic_copy_to_backup", real_copy)
    result, returned_state_path, final_state = resumable.resume_resumable_backup(state_path)

    assert returned_state_path == state_path.resolve()
    assert final_state["status"] == "completed"
    verify_backup(result)
    manifest = read_backup_manifest(result)
    assert {Path(item["source_path"]).name for item in manifest["items"]} == {"a.txt", "b.txt", "c.txt"}


def test_storage_layout_mirrors_source_tree_for_manual_inspection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_test_appdata(tmp_path, monkeypatch)
    source = tmp_path / "项目A" / "参考资料" / "子目录" / "报告版本 V2.4.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"payload")

    result, _state_path, state = resumable.create_resumable_backup(
        [source],
        tmp_path / "backup",
        batch_id="FC-20260907-MIRROR01",
    )
    manifest = read_backup_manifest(result)
    item = manifest["items"][0]
    backup_path = item["backup_path"]

    assert state["storage_layout"] == "mirrored-source-tree-v1"
    assert manifest["storage_layout"] == "mirrored-source-tree-v1"
    assert backup_path.startswith("files/")
    assert "项目A/参考资料/子目录/报告版本 V2.4.pdf" in backup_path
    assert (result / Path(backup_path)).is_file()
    verify_backup(result)


def test_migrate_operation_stops_at_backup_verified_before_source_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_test_appdata(tmp_path, monkeypatch)
    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")

    backup, state_path, state = resumable.create_resumable_backup(
        [source],
        tmp_path / "backup",
        operation="migrate",
        batch_id="FC-20260907-MIGRATE1",
    )

    assert source.exists()
    assert state["status"] == "backup_verified"
    assert resumable.load_operation_state(state_path)["backup_path"] == str(backup)
    verify_backup(backup)


def test_discover_operation_states_lists_only_unfinished_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_test_appdata(tmp_path, monkeypatch)
    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")

    _backup, completed_state, _ = resumable.create_resumable_backup(
        [source],
        tmp_path / "backup-a",
        batch_id="FC-20260907-DONE0001",
    )
    state = resumable.load_operation_state(completed_state)
    assert state["status"] == "completed"

    pending_path = resumable.operation_state_path("FC-20260907-PEND0001")
    pending = dict(state)
    pending["batch_id"] = "FC-20260907-PEND0001"
    pending["status"] = "interrupted"
    pending["destination_root"] = str(tmp_path / "backup-b")
    resumable.save_operation_state(pending_path, pending)

    found = resumable.discover_operation_states()
    assert [path.name for path, _ in found] == [pending_path.name]

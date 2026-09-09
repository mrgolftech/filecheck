from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import filecheck.backup as backup_mod
import filecheck.gui.scan_service as scan_service
from filecheck import deletion_runtime
from filecheck.backup import (
    BackupError,
    create_backup,
    find_containing_backup_batch,
    is_filecheck_backup_batch,
    read_backup_manifest,
)


class FakeTask:
    def __init__(self) -> None:
        self.logs: list[str] = []
        self.progress: list[tuple[object, str]] = []

    def log(self, message: str) -> None:
        self.logs.append(message)

    def set_progress(self, progress, message: str = "") -> None:
        self.progress.append((progress, message))

    def raise_if_cancelled(self) -> None:
        return None


def _stored_path(batch: Path) -> Path:
    manifest = read_backup_manifest(batch)
    return batch.joinpath(*str(manifest["items"][0]["backup_path"]).split("/"))


def _make_backup(tmp_path: Path, name: str = "机密报告.txt", payload: bytes = b"payload") -> tuple[Path, Path, Path]:
    source = tmp_path / "workspace" / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(payload)
    batch = create_backup([source], tmp_path / "old-backups")
    return source, batch, _stored_path(batch)


def test_new_batch_marker_identifies_backup_after_move_and_rename(tmp_path: Path) -> None:
    _, batch, stored = _make_backup(tmp_path)

    marker = batch / ".filecheck-backup"
    assert marker.is_file()
    marker_payload = json.loads(marker.read_text(encoding="utf-8-sig"))
    assert marker_payload["format"] == "filecheck-backup"
    assert marker_payload["version"] == 1
    assert marker_payload["batch_id"] == batch.name
    assert is_filecheck_backup_batch(batch)
    assert find_containing_backup_batch(stored) == batch.resolve()

    moved_parent = tmp_path / "archive" / "moved"
    moved_parent.mkdir(parents=True)
    renamed = moved_parent / "historical-backup-renamed"
    batch.rename(renamed)
    moved_stored = _stored_path(renamed)

    assert is_filecheck_backup_batch(renamed)
    assert find_containing_backup_batch(moved_stored) == renamed.resolve()


def test_legacy_batch_without_marker_is_still_protected(tmp_path: Path) -> None:
    _, batch, stored = _make_backup(tmp_path)
    (batch / ".filecheck-backup").unlink()

    assert is_filecheck_backup_batch(batch)
    assert find_containing_backup_batch(stored) == batch.resolve()


def test_fake_fc_like_directory_is_not_false_positive(tmp_path: Path) -> None:
    fake = tmp_path / "FC-20260909-120000-deadbeef"
    (fake / "files").mkdir(parents=True)
    (fake / "manifest.json").write_text('{"batch_id":"not-a-real-batch"}', encoding="utf-8")
    ordinary = fake / "files" / "normal.txt"
    ordinary.write_text("normal", encoding="utf-8")

    assert not is_filecheck_backup_batch(fake)
    assert find_containing_backup_batch(ordinary) is None
    created = create_backup([ordinary], tmp_path / "new-backup")
    assert created.is_dir()


def test_core_backup_rejects_file_from_historical_backup(tmp_path: Path) -> None:
    _, old_batch, stored = _make_backup(tmp_path)

    with pytest.raises(BackupError, match="历史备份"):
        create_backup([stored], tmp_path / "new-backup")

    assert list((tmp_path / "new-backup").glob("FC-*")) == []
    assert is_filecheck_backup_batch(old_batch)


def test_core_backup_rejects_directory_containing_nested_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # This test targets nested-backup protection, not the independent Win7
    # 240-character safety gate. GitHub's Windows temp path is already very deep.
    monkeypatch.setattr(backup_mod, "_is_windows", lambda: False)
    root = tmp_path / "mixed-source"
    normal = root / "normal.txt"
    normal.parent.mkdir(parents=True)
    normal.write_text("normal", encoding="utf-8")

    original = tmp_path / "seed.txt"
    original.write_text("protected", encoding="utf-8")
    old_batch = create_backup([original], root / "history")
    assert is_filecheck_backup_batch(old_batch)

    with pytest.raises(BackupError, match="包含 FileCheck 历史备份"):
        create_backup([root], tmp_path / "destination")

    assert list((tmp_path / "destination").glob("FC-*")) == []


def test_scan_filters_old_backup_after_backup_root_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backup_mod, "_is_windows", lambda: False)
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(
        json.dumps({"keywords": {"high": ["机密"]}, "extensions": ["txt"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    indexed_root = tmp_path / "indexed"
    indexed_root.mkdir()
    normal = indexed_root / "机密正常文件.txt"
    normal.write_text("normal", encoding="utf-8")

    old_source = tmp_path / "seed" / "机密旧备份.txt"
    old_source.parent.mkdir(parents=True)
    old_source.write_text("old", encoding="utf-8")
    old_batch = create_backup([old_source], indexed_root / "backup0907")
    old_stored = _stored_path(old_batch)

    new_backup_root = tmp_path / "20260909"
    output = tmp_path / "scan-results.json"
    monkeypatch.setattr(scan_service.cli, "_default_rules_path", lambda: str(rules_path))
    monkeypatch.setattr(scan_service.cli, "_default_scan_output", lambda: str(output))
    monkeypatch.setattr(scan_service, "current_backup_root", lambda: str(new_backup_root))
    monkeypatch.setattr(scan_service, "program_dir", lambda: tmp_path / "program")
    monkeypatch.setattr(
        scan_service,
        "load_index_state",
        lambda required=True: {
            "selected_roots": [str(indexed_root)],
            "excluded_roots": [],
            "index_mode": "portable-folder-index",
            "updated_at": "index-v1",
        },
    )
    monkeypatch.setattr(
        scan_service.db_persistence,
        "ensure_instance",
        lambda: SimpleNamespace(everything_version="1.4.1.1032", es_version="1.1.0.37"),
    )

    def fake_scan_keywords(*args, **kwargs):
        def item(path: Path):
            return {
                "path": str(path),
                "directory": str(path.parent),
                "matched_keywords": ["机密"],
                "levels": ["high"],
                "severity": "high",
                "size": path.stat().st_size,
                "mtime_ns": path.stat().st_mtime_ns,
                "accessible": True,
            }

        return [item(normal), item(old_stored)]

    monkeypatch.setattr(scan_service, "scan_keywords", fake_scan_keywords)
    task = FakeTask()
    result = scan_service.run_scan(scan_service.ScanRequest(), task)

    assert [row["path"] for row in result.items] == [str(normal)]
    assert result.payload["excluded_backup_items"] == 1
    assert result.payload["protected_backup_batches"] == [str(old_batch.resolve())]
    assert any("自动排除 1 个" in line for line in task.logs)


def test_delete_preflight_refuses_nested_backup_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backup_mod, "_is_windows", lambda: False)
    _, old_batch, old_stored = _make_backup(tmp_path, payload=b"same-payload")

    seed = tmp_path / "second-seed.txt"
    seed.write_bytes(old_stored.read_bytes())
    second = create_backup([seed], tmp_path / "second-backups")
    manifest_path = second / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["items"][0]["source_path"] = str(old_stored)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(Exception, match="历史备份"):
        deletion_runtime.preflight_migration(second)

    assert old_stored.is_file()
    assert is_filecheck_backup_batch(old_batch)


def test_delete_runtime_hard_guard_blocks_nested_source_even_without_preflight(tmp_path: Path) -> None:
    _, _, old_stored = _make_backup(tmp_path)
    row = {"source_path": str(old_stored), "state": "pending", "error": None}
    snap = deletion_runtime._snapshot(old_stored)

    deletion_runtime._remove_one_fast(row, snap)

    assert row["state"] == "failed"
    assert "历史备份" in str(row["error"])
    assert old_stored.is_file()


def test_delete_is_not_reported_success_if_path_still_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "normal-source.txt"
    source.write_text("payload", encoding="utf-8")
    batch = create_backup([source], tmp_path / "backup")
    deletion_runtime.preflight_migration(batch)

    monkeypatch.setattr(deletion_runtime, "_unlink_ignoring_readonly", lambda _path: None)
    _, state = deletion_runtime.remove_verified_sources(batch, preflight=False)

    assert state["deleted"] == 0
    assert state["failed"] == 1
    assert source.is_file()
    assert "仍然存在" in str(state["items"][0]["error"])

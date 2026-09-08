from __future__ import annotations

from pathlib import Path

from filecheck.gui import batch_service


def _batch(root: Path, name: str) -> Path:
    path = root / name
    path.mkdir()
    (path / "manifest.json").write_text("{}", encoding="utf-8")
    return path


def test_discover_backup_batches_uses_direct_manifest_children_and_newest_name_first(tmp_path: Path) -> None:
    root = tmp_path / "backup"
    root.mkdir()
    older = _batch(root, "FC-20260908-090000")
    newest = _batch(root, "FC-20260908-110000")
    middle = _batch(root, "FC-20260908-100000")

    invalid = root / "FC-20260908-120000"
    invalid.mkdir()
    nested = invalid / "nested"
    nested.mkdir()
    (nested / "manifest.json").write_text("{}", encoding="utf-8")

    rows = batch_service.discover_backup_batches(str(root))
    assert [row.name for row in rows] == [newest.name, middle.name, older.name]
    assert [row.path for row in rows] == [newest.resolve(), middle.resolve(), older.resolve()]
    assert batch_service.latest_backup_batch(str(root)) == newest.resolve()


def test_discover_backup_batches_defaults_to_configured_single_root(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "backup"
    root.mkdir()
    batch = _batch(root, "FC-20260908-130000")
    monkeypatch.setattr(batch_service, "current_backup_root", lambda: str(root))
    rows = batch_service.discover_backup_batches()
    assert len(rows) == 1
    assert rows[0].path == batch.resolve()


def test_discover_backup_batches_returns_empty_without_configured_root(monkeypatch) -> None:
    monkeypatch.setattr(batch_service, "current_backup_root", lambda: None)
    assert batch_service.discover_backup_batches() == []
    assert batch_service.latest_backup_batch() is None

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import filecheck.backup as backup_mod
from filecheck.backup import BackupError, create_backup, restore_backup, verify_backup
from filecheck.util import sha256_file


def make_tree(root: Path) -> dict[str, str]:
    files = {
        "a.txt": b"alpha",
        "中文/机密 测试.txt": "中文内容\n".encode("utf-8"),
        "nested/a/b/empty.bin": b"",
        "nested/data.bin": bytes(range(256)) * 4096,
    }
    expected: dict[str, str] = {}
    for rel, data in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        expected[str(path.resolve())] = sha256_file(path)
    return expected


def assert_expected(expected: dict[str, str]) -> None:
    for raw, digest in expected.items():
        path = Path(raw)
        assert path.is_file(), raw
        assert sha256_file(path) == digest, raw


def test_roundtrip_backup_restore(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    expected = make_tree(source)
    backup = create_backup([source], tmp_path / "backup")

    manifest = verify_backup(backup)
    assert manifest["mode"] == "directory"
    assert len(manifest["items"]) == len(expected)
    assert "source_removed" not in manifest
    assert all("source_removed" not in item for item in manifest["items"])

    shutil.rmtree(source)
    results = restore_backup(backup)
    assert sum(row["state"] == "restored" for row in results) == len(expected)
    assert_expected(expected)


def test_skip_and_overwrite_conflicts(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    expected = make_tree(source)
    backup = create_backup([source], tmp_path / "backup")

    target = source / "a.txt"
    target.write_bytes(b"local change")
    restore_backup(backup, conflict="skip")
    assert target.read_bytes() == b"local change"

    restore_backup(backup, conflict="overwrite")
    assert_expected(expected)


def test_rename_conflict(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    original = source / "a.txt"
    original.write_bytes(b"alpha")
    backup = create_backup([original], tmp_path / "backup")

    original.write_bytes(b"local")
    result = restore_backup(backup, conflict="rename")
    restored = Path(result[0]["target"])
    assert restored != original
    assert restored.read_bytes() == b"alpha"
    assert original.read_bytes() == b"local"


def test_corrupted_directory_backup_is_rejected_before_restore(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    expected = make_tree(source)
    backup = create_backup([source], tmp_path / "backup")
    manifest = verify_backup(backup)

    first = manifest["items"][0]
    stored = backup / Path(first["backup_path"])
    stored.write_bytes(b"corrupted")

    protected_target = Path(first["source_path"])
    protected_target.write_bytes(b"do not touch")
    with pytest.raises(BackupError):
        restore_backup(backup, conflict="overwrite")
    assert protected_target.read_bytes() == b"do not touch"
    assert len(expected) == len(manifest["items"])


def test_extracted_legacy_zip_manifest_is_accepted_as_directory(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    expected = make_tree(source)
    backup = create_backup([source], tmp_path / "backup")
    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["mode"] = "zip"  # v0.1.0 archive after the user has extracted it
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    verify_backup(backup)
    shutil.rmtree(source)
    restore_backup(backup)
    assert_expected(expected)


def test_zip_file_input_is_not_supported(tmp_path: Path) -> None:
    fake_zip = tmp_path / "old.zip"
    fake_zip.write_bytes(b"PK")
    with pytest.raises(BackupError, match="目录备份"):
        verify_backup(fake_zip)


def test_destination_inside_source_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "a.txt").write_text("alpha", encoding="utf-8")
    with pytest.raises(BackupError, match="备份目标不能位于"):
        create_backup([source], source / "backup")


def test_overlapping_selection_is_deduplicated(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    file = source / "a.txt"
    file.write_text("alpha", encoding="utf-8")
    backup = create_backup([source, file], tmp_path / "backup")
    manifest = verify_backup(backup)
    assert len(manifest["items"]) == 1


def test_same_filename_in_different_paths_are_all_preserved(tmp_path: Path) -> None:
    first = tmp_path / "C-tree" / "ProjectA" / "报告.pdf"
    second = tmp_path / "C-tree" / "ProjectB" / "报告.pdf"
    third = tmp_path / "D-tree" / "资料" / "报告.pdf"
    for index, path in enumerate((first, second, third), start=1):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"payload-{index}".encode())

    backup = create_backup([first, second, third], tmp_path / "backup")
    manifest = verify_backup(backup)
    assert len(manifest["items"]) == 3
    backup_paths = [item["backup_path"] for item in manifest["items"]]
    assert len(set(backup_paths)) == 3

    expected = {str(path.resolve()): sha256_file(path) for path in (first, second, third)}
    for path in (first, second, third):
        path.unlink()
    restore_backup(backup)
    assert_expected(expected)


def test_source_change_during_copy_aborts_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "src.txt"
    source.write_bytes(b"original")
    destination = tmp_path / "backup"
    real_copy = backup_mod._copy_source_to_temp_with_hash

    def changing_copy(src: Path, temp: Path):
        result = real_copy(src, temp)
        Path(src).write_bytes(b"changed while copying")
        return result

    monkeypatch.setattr(backup_mod, "_copy_source_to_temp_with_hash", changing_copy)
    with pytest.raises(BackupError, match="发生变化"):
        create_backup([source], destination)

    manifests = list(destination.rglob("manifest.json")) if destination.exists() else []
    assert manifests == []


def test_manifest_tampering_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "src.txt"
    source.write_text("alpha", encoding="utf-8")
    backup = create_backup([source], tmp_path / "backup")
    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["items"][0]["backup_path"] = "../escape.txt"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(BackupError, match="非法 backup_path"):
        verify_backup(backup)


def test_batch_ids_do_not_collide(tmp_path: Path) -> None:
    source = tmp_path / "a.txt"
    source.write_text("alpha", encoding="utf-8")
    first = create_backup([source], tmp_path / "backup")
    second = create_backup([source], tmp_path / "backup")
    assert first.name != second.name

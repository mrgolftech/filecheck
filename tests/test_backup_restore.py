from __future__ import annotations

import json
import shutil
import zipfile
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


@pytest.mark.parametrize("zip_mode", [False, True])
def test_roundtrip_backup_restore(tmp_path: Path, zip_mode: bool) -> None:
    source = tmp_path / "src"
    source.mkdir()
    expected = make_tree(source)
    backup = create_backup([source], tmp_path / "backup", zip_mode=zip_mode)

    manifest = verify_backup(backup)
    assert len(manifest["items"]) == len(expected)

    shutil.rmtree(source)
    results = restore_backup(backup)
    assert sum(row["state"] == "restored" for row in results) == len(expected)
    assert_expected(expected)


@pytest.mark.parametrize("zip_mode", [False, True])
def test_skip_and_overwrite_conflicts(tmp_path: Path, zip_mode: bool) -> None:
    source = tmp_path / "src"
    source.mkdir()
    expected = make_tree(source)
    backup = create_backup([source], tmp_path / "backup", zip_mode=zip_mode)

    target = source / "a.txt"
    target.write_bytes(b"local change")
    restore_backup(backup, conflict="skip")
    assert target.read_bytes() == b"local change"

    restore_backup(backup, conflict="overwrite")
    assert_expected(expected)


@pytest.mark.parametrize("zip_mode", [False, True])
def test_rename_conflict(tmp_path: Path, zip_mode: bool) -> None:
    source = tmp_path / "src"
    source.mkdir()
    original = source / "a.txt"
    original.write_bytes(b"alpha")
    backup = create_backup([original], tmp_path / "backup", zip_mode=zip_mode)

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
    backup = create_backup([source], tmp_path / "backup", zip_mode=False)
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


def test_zip_crc_valid_but_sha_invalid_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    file = source / "a.txt"
    file.write_bytes(b"alpha")
    archive = create_backup([file], tmp_path / "backup", zip_mode=True)
    manifest = verify_backup(archive)
    member = manifest["items"][0]["backup_path"]

    replacement = tmp_path / "replacement.zip"
    with zipfile.ZipFile(archive, "r") as src, zipfile.ZipFile(replacement, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename == member:
                dst.writestr(info.filename, b"bravo")  # same length; ZIP CRC itself is valid
            else:
                dst.writestr(info, src.read(info.filename))
    replacement.replace(archive)

    with pytest.raises(BackupError, match="SHA-256"):
        verify_backup(archive)


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


def test_source_change_during_copy_aborts_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "src.txt"
    source.write_bytes(b"original")
    destination = tmp_path / "backup"
    real_copy2 = shutil.copy2

    def changing_copy(src, dst, *args, **kwargs):
        result = real_copy2(src, dst, *args, **kwargs)
        Path(src).write_bytes(b"changed while copying")
        return result

    monkeypatch.setattr(backup_mod.shutil, "copy2", changing_copy)
    with pytest.raises(BackupError, match="发生变化"):
        create_backup([source], destination)

    # No completed manifest/backup is allowed after an inconsistent copy.
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

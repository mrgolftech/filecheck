from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path

from .backup import create_backup, restore_backup, verify_backup
from .migration import preflight_migration, remove_verified_sources


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


def _make_fixture(root: Path) -> dict[str, str]:
    files = {
        "普通.txt": "hello filecheck\n",
        "中文目录/机密_测试.docx": "not a real docx, only a selftest fixture\n",
        "带 空格/方案 报告.txt": "content with spaces\n",
        "nested/a/b/c/empty.bin": "",
    }
    result: dict[str, str] = {}
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        result[str(path.resolve())] = _sha256(path)

    binary = root / "nested" / "binary-2MiB.bin"
    binary.parent.mkdir(parents=True, exist_ok=True)
    pattern = bytes(range(256))
    with binary.open("wb") as fh:
        for _ in range((2 * 1024 * 1024) // len(pattern)):
            fh.write(pattern)
    result[str(binary.resolve())] = _sha256(binary)
    return result


def _assert_restored(expected: dict[str, str]) -> None:
    for raw, digest in expected.items():
        path = Path(raw)
        if not path.is_file():
            raise RuntimeError(f"自检恢复文件缺失: {path}")
        if _sha256(path) != digest:
            raise RuntimeError(f"自检恢复 SHA-256 不一致: {path}")


def _exercise(zip_mode: bool) -> int:
    with tempfile.TemporaryDirectory(prefix="filecheck-selftest-") as tmp:
        base = Path(tmp)
        source = base / "源数据"
        backup_root = base / "备份"
        source.mkdir()
        expected = _make_fixture(source)

        backup = create_backup([source], backup_root, zip_mode=zip_mode)
        manifest = verify_backup(backup)
        if len(manifest["items"]) != len(expected):
            raise RuntimeError("自检 manifest 文件数量不一致")

        # This deletes only disposable files created under this TemporaryDirectory.
        shutil.rmtree(source)
        results = restore_backup(backup, conflict="skip")
        if sum(row["state"] == "restored" for row in results) != len(expected):
            raise RuntimeError("自检恢复文件数量不一致")
        _assert_restored(expected)

        # Verify conflict=skip does not alter an existing file.
        target = Path(next(iter(expected)))
        target.write_bytes(b"LOCAL-CHANGE")
        restore_backup(backup, conflict="skip")
        if target.read_bytes() != b"LOCAL-CHANGE":
            raise RuntimeError("conflict=skip 自检失败：现有文件被修改")

        # Verify conflict=overwrite restores verified content.
        restore_backup(backup, conflict="overwrite")
        _assert_restored(expected)
        return len(expected)


def _exercise_migration(zip_mode: bool) -> int:
    with tempfile.TemporaryDirectory(prefix="filecheck-migrate-selftest-") as tmp:
        base = Path(tmp)
        source = base / "待迁移"
        backup_root = base / "备份"
        source.mkdir()
        expected = _make_fixture(source)

        backup = create_backup([source], backup_root, zip_mode=zip_mode)
        preflight = preflight_migration(backup)
        if preflight["files"] != len(expected):
            raise RuntimeError("迁移自检源文件复核数量不一致")

        state_path, state = remove_verified_sources(backup, preflight=False, checkpoint_every=2)
        if state["status"] != "completed" or state["deleted"] != len(expected):
            raise RuntimeError(f"迁移自检源文件移除失败: {state_path}")
        for raw in expected:
            if Path(raw).exists():
                raise RuntimeError(f"迁移自检源文件仍存在: {raw}")

        # The backup must remain fully valid after source removal.
        verify_backup(backup)
        restored = restore_backup(backup, conflict="skip")
        if sum(row["state"] == "restored" for row in restored) != len(expected):
            raise RuntimeError("迁移自检恢复数量不一致")
        _assert_restored(expected)
        return len(expected)


def run_selftest() -> dict[str, str]:
    directory_count = _exercise(zip_mode=False)
    zip_count = _exercise(zip_mode=True)
    migrate_directory_count = _exercise_migration(zip_mode=False)
    migrate_zip_count = _exercise_migration(zip_mode=True)
    return {
        "directory_roundtrip": f"PASS ({directory_count} files)",
        "zip_roundtrip": f"PASS ({zip_count} files)",
        "migration_directory_roundtrip": f"PASS ({migrate_directory_count} files)",
        "migration_zip_roundtrip": f"PASS ({migrate_zip_count} files)",
        "sha256_verification": "PASS",
        "conflict_skip": "PASS",
        "conflict_overwrite": "PASS",
        "migration_source_recheck": "PASS",
        "migration_restore": "PASS",
    }

from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path

from .backup import create_backup, restore_backup, verify_backup
from .migration import remove_verified_sources


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


def _exercise_roundtrip() -> int:
    with tempfile.TemporaryDirectory(prefix="filecheck-selftest-") as tmp:
        base = Path(tmp)
        source = base / "源数据"
        backup_root = base / "备份"
        source.mkdir()
        expected = _make_fixture(source)
        backup = create_backup([source], backup_root)
        manifest = verify_backup(backup)
        if len(manifest["items"]) != len(expected):
            raise RuntimeError("自检 manifest 文件数量不一致")
        if "source_removed" in manifest or any("source_removed" in row for row in manifest["items"]):
            raise RuntimeError("v0.1.1 manifest 不应包含 source_removed")

        shutil.rmtree(source)
        results = restore_backup(backup, conflict="skip")
        if sum(row["state"] == "restored" for row in results) != len(expected):
            raise RuntimeError("自检恢复文件数量不一致")
        _assert_restored(expected)

        target = Path(next(iter(expected)))
        target.write_bytes(b"LOCAL-CHANGE")
        restore_backup(backup, conflict="skip")
        if target.read_bytes() != b"LOCAL-CHANGE":
            raise RuntimeError("conflict=skip 自检失败")
        restore_backup(backup, conflict="overwrite")
        _assert_restored(expected)
        return len(expected)


def _exercise_removal_restore() -> int:
    with tempfile.TemporaryDirectory(prefix="filecheck-remove-selftest-") as tmp:
        base = Path(tmp)
        source = base / "待删除"
        backup_root = base / "备份"
        source.mkdir()
        expected = _make_fixture(source)
        backup = create_backup([source], backup_root)

        state_path, state = remove_verified_sources(backup)
        if state["status"] != "completed" or state["deleted"] != len(expected):
            raise RuntimeError(f"源文件删除自检失败: {state_path}")
        if state_path != backup / "source-removal.json":
            raise RuntimeError("source-removal.json 未保存在备份目录")
        for raw in expected:
            if Path(raw).exists():
                raise RuntimeError(f"源文件仍存在: {raw}")

        verify_backup(backup)
        restored = restore_backup(backup, conflict="skip")
        if sum(row["state"] == "restored" for row in restored) != len(expected):
            raise RuntimeError("删除后恢复数量不一致")
        _assert_restored(expected)
        return len(expected)


def run_selftest() -> dict[str, str]:
    directory_count = _exercise_roundtrip()
    removal_count = _exercise_removal_restore()
    return {
        "directory_roundtrip": f"PASS ({directory_count} files)",
        "manifest_immutable": "PASS",
        "source_removal_state": f"PASS ({removal_count} files)",
        "sha256_verification": "PASS",
        "conflict_skip": "PASS",
        "conflict_overwrite": "PASS",
        "source_removal_restore": "PASS",
    }

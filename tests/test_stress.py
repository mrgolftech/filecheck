from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from filecheck.backup import create_backup, restore_backup, verify_backup
from filecheck.util import sha256_file


@pytest.mark.parametrize("zip_mode", [False, True])
def test_repeated_roundtrip_20_cycles(tmp_path: Path, zip_mode: bool) -> None:
    for index in range(20):
        source = tmp_path / f"src-{index}"
        source.mkdir()
        files = []
        for n in range(4):
            path = source / f"层级 {n}" / f"测试-{index}-{n}.bin"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((bytes([index % 251, n]) * 32768) + f"尾部-{index}-{n}".encode("utf-8"))
            files.append((path, sha256_file(path)))

        backup = create_backup([source], tmp_path / "backups", zip_mode=zip_mode)
        verify_backup(backup)
        shutil.rmtree(source)
        restore_backup(backup)

        for path, digest in files:
            assert path.is_file()
            assert sha256_file(path) == digest

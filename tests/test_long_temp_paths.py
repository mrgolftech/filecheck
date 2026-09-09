from __future__ import annotations

from pathlib import Path, PureWindowsPath

import filecheck.backup as backup_mod


def test_user_reported_backup_temp_path_stays_below_max_path(monkeypatch) -> None:
    target = PureWindowsPath(
        r"E:\0908\.FC-20260908-230005-4afcf6b1.incomplete\files\E\01-task\00-0518\0-0518打包\0-E盘打包\E盘-01_task\01-高速加密卡\01-高速加密卡\底板设计\Hspeed_PCIE_KCU105_V16_good\Hspeed_PCIE.srcs\sources_1\sources\axi_ctrl\AXIS_CTRL_MODULE\新建文本文档.txt"
    )
    old_temp = target.with_name(
        ".新建文本文档.txt.65738f732c5e459ebdb471a472b7c935.part"
    )

    monkeypatch.setattr(backup_mod.uuid, "uuid4", lambda: type("U", (), {"hex": "65738f732c5e459ebdb471a472b7c935"})())
    new_temp = target.with_name(backup_mod._compact_temp_name("b"))

    assert len(str(target)) == 221
    assert len(str(old_temp)) == 260
    assert len(str(new_temp)) == 238
    assert target.name not in new_temp.name
    assert new_temp.name == ".fc-b-65738f732c5e459e.part"


def test_backup_atomic_copy_uses_short_same_directory_temp(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "新建文本文档.txt"
    source.write_bytes(b"payload")
    target = tmp_path / "backup" / "deep" / "新建文本文档.txt"
    seen: list[Path] = []
    real_copy = backup_mod._copy_source_to_temp_with_hash

    def capture_copy(src: Path, temp: Path):
        seen.append(temp)
        return real_copy(src, temp)

    monkeypatch.setattr(backup_mod, "_copy_source_to_temp_with_hash", capture_copy)
    digest, source_stat = backup_mod._atomic_copy_to_backup(source, target)

    assert target.read_bytes() == b"payload"
    assert source_stat.st_size == len(b"payload")
    assert len(digest) == 64
    assert len(seen) == 1
    assert seen[0].parent == target.parent
    assert seen[0].name.startswith(".fc-b-")
    assert seen[0].name.endswith(".part")
    assert target.name not in seen[0].name
    assert not seen[0].exists()


def test_restore_temp_name_is_compact_and_does_not_repeat_target(monkeypatch) -> None:
    target = Path(r"C:\very\deep\path\报告最终版.docx")
    monkeypatch.setattr(backup_mod.uuid, "uuid4", lambda: type("U", (), {"hex": "0123456789abcdef0123456789abcdef"})())

    temp = backup_mod._restore_temp_path(target)

    assert temp.name == ".fc-r-0123456789abcdef.part"
    assert target.name not in temp.name
    assert len(temp.name) == 27

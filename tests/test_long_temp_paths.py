from __future__ import annotations

import json
import shutil
from pathlib import Path, PureWindowsPath

import filecheck.backup as backup_mod
from filecheck.backup import create_backup, restore_backup, verify_backup


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


def test_user_reported_mirrored_path_is_still_safe_with_short_temp(monkeypatch) -> None:
    source = Path(
        r"E:\01-task\00-0518\0-0518打包\0-E盘打包\E盘-01_task\01-高速加密卡\01-高速加密卡\底板设计\Hspeed_PCIE_KCU105_V16_good\Hspeed_PCIE.srcs\sources_1\sources\axi_ctrl\AXIS_CTRL_MODULE\新建文本文档.txt"
    )
    staging = Path(r"E:\0908\.FC-20260908-230005-4afcf6b1.incomplete")
    final_dir = Path(r"E:\0908\FC-20260908-230005-4afcf6b1")
    monkeypatch.setattr(backup_mod, "_is_windows", lambda: True)

    rel, mode = backup_mod._select_backup_relpath(source, staging, final_dir)

    assert mode == "mirrored"
    assert rel.as_posix().endswith("AXIS_CTRL_MODULE/新建文本文档.txt")
    assert backup_mod._windows_backup_relpath_is_safe(rel, staging, final_dir)


def test_deeper_mirrored_path_falls_back_to_compact_storage(monkeypatch) -> None:
    source = Path(
        r"E:\01-task\00-0518\0-0518打包\0-E盘打包\E盘-01_task\01-高速加密卡\01-高速加密卡\底板设计\Hspeed_PCIE_KCU105_V16_good\Hspeed_PCIE.srcs\sources_1\sources\axi_ctrl\AXIS_CTRL_MODULE\更深一级目录\再深一级目录\继续增加目录长度\新建文本文档.txt"
    )
    staging = Path(r"E:\0908\.FC-20260908-230005-4afcf6b1.incomplete")
    final_dir = Path(r"E:\0908\FC-20260908-230005-4afcf6b1")
    monkeypatch.setattr(backup_mod, "_is_windows", lambda: True)

    mirrored = backup_mod.backup_relpath(source)
    rel, mode = backup_mod._select_backup_relpath(source, staging, final_dir)

    assert not backup_mod._windows_backup_relpath_is_safe(mirrored, staging, final_dir)
    assert mode == "compact-long-path"
    assert rel.parts[:2] == ("files", "_long")
    assert backup_mod._windows_backup_relpath_is_safe(rel, staging, final_dir)
    assert len(str(backup_mod._windows_full_path(final_dir, rel))) <= backup_mod._WINDOWS_SAFE_PATH_CHARS


def test_compact_storage_path_is_deterministic_and_distinct() -> None:
    first = Path(r"E:\deep\one\报告.docx")
    same = Path(r"E:\deep\one\报告.docx")
    second = Path(r"E:\deep\two\报告.docx")

    assert backup_mod._compact_backup_relpath(first) == backup_mod._compact_backup_relpath(same)
    assert backup_mod._compact_backup_relpath(first) != backup_mod._compact_backup_relpath(second)
    assert backup_mod._compact_backup_relpath(first).suffix == ".docx"


def test_roundtrip_restore_accepts_compact_storage_layout(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source" / "deep" / "报告.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"long-path-payload")

    real_select = backup_mod._select_backup_relpath

    def force_compact(src: Path, staging: Path, final_dir: Path):
        rel = backup_mod._compact_backup_relpath(src)
        return rel, "compact-long-path"

    monkeypatch.setattr(backup_mod, "_select_backup_relpath", force_compact)
    backup = create_backup([source], tmp_path / "backup")
    manifest = verify_backup(backup)

    item = manifest["items"][0]
    assert manifest["storage_layout"] == "mirrored-source-tree-with-compact-fallback-v2"
    assert item["storage_path_mode"] == "compact-long-path"
    assert item["backup_path"].startswith("files/_long/")
    stored = backup / Path(item["backup_path"])
    assert stored.read_bytes() == b"long-path-payload"

    source.unlink()
    restore_backup(backup)
    assert source.read_bytes() == b"long-path-payload"


def test_existing_v020_style_manifest_without_storage_mode_remains_valid(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"legacy-compatible")
    backup = create_backup([source], tmp_path / "backup")
    manifest_path = backup / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["storage_layout"] = "mirrored-source-tree-v1"
    for item in manifest["items"]:
        item.pop("storage_path_mode", None)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    verify_backup(backup)
    source.unlink()
    restore_backup(backup)
    assert source.read_bytes() == b"legacy-compatible"

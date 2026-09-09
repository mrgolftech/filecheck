from __future__ import annotations

from pathlib import Path

import filecheck.fast_index as fast_index
import filecheck.portable_everything as portable


def _drives():
    return [
        portable.DriveInfo(root="C:\\", kind="fixed", filesystem="NTFS"),
        portable.DriveInfo(root="D:\\", kind="fixed", filesystem="NTFS"),
        portable.DriveInfo(root="E:\\", kind="fixed", filesystem="exFAT"),
        portable.DriveInfo(root="F:\\", kind="removable", filesystem="NTFS"),
    ]


def test_default_drive_selection_uses_all_fixed_disks() -> None:
    assert fast_index._select_drives("", _drives()) == ["C:\\", "D:\\", "E:\\"]
    assert fast_index._select_drives("A", _drives()) == ["C:\\", "D:\\", "E:\\"]
    assert fast_index._select_drives("all", _drives()) == ["C:\\", "D:\\", "E:\\"]


def test_drive_selection_accepts_letters_and_explicit_removable() -> None:
    assert fast_index._select_drives("c,d", _drives()) == ["C:\\", "D:\\"]
    assert fast_index._select_drives("D F", _drives()) == ["D:\\", "F:\\"]


def test_split_index_roots_prefers_ntfs_fast_index(monkeypatch) -> None:
    monkeypatch.setattr(portable, "list_windows_drives", _drives)
    ntfs, folders, filesystems = portable._split_index_roots(["C:\\", "D:\\", "E:\\"])
    assert ntfs == ["C:\\", "D:\\"]
    assert folders == ["E:\\"]
    assert filesystems["C:\\"] == "NTFS"
    assert filesystems["E:\\"] == "exFAT"


def test_write_ini_uses_ntfs_volume_keys_and_folder_fallback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(portable, "portable_root", lambda: tmp_path / "runtime" / "everything")
    monkeypatch.setattr(portable, "everything_ini_path", lambda: tmp_path / "runtime" / "everything" / "Everything.ini")
    ini = portable._write_ini(
        ["C:\\", "E:\\"],
        ["X:\\FileCheck", "Y:\\Backup"],
        ntfs_roots=["C:\\"],
        folder_roots=["E:\\"],
    )
    text = ini.read_text(encoding="utf-8")
    assert 'ntfs_volume_paths="C:"' in text
    assert 'ntfs_volume_includes=1' in text
    assert 'ntfs_volume_monitors=1' in text
    assert 'folders=E:\\' in text
    assert 'auto_include_fixed_volumes=0' in text
    assert 'exclude_hidden_files_and_folders=0' in text
    assert 'exclude_system_files_and_folders=0' in text
    assert 'run_in_background=1' in text
    assert 'ipc=1' in text
    assert 'db_location=' not in text

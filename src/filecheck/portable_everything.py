from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .everything import FILECHECK_INSTANCE, EverythingError, EverythingStatus, get_status, reindex
from .util import now_iso, program_dir, runtime_dir, write_json


class PortableEverythingError(EverythingError):
    pass


@dataclass(frozen=True)
class DriveInfo:
    root: str
    kind: str
    filesystem: str = "unknown"


@dataclass(frozen=True)
class PortableIndexResult:
    status: EverythingStatus
    config_path: Path
    database_path: Path
    selected_roots: tuple[str, ...]
    excluded_roots: tuple[str, ...]
    ntfs_roots: tuple[str, ...] = ()
    folder_roots: tuple[str, ...] = ()


def portable_root() -> Path:
    return runtime_dir() / "everything"


def index_state_path() -> Path:
    return portable_root() / "index-config.json"


def everything_ini_path() -> Path:
    return portable_root() / "Everything.ini"


def everything_db_path() -> Path:
    return portable_root() / "Everything.db"


def find_everything_exe(explicit: str | None = None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    env = os.environ.get("FILECHECK_EVERYTHING")
    if env:
        candidates.append(Path(env))
    candidates.append(program_dir() / "tools" / "Everything.exe")
    candidates.append(Path.cwd() / "tools" / "Everything.exe")
    located = shutil.which("Everything.exe") or shutil.which("Everything")
    if located:
        candidates.append(Path(located))

    seen: set[str] = set()
    for candidate in candidates:
        key = os.path.normcase(os.path.abspath(str(candidate)))
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file():
            return candidate.resolve()
    raise PortableEverythingError(
        "未找到 portable Everything.exe。正式发布包应包含 tools/Everything.exe。"
    )


def _filesystem_for_root(root: str) -> str:
    if os.name != "nt":
        return "unknown"
    fs_name = ctypes.create_unicode_buffer(64)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(root),
        None,
        0,
        None,
        None,
        None,
        fs_name,
        len(fs_name),
    )
    if not ok:
        return "unknown"
    return fs_name.value or "unknown"


def list_windows_drives() -> list[DriveInfo]:
    """Return fixed/removable Windows drive roots in drive-letter order."""
    if os.name != "nt":
        return []
    mask = int(ctypes.windll.kernel32.GetLogicalDrives())
    result: list[DriveInfo] = []
    drive_types = {2: "removable", 3: "fixed"}
    for index in range(26):
        if not (mask & (1 << index)):
            continue
        root = f"{chr(ord('A') + index)}:\\"
        dtype = int(ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)))
        if dtype in drive_types:
            result.append(
                DriveInfo(
                    root=root,
                    kind=drive_types[dtype],
                    filesystem=_filesystem_for_root(root),
                )
            )
    return result


def _normalize_roots(values: Iterable[str | Path]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = os.path.abspath(os.path.expanduser(str(raw)))
        if len(text) == 2 and text[1] == ":":
            text += "\\"
        key = os.path.normcase(text.rstrip("\\/") or text)
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _ini_list(values: Iterable[str]) -> str:
    parts: list[str] = []
    for value in values:
        if any(ch in value for ch in (",", '"')):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'"{escaped}"')
        else:
            parts.append(value)
    return ",".join(parts)


def _ini_quoted_list(values: Iterable[str]) -> str:
    parts: list[str] = []
    for value in values:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        parts.append(f'"{escaped}"')
    return ",".join(parts)


def _drive_root(text: str) -> str | None:
    match = re.fullmatch(r"([A-Za-z]):[\\/]?", text.strip())
    if not match:
        return None
    return f"{match.group(1).upper()}:\\"


def _is_admin() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _split_index_roots(selected_roots: list[str]) -> tuple[list[str], list[str], dict[str, str]]:
    ntfs: list[str] = []
    folders: list[str] = []
    filesystems: dict[str, str] = {}
    drive_map = {os.path.normcase(info.root): info for info in list_windows_drives()}

    for root in selected_roots:
        drive = _drive_root(root)
        if drive is None:
            folders.append(root)
            filesystems[root] = "folder"
            continue
        info = drive_map.get(os.path.normcase(drive))
        filesystem = info.filesystem if info else _filesystem_for_root(drive)
        filesystems[drive] = filesystem
        if filesystem.upper() == "NTFS":
            ntfs.append(drive)
        else:
            folders.append(drive)
    return ntfs, folders, filesystems


def _write_ini(
    selected_roots: list[str],
    excluded_roots: list[str],
    *,
    ntfs_roots: list[str],
    folder_roots: list[str],
) -> Path:
    root = portable_root()
    root.mkdir(parents=True, exist_ok=True)
    ini = everything_ini_path()

    ntfs_paths = [drive.rstrip("\\/") for drive in ntfs_roots]
    ntfs_count = len(ntfs_paths)
    monitor = ",".join("1" for _ in folder_roots)
    buffers = ",".join("65536" for _ in folder_roots)
    rescan = ",".join("0" for _ in folder_roots)
    update_types = ",".join("0" for _ in folder_roots)

    lines = [
        "[Everything]",
        "app_data=0",
        "run_as_admin=0",
        "run_in_background=1",
        "ipc=1",
        "auto_include_fixed_volumes=0",
        "auto_include_removable_volumes=0",
        "auto_remove_offline_ntfs_volumes=0",
        "auto_remove_moved_ntfs_volumes=0",
        "exclude_list_enabled=1",
        "exclude_hidden_files_and_folders=1",
        "exclude_system_files_and_folders=1",
        f"exclude_folders={_ini_list(excluded_roots)}",
        f"ntfs_volume_guids={_ini_quoted_list([''] * ntfs_count)}",
        f"ntfs_volume_paths={_ini_quoted_list(ntfs_paths)}",
        f"ntfs_volume_roots={_ini_quoted_list([''] * ntfs_count)}",
        f"ntfs_volume_includes={','.join('1' for _ in ntfs_paths)}",
        f"ntfs_volume_load_recent_changes={','.join('1' for _ in ntfs_paths)}",
        f"ntfs_volume_include_onlys={_ini_quoted_list([''] * ntfs_count)}",
        f"ntfs_volume_monitors={','.join('1' for _ in ntfs_paths)}",
        f"folders={_ini_list(folder_roots)}",
        f"folder_monitor_changes={monitor}",
        f"folder_buffer_size_list={buffers}",
        f"folder_rescan_if_full_list={rescan}",
        f"folder_update_types={update_types}",
        "db_multi_user_filename=0",
        "db_compress=0",
        "check_for_updates_on_startup=0",
        "show_tray_icon=0",
        "",
    ]
    ini.write_text("\r\n".join(lines), encoding="utf-8")
    return ini


def _creationflags() -> int:
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def _run_everything(exe: Path, args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(exe), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
        creationflags=_creationflags(),
    )


def stop_instance(everything: str | None = None) -> None:
    exe = find_everything_exe(everything)
    try:
        _run_everything(exe, ["-instance", FILECHECK_INSTANCE, "-exit"], timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass


def start_instance(
    everything: str | None = None,
    *,
    es: str | None = None,
    wait_seconds: int = 20,
) -> EverythingStatus:
    exe = find_everything_exe(everything)
    ini = everything_ini_path()
    db = everything_db_path()
    if not ini.is_file():
        raise PortableEverythingError("尚未创建 FileCheck 索引配置，请先选择磁盘并建立索引。")

    subprocess.Popen(
        [
            str(exe),
            "-instance",
            FILECHECK_INSTANCE,
            "-config",
            str(ini),
            "-db",
            str(db),
            "-startup",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_creationflags(),
    )

    deadline = time.time() + max(1, wait_seconds)
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            return get_status(es, instance=FILECHECK_INSTANCE)
        except Exception as exc:
            last_error = exc
            time.sleep(0.25)
    raise PortableEverythingError(f"FileCheck 专用 Everything 实例启动超时: {last_error}")


def configure_and_reindex(
    selected_roots: Iterable[str | Path],
    backup_root: str | Path,
    *,
    additional_excluded_roots: Iterable[str | Path] = (),
    everything: str | None = None,
    es: str | None = None,
    progress: Callable[[float], None] | None = None,
) -> PortableIndexResult:
    selected = _normalize_roots(selected_roots)
    if not selected:
        raise PortableEverythingError("至少选择一个要建立索引的磁盘/目录")

    backup = os.path.abspath(os.path.expanduser(str(backup_root)))
    backup_roots = _normalize_roots([backup, *list(additional_excluded_roots)])
    excluded = _normalize_roots([program_dir(), *backup_roots])
    ntfs_roots, folder_roots, filesystems = _split_index_roots(selected)

    if ntfs_roots and os.name == "nt" and not _is_admin():
        drives = ", ".join(ntfs_roots)
        raise PortableEverythingError(
            f"NTFS 快速索引需要读取 MFT/USN。当前 FileCheck 未以管理员权限运行。"
            f"请右键“以管理员身份运行”后重试。NTFS 磁盘: {drives}"
        )

    try:
        stop_instance(everything)
        time.sleep(0.3)
    except PortableEverythingError:
        pass

    ini = _write_ini(
        selected,
        excluded,
        ntfs_roots=ntfs_roots,
        folder_roots=folder_roots,
    )
    status = start_instance(everything, es=es)
    reindex(es, instance=FILECHECK_INSTANCE, timeout=1800, progress=progress)
    status = get_status(es, instance=FILECHECK_INSTANCE)

    if ntfs_roots and not folder_roots:
        index_mode = "portable-ntfs-fast"
    elif ntfs_roots:
        index_mode = "portable-hybrid"
    else:
        index_mode = "portable-folder-index"

    state = {
        "schema_version": 1,
        "updated_at": now_iso(),
        "instance": FILECHECK_INSTANCE,
        "index_mode": index_mode,
        "selected_roots": selected,
        "ntfs_roots": ntfs_roots,
        "folder_roots": folder_roots,
        "filesystems": filesystems,
        "backup_root": backup_roots[0],
        "backup_roots": backup_roots,
        "excluded_roots": excluded,
        "everything_exe": str(find_everything_exe(everything)),
        "everything_version": status.everything_version,
        "es_version": status.es_version,
        "config_path": str(ini),
        "database_path": str(everything_db_path()),
    }
    write_json(index_state_path(), state)
    return PortableIndexResult(
        status=status,
        config_path=ini,
        database_path=everything_db_path(),
        selected_roots=tuple(selected),
        excluded_roots=tuple(excluded),
        ntfs_roots=tuple(ntfs_roots),
        folder_roots=tuple(folder_roots),
    )


def load_index_state(*, required: bool = True) -> dict | None:
    path = index_state_path()
    if not path.is_file():
        if required:
            raise PortableEverythingError("尚未建立 FileCheck 专用索引，请先执行“环境与索引”。")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PortableEverythingError(f"索引状态文件损坏: {path}") from exc
    if payload.get("schema_version") != 1:
        raise PortableEverythingError("不支持的索引状态版本")
    return payload


def ensure_instance(es: str | None = None, everything: str | None = None) -> EverythingStatus:
    try:
        return get_status(es, instance=FILECHECK_INSTANCE)
    except EverythingError:
        return start_instance(everything, es=es)

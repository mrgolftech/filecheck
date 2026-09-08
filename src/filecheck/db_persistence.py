from __future__ import annotations

import subprocess
import time
from dataclasses import replace
from pathlib import Path
from typing import Callable, Iterable

from .everything import FILECHECK_INSTANCE, EverythingError, EverythingStatus, find_es, get_status
from . import portable_everything as portable


_ORIGINAL_CONFIGURE_AND_REINDEX = portable.configure_and_reindex


def database_path() -> Path:
    """Return the explicit DB file used by the dedicated FileCheck instance."""
    return portable.portable_root() / f"Everything-{FILECHECK_INSTANCE}.db"


def _remove_legacy_empty_db_directory() -> None:
    """Remove the v0.1.1 bug artifact: an empty directory named Everything.db."""
    legacy = portable.portable_root() / "Everything.db"
    if not legacy.is_dir():
        return
    try:
        legacy.rmdir()
    except OSError as exc:
        raise portable.PortableEverythingError(
            f"检测到旧版错误创建的数据库目录且目录非空，请先人工检查后删除: {legacy}"
        ) from exc


def start_instance(
    everything: str | None = None,
    *,
    es: str | None = None,
    wait_seconds: int = 20,
) -> EverythingStatus:
    exe = portable.find_everything_exe(everything)
    ini = portable.everything_ini_path()
    db = database_path()
    if not ini.is_file():
        raise portable.PortableEverythingError("尚未创建 FileCheck 索引配置，请先选择磁盘并建立索引。")

    # Use one and only one database-location mechanism: an explicit -db file.
    # Do not also set db_location in the INI. -startup plus the INI's
    # run_in_background=1 keeps the dedicated instance headless.
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
        creationflags=portable._creationflags(),
    )

    deadline = time.time() + max(1, wait_seconds)
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            return get_status(es, instance=FILECHECK_INSTANCE)
        except Exception as exc:
            last_error = exc
            time.sleep(0.25)
    raise portable.PortableEverythingError(f"FileCheck 专用 Everything 实例启动超时: {last_error}")


def _flush_database_to_disk(
    everything: str | None = None,
    *,
    es: str | None = None,
    wait_seconds: int = 30,
) -> Path:
    """Persist the live Everything DB through ES IPC without opening a GUI."""
    del everything  # persistence is sent to the already-running named instance through ES
    es_path = find_es(es)
    command = [
        str(es_path),
        "-argv",
        "-instance",
        FILECHECK_INSTANCE,
        "-save-db",
    ]
    proc = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=60,
        creationflags=portable._creationflags(),
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).decode(errors="replace").strip()
        raise portable.PortableEverythingError(
            f"Everything 索引已完成，但数据库写盘失败，exit={proc.returncode}"
            + (f"，{detail}" if detail else "")
        )

    db = database_path()
    deadline = time.time() + max(1, wait_seconds)
    while time.time() < deadline:
        try:
            if db.is_file() and db.stat().st_size > 0:
                return db
        except OSError:
            pass
        time.sleep(0.2)

    raise portable.PortableEverythingError(
        f"Everything 已通过 ES 完成数据库保存，但未找到预期文件: {db}"
    )


def configure_and_reindex(
    selected_roots: Iterable[str | Path],
    backup_root: str | Path,
    *,
    everything: str | None = None,
    es: str | None = None,
    progress: Callable[[float], None] | None = None,
) -> portable.PortableIndexResult:
    _remove_legacy_empty_db_directory()
    result = _ORIGINAL_CONFIGURE_AND_REINDEX(
        selected_roots,
        backup_root,
        everything=everything,
        es=es,
        progress=progress,
    )
    db = _flush_database_to_disk(everything, es=es)
    return replace(result, database_path=db)


def ensure_instance(es: str | None = None, everything: str | None = None) -> EverythingStatus:
    try:
        return get_status(es, instance=FILECHECK_INSTANCE)
    except EverythingError:
        return start_instance(everything, es=es)


def install() -> None:
    """Install the hardened DB path/startup behavior into portable_everything."""
    portable.everything_db_path = database_path
    portable.start_instance = start_instance

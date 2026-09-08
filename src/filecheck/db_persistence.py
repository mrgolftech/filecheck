from __future__ import annotations

import subprocess
import time
from dataclasses import replace
from pathlib import Path
from typing import Callable, Iterable

from .everything import FILECHECK_INSTANCE, EverythingError, EverythingStatus, get_status
from . import portable_everything as portable


_ORIGINAL_CONFIGURE_AND_REINDEX = portable.configure_and_reindex


def database_path() -> Path:
    """Return the actual database filename for the dedicated named instance.

    Everything named instances use Everything-<instance>.db.  FileCheck relies
    on db_location for the directory and deliberately does not pass -db, which
    avoids treating a filename as a database directory on some Everything 1.4
    portable runs.
    """
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
    if not ini.is_file():
        raise portable.PortableEverythingError("尚未创建 FileCheck 索引配置，请先选择磁盘并建立索引。")

    # db_location in Everything.ini is the single source of truth for the
    # database directory. Named instance FileCheck then uses
    # Everything-FileCheck.db inside that directory.
    subprocess.Popen(
        [
            str(exe),
            "-instance",
            FILECHECK_INSTANCE,
            "-config",
            str(ini),
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
    wait_seconds: int = 30,
) -> Path:
    exe = portable.find_everything_exe(everything)
    db = database_path()
    proc = portable._run_everything(
        exe,
        ["-instance", FILECHECK_INSTANCE, "-update", "-no-first-instance"],
        timeout=60,
    )
    if proc.returncode != 0:
        raise portable.PortableEverythingError(
            f"Everything 索引已完成，但数据库写盘失败，exit={proc.returncode}"
        )

    deadline = time.time() + max(1, wait_seconds)
    while time.time() < deadline:
        try:
            if db.is_file() and db.stat().st_size > 0:
                return db
        except OSError:
            pass
        time.sleep(0.2)

    raise portable.PortableEverythingError(
        f"Everything 索引已完成，但未生成有效数据库文件: {db}"
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
    db = _flush_database_to_disk(everything)
    return replace(result, database_path=db)


def ensure_instance(es: str | None = None, everything: str | None = None) -> EverythingStatus:
    try:
        return get_status(es, instance=FILECHECK_INSTANCE)
    except EverythingError:
        return start_instance(everything, es=es)


def install() -> None:
    """Install the fixed DB path/startup behavior into portable_everything."""
    portable.everything_db_path = database_path
    portable.start_instance = start_instance

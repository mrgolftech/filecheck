from __future__ import annotations

import os
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from typing import Callable, Iterable

from .everything import FILECHECK_INSTANCE, EverythingError, EverythingStatus, find_es, get_status
from . import portable_everything as portable


_ORIGINAL_CONFIGURE_AND_REINDEX = portable.configure_and_reindex


def database_path() -> Path:
    """Return the one explicit DB file used by the dedicated FileCheck instance."""
    return portable.portable_root() / f"Everything-{FILECHECK_INSTANCE}.db"


def _hidden_startupinfo():
    if os.name != "nt" or not hasattr(subprocess, "STARTUPINFO"):
        return None
    info = subprocess.STARTUPINFO()
    info.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    info.wShowWindow = 0
    return info


def _remove_legacy_empty_db_directory() -> None:
    legacy = portable.portable_root() / "Everything.db"
    if not legacy.is_dir():
        return
    try:
        legacy.rmdir()
    except OSError as exc:
        raise portable.PortableEverythingError(
            f"检测到旧版错误创建的数据库目录且目录非空，请先人工检查后删除: {legacy}"
        ) from exc


def _remove_legacy_wrong_db_file_after_success(db: Path) -> None:
    legacy = portable.portable_root() / "Everything.db"
    try:
        if legacy.is_file() and legacy.resolve() != db.resolve():
            legacy.unlink()
    except OSError:
        pass


def _invalidate_index_state() -> None:
    state = portable.index_state_path()
    for candidate in (state, state.with_suffix(state.suffix + ".tmp")):
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            pass


def stop_instance(
    everything: str | None = None,
    *,
    es: str | None = None,
    wait_seconds: int = 10,
) -> None:
    """Stop only an actually-running FileCheck instance and wait for IPC exit."""
    try:
        get_status(es, instance=FILECHECK_INSTANCE)
    except Exception:
        return

    exe = portable.find_everything_exe(everything)
    try:
        subprocess.run(
            [str(exe), "-instance", FILECHECK_INSTANCE, "-exit"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
            creationflags=portable._creationflags(),
            startupinfo=_hidden_startupinfo(),
        )
    except (OSError, subprocess.SubprocessError):
        pass

    deadline = time.time() + max(1, wait_seconds)
    while time.time() < deadline:
        try:
            get_status(es, instance=FILECHECK_INSTANCE)
        except Exception:
            return
        time.sleep(0.1)
    raise portable.PortableEverythingError("旧的 FileCheck Everything 实例未能完全退出，请稍后重试。")


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
    db.parent.mkdir(parents=True, exist_ok=True)

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
        startupinfo=_hidden_startupinfo(),
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
    del everything
    es_path = find_es(es)
    command = [str(es_path), "-argv", "-instance", FILECHECK_INSTANCE, "-save-db"]
    proc = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=60,
        creationflags=portable._creationflags(),
        startupinfo=_hidden_startupinfo(),
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
    # GUI imports this function directly and does not pass through launcher.py.
    # Install here so every entry point uses the same named DB/start/stop path.
    install()
    _remove_legacy_empty_db_directory()
    try:
        result = _ORIGINAL_CONFIGURE_AND_REINDEX(
            selected_roots,
            backup_root,
            everything=everything,
            es=es,
            progress=progress,
        )
        db = _flush_database_to_disk(everything, es=es)
    except BaseException:
        _invalidate_index_state()
        raise

    _remove_legacy_wrong_db_file_after_success(db)
    return replace(result, database_path=db)


def ensure_instance(es: str | None = None, everything: str | None = None) -> EverythingStatus:
    install()
    try:
        return get_status(es, instance=FILECHECK_INSTANCE)
    except EverythingError:
        return start_instance(everything, es=es)


def install() -> None:
    """Install hardened DB path/start/stop behavior into portable_everything."""
    portable.everything_db_path = database_path
    portable.start_instance = start_instance
    portable.stop_instance = stop_instance

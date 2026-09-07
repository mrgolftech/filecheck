from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Iterable

from .backup import (
    BackupError,
    ProgressCallback,
    _atomic_copy_to_backup,
    _create_zip_from_staging,
    verify_backup,
)
from .util import app_data_dir, make_batch_id, now_iso, read_json, safe_component, sha256_file, write_json


_OPERATION_SCHEMA_VERSION = 1
_CHECKPOINT_EVERY = 25
_MIN_FREE_RESERVE = 16 * 1024 * 1024
_MAX_FREE_RESERVE = 512 * 1024 * 1024


def _notify(progress: ProgressCallback | None, stage: str, current: int, total: int, path: str | Path) -> None:
    if progress is not None:
        progress(stage, current, total, str(path))


def _io_path(path: str | Path) -> Path:
    """Return a Windows extended-length path for actual file I/O.

    The scan manifest must keep the ordinary absolute path because that is the
    path users know and the path restore targets.  File I/O is a different
    concern: a mirrored backup destination can easily become longer than the
    original source path.  Using the Win32 extended-length prefix prevents a
    portable FileCheck build from depending on the machine-wide MAX_PATH policy.
    """

    path = Path(path)
    if os.name != "nt":
        return path

    raw = os.path.abspath(str(path))
    if raw.startswith("\\\\?\\"):
        return Path(raw)
    if raw.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + raw[2:])
    return Path("\\\\?\\" + raw)


def _display_path_from_io(value: str | Path) -> str:
    raw = str(value)
    if os.name != "nt":
        return raw
    if raw.startswith("\\\\?\\UNC\\"):
        return "\\\\" + raw[8:]
    if raw.startswith("\\\\?\\"):
        return raw[4:]
    return raw


def _absolute_source_text(raw: str | Path) -> str:
    return os.path.abspath(os.path.expanduser(str(raw)))


def _is_within_text(child: str, parent: str) -> bool:
    try:
        common = os.path.commonpath([os.path.normcase(child), os.path.normcase(parent)])
    except ValueError:
        return False
    return common == os.path.normcase(parent)


def _expand_sources(sources: Iterable[str | Path], destination_root: Path) -> list[str]:
    """Expand explicit directories while retaining missing indexed file paths.

    scan-results.json can legitimately contain an indexed path that disappears
    before backup begins.  We keep such file entries in the operation plan so
    the batch reports the exact failure and can retry after the user fixes the
    condition, rather than failing before a resumable state exists.
    """

    result: list[str] = []
    seen: set[str] = set()
    dest_text = os.path.abspath(str(destination_root))

    for raw in sources:
        source_text = _absolute_source_text(raw)
        source_io = _io_path(source_text)

        try:
            is_link = source_io.is_symlink()
        except OSError:
            is_link = False
        if is_link:
            raise BackupError(f"V0.1 不处理符号链接/重解析入口: {source_text}")

        try:
            is_dir = source_io.is_dir()
        except OSError:
            is_dir = False

        if is_dir:
            if _is_within_text(dest_text, source_text):
                raise BackupError(f"备份目标不能位于待备份源目录内部: {source_text}")
            for root, dirs, files in os.walk(str(source_io), followlinks=False):
                # Do not descend through directory symlinks/reparse points.
                kept_dirs: list[str] = []
                for name in dirs:
                    candidate = Path(root) / name
                    try:
                        if not candidate.is_symlink():
                            kept_dirs.append(name)
                    except OSError:
                        continue
                dirs[:] = kept_dirs
                for name in files:
                    candidate_io = Path(root) / name
                    try:
                        if candidate_io.is_symlink():
                            continue
                    except OSError:
                        continue
                    candidate_text = _display_path_from_io(candidate_io)
                    key = os.path.normcase(os.path.abspath(candidate_text))
                    if key not in seen:
                        seen.add(key)
                        result.append(os.path.abspath(candidate_text))
            continue

        # Treat a non-directory entry as an intended file even when it is
        # currently missing/inaccessible.  The copy phase records a precise
        # per-file failure and leaves the operation resumable.
        key = os.path.normcase(source_text)
        if key not in seen:
            seen.add(key)
            result.append(source_text)

    if not result:
        raise BackupError("没有可备份的普通文件")
    return result


def _compact_backup_relpath(source_text: str) -> Path:
    """Map a source path to a short collision-resistant storage path.

    Mirroring the complete absolute source tree below ``files/`` adds tens of
    characters and can push an otherwise valid Windows source beyond MAX_PATH.
    The manifest already carries the authoritative original path, so the payload
    storage path can be compact without changing restore semantics.
    """

    identity = os.path.normcase(os.path.abspath(source_text))
    digest = hashlib.sha256(identity.encode("utf-8", errors="surrogatepass")).hexdigest()
    suffix = safe_component(Path(source_text).suffix)[:16]
    if suffix and not suffix.startswith("."):
        suffix = "." + suffix
    return Path("files") / digest[:2] / f"{digest}{suffix}"


def operation_state_path(batch_id: str) -> Path:
    return app_data_dir() / "operations" / f"{batch_id}.operation.json"


def _operation_paths(destination_root: Path, batch_id: str) -> tuple[Path, Path, Path]:
    return (
        destination_root / f".{batch_id}.incomplete",
        destination_root / batch_id,
        destination_root / f"{batch_id}.zip",
    )


def _validate_batch_id(batch_id: str) -> str:
    if not batch_id.startswith("FC-") or any(ch in batch_id for ch in ("/", "\\", ":")):
        raise BackupError(f"非法备份批次 ID: {batch_id}")
    return batch_id


def _new_state(
    sources: list[str],
    destination_root: Path,
    *,
    batch_id: str,
    zip_mode: bool,
    operation: str,
) -> dict:
    created = now_iso()
    items = []
    for source_text in sources:
        rel = _compact_backup_relpath(source_text)
        planned_size: int | None = None
        try:
            source_io = _io_path(source_text)
            if source_io.is_file():
                planned_size = int(source_io.stat().st_size)
        except OSError:
            planned_size = None
        items.append(
            {
                "source_path": source_text,
                "backup_path": rel.as_posix(),
                "planned_size": planned_size,
                "size": None,
                "mtime_ns": None,
                "sha256": None,
                "state": "pending",
                "error": None,
            }
        )

    return {
        "schema_version": _OPERATION_SCHEMA_VERSION,
        "kind": "filecheck-operation",
        "operation": operation,
        "batch_id": batch_id,
        "created_at": created,
        "updated_at": created,
        "status": "copying",
        "destination_root": str(destination_root),
        "zip_mode": bool(zip_mode),
        "storage_layout": "compact-path-sha256-v1",
        "backup_path": None,
        "last_error": None,
        "total": len(items),
        "copied": 0,
        "failed": 0,
        "items": items,
    }


def _recount(state: dict) -> None:
    rows = state.get("items", [])
    state["total"] = len(rows)
    state["copied"] = sum(row.get("state") == "copied" for row in rows)
    state["failed"] = sum(row.get("state") == "failed" for row in rows)
    state["updated_at"] = now_iso()


def save_operation_state(state_path: str | Path, state: dict) -> Path:
    path = Path(state_path).expanduser().resolve()
    _recount(state)
    write_json(path, state)
    return path


def load_operation_state(state_path: str | Path) -> dict:
    path = Path(state_path).expanduser().resolve()
    if not path.is_file():
        raise BackupError(f"操作状态文件不存在: {path}")
    state = read_json(path)
    if not isinstance(state, dict) or state.get("kind") != "filecheck-operation":
        raise BackupError(f"不是 FileCheck 批处理操作状态文件: {path}")
    if state.get("schema_version") != _OPERATION_SCHEMA_VERSION:
        raise BackupError("不支持的操作状态 schema_version")
    batch_id = _validate_batch_id(str(state.get("batch_id", "")))
    if state.get("operation") not in ("backup", "migrate"):
        raise BackupError(f"未知操作类型: {state.get('operation')}")
    if not isinstance(state.get("items"), list) or not state["items"]:
        raise BackupError("操作状态中没有有效 items")
    if Path(str(state.get("destination_root", ""))).expanduser().resolve() == Path("").resolve():
        raise BackupError("操作状态缺少有效 destination_root")
    state["batch_id"] = batch_id
    return state


def discover_operation_states(*, include_completed: bool = False) -> list[tuple[Path, dict]]:
    root = app_data_dir() / "operations"
    if not root.is_dir():
        return []
    results: list[tuple[Path, dict]] = []
    for path in root.glob("*.operation.json"):
        try:
            state = load_operation_state(path)
        except Exception:
            continue
        if include_completed or state.get("status") not in ("completed", "migration_completed"):
            results.append((path, state))
    results.sort(key=lambda row: row[0].stat().st_mtime, reverse=True)
    return results


def _capacity_check(destination_root: Path, state: dict) -> None:
    known = sum(
        int(row["planned_size"])
        for row in state["items"]
        if isinstance(row.get("planned_size"), int) and row["planned_size"] >= 0
    )
    reserve = max(_MIN_FREE_RESERVE, min(_MAX_FREE_RESERVE, known // 20))
    required = known * (2 if state.get("zip_mode") else 1) + reserve
    try:
        free = int(shutil.disk_usage(destination_root).free)
    except OSError:
        return
    if free < required:
        raise BackupError(
            "备份目标可用空间不足："
            f"预计至少需要 {required} 字节，当前可用 {free} 字节"
        )


def _target_for(staging: Path, row: dict) -> Path:
    return staging / Path(str(row["backup_path"]).replace("/", os.sep))


def _copied_payload_still_valid(staging: Path, row: dict) -> bool:
    if row.get("state") != "copied":
        return False
    if not isinstance(row.get("size"), int) or not isinstance(row.get("sha256"), str):
        return False
    target = _io_path(_target_for(staging, row))
    try:
        if not target.is_file() or target.stat().st_size != row["size"]:
            return False
        return sha256_file(target).lower() == row["sha256"].lower()
    except OSError:
        return False


def _copy_one(staging: Path, row: dict) -> None:
    source_text = str(row["source_path"])
    source = _io_path(source_text)
    target = _io_path(_target_for(staging, row))

    try:
        if source.is_symlink():
            raise BackupError("源路径是符号链接/重解析入口")
        if not source.exists():
            raise BackupError("源路径不存在")
        if not source.is_file():
            raise BackupError("源路径不是普通文件")
        digest, source_stat = _atomic_copy_to_backup(source, target)
    except (BackupError, OSError) as exc:
        raise BackupError(f"{source_text}: {exc}") from exc

    row["size"] = int(source_stat.st_size)
    row["mtime_ns"] = int(source_stat.st_mtime_ns)
    row["sha256"] = digest
    row["state"] = "copied"
    row["error"] = None


def _manifest_from_state(state: dict) -> dict:
    copied = [row for row in state["items"] if row.get("state") == "copied"]
    if len(copied) != len(state["items"]):
        raise BackupError("操作状态仍有未成功复制的文件，不能生成完整 manifest")
    total_bytes = sum(int(row["size"]) for row in copied)
    return {
        "schema_version": 1,
        "batch_id": state["batch_id"],
        "created_at": state["created_at"],
        "mode": "zip" if state.get("zip_mode") else "directory",
        "source_removed": False,
        "copy_strategy": "resumable-single-pass-sha256-v1",
        "storage_layout": state.get("storage_layout", "compact-path-sha256-v1"),
        "source_bytes_total": total_bytes,
        "space_required_estimate": None,
        "space_free_at_start": None,
        "items": [
            {
                "source_path": row["source_path"],
                "backup_path": row["backup_path"],
                "size": int(row["size"]),
                "mtime_ns": int(row["mtime_ns"]),
                "sha256": row["sha256"],
                "backup_verified": True,
                "source_removed": False,
            }
            for row in copied
        ],
    }


def _first_failure_summary(state: dict) -> str:
    failures = [row for row in state["items"] if row.get("state") == "failed"]
    if not failures:
        return ""
    first = failures[0]
    extra = len(failures) - 1
    suffix = f"；另有 {extra} 个失败文件" if extra else ""
    return f"首个失败: {first['source_path']} -> {first.get('error')}{suffix}"


def _final_candidate(state: dict) -> Path:
    destination_root = Path(str(state["destination_root"])).expanduser().resolve()
    _, final_dir, archive = _operation_paths(destination_root, state["batch_id"])
    return archive if state.get("zip_mode") else final_dir


def _finish_verified_backup(
    state_path: Path,
    state: dict,
    staging: Path,
    *,
    progress: ProgressCallback | None,
) -> Path:
    manifest = _manifest_from_state(state)
    write_json(staging / "manifest.json", manifest)
    state["status"] = "verifying"
    state["last_error"] = None
    save_operation_state(state_path, state)

    total = len(manifest["items"])
    _notify(progress, "verify_begin", 0, total, "")

    destination_root = Path(str(state["destination_root"])).expanduser().resolve()
    _, final_dir, archive = _operation_paths(destination_root, state["batch_id"])

    if state.get("zip_mode"):
        _create_zip_from_staging(staging, archive, progress=progress)
        shutil.rmtree(_io_path(staging))
        result = archive
    else:
        verify_backup(_io_path(staging), progress=progress)
        os.replace(_io_path(staging), _io_path(final_dir))
        result = final_dir

    state["backup_path"] = str(result)
    state["status"] = "backup_verified" if state.get("operation") == "migrate" else "completed"
    state["last_error"] = None
    save_operation_state(state_path, state)
    return result


def create_resumable_backup(
    sources: Iterable[str | Path],
    destination_root: str | Path,
    *,
    zip_mode: bool = False,
    progress: ProgressCallback | None = None,
    operation: str = "backup",
    batch_id: str | None = None,
) -> tuple[Path, Path, dict]:
    """Create a backup with a durable, user-resumable operation journal.

    No final backup is published until every planned file has been copied and a
    full SHA-256 verification has passed.  Per-file failures are collected so a
    1,500-file run does not lose the first 1,499 successful copies merely because
    the last file disappears or is temporarily inaccessible.
    """

    if operation not in ("backup", "migrate"):
        raise BackupError(f"未知批处理操作: {operation}")

    destination = Path(destination_root).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    planned = _expand_sources(sources, destination)
    batch = _validate_batch_id(batch_id or make_batch_id())
    state_path = operation_state_path(batch).resolve()
    if state_path.exists():
        raise BackupError(f"操作状态已存在，请使用继续功能: {state_path}")

    staging, final_dir, archive = _operation_paths(destination, batch)
    if staging.exists() or final_dir.exists() or archive.exists():
        raise BackupError(f"备份批次已存在: {batch}")
    staging.mkdir(parents=True, exist_ok=False)

    state = _new_state(
        planned,
        destination,
        batch_id=batch,
        zip_mode=zip_mode,
        operation=operation,
    )
    save_operation_state(state_path, state)
    _capacity_check(destination, state)
    return _run_operation(state_path, state, progress=progress)


def _run_operation(
    state_path: Path,
    state: dict,
    *,
    progress: ProgressCallback | None = None,
) -> tuple[Path, Path, dict]:
    destination = Path(str(state["destination_root"])).expanduser().resolve()
    staging, final_dir, archive = _operation_paths(destination, state["batch_id"])
    final = archive if state.get("zip_mode") else final_dir

    # Crash window: publication may have succeeded immediately before the state
    # checkpoint.  Trust it only after a fresh complete verification.
    if final.exists():
        verify_backup(_io_path(final), progress=progress)
        state["backup_path"] = str(final)
        state["status"] = "backup_verified" if state.get("operation") == "migrate" else "completed"
        state["last_error"] = None
        save_operation_state(state_path, state)
        return final, state_path, state

    if not staging.is_dir():
        raise BackupError(
            f"未完成批次的暂存目录不存在，无法续传: {staging}；状态文件: {state_path}"
        )

    # Revalidate copied checkpoints before skipping them on resume.  Any missing
    # or corrupted partial payload is simply copied again from the source.
    if state.get("status") not in ("copying",):
        for row in state["items"]:
            if row.get("state") == "copied" and not _copied_payload_still_valid(staging, row):
                row["state"] = "pending"
                row["error"] = "未完成暂存副本缺失或校验失败，准备重新复制"

    total = len(state["items"])
    state["status"] = "copying"
    state["last_error"] = None
    save_operation_state(state_path, state)

    try:
        for index, row in enumerate(state["items"], start=1):
            if row.get("state") == "copied":
                _notify(progress, "copy", index, total, row["source_path"])
                continue

            row["state"] = "pending"
            row["error"] = None
            _notify(progress, "copy_begin", index, total, row["source_path"])
            try:
                _copy_one(staging, row)
            except (BackupError, OSError) as exc:
                row["state"] = "failed"
                row["error"] = str(exc)
                _notify(progress, "copy_error", index, total, f"{row['source_path']} -> {exc}")
            else:
                _notify(progress, "copy", index, total, row["source_path"])

            if row.get("state") == "failed" or index % _CHECKPOINT_EVERY == 0 or index == total:
                save_operation_state(state_path, state)

        _recount(state)
        if state["failed"]:
            state["status"] = "copy_failed"
            state["last_error"] = _first_failure_summary(state)
            save_operation_state(state_path, state)
            raise BackupError(
                f"批量复制未完整完成：成功 {state['copied']}/{state['total']}，"
                f"失败 {state['failed']}。{state['last_error']}。"
                f"已保留未完成副本；状态文件: {state_path}"
            )

        result = _finish_verified_backup(state_path, state, staging, progress=progress)
        return result, state_path, state
    except KeyboardInterrupt:
        state["status"] = "interrupted"
        state["last_error"] = "用户中断"
        try:
            save_operation_state(state_path, state)
        finally:
            raise
    except Exception as exc:
        if state.get("status") not in ("copy_failed", "completed", "backup_verified"):
            state["status"] = "failed"
            state["last_error"] = str(exc)
            try:
                save_operation_state(state_path, state)
            except Exception:
                pass
        raise


def resume_resumable_backup(
    state_path: str | Path,
    *,
    progress: ProgressCallback | None = None,
) -> tuple[Path, Path, dict]:
    path = Path(state_path).expanduser().resolve()
    state = load_operation_state(path)
    return _run_operation(path, state, progress=progress)


def mark_operation_state(state_path: str | Path, status: str, **updates: object) -> dict:
    path = Path(state_path).expanduser().resolve()
    state = load_operation_state(path)
    state["status"] = status
    state.update(updates)
    save_operation_state(path, state)
    return state

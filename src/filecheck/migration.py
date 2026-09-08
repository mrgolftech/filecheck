from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from .backup import BackupError, ProgressCallback, verify_backup
from .util import now_iso, read_json, sha256_file, write_json, write_text


class MigrationError(BackupError):
    pass


_STATE_SCHEMA_VERSION = 2
_DEFAULT_CHECKPOINT_EVERY = 1
_ALLOWED_ITEM_STATES = {"pending", "deleted", "already_absent", "failed", "reappeared"}
_STATE_NAME = "source-removal.json"
_FAILED_REPORT_NAME = "not-deleted.txt"


def migration_state_path(backup: str | Path) -> Path:
    backup_path = Path(backup).expanduser().resolve()
    if not backup_path.is_dir():
        raise MigrationError("v0.1.1 只支持目录备份的源文件删除")
    return backup_path / _STATE_NAME


def failed_report_path(backup: str | Path) -> Path:
    backup_path = Path(backup).expanduser().resolve()
    if not backup_path.is_dir():
        raise MigrationError("v0.1.1 只支持目录备份")
    return backup_path / _FAILED_REPORT_NAME


def _notify(progress: ProgressCallback | None, stage: str, current: int, total: int, path: str | Path) -> None:
    if progress is not None:
        progress(stage, current, total, str(path))


def _entry_exists(path: Path) -> bool:
    try:
        return path.exists() or path.is_symlink()
    except OSError:
        return True


def _check_source_item(item: dict) -> tuple[bool, str | None]:
    source = Path(item["source_path"])
    try:
        if source.is_symlink():
            return False, "源路径已变成符号链接/重解析入口"
        if not source.exists():
            return False, "源文件不存在"
        if not source.is_file():
            return False, "源路径已不是普通文件"
        before = source.stat()
        if before.st_size != item["size"]:
            return False, "文件大小已变化"
        digest = sha256_file(source)
        after = source.stat()
        if (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or getattr(before, "st_ino", 0) != getattr(after, "st_ino", 0)
        ):
            return False, "源文件在复核过程中发生变化"
        if digest.lower() != str(item["sha256"]).lower():
            return False, "SHA-256 已变化"
    except OSError as exc:
        return False, f"源文件无法复核: {exc}"
    return True, None


def _preflight_items(items: Iterable[dict], *, progress: ProgressCallback | None = None) -> None:
    rows = list(items)
    total = len(rows)
    problems: list[tuple[str, str]] = []
    problem_count = 0
    for index, item in enumerate(rows, start=1):
        ok, reason = _check_source_item(item)
        if not ok:
            problem_count += 1
            if len(problems) < 10:
                problems.append((str(item["source_path"]), reason or "未知原因"))
        _notify(progress, "recheck", index, total, item["source_path"])
    if problem_count:
        detail = "；".join(f"{path}: {reason}" for path, reason in problems)
        if problem_count > len(problems):
            detail += f"；另有 {problem_count - len(problems)} 个异常文件"
        raise MigrationError(
            f"源文件批量复核失败，共 {problem_count} 个文件与已验证备份不一致；"
            f"未删除任何源文件。{detail}"
        )


def preflight_migration(backup: str | Path, *, progress: ProgressCallback | None = None) -> dict:
    backup_path = Path(backup).expanduser().resolve()
    manifest = verify_backup(backup_path)
    _preflight_items(manifest["items"], progress=progress)
    return {
        "backup_path": str(backup_path),
        "batch_id": manifest.get("batch_id"),
        "files": len(manifest["items"]),
        "bytes": sum(int(item["size"]) for item in manifest["items"]),
    }


def _new_state(backup: Path, manifest: dict) -> dict:
    created = now_iso()
    return {
        "schema_version": _STATE_SCHEMA_VERSION,
        "kind": "filecheck-source-removal",
        "batch_id": manifest.get("batch_id"),
        "backup_path": str(backup),
        "created_at": created,
        "updated_at": created,
        "status": "removing",
        "total": len(manifest["items"]),
        "deleted": 0,
        "already_absent": 0,
        "failed": 0,
        "items": [
            {
                "source_path": item["source_path"],
                "size": item["size"],
                "sha256": item["sha256"],
                "state": "pending",
                "error": None,
            }
            for item in manifest["items"]
        ],
    }


def _manifest_by_source(manifest: dict) -> dict[str, dict]:
    return {
        os.path.normcase(os.path.abspath(str(item["source_path"]))): item
        for item in manifest["items"]
    }


def _validate_state(state: dict, manifest: dict, backup: Path) -> dict[str, dict]:
    if state.get("schema_version") != _STATE_SCHEMA_VERSION:
        raise MigrationError("不支持的 source-removal state schema_version")
    if state.get("kind") != "filecheck-source-removal":
        raise MigrationError("不是 FileCheck 源文件删除状态")
    if state.get("batch_id") != manifest.get("batch_id"):
        raise MigrationError("source-removal state 的 batch_id 与备份不一致")
    try:
        state_backup = Path(str(state["backup_path"])).expanduser().resolve()
    except (KeyError, OSError, RuntimeError) as exc:
        raise MigrationError("source-removal state 缺少有效 backup_path") from exc
    if os.path.normcase(str(state_backup)) != os.path.normcase(str(backup)):
        raise MigrationError("source-removal state 指向的备份与当前备份不一致")
    rows = state.get("items")
    if not isinstance(rows, list):
        raise MigrationError("source-removal state 缺少有效 items")
    manifest_map = _manifest_by_source(manifest)
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or "source_path" not in row:
            raise MigrationError("source-removal item 格式无效")
        key = os.path.normcase(os.path.abspath(str(row["source_path"])))
        item = manifest_map.get(key)
        if item is None:
            raise MigrationError(f"source-removal 包含不属于备份的源路径: {row['source_path']}")
        if key in seen:
            raise MigrationError(f"source-removal 源路径重复: {row['source_path']}")
        seen.add(key)
        if row.get("state") not in _ALLOWED_ITEM_STATES:
            raise MigrationError(f"source-removal 包含未知状态: {row.get('state')}")
        if row.get("size") != item["size"] or str(row.get("sha256", "")).lower() != str(item["sha256"]).lower():
            raise MigrationError(f"source-removal 文件摘要与 manifest 不一致: {row['source_path']}")
    if seen != set(manifest_map):
        raise MigrationError("source-removal 与 manifest 文件集合不一致")
    return manifest_map


def _recount(state: dict) -> None:
    rows = state["items"]
    state["deleted"] = sum(row.get("state") == "deleted" for row in rows)
    state["already_absent"] = sum(row.get("state") == "already_absent" for row in rows)
    state["failed"] = sum(row.get("state") in ("failed", "reappeared") for row in rows)
    finished = state["deleted"] + state["already_absent"]
    if finished == state["total"]:
        state["status"] = "completed"
    elif state["failed"]:
        state["status"] = "partial"
    else:
        state["status"] = "removing"
    state["updated_at"] = now_iso()


def _write_failed_report(backup: Path, state: dict) -> None:
    report = failed_report_path(backup)
    failed_rows = [row for row in state["items"] if row.get("state") in ("failed", "reappeared")]
    if not failed_rows:
        try:
            report.unlink(missing_ok=True)
        except OSError:
            pass
        return
    lines = [
        "FileCheck 未删除源文件清单",
        f"批次: {state.get('batch_id', '-')}",
        f"生成时间: {state.get('updated_at', '-')}",
        f"未删除数量: {len(failed_rows)}",
        "",
    ]
    for index, row in enumerate(failed_rows, start=1):
        lines.append(f"{index}. {row['source_path']}")
        lines.append(f"   状态: {row.get('state')}")
        lines.append(f"   原因: {row.get('error') or '未知原因'}")
        lines.append("")
    write_text(report, "\n".join(lines))


def _checkpoint(path: Path, state: dict) -> None:
    _recount(state)
    write_json(path, state)
    _write_failed_report(Path(str(state["backup_path"])), state)


def _remove_one(row: dict, manifest_item: dict) -> None:
    source = Path(row["source_path"])
    ok, reason = _check_source_item(manifest_item)
    if not ok:
        row["state"] = "failed"
        row["error"] = reason
        return
    try:
        source.unlink()
    except OSError as exc:
        row["state"] = "failed"
        row["error"] = str(exc)
        return
    row["state"] = "deleted"
    row["error"] = None


def _resolve_state_path(state_path: str | Path) -> Path:
    candidate = Path(state_path).expanduser().resolve()
    if candidate.is_dir():
        candidate = candidate / _STATE_NAME
    return candidate


def remove_verified_sources(
    backup: str | Path,
    *,
    state_path: str | Path | None = None,
    progress: ProgressCallback | None = None,
    preflight: bool = True,
    checkpoint_every: int = _DEFAULT_CHECKPOINT_EVERY,
) -> tuple[Path, dict]:
    """Remove only manifest-listed files, skipping failures and journaling each step."""
    backup_path = Path(backup).expanduser().resolve()
    manifest = verify_backup(backup_path)
    if preflight:
        _preflight_items(manifest["items"], progress=progress)
    state_file = _resolve_state_path(state_path) if state_path else migration_state_path(backup_path)
    if state_file.parent != backup_path:
        raise MigrationError("source-removal.json 必须保存在对应备份批次目录中")
    if state_file.exists():
        raise MigrationError(f"源文件删除状态已存在，请使用继续删除功能: {state_file}")
    manifest_map = _manifest_by_source(manifest)
    state = _new_state(backup_path, manifest)
    _checkpoint(state_file, state)

    total = len(state["items"])
    every = max(1, int(checkpoint_every))
    for index, row in enumerate(state["items"], start=1):
        key = os.path.normcase(os.path.abspath(str(row["source_path"])))
        _remove_one(row, manifest_map[key])
        _notify(progress, "remove", index, total, row["source_path"])
        if index % every == 0 or row["state"] == "failed" or index == total:
            _checkpoint(state_file, state)
    _checkpoint(state_file, state)
    return state_file, state


def resume_migration(
    state_path: str | Path,
    *,
    progress: ProgressCallback | None = None,
    checkpoint_every: int = _DEFAULT_CHECKPOINT_EVERY,
) -> tuple[Path, dict]:
    state_file = _resolve_state_path(state_path)
    if not state_file.is_file():
        raise MigrationError(f"源文件删除状态不存在: {state_file}")
    state = read_json(state_file)
    if not isinstance(state, dict):
        raise MigrationError("源文件删除状态格式无效")
    try:
        backup_path = Path(str(state["backup_path"])).expanduser().resolve()
    except (KeyError, OSError, RuntimeError) as exc:
        raise MigrationError("源文件删除状态缺少有效 backup_path") from exc
    manifest = verify_backup(backup_path)
    manifest_map = _validate_state(state, manifest, backup_path)

    for row in state["items"]:
        if row.get("state") in ("deleted", "already_absent"):
            source = Path(row["source_path"])
            if _entry_exists(source):
                row["state"] = "reappeared"
                row["error"] = "源路径在此前删除后重新出现；为避免删除新数据，本次不自动处理"
    _checkpoint(state_file, state)

    retry_rows = [row for row in state["items"] if row.get("state") in ("pending", "failed")]
    total = len(retry_rows)
    every = max(1, int(checkpoint_every))
    for index, row in enumerate(retry_rows, start=1):
        source = Path(row["source_path"])
        if not _entry_exists(source):
            row["state"] = "already_absent"
            row["error"] = None
        else:
            key = os.path.normcase(os.path.abspath(str(row["source_path"])))
            _remove_one(row, manifest_map[key])
        _notify(progress, "remove", index, total, row["source_path"])
        if index % every == 0 or row["state"] == "failed" or index == total:
            _checkpoint(state_file, state)
    _checkpoint(state_file, state)
    return state_file, state

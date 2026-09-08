from __future__ import annotations

import os
import stat
from pathlib import Path

from . import migration as base
from .backup import verify_backup
from .util import now_iso, read_json, sha256_file


_DEFAULT_CHECKPOINT_EVERY = 20
_PREFLIGHT_CACHE: dict[str, dict] = {}


def _key(path: str | Path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def _snapshot(path: Path) -> dict[str, int]:
    value = path.stat()
    return {
        "size": int(value.st_size),
        "mtime_ns": int(value.st_mtime_ns),
        "ino": int(getattr(value, "st_ino", 0) or 0),
        "ctime_ns": int(getattr(value, "st_ctime_ns", 0) or 0),
    }


def _snapshot_changed(current: dict[str, int], expected: dict[str, int]) -> bool:
    for name in ("size", "mtime_ns"):
        if int(current.get(name, -1)) != int(expected.get(name, -2)):
            return True
    for name in ("ino", "ctime_ns"):
        old = int(expected.get(name, 0) or 0)
        new = int(current.get(name, 0) or 0)
        if old and new and old != new:
            return True
    return False


def _check_source_and_snapshot(item: dict) -> tuple[bool, str | None, dict[str, int] | None]:
    source = Path(item["source_path"])
    try:
        if source.is_symlink():
            return False, "源路径已变成符号链接/重解析入口", None
        if not source.exists():
            return False, "源文件不存在", None
        if not source.is_file():
            return False, "源路径已不是普通文件", None
        before = source.stat()
        if before.st_size != item["size"]:
            return False, "文件大小已变化", None
        digest = sha256_file(source)
        after = source.stat()
        if (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or getattr(before, "st_ino", 0) != getattr(after, "st_ino", 0)
        ):
            return False, "源文件在复核过程中发生变化", None
        if digest.lower() != str(item["sha256"]).lower():
            return False, "SHA-256 已变化", None
        return True, None, _snapshot(source)
    except OSError as exc:
        return False, f"源文件无法复核: {exc}", None


def preflight_migration(backup: str | Path, *, progress=None) -> dict:
    """Strong batch preflight and cache cheap post-confirmation snapshots."""
    backup_path = Path(backup).expanduser().resolve()
    manifest = verify_backup(backup_path)
    total = len(manifest["items"])
    problems: list[tuple[str, str]] = []
    source_snapshots: dict[str, dict[str, int]] = {}

    for index, item in enumerate(manifest["items"], start=1):
        ok, reason, snap = _check_source_and_snapshot(item)
        if not ok:
            if len(problems) < 10:
                problems.append((str(item["source_path"]), reason or "未知原因"))
        elif snap is not None:
            source_snapshots[_key(item["source_path"])] = snap
        if progress is not None:
            progress("recheck", index, total, str(item["source_path"]))

    if len(source_snapshots) != total:
        problem_count = total - len(source_snapshots)
        detail = "；".join(f"{path}: {reason}" for path, reason in problems)
        if problem_count > len(problems):
            detail += f"；另有 {problem_count - len(problems)} 个异常文件"
        raise base.MigrationError(
            f"源文件批量复核失败，共 {problem_count} 个文件与已验证备份不一致；"
            f"未删除任何源文件。{detail}"
        )

    backup_snapshots: dict[str, dict[str, int]] = {}
    for item in manifest["items"]:
        stored = backup_path / Path(str(item["backup_path"]).replace("/", os.sep))
        backup_snapshots[_key(item["source_path"])] = _snapshot(stored)

    cache_key = _key(backup_path)
    _PREFLIGHT_CACHE[cache_key] = {
        "manifest": manifest,
        "manifest_snapshot": _snapshot(backup_path / "manifest.json"),
        "source_snapshots": source_snapshots,
        "backup_snapshots": backup_snapshots,
        "created_at": now_iso(),
    }
    return {
        "backup_path": str(backup_path),
        "batch_id": manifest.get("batch_id"),
        "files": total,
        "bytes": sum(int(item["size"]) for item in manifest["items"]),
    }


def _validated_cached_preflight(backup_path: Path, *, progress=None) -> dict:
    cache_key = _key(backup_path)
    cached = _PREFLIGHT_CACHE.get(cache_key)
    if cached is None:
        preflight_migration(backup_path, progress=progress)
        cached = _PREFLIGHT_CACHE[cache_key]

    manifest_path = backup_path / "manifest.json"
    try:
        if _snapshot_changed(_snapshot(manifest_path), cached["manifest_snapshot"]):
            raise base.MigrationError("manifest 在删除确认前后发生变化；未删除任何源文件")
        manifest = cached["manifest"]
        for item in manifest["items"]:
            stored = backup_path / Path(str(item["backup_path"]).replace("/", os.sep))
            expected = cached["backup_snapshots"][_key(item["source_path"])]
            if not stored.is_file() or _snapshot_changed(_snapshot(stored), expected):
                raise base.MigrationError(
                    f"备份文件在删除确认前后发生变化；未删除任何源文件: {stored}"
                )
    except OSError as exc:
        raise base.MigrationError(f"删除前快速复核备份状态失败；未删除任何源文件: {exc}") from exc
    return cached


def _unlink_with_readonly_retry(source: Path) -> None:
    """Delete a file, clearing only the Windows-style read-only bit when needed."""
    try:
        source.unlink()
        return
    except FileNotFoundError:
        raise
    except OSError as first:
        access_denied = isinstance(first, PermissionError) or getattr(first, "winerror", None) == 5
        if not access_denied:
            raise
        try:
            original_mode = source.stat().st_mode
        except OSError:
            raise first
        if original_mode & stat.S_IWRITE:
            raise first
        try:
            source.chmod(original_mode | stat.S_IWRITE)
            source.unlink()
            return
        except OSError:
            try:
                if source.exists():
                    source.chmod(original_mode)
            except OSError:
                pass
            raise


def _remove_one_fast(row: dict, snapshot: dict[str, int]) -> None:
    source = Path(row["source_path"])
    try:
        if not base._entry_exists(source):
            row["state"] = "already_absent"
            row["error"] = None
            return
        if source.is_symlink():
            row["state"] = "failed"
            row["error"] = "源路径已变成符号链接/重解析入口"
            return
        if not source.is_file():
            row["state"] = "failed"
            row["error"] = "源路径已不是普通文件"
            return
        if _snapshot_changed(_snapshot(source), snapshot):
            row["state"] = "failed"
            row["error"] = "源文件在整批 SHA-256 复核通过后发生变化，已跳过"
            return
        _unlink_with_readonly_retry(source)
    except FileNotFoundError:
        row["state"] = "already_absent"
        row["error"] = None
        return
    except OSError as exc:
        row["state"] = "failed"
        row["error"] = str(exc)
        return
    row["state"] = "deleted"
    row["error"] = None


def remove_verified_sources(
    backup: str | Path,
    *,
    state_path: str | Path | None = None,
    progress=None,
    preflight: bool = True,
    checkpoint_every: int = _DEFAULT_CHECKPOINT_EVERY,
):
    """Delete after one strong batch SHA-256 pass; use metadata checks per file."""
    backup_path = Path(backup).expanduser().resolve()
    if preflight:
        preflight_migration(backup_path, progress=progress)
    cached = _validated_cached_preflight(backup_path, progress=progress if preflight else None)
    manifest = cached["manifest"]

    state_file = base._resolve_state_path(state_path) if state_path else base.migration_state_path(backup_path)
    if state_file.parent != backup_path:
        raise base.MigrationError("source-removal.json 必须保存在对应备份批次目录中")
    if state_file.exists():
        raise base.MigrationError(f"源文件删除状态已存在，请使用继续删除功能: {state_file}")

    state = base._new_state(backup_path, manifest)
    base._checkpoint(state_file, state)
    total = len(state["items"])
    every = max(1, int(checkpoint_every))
    snapshots = cached["source_snapshots"]

    for index, row in enumerate(state["items"], start=1):
        _remove_one_fast(row, snapshots[_key(row["source_path"])])
        if progress is not None:
            progress("remove", index, total, str(row["source_path"]))
        if index % every == 0 or row["state"] == "failed" or index == total:
            base._checkpoint(state_file, state)
    base._checkpoint(state_file, state)
    _PREFLIGHT_CACHE.pop(_key(backup_path), None)
    return state_file, state


def _remove_one_verified(row: dict, manifest_item: dict) -> None:
    source = Path(row["source_path"])
    ok, reason = base._check_source_item(manifest_item)
    if not ok:
        if not base._entry_exists(source):
            row["state"] = "already_absent"
            row["error"] = None
        else:
            row["state"] = "failed"
            row["error"] = reason
        return
    try:
        _unlink_with_readonly_retry(source)
    except FileNotFoundError:
        row["state"] = "already_absent"
        row["error"] = None
        return
    except OSError as exc:
        row["state"] = "failed"
        row["error"] = str(exc)
        return
    row["state"] = "deleted"
    row["error"] = None


def resume_migration(state_path: str | Path, *, progress=None, checkpoint_every: int = _DEFAULT_CHECKPOINT_EVERY):
    """Resume conservatively: backup is rehashed and retry candidates are rehashed."""
    state_file = base._resolve_state_path(state_path)
    if not state_file.is_file():
        raise base.MigrationError(f"源文件删除状态不存在: {state_file}")
    state = read_json(state_file)
    if not isinstance(state, dict):
        raise base.MigrationError("源文件删除状态格式无效")
    try:
        backup_path = Path(str(state["backup_path"])).expanduser().resolve()
    except (KeyError, OSError, RuntimeError) as exc:
        raise base.MigrationError("源文件删除状态缺少有效 backup_path") from exc

    manifest = verify_backup(backup_path)
    manifest_map = base._validate_state(state, manifest, backup_path)

    for row in state["items"]:
        if row.get("state") in ("deleted", "already_absent"):
            source = Path(row["source_path"])
            if base._entry_exists(source):
                row["state"] = "reappeared"
                row["error"] = "源路径在此前删除后重新出现；为避免删除新数据，本次不自动处理"
    base._checkpoint(state_file, state)

    retry_rows = [row for row in state["items"] if row.get("state") in ("pending", "failed")]
    total = len(retry_rows)
    every = max(1, int(checkpoint_every))
    for index, row in enumerate(retry_rows, start=1):
        source = Path(row["source_path"])
        if not base._entry_exists(source):
            row["state"] = "already_absent"
            row["error"] = None
        else:
            _remove_one_verified(row, manifest_map[_key(row["source_path"])])
        if progress is not None:
            progress("remove", index, total, str(row["source_path"]))
        if index % every == 0 or row["state"] == "failed" or index == total:
            base._checkpoint(state_file, state)
    base._checkpoint(state_file, state)
    return state_file, state


def install() -> None:
    from . import cli, resilient_cli

    cli.preflight_migration = preflight_migration
    cli.remove_verified_sources = remove_verified_sources
    cli.resume_migration = resume_migration
    resilient_cli.preflight_migration = preflight_migration
    resilient_cli.remove_verified_sources = remove_verified_sources
    resilient_cli.resume_migration = resume_migration

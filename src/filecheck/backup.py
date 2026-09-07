from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import uuid
import zipfile
from pathlib import Path, PureWindowsPath
from typing import BinaryIO, Callable, Iterable

from .util import backup_relpath, choose_renamed_path, make_batch_id, now_iso, sha256_file, write_json


class BackupError(RuntimeError):
    pass


ProgressCallback = Callable[[str, int, int, str], None]

_MIN_FREE_RESERVE = 16 * 1024 * 1024
_MAX_FREE_RESERVE = 512 * 1024 * 1024


def _notify(progress: ProgressCallback | None, stage: str, current: int, total: int, path: str | Path) -> None:
    if progress is not None:
        progress(stage, current, total, str(path))


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _collect_files(sources: Iterable[str | Path], destination_root: Path) -> list[Path]:
    files: list[Path] = []
    seen: set[str] = set()

    for raw in sources:
        source = Path(raw).expanduser()
        if not source.exists():
            raise BackupError(f"源路径不存在: {source}")
        if source.is_symlink():
            raise BackupError(f"V0.1 不处理符号链接/重解析入口: {source}")
        if source.is_dir() and _is_within(destination_root, source):
            raise BackupError(f"备份目标不能位于待备份源目录内部: {source}")

        if source.is_file():
            candidates = [source]
        elif source.is_dir():
            candidates = [p for p in source.rglob("*") if p.is_file() and not p.is_symlink()]
        else:
            continue

        for candidate in candidates:
            key = os.path.normcase(os.path.abspath(str(candidate)))
            if key not in seen:
                seen.add(key)
                files.append(candidate)

    if not files:
        raise BackupError("没有可备份的普通文件")
    return files


def _stream_sha256(stream: BinaryIO, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            return digest.hexdigest()
        digest.update(chunk)


def _sync_file(path: Path) -> None:
    """Flush file data using a writable handle on Windows/POSIX.

    Windows rejects ``os.fsync`` on a read-only descriptor. ``shutil.copy2`` may
    also preserve a source read-only attribute onto the temporary copy, so this
    helper temporarily enables owner-write only when required, flushes the file,
    and restores the original mode before returning.
    """

    def flush_with_write_handle() -> None:
        with path.open("r+b") as fh:
            fh.flush()
            os.fsync(fh.fileno())

    try:
        flush_with_write_handle()
        return
    except PermissionError:
        original_mode = path.stat().st_mode
        try:
            path.chmod(original_mode | stat.S_IWRITE)
            flush_with_write_handle()
        finally:
            try:
                path.chmod(original_mode)
            except OSError:
                pass


def _estimate_required_bytes(files: Iterable[Path], *, zip_mode: bool) -> tuple[int, int]:
    total = 0
    for path in files:
        total += path.stat().st_size
    reserve = max(_MIN_FREE_RESERVE, min(_MAX_FREE_RESERVE, total // 20))
    # ZIP creation currently uses a fully verified staging copy plus a temporary
    # archive at the same time, so worst-case storage is roughly 2x input size.
    multiplier = 2 if zip_mode else 1
    return total, total * multiplier + reserve


def _ensure_destination_capacity(
    destination_root: Path, files: Iterable[Path], *, zip_mode: bool
) -> tuple[int, int, int | None]:
    total, required = _estimate_required_bytes(files, zip_mode=zip_mode)
    try:
        free = shutil.disk_usage(destination_root).free
    except OSError:
        # Some network/removable backends do not expose reliable free-space
        # information. In that case writes remain fail-closed later in the flow.
        return total, required, None
    if free < required:
        raise BackupError(
            "备份目标可用空间不足："
            f"预计至少需要 {required} 字节，当前可用 {free} 字节"
        )
    return total, required, free


def _validate_manifest(manifest: dict) -> list[dict]:
    if manifest.get("schema_version") != 1:
        raise BackupError("不支持的 manifest schema_version")
    items = manifest.get("items")
    if not isinstance(items, list) or not items:
        raise BackupError("manifest 中没有有效 items")

    seen_backup: set[str] = set()
    seen_source: set[str] = set()
    for item in items:
        for key in ("source_path", "backup_path", "size", "sha256"):
            if key not in item:
                raise BackupError(f"manifest item 缺少字段: {key}")

        backup_path = PureWindowsPath(str(item["backup_path"]).replace("/", "\\"))
        if backup_path.is_absolute() or ".." in backup_path.parts:
            raise BackupError(f"非法 backup_path: {item['backup_path']}")
        if not backup_path.parts or backup_path.parts[0].lower() != "files":
            raise BackupError(f"backup_path 必须位于 files/ 下: {item['backup_path']}")

        source_text = str(item["source_path"])
        if not (Path(source_text).is_absolute() or PureWindowsPath(source_text).is_absolute()):
            raise BackupError(f"source_path 不是绝对路径: {source_text}")

        bkey = str(item["backup_path"]).replace("\\", "/").lower()
        skey = os.path.normcase(source_text)
        if bkey in seen_backup:
            raise BackupError(f"manifest 中 backup_path 重复: {item['backup_path']}")
        if skey in seen_source:
            raise BackupError(f"manifest 中 source_path 重复: {source_text}")
        seen_backup.add(bkey)
        seen_source.add(skey)

        digest = str(item["sha256"]).lower()
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise BackupError(f"非法 SHA-256: {source_text}")
        if not isinstance(item["size"], int) or item["size"] < 0:
            raise BackupError(f"非法文件大小: {source_text}")

    return items


def _read_manifest_from_dir(source: Path) -> dict:
    manifest_path = source / "manifest.json"
    if not manifest_path.is_file():
        raise BackupError(f"未找到 manifest.json: {source}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BackupError(f"manifest.json 损坏: {source}") from exc
    _validate_manifest(manifest)
    return manifest


def _read_manifest_from_zip(zf: zipfile.ZipFile) -> dict:
    try:
        raw = zf.read("manifest.json")
    except KeyError as exc:
        raise BackupError("ZIP 中没有 manifest.json") from exc
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BackupError("ZIP 中 manifest.json 损坏") from exc
    _validate_manifest(manifest)
    return manifest


def verify_backup(source: str | Path, *, progress: ProgressCallback | None = None) -> dict:
    """Verify every backed-up payload against its original SHA-256 manifest."""
    source = Path(source).expanduser()
    if not source.exists():
        raise BackupError(f"备份不存在: {source}")

    if source.is_dir():
        manifest = _read_manifest_from_dir(source)
        total = len(manifest["items"])
        for index, item in enumerate(manifest["items"], start=1):
            stored = source / Path(str(item["backup_path"]).replace("/", os.sep))
            if not stored.is_file():
                raise BackupError(f"备份文件缺失: {stored}")
            if stored.stat().st_size != item["size"]:
                raise BackupError(f"备份文件大小不一致: {stored}")
            if sha256_file(stored).lower() != item["sha256"].lower():
                raise BackupError(f"备份文件 SHA-256 不一致: {stored}")
            _notify(progress, "verify", index, total, stored)
        return manifest

    if not zipfile.is_zipfile(source):
        raise BackupError(f"不是有效 ZIP 备份: {source}")
    try:
        with zipfile.ZipFile(source, "r") as zf:
            bad = zf.testzip()
            if bad:
                raise BackupError(f"ZIP CRC 完整性检查失败: {bad}")
            manifest = _read_manifest_from_zip(zf)
            names = set(zf.namelist())
            total = len(manifest["items"])
            for index, item in enumerate(manifest["items"], start=1):
                member = str(item["backup_path"]).replace("\\", "/")
                if member not in names:
                    raise BackupError(f"ZIP 中缺少备份文件: {member}")
                info = zf.getinfo(member)
                if info.file_size != item["size"]:
                    raise BackupError(f"ZIP 文件大小不一致: {member}")
                with zf.open(member, "r") as stream:
                    digest = _stream_sha256(stream)
                if digest.lower() != item["sha256"].lower():
                    raise BackupError(f"ZIP 文件 SHA-256 不一致: {member}")
                _notify(progress, "verify", index, total, member)
            return manifest
    except zipfile.BadZipFile as exc:
        raise BackupError(f"ZIP 备份损坏或不可读: {source}") from exc


def _atomic_copy_to_backup(source: Path, target: Path) -> tuple[str, os.stat_result]:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.part")
    before = source.stat()
    before_hash = sha256_file(source)
    try:
        shutil.copy2(source, temp)
        _sync_file(temp)
        copied_hash = sha256_file(temp)
        after = source.stat()
        after_hash = sha256_file(source)
        if (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or before_hash != after_hash
        ):
            raise BackupError(f"源文件在备份过程中发生变化，拒绝继续: {source}")
        if before_hash != copied_hash:
            raise BackupError(f"备份 SHA-256 校验失败: {source}")
        os.replace(temp, target)
        _sync_file(target)
        return before_hash, before
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def _create_zip_from_staging(staging: Path, archive: Path) -> None:
    temp_archive = archive.with_name(f".{archive.stem}.{uuid.uuid4().hex}.tmp.zip")
    try:
        with zipfile.ZipFile(temp_archive, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            for path in staging.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(staging).as_posix())
        _sync_file(temp_archive)
        verify_backup(temp_archive)
        os.replace(temp_archive, archive)
        _sync_file(archive)
        verify_backup(archive)
    finally:
        try:
            temp_archive.unlink(missing_ok=True)
        except OSError:
            pass


def create_backup(
    sources: Iterable[str | Path],
    destination_root: str | Path,
    *,
    zip_mode: bool = False,
    progress: ProgressCallback | None = None,
) -> Path:
    """Create and fully verify a backup. This function never removes source files."""
    destination_root = Path(destination_root).expanduser().resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    files = _collect_files(sources, destination_root)
    source_bytes, required_bytes, free_bytes = _ensure_destination_capacity(
        destination_root, files, zip_mode=zip_mode
    )

    batch_id = make_batch_id()
    staging = destination_root / f".{batch_id}.incomplete"
    final_dir = destination_root / batch_id
    archive = destination_root / f"{batch_id}.zip"
    if staging.exists() or final_dir.exists() or archive.exists():
        raise BackupError(f"备份批次已存在: {batch_id}")
    staging.mkdir(parents=True)

    manifest = {
        "schema_version": 1,
        "batch_id": batch_id,
        "created_at": now_iso(),
        "mode": "zip" if zip_mode else "directory",
        "source_removed": False,
        "source_bytes_total": source_bytes,
        "space_required_estimate": required_bytes,
        "space_free_at_start": free_bytes,
        "items": [],
    }

    completed = False
    try:
        total = len(files)
        for index, source in enumerate(files, start=1):
            source = source.resolve()
            rel = backup_relpath(source)
            target = staging / rel
            source_hash, source_stat = _atomic_copy_to_backup(source, target)
            manifest["items"].append(
                {
                    "source_path": str(source),
                    "backup_path": rel.as_posix(),
                    "size": source_stat.st_size,
                    "mtime_ns": source_stat.st_mtime_ns,
                    "sha256": source_hash,
                    "backup_verified": True,
                    "source_removed": False,
                }
            )
            _notify(progress, "copy", index, total, source)

        write_json(staging / "manifest.json", manifest)
        verify_backup(staging)

        if zip_mode:
            _create_zip_from_staging(staging, archive)
            shutil.rmtree(staging)
            result: Path = archive
        else:
            os.replace(staging, final_dir)
            result = final_dir

        verify_backup(result)
        completed = True
        return result
    finally:
        if not completed:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            if final_dir.exists():
                shutil.rmtree(final_dir, ignore_errors=True)
            try:
                archive.unlink(missing_ok=True)
            except OSError:
                pass


def _resolve_conflict(path: Path, mode: str) -> Path | None:
    if not path.exists():
        return path
    if mode == "skip":
        return None
    if mode == "overwrite":
        return path
    if mode == "rename":
        return choose_renamed_path(path)
    raise BackupError(f"未知冲突策略: {mode}")


def _restore_temp_path(target: Path) -> Path:
    return target.parent / f".{target.name}.filecheck-restore-{uuid.uuid4().hex}.part"


def _finish_atomic_restore(temp: Path, target: Path, item: dict) -> None:
    if temp.stat().st_size != item["size"] or sha256_file(temp) != item["sha256"]:
        raise BackupError(f"恢复临时文件校验失败，未替换目标文件: {target}")
    mtime_ns = item.get("mtime_ns")
    if isinstance(mtime_ns, int) and mtime_ns >= 0:
        try:
            os.utime(temp, ns=(mtime_ns, mtime_ns))
        except OSError:
            pass
    # Atomic replacement on the same filesystem: an existing target is not
    # touched until the temporary restored copy has passed SHA-256 verification.
    os.replace(temp, target)
    _sync_file(target)
    if target.stat().st_size != item["size"] or sha256_file(target) != item["sha256"]:
        raise BackupError(f"恢复后最终 SHA-256 校验失败: {target}")


def _restore_one_from_file(source: Path, item: dict, conflict: str) -> tuple[str, str]:
    target = _resolve_conflict(Path(item["source_path"]), conflict)
    if target is None:
        return item["source_path"], "skipped"
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = _restore_temp_path(target)
    try:
        shutil.copy2(source, temp)
        _sync_file(temp)
        _finish_atomic_restore(temp, target, item)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
    return str(target), "restored"


def _preflight_restore_targets(items: list[dict]) -> None:
    if os.name != "nt":
        return
    anchors: set[str] = set()
    for item in items:
        win = PureWindowsPath(item["source_path"])
        if not win.is_absolute():
            raise BackupError(f"Windows 恢复路径不是绝对路径: {item['source_path']}")
        anchors.add(win.anchor)
    unavailable = [anchor for anchor in anchors if anchor and not Path(anchor).exists()]
    if unavailable:
        raise BackupError(f"以下原始驱动器/共享当前不可用，尚未开始恢复: {', '.join(unavailable)}")


def restore_backup(
    source: str | Path,
    *,
    conflict: str = "skip",
    progress: ProgressCallback | None = None,
) -> list[dict]:
    source = Path(source).expanduser()
    # Safety invariant: verify the entire backup before touching any target.
    manifest = verify_backup(source)
    items = manifest["items"]
    _preflight_restore_targets(items)

    results: list[dict] = []
    total = len(items)
    if source.is_dir():
        for index, item in enumerate(items, start=1):
            stored = source / Path(str(item["backup_path"]).replace("/", os.sep))
            target, state_value = _restore_one_from_file(stored, item, conflict)
            results.append({"target": target, "state": state_value})
            _notify(progress, "restore", index, total, target)
        return results

    with zipfile.ZipFile(source, "r") as zf:
        for index, item in enumerate(items, start=1):
            target = _resolve_conflict(Path(item["source_path"]), conflict)
            if target is None:
                results.append({"target": item["source_path"], "state": "skipped"})
                _notify(progress, "restore", index, total, item["source_path"])
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            member = str(item["backup_path"]).replace("\\", "/")
            temp = _restore_temp_path(target)
            try:
                with zf.open(member, "r") as src, temp.open("wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                    dst.flush()
                    os.fsync(dst.fileno())
                _finish_atomic_restore(temp, target, item)
            finally:
                try:
                    temp.unlink(missing_ok=True)
                except OSError:
                    pass
            results.append({"target": str(target), "state": "restored"})
            _notify(progress, "restore", index, total, target)
    return results

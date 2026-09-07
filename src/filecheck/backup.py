from __future__ import annotations

import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Iterable

from .util import backup_relpath, choose_renamed_path, make_batch_id, now_iso, sha256_file, write_json


class BackupError(RuntimeError):
    pass


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _collect_files(sources: Iterable[str | Path], destination_root: Path) -> tuple[list[Path], list[Path]]:
    files: list[Path] = []
    selected_dirs: list[Path] = []
    seen: set[str] = set()

    for raw in sources:
        source = Path(raw).expanduser()
        if not source.exists():
            raise BackupError(f"源路径不存在: {source}")
        if source.is_symlink():
            raise BackupError(f"V0.1 不处理符号链接/重解析入口: {source}")
        if _is_within(destination_root, source):
            raise BackupError(f"备份目标不能位于待备份源目录内部: {source}")

        if source.is_file():
            candidates = [source]
        elif source.is_dir():
            selected_dirs.append(source)
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
    return files, selected_dirs


def create_backup(
    sources: Iterable[str | Path],
    destination_root: str | Path,
    *,
    zip_mode: bool = False,
    remove_source: bool = False,
) -> Path:
    destination_root = Path(destination_root).expanduser()
    destination_root.mkdir(parents=True, exist_ok=True)
    files, selected_dirs = _collect_files(sources, destination_root)

    batch_id = make_batch_id()
    staging = destination_root / batch_id
    if staging.exists():
        raise BackupError(f"备份批次目录已存在: {staging}")
    staging.mkdir(parents=True)

    manifest = {
        "schema_version": 1,
        "batch_id": batch_id,
        "created_at": now_iso(),
        "mode": "zip" if zip_mode else "directory",
        "source_removed": False,
        "items": [],
    }

    try:
        for source in files:
            rel = backup_relpath(source)
            target = staging / rel
            target.parent.mkdir(parents=True, exist_ok=True)

            source_hash = sha256_file(source)
            shutil.copy2(source, target)
            target_hash = sha256_file(target)
            if source_hash != target_hash:
                raise BackupError(f"SHA-256 校验失败: {source}")

            stat = source.stat()
            manifest["items"].append(
                {
                    "source_path": str(source.resolve()),
                    "backup_path": rel.as_posix(),
                    "size": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                    "sha256": source_hash,
                    "backup_verified": True,
                    "source_removed": False,
                }
            )

        write_json(staging / "manifest.json", manifest)

        result: Path = staging
        if zip_mode:
            archive = destination_root / f"{batch_id}.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
                for path in staging.rglob("*"):
                    if path.is_file():
                        zf.write(path, path.relative_to(staging).as_posix())
            with zipfile.ZipFile(archive, "r") as zf:
                bad = zf.testzip()
                if bad:
                    raise BackupError(f"ZIP 完整性检查失败: {bad}")
            shutil.rmtree(staging)
            result = archive

        if remove_source:
            # Only remove originals after the whole backup has been verified.
            for item in manifest["items"]:
                source = Path(item["source_path"])
                if source.exists():
                    if sha256_file(source) != item["sha256"]:
                        raise BackupError(f"源文件在备份后发生变化，拒绝移除: {source}")
                    source.unlink()
                    item["source_removed"] = True

            # Remove only empty directories, deepest first. Never remove non-empty directories.
            for root in sorted(selected_dirs, key=lambda p: len(p.parts), reverse=True):
                for directory in sorted(
                    [p for p in root.rglob("*") if p.is_dir()],
                    key=lambda p: len(p.parts),
                    reverse=True,
                ):
                    try:
                        directory.rmdir()
                    except OSError:
                        pass
                try:
                    root.rmdir()
                except OSError:
                    pass

            manifest["source_removed"] = True
            if zip_mode:
                # Rebuild the archive so the manifest inside reflects removal state.
                temp = destination_root / f".{batch_id}.manifest-update"
                temp.mkdir()
                try:
                    with zipfile.ZipFile(result, "r") as zf:
                        zf.extractall(temp)
                    write_json(temp / "manifest.json", manifest)
                    replacement = destination_root / f".{batch_id}.zip.tmp"
                    with zipfile.ZipFile(replacement, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
                        for path in temp.rglob("*"):
                            if path.is_file():
                                zf.write(path, path.relative_to(temp).as_posix())
                    with zipfile.ZipFile(replacement, "r") as zf:
                        bad = zf.testzip()
                        if bad:
                            raise BackupError(f"更新后的 ZIP 完整性检查失败: {bad}")
                    replacement.replace(result)
                finally:
                    shutil.rmtree(temp, ignore_errors=True)
            else:
                write_json(result / "manifest.json", manifest)

        return result
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise


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


def _restore_one_from_file(source: Path, item: dict, conflict: str) -> tuple[str, str]:
    target = _resolve_conflict(Path(item["source_path"]), conflict)
    if target is None:
        return item["source_path"], "skipped"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if sha256_file(target) != item["sha256"]:
        raise BackupError(f"恢复后 SHA-256 校验失败: {target}")
    return str(target), "restored"


def restore_backup(source: str | Path, *, conflict: str = "skip") -> list[dict]:
    source = Path(source).expanduser()
    if not source.exists():
        raise BackupError(f"备份不存在: {source}")

    results: list[dict] = []
    if source.is_dir():
        manifest_path = source / "manifest.json"
        if not manifest_path.is_file():
            raise BackupError(f"未找到 manifest.json: {source}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in manifest.get("items", []):
            stored = source / Path(item["backup_path"])
            if not stored.is_file():
                raise BackupError(f"备份文件缺失: {stored}")
            target, state = _restore_one_from_file(stored, item, conflict)
            results.append({"target": target, "state": state})
        return results

    if source.suffix.lower() != ".zip":
        raise BackupError("恢复源必须是批次目录或 .zip 文件")

    with zipfile.ZipFile(source, "r") as zf:
        bad = zf.testzip()
        if bad:
            raise BackupError(f"ZIP 完整性检查失败: {bad}")
        try:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        except KeyError as exc:
            raise BackupError("ZIP 中没有 manifest.json") from exc

        for item in manifest.get("items", []):
            target = _resolve_conflict(Path(item["source_path"]), conflict)
            if target is None:
                results.append({"target": item["source_path"], "state": "skipped"})
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            member = item["backup_path"].replace("\\", "/")
            try:
                with zf.open(member, "r") as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
            except KeyError as exc:
                raise BackupError(f"ZIP 中缺少备份文件: {member}") from exc
            if sha256_file(target) != item["sha256"]:
                raise BackupError(f"恢复后 SHA-256 校验失败: {target}")
            results.append({"target": str(target), "state": "restored"})
    return results

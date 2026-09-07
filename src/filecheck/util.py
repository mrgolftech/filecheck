from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Any


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def make_batch_id() -> str:
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    return f"FC-{stamp}-{uuid.uuid4().hex[:8]}"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "FileCheck"
    return Path.home() / ".filecheck"


def _fsync_parent(path: Path) -> None:
    """Best-effort directory sync on platforms that support it."""
    if os.name == "nt":
        return
    try:
        fd = os.open(str(path.parent), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def write_json(path: Path, data: Any) -> None:
    """Atomically write JSON and flush file data before publishing it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        _fsync_parent(path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_component(value: str) -> str:
    value = re.sub(r"[<>:\"/\\|?*]", "_", value)
    return value.rstrip(" .") or "_"


def backup_relpath(source: Path) -> Path:
    """Map an absolute source path to a deterministic path inside a backup.

    Windows examples:
      C:\\Work\\a.docx -> files/C/Work/a.docx
      \\\\server\\share\\a -> files/UNC/server/share/a

    A POSIX mapping is also supported to keep unit tests portable.
    """
    raw = str(source)
    win = PureWindowsPath(raw)
    if win.drive:
        if raw.startswith("\\\\"):
            parts = [safe_component(p) for p in win.parts if p not in ("\\", "\\\\")]
            return Path("files") / "UNC" / Path(*parts)
        drive = safe_component(win.drive.rstrip(":"))
        tail = [safe_component(p) for p in win.parts[1:]]
        return Path("files") / drive / Path(*tail)

    posix = source.absolute()
    parts = [safe_component(p) for p in posix.parts if p not in (posix.anchor, "/")]
    return Path("files") / "ROOT" / Path(*parts)


def choose_renamed_path(path: Path) -> Path:
    stem = path.stem
    suffix = path.suffix
    for index in range(1, 10000):
        candidate = path.with_name(f"{stem}.restored-{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"无法为恢复文件生成不冲突的名称: {path}")

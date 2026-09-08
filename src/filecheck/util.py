from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Any


_IO_CHUNK_SIZE = 8 * 1024 * 1024


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def make_batch_id() -> str:
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    return f"FC-{stamp}-{uuid.uuid4().hex[:8]}"


def sha256_file(path: Path, chunk_size: int = _IO_CHUNK_SIZE) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


def program_dir() -> Path:
    """Return the portable FileCheck home directory.

    Frozen releases keep runtime data next to FileCheck.exe. Source/development
    runs use FILECHECK_HOME when set, otherwise the current working directory.
    This makes the command-line workflow portable and keeps scan/index state in
    one visible location instead of scattering it through AppData.
    """
    override = os.environ.get("FILECHECK_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def runtime_dir() -> Path:
    return program_dir() / "runtime"


def scan_results_dir() -> Path:
    return program_dir() / "scan-results"


def app_data_dir() -> Path:
    """Backward-compatible alias for v0.1 operation-state callers.

    v0.1.1 intentionally keeps state under the portable application directory.
    """
    return runtime_dir()


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


def write_text(path: Path, text: str) -> None:
    """Atomically write a UTF-8 text report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8-sig", newline="\r\n") as fh:
            fh.write(text)
            if text and not text.endswith("\n"):
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

    Different absolute source paths remain different backup paths even when the
    final file names are identical.
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

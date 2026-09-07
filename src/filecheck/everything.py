from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


class EverythingError(RuntimeError):
    pass


FILECHECK_INSTANCE = "FileCheck"


@dataclass(frozen=True)
class EverythingStatus:
    es_path: str
    es_version: str
    everything_version: str
    instance: str | None = None


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "mbcs", "gb18030", "utf-8"):
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode(errors="replace")


def find_es(explicit: str | None = None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("FILECHECK_ES"):
        candidates.append(Path(os.environ["FILECHECK_ES"]))
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "tools" / "es.exe")
    candidates.append(Path.cwd() / "tools" / "es.exe")
    located = shutil.which("es.exe") or shutil.which("es")
    if located:
        candidates.append(Path(located))
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(env_name)
        if base:
            candidates.extend(
                [
                    Path(base) / "Everything" / "es.exe",
                    Path(base) / "voidtools" / "Everything" / "es.exe",
                ]
            )

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file():
            return candidate
    raise EverythingError(
        "未找到 es.exe。正式发布包应自带 tools/es.exe；开发版可放到 tools/es.exe、"
        "加入 PATH，或设置 FILECHECK_ES。"
    )


def _creationflags() -> int:
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def _build_command(es_path: Path, args: list[str], *, argv_mode: bool) -> list[str]:
    command = [str(es_path)]
    if argv_mode:
        command.append("-argv")
    command.extend(args)
    return command


def _with_instance(args: list[str], instance: str | None) -> list[str]:
    if not instance:
        return list(args)
    return ["-instance", instance, *args]


def _raise_for_es_error(proc: subprocess.CompletedProcess[bytes], stdout: str, stderr: str) -> None:
    if proc.returncode == 0:
        return
    detail = stderr or stdout or f"exit={proc.returncode}"
    if proc.returncode in (7, 8):
        detail += "；请确认 FileCheck 专用 Everything 实例已启动且索引已加载"
    raise EverythingError(detail)


def _run(
    es_path: Path,
    args: list[str],
    timeout: int = 30,
    *,
    argv_mode: bool = False,
) -> str:
    proc = subprocess.run(
        _build_command(es_path, args, argv_mode=argv_mode),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        creationflags=_creationflags(),
        check=False,
    )
    stdout = _decode(proc.stdout).strip()
    stderr = _decode(proc.stderr).strip()
    _raise_for_es_error(proc, stdout, stderr)
    return stdout


def _run_export_txt(
    es_path: Path,
    args: list[str],
    timeout: int = 60,
    *,
    argv_mode: bool = True,
) -> str:
    """Run ES through its UTF-8 file export channel to preserve exact paths."""
    with tempfile.TemporaryDirectory(prefix="filecheck-es-") as temp_dir:
        export_path = Path(temp_dir) / "results.txt"
        if args:
            export_args = [
                *args[:-1],
                "-export-txt",
                str(export_path),
                "-utf8-bom",
                args[-1],
            ]
        else:
            export_args = ["-export-txt", str(export_path), "-utf8-bom"]
        proc = subprocess.run(
            _build_command(es_path, export_args, argv_mode=argv_mode),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            creationflags=_creationflags(),
            check=False,
        )
        stdout = _decode(proc.stdout).strip()
        stderr = _decode(proc.stderr).strip()
        _raise_for_es_error(proc, stdout, stderr)
        if not export_path.exists():
            raise EverythingError("ES 查询成功但未生成 UTF-8 导出结果文件")
        try:
            return export_path.read_bytes().decode("utf-8-sig").strip()
        except UnicodeDecodeError as exc:
            raise EverythingError("ES 导出结果不是有效的 UTF-8 文本") from exc


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for token in value.strip().split("."):
        digits = "".join(ch for ch in token if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def get_status(es: str | None = None, *, instance: str | None = None) -> EverythingStatus:
    es_path = find_es(es)
    es_version = _run(es_path, ["-version"])
    everything_version = _run(
        es_path,
        _with_instance(["-get-everything-version"], instance),
        argv_mode=True,
    )
    if not everything_version.startswith("1.4."):
        raise EverythingError(
            f"当前 Everything 版本为 {everything_version}，FileCheck v0.1.1 按 1.4.x 环境验证。"
        )
    if _version_tuple(es_version) < (1, 1, 0, 37):
        raise EverythingError(
            f"当前 ES CLI 版本为 {es_version}；要求 ES 1.1.0.37 或更高版本。"
        )
    return EverythingStatus(str(es_path), es_version, everything_version, instance)


def reindex(
    es: str | None = None,
    *,
    instance: str | None = None,
    timeout: int = 900,
    progress: Callable[[float], None] | None = None,
    interval: float = 1.0,
) -> None:
    """Force an Everything rebuild and optionally report live elapsed time.

    ES 1.1 / Everything 1.4 does not expose a reliable per-file percentage.
    The ES -reindex process stays alive until the rebuild is complete, so we
    can report a truthful live busy/elapsed status without inventing a percent.
    """
    es_path = find_es(es)
    args = _with_instance(["-reindex"], instance)
    if progress is None:
        _run(es_path, args, timeout=timeout, argv_mode=True)
        return

    command = _build_command(es_path, args, argv_mode=True)
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=_creationflags(),
    )
    started = time.monotonic()
    tick = max(0.2, float(interval))
    stdout_bytes = b""
    stderr_bytes = b""
    try:
        while True:
            elapsed = time.monotonic() - started
            remaining = float(timeout) - elapsed
            if remaining <= 0:
                proc.kill()
                proc.communicate()
                raise EverythingError(f"Everything 索引超时（>{timeout} 秒）")
            try:
                stdout_bytes, stderr_bytes = proc.communicate(timeout=min(tick, remaining))
                break
            except subprocess.TimeoutExpired:
                progress(time.monotonic() - started)
        progress(time.monotonic() - started)
    except BaseException:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()
        raise

    stdout = _decode(stdout_bytes).strip()
    stderr = _decode(stderr_bytes).strip()
    completed = subprocess.CompletedProcess(command, int(proc.returncode or 0), stdout_bytes, stderr_bytes)
    _raise_for_es_error(completed, stdout, stderr)


def _safe_keyword(keyword: str) -> str:
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("关键词不能为空")
    if '"' in keyword:
        raise ValueError(f"暂不支持包含双引号的关键词: {keyword!r}")
    return f'"{keyword}"'


def _under_root(path: str | Path, root: str | Path) -> bool:
    try:
        child = os.path.normcase(os.path.abspath(str(path)))
        parent = os.path.normcase(os.path.abspath(str(root)))
        return os.path.commonpath([child, parent]) == parent
    except (OSError, ValueError):
        return False


def search_keyword(
    es_path: Path,
    keyword: str,
    extensions: Iterable[str],
    *,
    max_results: int = 100000,
    match_path: bool = False,
    path_prefix: str | None = None,
    instance: str | None = None,
    exclude_roots: Iterable[str | Path] = (),
) -> list[Path]:
    ext_list = [e.lower().lstrip(".") for e in extensions if e.strip()]
    if not ext_list:
        raise ValueError("扩展名列表不能为空")

    query = f"{_safe_keyword(keyword)} ext:{';'.join(ext_list)}"
    args = _with_instance(
        ["-timeout", "10000", "/a-d", "-full-path-and-name", "-n", str(max_results), "-s"],
        instance,
    )
    if match_path:
        args.append("-p")
    if path_prefix:
        args.extend(["-path", str(Path(path_prefix).expanduser())])
    args.append(query)

    output = _run_export_txt(es_path, args, timeout=60, argv_mode=True)
    prefix = os.path.normcase(os.path.abspath(path_prefix)) if path_prefix else None
    exclusions = [str(root) for root in exclude_roots if str(root).strip()]
    results: list[Path] = []
    for line in output.splitlines():
        raw = line.strip().strip('"')
        if not raw:
            continue
        candidate = Path(raw)
        if prefix:
            normalized = os.path.normcase(os.path.abspath(str(candidate)))
            try:
                common = os.path.commonpath([prefix, normalized])
            except ValueError:
                continue
            if common != prefix:
                continue
        if any(_under_root(candidate, root) for root in exclusions):
            continue
        results.append(candidate)
    return results


def scan_keywords(
    keywords_by_level: dict[str, list[str]],
    extensions: Iterable[str],
    *,
    es: str | None = None,
    max_results_per_keyword: int = 100000,
    match_path: bool = False,
    path_prefix: str | None = None,
    instance: str | None = None,
    exclude_roots: Iterable[str | Path] = (),
) -> list[dict]:
    status = get_status(es, instance=instance)
    es_path = Path(status.es_path)
    found: dict[str, dict] = {}
    level_rank = {"high": 3, "sensitive": 2, "review": 1}

    for level, keywords in keywords_by_level.items():
        for keyword in keywords:
            for path in search_keyword(
                es_path,
                keyword,
                extensions,
                max_results=max_results_per_keyword,
                match_path=match_path,
                path_prefix=path_prefix,
                instance=instance,
                exclude_roots=exclude_roots,
            ):
                key = os.path.normcase(os.path.abspath(str(path)))
                item = found.setdefault(
                    key,
                    {
                        "path": str(path),
                        "directory": str(path.parent),
                        "matched_keywords": [],
                        "levels": [],
                    },
                )
                if keyword not in item["matched_keywords"]:
                    item["matched_keywords"].append(keyword)
                if level not in item["levels"]:
                    item["levels"].append(level)

    for item in found.values():
        item["severity"] = max(
            item["levels"], key=lambda name: level_rank.get(name, 0), default="review"
        )
        try:
            stat_result = Path(item["path"]).stat()
            item["size"] = stat_result.st_size
            item["mtime_ns"] = stat_result.st_mtime_ns
            item["accessible"] = True
        except OSError:
            item["size"] = None
            item["mtime_ns"] = None
            item["accessible"] = False

    return sorted(found.values(), key=lambda x: (x["directory"].lower(), x["path"].lower()))
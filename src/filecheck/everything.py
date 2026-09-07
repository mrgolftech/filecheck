from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class EverythingError(RuntimeError):
    pass


@dataclass(frozen=True)
class EverythingStatus:
    es_path: str
    es_version: str
    everything_version: str


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
        "未找到 es.exe。请将 ES CLI 放到 tools/es.exe、加入 PATH，"
        "或设置 FILECHECK_ES 环境变量。"
    )


def _creationflags() -> int:
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def _build_command(es_path: Path, args: list[str], *, argv_mode: bool) -> list[str]:
    # ES <= 1.1.0.36 used a custom Windows command-line parser which can split
    # arguments produced by Python/PowerShell incorrectly. ES 1.1.0.37 added
    # -argv to opt into CommandLineToArgvW. It must be the first ES parameter.
    command = [str(es_path)]
    if argv_mode:
        command.append("-argv")
    command.extend(args)
    return command


def _raise_for_es_error(proc: subprocess.CompletedProcess[bytes], stdout: str, stderr: str) -> None:
    if proc.returncode == 0:
        return
    detail = stderr or stdout or f"exit={proc.returncode}"
    if proc.returncode in (7, 8):
        detail += "；请确认 Everything 1.4 已启动且索引已加载"
    raise EverythingError(detail)


def _run(
    es_path: Path,
    args: list[str],
    timeout: int = 30,
    *,
    argv_mode: bool = False,
) -> str:
    command = _build_command(es_path, args, argv_mode=argv_mode)
    proc = subprocess.run(
        command,
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
    """Run an ES search through its UTF-8 text export path.

    ES console stdout is constrained by the active Windows console code page.
    Characters that are not representable there can already be replaced with
    '?' before Python receives stdout. That is irreversible and can corrupt a
    filename in scan-results.json. Exporting to a UTF-8 file avoids the console
    encoding boundary and preserves the exact Unicode path.
    """

    with tempfile.TemporaryDirectory(prefix="filecheck-es-") as temp_dir:
        export_path = Path(temp_dir) / "results.txt"

        # Keep the search expression as the final argument. ES accepts export
        # options alongside a search, and -utf8-bom makes the export encoding
        # explicit and unambiguous for us to decode.
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

        command = _build_command(es_path, export_args, argv_mode=argv_mode)
        proc = subprocess.run(
            command,
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


def get_status(es: str | None = None) -> EverythingStatus:
    es_path = find_es(es)
    es_version = _run(es_path, ["-version"])
    everything_version = _run(es_path, ["-get-everything-version"])
    if not everything_version.startswith("1.4."):
        raise EverythingError(
            f"当前 Everything 版本为 {everything_version}，V0.1 按 1.4.x 环境验证。"
        )
    if _version_tuple(es_version) < (1, 1, 0, 37):
        raise EverythingError(
            f"当前 ES CLI 版本为 {es_version}；V0.1 要求 ES 1.1.0.37 或更高版本，"
            "以使用 -argv 避免 Windows 参数解析错误。"
        )
    return EverythingStatus(str(es_path), es_version, everything_version)


def _safe_keyword(keyword: str) -> str:
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("关键词不能为空")
    if '"' in keyword:
        raise ValueError(f"V0.1 暂不支持包含双引号的关键词: {keyword!r}")
    # Quotes are Everything search syntax (exact phrase), not shell quoting.
    # With ES 1.1.0.37 -argv they survive Python's Windows argv handling safely.
    return f'"{keyword}"'


def search_keyword(
    es_path: Path,
    keyword: str,
    extensions: Iterable[str],
    *,
    max_results: int = 100000,
    match_path: bool = False,
    path_prefix: str | None = None,
) -> list[Path]:
    ext_list = [e.lower().lstrip(".") for e in extensions if e.strip()]
    if not ext_list:
        raise ValueError("扩展名列表不能为空")

    query = f"{_safe_keyword(keyword)} ext:{';'.join(ext_list)}"
    # /a-d asks Everything itself for files only. -path is applied by Everything
    # before -n limiting, avoiding false omissions when scanning one drive/folder.
    args = ["-timeout", "10000", "/a-d", "-full-path-and-name", "-n", str(max_results), "-s"]
    if match_path:
        args.append("-p")
    if path_prefix:
        args.extend(["-path", str(Path(path_prefix).expanduser())])
    args.append(query)

    # Do not consume search result paths from ES console stdout. On Windows the
    # console code page can replace legitimate Unicode filename characters with
    # '?'. The UTF-8 export path preserves exact NTFS names such as NBSP/emoji.
    output = _run_export_txt(es_path, args, timeout=60, argv_mode=True)
    prefix = os.path.normcase(os.path.abspath(path_prefix)) if path_prefix else None
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
        # Do not silently discard indexed files only because stat/is_file fails
        # (for example permissions or temporarily unavailable removable media).
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
) -> list[dict]:
    status = get_status(es)
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
            stat = Path(item["path"]).stat()
            item["size"] = stat.st_size
            item["mtime_ns"] = stat.st_mtime_ns
            item["accessible"] = True
        except OSError:
            item["size"] = None
            item["mtime_ns"] = None
            item["accessible"] = False

    return sorted(found.values(), key=lambda x: (x["directory"].lower(), x["path"].lower()))

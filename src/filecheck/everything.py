from __future__ import annotations

import os
import shutil
import subprocess
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


def _run(es_path: Path, args: list[str], timeout: int = 30) -> str:
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.run(
        [str(es_path), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        creationflags=creationflags,
        check=False,
    )
    stdout = _decode(proc.stdout).strip()
    stderr = _decode(proc.stderr).strip()
    if proc.returncode != 0:
        detail = stderr or stdout or f"exit={proc.returncode}"
        if proc.returncode in (7, 8):
            detail += "；请确认 Everything 1.4 已启动且索引已加载"
        raise EverythingError(detail)
    return stdout


def get_status(es: str | None = None) -> EverythingStatus:
    es_path = find_es(es)
    es_version = _run(es_path, ["-version"])
    everything_version = _run(es_path, ["-get-everything-version"])
    if not everything_version.startswith("1.4."):
        raise EverythingError(
            f"当前 Everything 版本为 {everything_version}，V0.1 按 1.4.x 环境验证。"
        )
    return EverythingStatus(str(es_path), es_version, everything_version)


def _safe_keyword(keyword: str) -> str:
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("关键词不能为空")
    if '"' in keyword:
        raise ValueError(f"V0.1 暂不支持包含双引号的关键词: {keyword!r}")
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
    args = ["-timeout", "10000", "/a-d", "-full-path", "-n", str(max_results), "-s"]
    if match_path:
        args.append("-p")
    if path_prefix:
        args.extend(["-path", str(Path(path_prefix).expanduser())])
    args.append(query)

    output = _run(es_path, args, timeout=60)
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

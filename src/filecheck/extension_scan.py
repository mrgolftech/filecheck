"""Extension-only search against the same portable Everything index used by keyword scans."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable

from . import everything


def normalize_extensions(values: str | Iterable[str]) -> list[str]:
    """Parse .pdf, DOCX; xlsx while rejecting unsafe Everything query tokens.

    A blank selection is never interpreted as 'all files'.
    """
    if isinstance(values, str):
        parts = re.split(r"[,，;；\s]+", values)
    else:
        parts = list(values)
    result: list[str] = []
    seen: set[str] = set()
    for raw in parts:
        token = str(raw).strip().lower().lstrip(".")
        if not token:
            continue
        if not re.fullmatch(r"[a-z0-9][a-z0-9_+\-]*", token):
            raise ValueError(f"无效扩展名: {raw!r}；请填写 pdf、.docx 等单段扩展名")
        if token not in seen:
            result.append(token)
            seen.add(token)
    if not result:
        raise ValueError("扩展名列表不能为空，请至少指定一种文件扩展名")
    return result


def scan_extensions(
    extensions: str | Iterable[str],
    *,
    es: str | None = None,
    max_results_per_extension: int = 100000,
    path_prefix: str | None = None,
    instance: str | None = None,
    exclude_roots: Iterable[str | Path] = (),
) -> list[dict]:
    """Find files by suffix, without applying any filename keyword or sensitivity rule.

    Each extension is queried separately to make per-extension result caps observable.
    An over-limit query fails closed rather than creating a silently incomplete backup.
    """
    wanted = normalize_extensions(extensions)
    limit = int(max_results_per_extension)
    if limit < 1:
        raise ValueError("单个扩展名的查询结果上限必须大于零")

    status = everything.get_status(es, instance=instance)
    es_path = Path(status.es_path)
    exclusions = [str(root) for root in exclude_roots if str(root).strip()]
    prefix = str(Path(path_prefix).expanduser()) if path_prefix else None
    found: dict[str, dict] = {}

    for ext in wanted:
        args = everything._with_instance(
            ["-timeout", "10000", "/a-d", "-full-path-and-name", "-n", str(limit), "-s"],
            instance,
        )
        if prefix:
            args.extend(["-path", prefix])
        args.append(f"ext:{ext}")
        output = everything._run_export_txt(es_path, args, timeout=60, argv_mode=True)
        lines = [line.strip().strip('"') for line in output.splitlines() if line.strip()]
        if len(lines) >= limit:
            raise RuntimeError(
                f".{ext} 文件查询已达到 {limit} 条上限，结果可能不完整；"
                "请缩小索引范围或提高规则 max_results_per_keyword 后重试"
            )
        for raw in lines:
            path = Path(raw)
            if path.suffix.lower() != "." + ext:
                continue
            if prefix and not everything._under_root(path, prefix):
                continue
            if any(everything._under_root(path, excluded) for excluded in exclusions):
                continue
            key = os.path.normcase(os.path.abspath(str(path))).casefold()
            if key in found:
                continue
            item = {
                "path": str(path),
                "directory": str(path.parent),
                "matched_keywords": [],
                "matched_extension": ext,
                "levels": ["review"],
                "severity": "review",
            }
            try:
                stat = path.stat()
                item["size"] = stat.st_size
                item["mtime_ns"] = stat.st_mtime_ns
                item["accessible"] = True
            except OSError:
                item["size"] = None
                item["mtime_ns"] = None
                item["accessible"] = False
            found[key] = item
    return sorted(found.values(), key=lambda item: (item["directory"].lower(), item["path"].lower()))

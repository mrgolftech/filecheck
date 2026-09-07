from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .backup import BackupError, create_backup, restore_backup
from .everything import EverythingError, get_status, scan_keywords
from .util import now_iso, write_json


def _load_rules(path: str | Path) -> dict:
    rules_path = Path(path)
    try:
        data = json.loads(rules_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"规则文件不存在: {rules_path}") from exc
    if not isinstance(data.get("keywords"), dict) or not data.get("extensions"):
        raise RuntimeError(f"规则文件格式无效: {rules_path}")
    return data


def cmd_doctor(args: argparse.Namespace) -> int:
    status = get_status(args.es)
    print("Everything 环境检查通过")
    print(f"  es.exe: {status.es_path}")
    print(f"  ES CLI: {status.es_version}")
    print(f"  Everything: {status.everything_version}")
    return 0


def _print_scan(items: list[dict]) -> None:
    counts = Counter(item["severity"] for item in items)
    print(f"\n共发现 {len(items)} 个候选文件")
    print(
        "  high={high}  sensitive={sensitive}  review={review}".format(
            high=counts.get("high", 0),
            sensitive=counts.get("sensitive", 0),
            review=counts.get("review", 0),
        )
    )

    grouped: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for index, item in enumerate(items, start=1):
        grouped[item["directory"]].append((index, item))

    for directory, rows in grouped.items():
        print(f"\n[{directory}]  ({len(rows)} 个)")
        for index, item in rows:
            keywords = ", ".join(item["matched_keywords"])
            print(f"  {index:>5}. [{item['severity']:<9}] {Path(item['path']).name}  <{keywords}>")


def cmd_scan(args: argparse.Namespace) -> int:
    rules = _load_rules(args.rules)
    status = get_status(args.es)
    print(f"使用 Everything {status.everything_version} / ES {status.es_version}")
    print("正在按关键词查询 Everything 索引……")
    items = scan_keywords(
        rules["keywords"],
        rules["extensions"],
        es=args.es,
        max_results_per_keyword=int(rules.get("max_results_per_keyword", 100000)),
        match_path=args.match_path,
        path_prefix=args.path,
    )
    _print_scan(items)

    output = Path(args.output)
    payload = {
        "schema_version": 1,
        "created_at": now_iso(),
        "engine": "everything-1.4",
        "everything_version": status.everything_version,
        "match_path": args.match_path,
        "path_filter": args.path,
        "rules": str(Path(args.rules).resolve()),
        "items": items,
    }
    write_json(output, payload)
    print(f"\n扫描结果已保存: {output.resolve()}")
    print("注意：结果仅表示关键词命中，需要人工复核。")
    return 0


def _parse_selection(expr: str, total: int) -> list[int]:
    result: set[int] = set()
    for part in expr.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            left, right = part.split("-", 1)
            start, end = int(left), int(right)
            if start > end:
                start, end = end, start
            result.update(range(start, end + 1))
        else:
            result.add(int(part))
    invalid = sorted(i for i in result if i < 1 or i > total)
    if invalid:
        raise ValueError(f"选择编号超出范围: {invalid}")
    return sorted(result)


def _sources_from_scan(scan_path: str | Path, selection: str) -> list[str]:
    payload = json.loads(Path(scan_path).read_text(encoding="utf-8"))
    items = payload.get("items", [])
    indexes = _parse_selection(selection, len(items))
    return [items[i - 1]["path"] for i in indexes]


def cmd_backup(args: argparse.Namespace) -> int:
    sources = list(args.sources or [])
    if args.from_scan:
        if not args.select:
            raise RuntimeError("使用 --from-scan 时必须指定 --select，例如 1,3-5")
        sources.extend(_sources_from_scan(args.from_scan, args.select))
    if not sources:
        raise RuntimeError("至少指定一个源文件/目录，或使用 --from-scan")

    if args.remove_source:
        print("警告：--remove-source 会在完整备份并校验成功后移除原文件。")
        if not args.yes:
            answer = input("确认继续？输入 YES: ").strip()
            if answer != "YES":
                print("已取消。")
                return 2

    result = create_backup(
        sources,
        args.dest,
        zip_mode=args.zip,
        remove_source=args.remove_source,
    )
    print(f"备份完成: {result.resolve()}")
    if args.remove_source:
        print("原文件已在二次 SHA-256 校验后移出；恢复路径保存在 manifest 中。")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    results = restore_backup(args.backup, conflict=args.conflict)
    restored = sum(1 for row in results if row["state"] == "restored")
    skipped = sum(1 for row in results if row["state"] == "skipped")
    print(f"恢复完成：restored={restored}, skipped={skipped}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="filecheck",
        description="FileCheck V0.1 - Everything 1.4 加速的离线文件自查、备份和恢复工具",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="检查 Everything 1.4 / es.exe 环境")
    p.add_argument("--es", help="显式指定 es.exe 路径")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("scan", help="调用 Everything 按关键词快速扫描文件名/路径")
    p.add_argument("--rules", default="config/rules.json", help="规则 JSON 路径")
    p.add_argument("--es", help="显式指定 es.exe 路径")
    p.add_argument("--path", help="仅保留该目录/盘符下的结果，例如 D:\\")
    p.add_argument("--match-path", action="store_true", help="关键词同时匹配完整路径；默认只匹配文件名")
    p.add_argument("--output", default="scan-results.json", help="扫描结果 JSON")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("backup", help="复制/压缩备份，并记录原始路径和 SHA-256")
    p.add_argument("sources", nargs="*", help="要备份的文件或目录")
    p.add_argument("--dest", required=True, help="合规备份目标根目录")
    p.add_argument("--zip", action="store_true", help="生成 ZIP 包而不是目录备份")
    p.add_argument("--remove-source", action="store_true", help="备份完整校验后移除原文件")
    p.add_argument("--yes", action="store_true", help="与 --remove-source 配合，跳过交互确认")
    p.add_argument("--from-scan", help="从 scan-results.json 选择候选文件")
    p.add_argument("--select", help="候选编号，例如 1,3-5")
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("restore", help="依据 manifest 恢复到原始路径")
    p.add_argument("backup", help="备份批次目录或 ZIP 文件")
    p.add_argument(
        "--conflict",
        choices=("skip", "overwrite", "rename"),
        default="skip",
        help="原路径已有文件时的策略",
    )
    p.set_defaults(func=cmd_restore)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except (EverythingError, BackupError, RuntimeError, ValueError, OSError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

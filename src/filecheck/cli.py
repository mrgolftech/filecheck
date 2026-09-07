from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from colorama import Fore, Style, just_fix_windows_console

from .backup import BackupError, create_backup, restore_backup, verify_backup
from .everything import EverythingError, get_status, scan_keywords
from .selftest import run_selftest
from .util import now_iso, write_json


def _configure_console_streams() -> None:
    """Keep localized/color output working on Windows consoles."""
    just_fix_windows_console()
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (OSError, ValueError):
                pass


def _paint(text: str, color: str = "", *, bright: bool = False) -> str:
    prefix = (Style.BRIGHT if bright else "") + color
    return f"{prefix}{text}{Style.RESET_ALL}"


def _severity_text(level: str) -> str:
    if level == "high":
        return _paint(f"{level:<9}", Fore.RED, bright=True)
    if level == "sensitive":
        return _paint(f"{level:<9}", Fore.YELLOW, bright=True)
    return _paint(f"{level:<9}", Fore.CYAN)


def _success(text: str) -> str:
    return _paint(text, Fore.GREEN, bright=True)


def _warning(text: str) -> str:
    return _paint(text, Fore.YELLOW, bright=True)


def _info(text: str) -> str:
    return _paint(text, Fore.CYAN)


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
    print(_success("Everything 环境检查通过"))
    print(f"  es.exe: {_info(status.es_path)}")
    print(f"  ES CLI: {_info(status.es_version)}")
    print(f"  Everything: {_info(status.everything_version)}")
    return 0


def _print_scan(items: list[dict]) -> None:
    counts = Counter(item["severity"] for item in items)
    print(f"\n{Style.BRIGHT}共发现 {len(items)} 个候选文件{Style.RESET_ALL}")
    print(
        "  "
        + _paint(f"high={counts.get('high', 0)}", Fore.RED, bright=True)
        + "  "
        + _paint(f"sensitive={counts.get('sensitive', 0)}", Fore.YELLOW, bright=True)
        + "  "
        + _paint(f"review={counts.get('review', 0)}", Fore.CYAN)
    )

    grouped: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for index, item in enumerate(items, start=1):
        grouped[item["directory"]].append((index, item))

    for directory, rows in grouped.items():
        print(f"\n{_info(f'[{directory}]')}  ({len(rows)} 个)")
        for index, item in rows:
            keywords = ", ".join(item["matched_keywords"])
            severity = _severity_text(item["severity"])
            filename = Path(item["path"]).name
            print(
                f"  {index:>5}. [{severity}] "
                f"{filename}  {_paint(f'<{keywords}>', Fore.MAGENTA)}"
            )


def cmd_scan(args: argparse.Namespace) -> int:
    rules = _load_rules(args.rules)
    status = get_status(args.es)
    print(
        f"使用 Everything {_info(status.everything_version)} / "
        f"ES {_info(status.es_version)}"
    )
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
    resolved_output = output.resolve()
    print(f"\n扫描结果已保存: {_info(str(resolved_output))}")
    print(_warning("注意：结果仅表示关键词命中，需要人工复核。"))
    if items:
        print(_info("下一步：人工复核候选编号后，再选择文件进行备份。"))
        print(
            "  示例: filecheck backup --from-scan "
            f'"{resolved_output}" --select 1,3-5 --dest <备份目录>'
        )
        print(_warning("扫描结束后不会自动备份、移动或删除任何文件。"))
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

    result = create_backup(sources, args.dest, zip_mode=args.zip)
    manifest = verify_backup(result)
    print(_success("备份完成并通过全量 SHA-256 校验"))
    print(f"  路径: {_info(str(result.resolve()))}")
    print(f"  文件数: {len(manifest['items'])}")
    print(_warning("V0.1 为安全起见不会自动移除原文件；请先完成恢复演练和人工确认。"))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    manifest = verify_backup(args.backup)
    print(_success("备份验证通过"))
    print(f"  路径: {_info(str(Path(args.backup).resolve()))}")
    print(f"  批次: {manifest.get('batch_id', '-')}")
    print(f"  文件数: {len(manifest['items'])}")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    results = restore_backup(args.backup, conflict=args.conflict)
    restored = sum(1 for row in results if row["state"] == "restored")
    skipped = sum(1 for row in results if row["state"] == "skipped")
    print(_success("恢复完成"))
    print(f"  restored={_paint(str(restored), Fore.GREEN, bright=True)}")
    print(f"  skipped={_paint(str(skipped), Fore.YELLOW)}")
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    report = run_selftest()
    for name, state in report.items():
        color = Fore.GREEN if str(state).startswith("PASS") else Fore.YELLOW
        print(f"{name}: {_paint(str(state), color, bright=True)}")
    print(_success("FileCheck 备份/验证/恢复自检通过。"))
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

    p = sub.add_parser("backup", help="只读复制/压缩备份，并记录原始路径和 SHA-256")
    p.add_argument("sources", nargs="*", help="要备份的文件或目录")
    p.add_argument("--dest", required=True, help="合规备份目标根目录")
    p.add_argument("--zip", action="store_true", help="生成 ZIP 包而不是目录备份")
    p.add_argument("--from-scan", help="从 scan-results.json 选择候选文件")
    p.add_argument("--select", help="候选编号，例如 1,3-5")
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("verify", help="对备份逐文件执行大小 + SHA-256 全量验证")
    p.add_argument("backup", help="备份批次目录或 ZIP 文件")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("restore", help="验证整个备份后，依据 manifest 原子恢复到原始路径")
    p.add_argument("backup", help="备份批次目录或 ZIP 文件")
    p.add_argument(
        "--conflict",
        choices=("skip", "overwrite", "rename"),
        default="skip",
        help="原路径已有文件时的策略；overwrite 也会先恢复到临时文件并校验后再原子替换",
    )
    p.set_defaults(func=cmd_restore)

    p = sub.add_parser("selftest", help="在临时目录执行目录/ZIP备份与恢复回环自检")
    p.set_defaults(func=cmd_selftest)
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_console_streams()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except (EverythingError, BackupError, RuntimeError, ValueError, OSError) as exc:
        print(_paint(f"错误: {exc}", Fore.RED, bright=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

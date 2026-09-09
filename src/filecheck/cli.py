from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from colorama import Fore, Style, just_fix_windows_console

from .backup import BackupError, create_backup, read_backup_manifest, restore_backup, verify_backup
from .everything import FILECHECK_INSTANCE, EverythingError, find_es, scan_keywords
from .migration import MigrationError, preflight_migration, remove_verified_sources, resume_migration
from .portable_everything import (
    PortableEverythingError,
    configure_and_reindex,
    ensure_instance,
    find_everything_exe,
    load_index_state,
)
from .scan_guard import filter_protected_backup_items
from .selftest import run_selftest
from .util import now_iso, program_dir, scan_results_dir, sha256_file, write_json


_COLOR_ENABLED = False


def _configure_console_streams() -> None:
    global _COLOR_ENABLED
    just_fix_windows_console()
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (OSError, ValueError):
                pass
    _COLOR_ENABLED = bool(getattr(sys.stdout, "isatty", lambda: False)()) and not os.environ.get("NO_COLOR")


def _paint(text: str, color: str = "", *, bright: bool = False) -> str:
    if not _COLOR_ENABLED:
        return text
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


def _default_rules_path() -> str:
    return str(program_dir() / "config" / "rules.json")


def _default_scan_output() -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return str(scan_results_dir() / f"scan-results-{stamp}.json")


def _load_rules(path: str | Path) -> dict:
    rules_path = Path(path)
    try:
        data = json.loads(rules_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"规则文件不存在: {rules_path}") from exc
    if not isinstance(data.get("keywords"), dict) or not data.get("extensions"):
        raise RuntimeError(f"规则文件格式无效: {rules_path}")
    return data


def _rules_metadata(path: str | Path) -> dict:
    rules_path = Path(path)
    return {"file": rules_path.name, "sha256": sha256_file(rules_path)}


def cmd_doctor(args: argparse.Namespace) -> int:
    es_path = find_es(args.es)
    everything_path = find_everything_exe(args.everything)
    print(_success("FileCheck 便携运行环境检查通过"))
    print(f"  FileCheck 目录: {_info(str(program_dir()))}")
    print(f"  Everything.exe: {_info(str(everything_path))}")
    print(f"  es.exe: {_info(str(es_path))}")
    state = load_index_state(required=False)
    if state is None:
        print(_warning("  专用索引: 尚未建立；下一步请选择磁盘和备份目录建立索引。"))
        return 0
    status = ensure_instance(args.es, args.everything)
    print(f"  FileCheck Everything 实例: {_info(status.everything_version)}")
    print(f"  ES CLI: {_info(status.es_version)}")
    print(f"  已索引范围: {', '.join(state.get('selected_roots', []))}")
    print(f"  备份排除目录: {state.get('backup_root', '-')}")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    result = configure_and_reindex(
        args.drive,
        args.backup_root,
        everything=args.everything,
        es=args.es,
    )
    print(_success("FileCheck 专用索引建立完成"))
    print(f"  Everything: {result.status.everything_version}")
    print(f"  实例: {FILECHECK_INSTANCE}")
    print(f"  索引范围: {', '.join(result.selected_roots)}")
    print(f"  配置文件: {result.config_path}")
    print(f"  数据库: {result.database_path}")
    print(f"  自动排除: {', '.join(result.excluded_roots)}")
    return 0


def _print_scan(items: list[dict], *, limit: int = 100) -> None:
    counts = Counter(item["severity"] for item in items)
    print(f"\n{_paint(f'共发现 {len(items)} 个候选文件', bright=True)}")
    print(
        "  "
        + _paint(f"high={counts.get('high', 0)}", Fore.RED, bright=True)
        + "  "
        + _paint(f"sensitive={counts.get('sensitive', 0)}", Fore.YELLOW, bright=True)
        + "  "
        + _paint(f"review={counts.get('review', 0)}", Fore.CYAN)
    )
    effective_limit = max(0, int(limit))
    display_rows = list(enumerate(items[:effective_limit], start=1)) if effective_limit else []
    grouped: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for index, item in display_rows:
        grouped[item["directory"]].append((index, item))
    for directory, rows in grouped.items():
        print(f"\n{_info(f'[{directory}]')}  ({len(rows)} 个已显示)")
        for index, item in rows:
            keywords = ", ".join(item["matched_keywords"])
            severity = _severity_text(item["severity"])
            print(f"  {index:>5}. [{severity}] {Path(item['path']).name}  {_paint(f'<{keywords}>', Fore.MAGENTA)}")
    if len(items) > len(display_rows):
        print(_warning(f"\n候选较多，仅显示前 {len(display_rows)} 个；完整结果已写入 JSON/CSV。"))


def _write_scan_csv(json_output: Path, items: list[dict]) -> Path:
    csv_path = json_output.with_suffix(".csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["序号", "源文件完整路径", "目录", "命中关键词", "级别", "大小(字节)", "当前可访问"])
        for index, item in enumerate(items, start=1):
            writer.writerow(
                [
                    index,
                    item["path"],
                    item["directory"],
                    ",".join(item["matched_keywords"]),
                    item["severity"],
                    "" if item.get("size") is None else item["size"],
                    "是" if item.get("accessible") else "否",
                ]
            )
    return csv_path


def cmd_scan(args: argparse.Namespace) -> int:
    rules = _load_rules(args.rules)
    state = load_index_state(required=True)
    status = ensure_instance(args.es, args.everything)
    exclusions = list(state.get("excluded_roots", []))
    print(f"使用 FileCheck 专用 Everything {status.everything_version} / ES {status.es_version}")
    print(f"索引范围: {', '.join(state.get('selected_roots', []))}")
    print("正在按关键词查询专用索引……")
    raw_items = list(
        scan_keywords(
            rules["keywords"],
            rules["extensions"],
            es=args.es,
            max_results_per_keyword=int(rules.get("max_results_per_keyword", 100000)),
            match_path=args.match_path,
            path_prefix=args.path,
            instance=FILECHECK_INSTANCE,
            exclude_roots=exclusions,
        )
    )
    items, protected_batches = filter_protected_backup_items(raw_items)
    excluded_backup_items = len(raw_items) - len(items)
    if excluded_backup_items:
        print(
            _warning(
                f"已自动排除 {excluded_backup_items} 个位于历史 FileCheck 备份中的候选文件，"
                f"涉及 {len(protected_batches)} 个备份批次。"
            )
        )
        for batch_path in protected_batches[:5]:
            print(f"  保护的历史备份: {_info(batch_path)}")
        if len(protected_batches) > 5:
            print(f"  另有 {len(protected_batches) - 5} 个历史备份批次已保护。")
    _print_scan(items, limit=args.list_limit)
    output = Path(args.output)
    payload = {
        "schema_version": 1,
        "created_at": now_iso(),
        "engine": "everything-1.4-portable",
        "instance": FILECHECK_INSTANCE,
        "everything_version": status.everything_version,
        "selected_roots": state.get("selected_roots", []),
        "excluded_roots": exclusions,
        "protected_backup_batches": protected_batches,
        "excluded_backup_items": excluded_backup_items,
        "match_path": args.match_path,
        "path_filter": args.path,
        "rules": _rules_metadata(args.rules),
        "items": items,
    }
    write_json(output, payload)
    csv_path = _write_scan_csv(output, items)
    print(f"\n扫描 JSON: {_info(str(output.resolve()))}")
    print(f"人工核对 CSV: {_info(str(csv_path.resolve()))}")
    print(_warning("关键词命中只表示候选，请先人工核对，再进入备份。"))
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


def _load_scan_payload(scan_path: str | Path) -> dict:
    path = Path(scan_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"扫描结果不存在: {path}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"扫描结果 JSON 损坏: {path}") from exc
    if payload.get("schema_version") != 1 or not isinstance(payload.get("items"), list):
        raise RuntimeError(f"扫描结果格式无效: {path}")
    return payload


def _sources_from_scan(scan_path: str | Path, selection: str | None = None) -> list[str]:
    items = _load_scan_payload(scan_path)["items"]
    if not items:
        raise RuntimeError("扫描结果中没有候选文件")
    indexes = _parse_selection(selection, len(items)) if selection else list(range(1, len(items) + 1))
    return [items[i - 1]["path"] for i in indexes]


def _resolve_sources(args: argparse.Namespace) -> list[str]:
    sources = list(args.sources or [])
    if args.from_scan:
        sources.extend(_sources_from_scan(args.from_scan, getattr(args, "select", None)))
    if not sources:
        raise RuntimeError("至少指定一个源文件/目录，或使用 --from-scan")
    return sources


def _progress(stage: str, current: int, total: int, path: str) -> None:
    if total <= 0:
        return
    if current != 1 and current != total and current % 100 != 0:
        return
    labels = {"copy": "复制", "verify": "校验", "restore": "恢复", "recheck": "源文件复核", "remove": "源文件删除"}
    print(f"  {labels.get(stage, stage)}: {current}/{total}")


def _processing_rate(total_bytes: int, elapsed: float) -> str | None:
    if total_bytes <= 0 or elapsed <= 0:
        return None
    return f"{total_bytes / (1024 * 1024) / elapsed:.1f} MiB/s"


def cmd_backup(args: argparse.Namespace) -> int:
    sources = _resolve_sources(args)
    if args.from_scan and not args.select:
        print(f"准备目录备份扫描结果中的全部候选: {len(sources)} 个文件")
    started = time.perf_counter()
    result = create_backup(sources, args.dest, progress=_progress)
    elapsed = time.perf_counter() - started
    manifest = read_backup_manifest(result)
    total_bytes = int(manifest.get("source_bytes_total", sum(int(i["size"]) for i in manifest["items"])))
    print(_success("目录备份完成并通过全量 SHA-256 校验"))
    print(f"  路径: {_info(str(result.resolve()))}")
    print(f"  文件数: {len(manifest['items'])}")
    print(f"  总大小: {total_bytes} 字节")
    print(f"  总耗时: {elapsed:.1f} 秒")
    rate = _processing_rate(total_bytes, elapsed)
    if rate:
        print(f"  平均处理吞吐(含校验): {rate}")
    print(_warning("backup 永远不删除源文件。请人工检查备份目录并再次 verify 后，再执行 remove-sources。"))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    manifest = verify_backup(args.backup, progress=_progress)
    print(_success("备份验证通过"))
    print(f"  路径: {_info(str(Path(args.backup).resolve()))}")
    print(f"  批次: {manifest.get('batch_id', '-')}")
    print(f"  文件数: {len(manifest['items'])}")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    results = restore_backup(args.backup, conflict=args.conflict, progress=_progress)
    restored = sum(1 for row in results if row["state"] == "restored")
    skipped = sum(1 for row in results if row["state"] == "skipped")
    print(_success("恢复完成"))
    print(f"  restored={_paint(str(restored), Fore.GREEN, bright=True)}")
    print(f"  skipped={_paint(str(skipped), Fore.YELLOW)}")
    return 0


def _confirm_source_removal(files: int) -> bool:
    try:
        answer = input(f"备份与源文件复核均已通过。下一步将删除 {files} 个 manifest 源文件。输入 YES 继续: ")
    except (EOFError, KeyboardInterrupt):
        return False
    return answer.strip().upper() == "YES"


def _print_migration_result(state_file: Path, state: dict) -> int:
    print(f"  删除状态: {_info(str(state_file))}")
    print(f"  deleted={state.get('deleted', 0)}")
    print(f"  already_absent={state.get('already_absent', 0)}")
    print(f"  failed={state.get('failed', 0)}")
    if state.get("failed", 0):
        print(_warning("部分源文件未删除；已跳过并继续其余文件。关闭占用程序后可继续删除。"))
        print(f"  未删除清单: {state_file.parent / 'not-deleted.txt'}")
        print(f'  filecheck remove-resume "{state_file.parent}"')
        return 2
    print(_success("源文件删除完成；备份和 manifest 保持不变。"))
    return 0


def cmd_remove_sources(args: argparse.Namespace) -> int:
    summary = preflight_migration(args.backup, progress=_progress)
    print(_success("完整备份及全部源文件 SHA-256 复核通过"))
    print(f"  文件数: {summary['files']}")
    if not args.yes and not _confirm_source_removal(summary["files"]):
        print(_warning("已取消源文件删除；备份保持不变。"))
        return 0
    state_file, state = remove_verified_sources(args.backup, progress=_progress, preflight=False)
    return _print_migration_result(state_file, state)


def cmd_remove_resume(args: argparse.Namespace) -> int:
    if not args.yes:
        try:
            answer = input("将重新验证备份并继续处理未删除文件。输入 YES 继续: ")
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer.strip().upper() != "YES":
            print(_warning("已取消继续删除。"))
            return 0
    state_file, state = resume_migration(args.state, progress=_progress)
    return _print_migration_result(state_file, state)


def cmd_migrate(args: argparse.Namespace) -> int:
    sources = _resolve_sources(args)
    backup = create_backup(sources, args.dest, progress=_progress)
    print(_success(f"备份完成: {backup}"))
    summary = preflight_migration(backup, progress=_progress)
    if not args.yes and not _confirm_source_removal(summary["files"]):
        print(_warning("已取消源文件删除；已验证备份保留。"))
        return 0
    state_file, state = remove_verified_sources(backup, progress=_progress, preflight=False)
    return _print_migration_result(state_file, state)


def cmd_migrate_resume(args: argparse.Namespace) -> int:
    return cmd_remove_resume(args)


def cmd_selftest(args: argparse.Namespace) -> int:
    report = run_selftest()
    for name, state in report.items():
        color = Fore.GREEN if str(state).startswith("PASS") else Fore.YELLOW
        print(f"{name}: {_paint(str(state), color, bright=True)}")
    print(_success("FileCheck 目录备份/验证/删除/恢复自检通过。"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="filecheck",
        description="FileCheck v0.1.1 - portable Everything 索引、目录备份、验证、安全删除和恢复",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="检查 FileCheck、portable Everything 和 ES 环境")
    p.add_argument("--es")
    p.add_argument("--everything")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("index", help="选择磁盘/目录并建立 FileCheck 专用 portable Everything 索引")
    p.add_argument("--drive", action="append", required=True, help="要索引的盘符/目录；可重复，例如 --drive C: --drive D:\")
    p.add_argument("--backup-root", required=True, help="统一备份根目录；会自动从索引和扫描结果中排除")
    p.add_argument("--es")
    p.add_argument("--everything")
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("scan", help="查询 FileCheck 专用索引并保存 JSON/CSV")
    p.add_argument("--rules", default=_default_rules_path(), help="规则 JSON 路径")
    p.add_argument("--es")
    p.add_argument("--everything")
    p.add_argument("--path", help="高级用法：仅扫描已建索引中的指定子目录")
    p.add_argument("--match-path", action="store_true", help="关键词同时匹配完整路径；默认只匹配文件名")
    p.add_argument("--output", default=_default_scan_output(), help="扫描结果 JSON")
    p.add_argument("--list-limit", type=int, default=100)
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("backup", help="创建人工可读的目录备份并全量校验")
    p.add_argument("sources", nargs="*")
    p.add_argument("--dest", required=True)
    p.add_argument("--from-scan", help="从 scan-results.json 批量备份；默认全部候选")
    p.add_argument("--select", help="高级过滤，例如 1,3-5")
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("verify", help="对目录备份逐文件执行大小 + SHA-256 全量验证")
    p.add_argument("backup", help="已解压/原生目录备份批次")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("remove-sources", help="验证备份和源文件后，删除 manifest 列出的源文件")
    p.add_argument("backup", help="目录备份批次")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_remove_sources)

    p = sub.add_parser("remove-resume", help="继续 source-removal.json 中失败/未完成的删除")
    p.add_argument("state", help="备份批次目录或 source-removal.json")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_remove_resume)

    # Backward-compatible advanced aliases. They are intentionally not part of
    # the recommended interactive workflow.
    p = sub.add_parser("migrate", help=argparse.SUPPRESS)
    p.add_argument("sources", nargs="*")
    p.add_argument("--dest", required=True)
    p.add_argument("--from-scan")
    p.add_argument("--select")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_migrate)

    p = sub.add_parser("migrate-resume", help=argparse.SUPPRESS)
    p.add_argument("state")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_migrate_resume)

    p = sub.add_parser("restore", help="验证目录备份后，依据 manifest 恢复到各自原始路径")
    p.add_argument("backup", help="已解压/原生目录备份批次")
    p.add_argument("--conflict", choices=("skip", "overwrite", "rename"), default="skip")
    p.set_defaults(func=cmd_restore)

    p = sub.add_parser("selftest", help="执行目录备份、验证、删除、恢复回环自检")
    p.set_defaults(func=cmd_selftest)
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_console_streams()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except (PortableEverythingError, EverythingError, MigrationError, BackupError, RuntimeError, ValueError, OSError) as exc:
        print(_paint(f"错误: {exc}", Fore.RED, bright=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

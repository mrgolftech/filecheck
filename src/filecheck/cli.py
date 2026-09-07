from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from colorama import Fore, Style, just_fix_windows_console

from .backup import BackupError, create_backup, read_backup_manifest, restore_backup, verify_backup
from .everything import EverythingError, get_status, scan_keywords
from .migration import MigrationError, preflight_migration, remove_verified_sources, resume_migration
from .selftest import run_selftest
from .util import now_iso, sha256_file, write_json


_COLOR_ENABLED = False


def _configure_console_streams() -> None:
    """Keep localized/color output working on Windows consoles."""
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
    return {
        "file": rules_path.name,
        "sha256": sha256_file(rules_path),
    }


def cmd_doctor(args: argparse.Namespace) -> int:
    status = get_status(args.es)
    print(_success("Everything 环境检查通过"))
    print(f"  es.exe: {_info(status.es_path)}")
    print(f"  ES CLI: {_info(status.es_version)}")
    print(f"  Everything: {_info(status.everything_version)}")
    return 0


def _print_scan(items: list[dict], *, limit: int = 100) -> None:
    counts = Counter(item["severity"] for item in items)
    heading = f"共发现 {len(items)} 个候选文件"
    print(f"\n{_paint(heading, bright=True)}")
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
            filename = Path(item["path"]).name
            print(
                f"  {index:>5}. [{severity}] "
                f"{filename}  {_paint(f'<{keywords}>', Fore.MAGENTA)}"
            )

    if len(items) > len(display_rows):
        print(
            _warning(
                f"\n候选较多，仅显示前 {len(display_rows)} 个；完整 {len(items)} 个结果均已写入 JSON。"
            )
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
    _print_scan(items, limit=args.list_limit)

    output = Path(args.output)
    payload = {
        "schema_version": 1,
        "created_at": now_iso(),
        "engine": "everything-1.4",
        "everything_version": status.everything_version,
        "match_path": args.match_path,
        "path_filter": args.path,
        "rules": _rules_metadata(args.rules),
        "items": items,
    }
    write_json(output, payload)
    resolved_output = output.resolve()
    print(f"\n扫描结果已保存: {_info(str(resolved_output))}")
    print(_warning("注意：结果仅表示关键词命中，不等同于文件性质认定。"))
    if items:
        print(_info("下一步可直接将本次扫描的全部候选批量备份："))
        print(
            "  filecheck backup --from-scan "
            f'"{resolved_output}" --dest <备份目录>'
        )
        print(_info("如需在备份全量验证后移除这些源文件，使用显式 migrate 命令："))
        print(
            "  filecheck migrate --from-scan "
            f'"{resolved_output}" --dest <备份目录>'
        )
        print(_warning("scan 本身不会备份、移动或删除任何文件。"))
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
    payload = _load_scan_payload(scan_path)
    items = payload["items"]
    if not items:
        raise RuntimeError("扫描结果中没有候选文件")
    if selection:
        indexes = _parse_selection(selection, len(items))
    else:
        indexes = list(range(1, len(items) + 1))
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
    labels = {
        "copy": "复制",
        "verify": "校验",
        "restore": "恢复",
        "recheck": "源文件复核",
        "remove": "源文件移除",
    }
    label = labels.get(stage, stage)
    print(f"  {label}: {current}/{total}")


def _processing_rate(total_bytes: int, elapsed: float) -> str | None:
    if total_bytes <= 0 or elapsed <= 0:
        return None
    return f"{total_bytes / (1024 * 1024) / elapsed:.1f} MiB/s"


def cmd_backup(args: argparse.Namespace) -> int:
    sources = _resolve_sources(args)
    if args.from_scan and not args.select:
        print(f"准备批量备份扫描结果中的全部候选: {len(sources)} 个文件")

    started = time.perf_counter()
    result = create_backup(sources, args.dest, zip_mode=args.zip, progress=_progress)
    elapsed = time.perf_counter() - started

    # create_backup only publishes after a full SHA-256 verification. Re-reading
    # every payload here merely to print metadata used to add another complete
    # disk pass, so read the already-validated manifest without hashing again.
    manifest = read_backup_manifest(result)
    total_bytes = int(
        manifest.get("source_bytes_total", sum(int(i["size"]) for i in manifest["items"]))
    )
    print(_success("备份完成并通过全量 SHA-256 校验"))
    print(f"  路径: {_info(str(result.resolve()))}")
    print(f"  文件数: {len(manifest['items'])}")
    print(f"  总大小: {total_bytes} 字节")
    print(f"  总耗时: {elapsed:.1f} 秒")
    rate = _processing_rate(total_bytes, elapsed)
    if rate:
        print(f"  平均处理吞吐(含校验): {rate}")
    print(_warning("backup 不会移除源文件；需要移除时必须显式使用 migrate。"))
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
        answer = input(
            f"备份与源文件复核均已通过。下一步将移除 {files} 个 manifest 源文件。"
            "输入 YES 继续: "
        )
    except (EOFError, KeyboardInterrupt):
        return False
    return answer.strip().upper() == "YES"


def _print_migration_result(state_file: Path, state: dict) -> int:
    print(f"  状态文件: {_info(str(state_file))}")
    print(f"  deleted={state.get('deleted', 0)}")
    print(f"  already_absent={state.get('already_absent', 0)}")
    print(f"  failed={state.get('failed', 0)}")
    if state.get("failed", 0):
        print(_warning("部分源文件未移除。关闭占用程序/处理权限后可执行 migrate-resume。"))
        print(f'  filecheck migrate-resume "{state_file}"')
        return 2
    print(_success("迁移完成：已验证备份仍可用，manifest 中的源文件已移除。"))
    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    sources = _resolve_sources(args)
    if args.from_scan and not args.select:
        print(f"准备迁移扫描结果中的全部候选: {len(sources)} 个文件")

    backup = create_backup(sources, args.dest, zip_mode=args.zip, progress=_progress)
    # The creation path has already completed one full payload verification.
    # preflight_migration below performs a fresh backup verification immediately
    # before any destructive source-removal decision, so an extra pass here is
    # redundant and was a significant cost for multi-gigabyte batches.
    manifest = read_backup_manifest(backup)
    print(_success("第一阶段完成：备份已创建并通过全量 SHA-256 校验"))
    print(f"  备份: {_info(str(backup.resolve()))}")
    print(f"  文件数: {len(manifest['items'])}")

    summary = preflight_migration(backup, progress=_progress)
    print(_success("第二阶段完成：全部源文件再次 SHA-256 复核通过"))
    print(f"  文件数: {summary['files']}")
    print(f"  总大小: {summary['bytes']} 字节")

    if not args.yes and not _confirm_source_removal(summary["files"]):
        print(_warning("已取消源文件移除。已验证备份保留不变。"))
        return 0

    state_file, state = remove_verified_sources(
        backup,
        progress=_progress,
        preflight=False,
    )
    return _print_migration_result(state_file, state)


def cmd_migrate_resume(args: argparse.Namespace) -> int:
    state_file = Path(args.state).expanduser().resolve()
    if not args.yes:
        try:
            answer = input(
                "将重新验证备份并继续处理迁移状态中尚未移除的源文件。输入 YES 继续: "
            )
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer.strip().upper() != "YES":
            print(_warning("已取消继续迁移。"))
            return 0
    result_path, state = resume_migration(state_file, progress=_progress)
    return _print_migration_result(result_path, state)


def cmd_selftest(args: argparse.Namespace) -> int:
    report = run_selftest()
    for name, state in report.items():
        color = Fore.GREEN if str(state).startswith("PASS") else Fore.YELLOW
        print(f"{name}: {_paint(str(state), color, bright=True)}")
    print(_success("FileCheck 备份/验证/恢复/迁移自检通过。"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="filecheck",
        description="FileCheck V0.1 - Everything 1.4 加速的离线文件自查、批量备份、迁移和恢复工具",
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
    p.add_argument("--list-limit", type=int, default=100, help="控制台最多显示多少个候选；0 表示只显示汇总")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("backup", help="批量复制/压缩备份，并记录原始路径和 SHA-256")
    p.add_argument("sources", nargs="*", help="要备份的文件或目录")
    p.add_argument("--dest", required=True, help="备份目标根目录")
    p.add_argument("--zip", action="store_true", help="生成 ZIP 包而不是目录备份")
    p.add_argument("--from-scan", help="从 scan-results.json 批量备份候选；默认处理全部候选")
    p.add_argument("--select", help="可选：仅处理候选编号，例如 1,3-5；省略时处理全部")
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("migrate", help="先批量备份并全量复核，再经一次确认移除 manifest 中的源文件")
    p.add_argument("sources", nargs="*", help="要迁移的文件或目录")
    p.add_argument("--dest", required=True, help="备份目标根目录")
    p.add_argument("--zip", action="store_true", help="生成 ZIP 备份后再进入源文件移除阶段")
    p.add_argument("--from-scan", help="从 scan-results.json 批量迁移候选；默认处理全部候选")
    p.add_argument("--select", help="可选：仅处理候选编号，例如 1,3-5；省略时处理全部")
    p.add_argument("--yes", action="store_true", help="跳过批次级 YES 确认；适用于明确的无人值守调用")
    p.set_defaults(func=cmd_migrate)

    p = sub.add_parser("migrate-resume", help="重新验证备份后继续处理上次未完成的源文件移除")
    p.add_argument("state", help="FC-xxxx[.zip].migration.json 状态文件")
    p.add_argument("--yes", action="store_true", help="跳过批次级 YES 确认")
    p.set_defaults(func=cmd_migrate_resume)

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

    p = sub.add_parser("selftest", help="在临时目录执行扫描后批量备份相关逻辑及目录/ZIP备份、迁移、恢复回环自检")
    p.set_defaults(func=cmd_selftest)
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_console_streams()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except (EverythingError, MigrationError, BackupError, RuntimeError, ValueError, OSError) as exc:
        print(_paint(f"错误: {exc}", Fore.RED, bright=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

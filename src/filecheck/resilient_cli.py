from __future__ import annotations

import sys
import time
from pathlib import Path

from . import cli as legacy
from .backup import BackupError, read_backup_manifest
from .everything import EverythingError
from .migration import (
    MigrationError,
    migration_state_path,
    preflight_migration,
    remove_verified_sources,
    resume_migration,
)
from .resumable import (
    create_resumable_backup,
    discover_operation_states,
    load_operation_state,
    mark_operation_state,
    operation_state_path,
    resume_resumable_backup,
)
from .util import make_batch_id, read_json


# Re-export the UI helpers used by menu.py. launcher.py replaces menu.cli with
# this module at runtime so the existing menu stays small and stable.
Fore = legacy.Fore
Style = legacy.Style
_configure_console_streams = legacy._configure_console_streams
_paint = legacy._paint
_success = legacy._success
_warning = legacy._warning
_info = legacy._info
build_parser = legacy.build_parser


def _progress(stage: str, current: int, total: int, path: str) -> None:
    if stage == "copy_error":
        print(_paint(f"  复制失败 [{current}/{total}]: {path}", Fore.RED, bright=True))
        return
    if stage == "verify_begin":
        print(
            _info(
                f"  开始全量 SHA-256 校验，共 {total} 个文件。"
                "若当前文件较大，单个文件校验期间可能暂时没有新的计数输出。"
            )
        )
        return
    if total <= 0:
        return
    if current != 1 and current != total and current % 100 != 0:
        return

    labels = {
        "copy_begin": "正在复制",
        "copy": "复制",
        "verify": "校验",
        "restore": "恢复",
        "recheck": "源文件复核",
        "remove": "源文件移除",
    }
    label = labels.get(stage, stage)
    suffix = ""
    if stage == "copy_begin" and path:
        suffix = f"  {path}"
    print(f"  {label}: {current}/{total}{suffix}")


def _processing_rate(total_bytes: int, elapsed: float) -> str | None:
    if total_bytes <= 0 or elapsed <= 0:
        return None
    return f"{total_bytes / (1024 * 1024) / elapsed:.1f} MiB/s"


def _print_backup_result(result: Path, state_path: Path, elapsed: float) -> int:
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
    print(f"  操作状态: {_info(str(state_path))}")
    print(_warning("backup 不会移除源文件；需要移除时必须显式使用 migrate。"))
    return 0


def cmd_backup(args) -> int:
    sources = legacy._resolve_sources(args)
    if args.from_scan and not args.select:
        print(f"准备批量备份扫描结果中的全部候选: {len(sources)} 个文件")

    batch_id = make_batch_id()
    state_path = operation_state_path(batch_id).resolve()
    print(_info(f"已建立可续传操作状态: {state_path}"))
    print(_info("中断后可在主菜单选择“继续未完成的备份/迁移”，无需重新复制已校验的暂存文件。"))

    started = time.perf_counter()
    result, actual_state_path, _state = create_resumable_backup(
        sources,
        args.dest,
        zip_mode=args.zip,
        progress=_progress,
        operation="backup",
        batch_id=batch_id,
    )
    elapsed = time.perf_counter() - started
    return _print_backup_result(result, actual_state_path, elapsed)


def _confirm_source_removal(files: int) -> bool:
    return legacy._confirm_source_removal(files)


def _finish_removal_state(op_state_path: Path, removal_state_path: Path, state: dict) -> int:
    status = "migration_completed" if not state.get("failed", 0) else "migration_partial"
    mark_operation_state(
        op_state_path,
        status,
        removal_state_path=str(removal_state_path),
    )
    return legacy._print_migration_result(removal_state_path, state)


def _continue_migration_after_backup(
    backup: Path,
    op_state_path: Path,
    *,
    yes: bool,
) -> int:
    manifest = read_backup_manifest(backup)
    print(_success("第一阶段完成：备份已创建并通过全量 SHA-256 校验"))
    print(f"  备份: {_info(str(backup.resolve()))}")
    print(f"  文件数: {len(manifest['items'])}")
    print(f"  操作状态: {_info(str(op_state_path))}")

    mark_operation_state(op_state_path, "source_rechecking", backup_path=str(backup))
    summary = preflight_migration(backup, progress=_progress)
    print(_success("第二阶段完成：全部源文件再次 SHA-256 复核通过"))
    print(f"  文件数: {summary['files']}")
    print(f"  总大小: {summary['bytes']} 字节")

    mark_operation_state(op_state_path, "awaiting_source_removal_confirmation")
    if not yes and not _confirm_source_removal(summary["files"]):
        print(_warning("已取消源文件移除。已验证备份保留不变，可稍后从“继续未完成任务”再次进入。"))
        return 0

    removal_path = migration_state_path(backup).resolve()
    # Record the removal-state destination before deleting the first source.
    # If the process dies after one or more unlinks, the next run knows exactly
    # which sidecar to resume instead of trying to repeat the whole preflight.
    mark_operation_state(
        op_state_path,
        "removing_sources",
        removal_state_path=str(removal_path),
    )
    removal_state_file, state = remove_verified_sources(
        backup,
        state_path=removal_path,
        progress=_progress,
        preflight=False,
    )
    return _finish_removal_state(op_state_path, removal_state_file, state)


def cmd_migrate(args) -> int:
    sources = legacy._resolve_sources(args)
    if args.from_scan and not args.select:
        print(f"准备迁移扫描结果中的全部候选: {len(sources)} 个文件")

    batch_id = make_batch_id()
    state_path = operation_state_path(batch_id).resolve()
    print(_info(f"迁移操作状态文件: {state_path}"))
    print(_info("该状态在复制开始前创建；复制、校验或后续移除阶段中断后均可继续。"))

    backup, op_state_path, _state = create_resumable_backup(
        sources,
        args.dest,
        zip_mode=args.zip,
        progress=_progress,
        operation="migrate",
        batch_id=batch_id,
    )
    return _continue_migration_after_backup(backup, op_state_path, yes=bool(args.yes))


def _resume_removal_state(state_file: Path, *, yes: bool) -> int:
    if not yes:
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
    return legacy._print_migration_result(result_path, state)


def _resume_operation_state(state_file: Path, *, yes: bool) -> int:
    state = load_operation_state(state_file)
    operation = state.get("operation")

    if operation == "migrate":
        removal_path_text = state.get("removal_state_path")
        if removal_path_text:
            removal_path = Path(str(removal_path_text)).expanduser().resolve()
            if removal_path.is_file():
                if not yes:
                    try:
                        answer = input(
                            "迁移已经进入源文件移除阶段。将重新验证备份并继续尚未完成的移除。"
                            "输入 YES 继续: "
                        )
                    except (EOFError, KeyboardInterrupt):
                        answer = ""
                    if answer.strip().upper() != "YES":
                        print(_warning("已取消继续迁移。"))
                        return 0
                result_path, removal_state = resume_migration(removal_path, progress=_progress)
                return _finish_removal_state(state_file, result_path, removal_state)

    started = time.perf_counter()
    backup, op_state_path, state = resume_resumable_backup(state_file, progress=_progress)
    elapsed = time.perf_counter() - started

    if operation == "backup":
        return _print_backup_result(backup, op_state_path, elapsed)
    return _continue_migration_after_backup(backup, op_state_path, yes=yes)


def cmd_migrate_resume(args) -> int:
    state_file = Path(args.state).expanduser().resolve()
    try:
        payload = read_json(state_file)
    except FileNotFoundError as exc:
        raise BackupError(f"状态文件不存在: {state_file}") from exc

    if isinstance(payload, dict) and payload.get("kind") == "filecheck-operation":
        return _resume_operation_state(state_file, yes=bool(args.yes))
    return _resume_removal_state(state_file, yes=bool(args.yes))


def menu_resume_flow() -> int:
    # Imported lazily to avoid a module cycle: launcher patches menu.cli to this
    # module and menu._resume_flow to this function.
    from . import menu

    states = discover_operation_states(include_completed=False)
    if states:
        print("\n检测到以下未完成/待确认任务：")
        for index, (path, state) in enumerate(states[:20], start=1):
            op = "迁移" if state.get("operation") == "migrate" else "备份"
            print(
                f"  {index}. [{op}] {state.get('status', '-')}  "
                f"{state.get('copied', 0)}/{state.get('total', 0)}  "
                f"目标={state.get('destination_root', '-')}"
            )
        print("  M. 手工输入状态文件路径")
        print("  0. 返回")
        while True:
            choice = menu._ask("请选择要继续的任务", default="1").strip()
            if choice == "0":
                return 0
            if choice.lower() == "m":
                break
            try:
                selected = int(choice)
            except ValueError:
                print(_warning("请输入列表编号、M 或 0"))
                continue
            if 1 <= selected <= min(20, len(states)):
                return main(["migrate-resume", str(states[selected - 1][0])])
            print(_warning("任务编号超出范围"))

    print(
        _warning(
            "如果这是旧版本在“备份/校验阶段”被直接退出的任务，当时版本尚未在复制前建立操作状态，"
            "因此不会存在可续传文件，只能重新执行该批次。新版本从复制开始前就会创建状态。"
        )
    )
    state = menu._ask("请输入 *.operation.json 或 *.migration.json 状态文件路径")
    if not state:
        return 0
    return main(["migrate-resume", state])


def menu_print_main_menu() -> None:
    print("\n" + "=" * 64)
    print(_info("FileCheck V0.1 · 文件扫描 / 批量备份 / 迁移 / 恢复"))
    print("=" * 64)
    print("  1. 检查 Everything / ES 环境")
    print("  2. 扫描并处理（推荐入口）")
    print("  3. 使用已有扫描结果批量备份")
    print("  4. 使用已有扫描结果迁移（会进入源文件移除确认）")
    print("  5. 验证已有备份")
    print("  6. 从备份恢复到原路径")
    print("  7. 继续未完成的备份 / 迁移")
    print("  8. 运行本机自检")
    print("  9. 显示高级命令帮助")
    print("  0. 退出")


def main(argv: list[str] | None = None) -> int:
    _configure_console_streams()
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list:
        # Normally launcher.py owns the no-argument interactive path.
        return legacy.main(args_list)

    command = args_list[0]
    if command not in ("backup", "migrate", "migrate-resume"):
        return int(legacy.main(args_list) or 0)

    parser = build_parser()
    args = parser.parse_args(args_list)
    try:
        if command == "backup":
            return int(cmd_backup(args) or 0)
        if command == "migrate":
            return int(cmd_migrate(args) or 0)
        return int(cmd_migrate_resume(args) or 0)
    except (EverythingError, MigrationError, BackupError, RuntimeError, ValueError, OSError) as exc:
        print(_paint(f"错误: {exc}", Fore.RED, bright=True), file=sys.stderr)
        return 1

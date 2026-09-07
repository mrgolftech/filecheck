from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from . import cli
from .util import app_data_dir


_MIB = 1024 * 1024
_MIN_FREE_RESERVE = 16 * _MIB
_MAX_FREE_RESERVE = 512 * _MIB


class MenuExit(Exception):
    pass


def _format_bytes(value: int) -> str:
    value = max(0, int(value))
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    amount = float(value)
    for unit in units:
        if amount < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(amount)} {unit}"
            return f"{amount:.2f} {unit}"
        amount /= 1024.0
    return f"{value} B"


def _capacity_from_scan(payload: dict) -> dict[str, int]:
    items = payload.get("items", [])
    known_total = 0
    unknown = 0
    accessible = 0
    for item in items:
        size = item.get("size")
        if isinstance(size, int) and size >= 0:
            known_total += size
            accessible += 1
        else:
            unknown += 1

    reserve = max(_MIN_FREE_RESERVE, min(_MAX_FREE_RESERVE, known_total // 20))
    return {
        "files": len(items),
        "accessible": accessible,
        "unknown": unknown,
        "payload_bytes": known_total,
        "directory_required": known_total + reserve,
        # Current ZIP implementation keeps a verified staging copy while a
        # temporary archive is being created, so 2x input + reserve is the
        # conservative peak working-space estimate.
        "zip_required": known_total * 2 + reserve,
    }


def _print_capacity(payload: dict) -> dict[str, int]:
    metrics = _capacity_from_scan(payload)
    print("\n扫描容量汇总")
    print(f"  候选文件: {metrics['files']}")
    print(f"  可统计大小: {metrics['accessible']}")
    print(f"  候选数据总量: {_format_bytes(metrics['payload_bytes'])}")
    if metrics["unknown"]:
        print(cli._warning(f"  当前不可访问/大小未知: {metrics['unknown']} 个；以下空间值仅为下限"))
    print(f"  目录备份建议至少可用: {_format_bytes(metrics['directory_required'])}")
    print(f"  ZIP 备份过程建议至少可用: {_format_bytes(metrics['zip_required'])}")
    print("  注：ZIP 最终文件大小取决于压缩率；这里显示的是创建过程的保守峰值空间。")
    return metrics


def _ask(prompt: str, *, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    try:
        value = input(f"{prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt) as exc:
        raise MenuExit from exc
    if not value and default is not None:
        return default
    return value


def _ask_choice(prompt: str, allowed: set[str], *, default: str | None = None) -> str:
    while True:
        value = _ask(prompt, default=default)
        if value in allowed:
            return value
        print(cli._warning(f"请输入有效选项: {', '.join(sorted(allowed))}"))


def _ask_yes_no(prompt: str, *, default: bool = False) -> bool:
    marker = "Y/n" if default else "y/N"
    value = _ask(f"{prompt} ({marker})").lower()
    if not value:
        return default
    return value in ("y", "yes", "是")


def _default_scan_output() -> Path:
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    return app_data_dir() / f"scan-results-{stamp}.json"


def _load_scan(path: str | Path) -> dict:
    scan_path = Path(path).expanduser()
    try:
        payload = json.loads(scan_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"扫描结果不存在: {scan_path}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"扫描结果 JSON 损坏: {scan_path}") from exc
    if payload.get("schema_version") != 1 or not isinstance(payload.get("items"), list):
        raise RuntimeError(f"扫描结果格式无效: {scan_path}")
    return payload


def _existing_parent(path: Path) -> Path | None:
    current = path.expanduser()
    while True:
        if current.exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _destination_free_bytes(path: str | Path) -> int | None:
    existing = _existing_parent(Path(path))
    if existing is None:
        return None
    try:
        return int(shutil.disk_usage(existing).free)
    except OSError:
        return None


def _warn_destination_inside_scan(dest: str, payload: dict) -> None:
    scope = payload.get("path_filter")
    if not scope:
        return
    try:
        scope_path = Path(str(scope)).expanduser().resolve()
        dest_path = Path(dest).expanduser().resolve()
        dest_path.relative_to(scope_path)
    except (ValueError, OSError, RuntimeError):
        return
    print(
        cli._warning(
            "备份目标位于本次扫描范围内部。这样做可以运行，但后续再次扫描可能把备份副本也检索出来；"
            "更推荐把备份放到扫描范围之外。"
        )
    )


def _print_destination_space(dest: str, required: int) -> None:
    free = _destination_free_bytes(dest)
    if free is None:
        print("  目标剩余空间: 无法预先读取；实际备份开始前仍会执行严格空间检查")
        return
    print(f"  目标剩余空间: {_format_bytes(free)}")
    if free < required:
        print(cli._warning(f"  空间不足：当前模式建议至少 {_format_bytes(required)}"))
    else:
        print(cli._success(f"  空间预检通过：当前模式建议至少 {_format_bytes(required)}"))


def _prompt_scan_scope() -> str | None:
    print("\n扫描范围")
    print("  1. Everything 当前已索引的全部范围")
    print("  2. 指定盘符或目录（推荐）")
    print("  0. 返回")
    choice = _ask_choice("请选择", {"0", "1", "2"}, default="2")
    if choice == "0":
        raise MenuExit
    if choice == "1":
        return None
    while True:
        path = _ask(r"请输入扫描路径，例如 C:\、D:\Work")
        if path:
            return path
        print(cli._warning("扫描路径不能为空"))


def _run_scan_flow() -> tuple[Path, dict] | None:
    path_filter = _prompt_scan_scope()
    match_path = _ask_yes_no("关键词是否同时匹配目录路径", default=False)
    output = _default_scan_output()

    args = ["scan", "--output", str(output), "--list-limit", "50"]
    if path_filter:
        args.extend(["--path", path_filter])
    if match_path:
        args.append("--match-path")

    print("\n开始扫描……")
    rc = cli.main(args)
    if rc != 0:
        return None
    payload = _load_scan(output)
    _print_capacity(payload)
    return output, payload


def _prompt_destination(payload: dict, *, zip_mode: bool, metrics: dict[str, int]) -> str:
    while True:
        dest = _ask("请输入统一备份目标目录")
        if not dest:
            print(cli._warning("备份目标不能为空"))
            continue
        _warn_destination_inside_scan(dest, payload)
        required = metrics["zip_required"] if zip_mode else metrics["directory_required"]
        _print_destination_space(dest, required)
        if _ask_yes_no("使用这个备份目标继续", default=True):
            return dest


def _process_scan(scan_path: Path, payload: dict, *, fixed_action: str | None = None) -> int:
    items = payload.get("items", [])
    if not items:
        print(cli._warning("扫描结果中没有候选文件，无需备份。"))
        return 0

    metrics = _print_capacity(payload)
    if fixed_action is None:
        print("\n扫描后处理")
        print("  1. 目录方式批量备份全部候选（推荐，源文件不动）")
        print("  2. ZIP 方式批量备份全部候选（源文件不动）")
        print("  3. 目录方式迁移：备份验证后移除候选源文件")
        print("  4. ZIP 方式迁移：备份验证后移除候选源文件")
        print("  5. 只保存扫描结果，暂不处理")
        print("  0. 返回")
        action = _ask_choice("请选择", {"0", "1", "2", "3", "4", "5"}, default="1")
    else:
        action = fixed_action

    if action in ("0", "5"):
        print(f"扫描结果保存在: {scan_path}")
        return 0

    zip_mode = action in ("2", "4")
    migrate = action in ("3", "4")
    dest = _prompt_destination(payload, zip_mode=zip_mode, metrics=metrics)

    args = [
        "migrate" if migrate else "backup",
        "--from-scan",
        str(scan_path),
        "--dest",
        dest,
    ]
    if zip_mode:
        args.append("--zip")

    if migrate:
        print(
            cli._warning(
                "迁移模式会在备份与源文件两轮 SHA-256 复核通过后，再要求一次 YES 批次确认；"
                "只有确认后才会移除 manifest 中列出的源文件。"
            )
        )
    return cli.main(args)


def _existing_scan_flow(*, migrate: bool | None = None) -> int:
    path = Path(_ask("请输入 scan-results.json 路径")).expanduser()
    payload = _load_scan(path)
    _print_capacity(payload)
    if migrate is None:
        return _process_scan(path, payload)

    zip_mode = _ask_yes_no("是否使用 ZIP 备份", default=False)
    action = "4" if migrate and zip_mode else "3" if migrate else "2" if zip_mode else "1"
    return _process_scan(path, payload, fixed_action=action)


def _verify_flow() -> int:
    backup = _ask("请输入备份批次目录或 ZIP 路径")
    if not backup:
        return 0
    return cli.main(["verify", backup])


def _restore_flow() -> int:
    backup = _ask("请输入备份批次目录或 ZIP 路径")
    if not backup:
        return 0
    print("恢复冲突策略: 1=skip(推荐)  2=rename  3=overwrite")
    choice = _ask_choice("请选择", {"1", "2", "3"}, default="1")
    conflict = {"1": "skip", "2": "rename", "3": "overwrite"}[choice]
    return cli.main(["restore", backup, "--conflict", conflict])


def _resume_flow() -> int:
    state = _ask("请输入 *.migration.json 状态文件路径")
    if not state:
        return 0
    return cli.main(["migrate-resume", state])


def _print_main_menu() -> None:
    print("\n" + "=" * 64)
    print(cli._info("FileCheck V0.1 · 文件扫描 / 批量备份 / 迁移 / 恢复"))
    print("=" * 64)
    print("  1. 检查 Everything / ES 环境")
    print("  2. 扫描并处理（推荐入口）")
    print("  3. 使用已有扫描结果批量备份")
    print("  4. 使用已有扫描结果迁移（会进入源文件移除确认）")
    print("  5. 验证已有备份")
    print("  6. 从备份恢复到原路径")
    print("  7. 继续未完成的迁移")
    print("  8. 运行本机自检")
    print("  9. 显示高级命令帮助")
    print("  0. 退出")


def run_menu() -> int:
    while True:
        _print_main_menu()
        try:
            choice = _ask_choice(
                "请选择功能",
                {str(i) for i in range(10)},
                default="2",
            )
            if choice == "0":
                print("已退出 FileCheck。")
                return 0
            if choice == "1":
                cli.main(["doctor"])
            elif choice == "2":
                scanned = _run_scan_flow()
                if scanned is not None:
                    scan_path, payload = scanned
                    _process_scan(scan_path, payload)
            elif choice == "3":
                _existing_scan_flow(migrate=False)
            elif choice == "4":
                _existing_scan_flow(migrate=True)
            elif choice == "5":
                _verify_flow()
            elif choice == "6":
                _restore_flow()
            elif choice == "7":
                _resume_flow()
            elif choice == "8":
                cli.main(["selftest"])
            elif choice == "9":
                cli.build_parser().print_help()
        except MenuExit:
            print("\n返回主菜单。")
        except (RuntimeError, OSError, ValueError) as exc:
            print(cli._paint(f"错误: {exc}", cli.Fore.RED, bright=True), file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    cli._configure_console_streams()
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args != ["menu"]:
        return int(cli.main(args) or 0)
    try:
        return run_menu()
    except MenuExit:
        print("\n已退出 FileCheck。")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

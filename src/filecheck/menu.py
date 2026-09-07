from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from . import cli
from .backup import read_backup_manifest
from .migration import migration_state_path
from .portable_everything import list_windows_drives, load_index_state
from .util import scan_results_dir


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
            return f"{int(amount)} {unit}" if unit == "B" else f"{amount:.2f} {unit}"
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
    }


def _print_capacity(payload: dict) -> dict[str, int]:
    metrics = _capacity_from_scan(payload)
    print("\n扫描容量汇总")
    print(f"  候选文件: {metrics['files']}")
    print(f"  可统计大小: {metrics['accessible']}")
    print(f"  候选数据总量: {_format_bytes(metrics['payload_bytes'])}")
    if metrics["unknown"]:
        print(cli._warning(f"  当前不可访问/大小未知: {metrics['unknown']} 个；空间值仅为下限"))
    print(f"  目录备份建议至少可用: {_format_bytes(metrics['directory_required'])}")
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
    return scan_results_dir() / f"scan-results-{stamp}.json"


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


def _latest_scan_files() -> list[Path]:
    root = scan_results_dir()
    if not root.is_dir():
        return []
    rows = list(root.glob("scan-results-*.json"))
    rows.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return rows


def _choose_scan_file() -> Path:
    rows = _latest_scan_files()
    if rows:
        print("\n最近扫描结果：")
        for index, path in enumerate(rows[:10], start=1):
            try:
                count = len(_load_scan(path).get("items", []))
            except Exception:
                count = -1
            print(f"  {index}. {path.name}  候选={count if count >= 0 else '?'}")
        print("  M. 手工输入 JSON 路径")
        choice = _ask("请选择", default="1")
        if choice.lower() != "m":
            try:
                index = int(choice)
                if 1 <= index <= min(10, len(rows)):
                    return rows[index - 1]
            except ValueError:
                pass
    path = Path(_ask("请输入 scan-results.json 完整路径")).expanduser()
    if not path.is_file():
        raise RuntimeError(f"扫描结果不存在: {path}")
    return path


def _index_state() -> dict:
    state = load_index_state(required=True)
    assert state is not None
    return state


def _backup_root() -> Path:
    state = _index_state()
    root = Path(str(state["backup_root"])).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _latest_backups() -> list[Path]:
    try:
        root = _backup_root()
    except Exception:
        return []
    rows = [p for p in root.iterdir() if p.is_dir() and p.name.startswith("FC-")]
    rows.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return rows


def _choose_backup() -> Path:
    rows = _latest_backups()
    if rows:
        print("\n最近备份批次：")
        for index, path in enumerate(rows[:10], start=1):
            try:
                manifest = read_backup_manifest(path)
                count = len(manifest["items"])
            except Exception:
                count = -1
            print(f"  {index}. {path.name}  文件={count if count >= 0 else '?'}")
        print("  M. 手工输入备份目录")
        choice = _ask("请选择", default="1")
        if choice.lower() != "m":
            try:
                index = int(choice)
                if 1 <= index <= min(10, len(rows)):
                    return rows[index - 1]
            except ValueError:
                pass
    path = Path(_ask("请输入备份批次目录")).expanduser().resolve()
    if not path.is_dir():
        raise RuntimeError(f"备份目录不存在: {path}")
    return path


def _destination_free_bytes(path: Path) -> int | None:
    try:
        return int(shutil.disk_usage(path).free)
    except OSError:
        return None


def _environment_and_index_flow() -> int:
    print("\n步骤 1/7 · 环境与索引")
    cli.main(["doctor"])
    existing = load_index_state(required=False)
    drives = list_windows_drives()
    if not drives:
        print(cli._warning("未自动枚举到 Windows 磁盘，请手工输入要索引的根目录。"))
        raw = _ask(r"请输入索引范围，多个用逗号分隔，例如 C:\,D:\")
        selected = [item.strip() for item in raw.split(",") if item.strip()]
    else:
        print("\n请选择需要建立 FileCheck 索引的磁盘：")
        current = set(existing.get("selected_roots", [])) if existing else set()
        for index, drive in enumerate(drives, start=1):
            mark = "*" if drive.root in current else " "
            print(f"  {index}. [{mark}] {drive.root}  {drive.kind}")
        default_indexes = [str(i) for i, d in enumerate(drives, start=1) if d.root in current]
        default = ",".join(default_indexes) if default_indexes else ",".join(str(i) for i in range(1, len(drives) + 1))
        raw = _ask("输入磁盘编号，多个用逗号分隔", default=default)
        selected = []
        for token in raw.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                index = int(token)
            except ValueError as exc:
                raise RuntimeError(f"无效磁盘编号: {token}") from exc
            if index < 1 or index > len(drives):
                raise RuntimeError(f"磁盘编号超出范围: {index}")
            selected.append(drives[index - 1].root)
    if not selected:
        raise RuntimeError("至少选择一个索引磁盘")

    backup_default = str(existing.get("backup_root")) if existing else ""
    backup = _ask("请输入统一备份根目录（会自动排除在索引之外）", default=backup_default or None)
    if not backup:
        raise RuntimeError("必须指定备份根目录")
    Path(backup).expanduser().mkdir(parents=True, exist_ok=True)

    args = ["index"]
    for root in selected:
        args.extend(["--drive", root])
    args.extend(["--backup-root", backup])
    print("\n正在建立/重建 FileCheck 专用索引，请等待……")
    return cli.main(args)


def _run_scan_flow() -> tuple[Path, dict] | None:
    print("\n步骤 2/7 · 扫描文件")
    _index_state()
    match_path = _ask_yes_no("关键词是否同时匹配目录路径（推荐 N）", default=False)
    output = _default_scan_output()
    args = ["scan", "--output", str(output), "--list-limit", "50"]
    if match_path:
        args.append("--match-path")
    rc = cli.main(args)
    if rc != 0:
        return None
    payload = _load_scan(output)
    print(cli._warning("下一步请人工核对 JSON/CSV，确认候选范围后再创建备份。"))
    return output, payload


def _review_scan_flow() -> int:
    print("\n步骤 3/7 · 人工核对扫描结果")
    path = _choose_scan_file()
    payload = _load_scan(path)
    _print_capacity(payload)
    print(f"  JSON: {path.resolve()}")
    print(f"  CSV : {path.with_suffix('.csv').resolve()}")
    print(cli._warning("请人工核对源文件完整路径；确认无误后再进入“创建目录备份”。"))
    return 0


def _backup_flow() -> int:
    print("\n步骤 4/7 · 创建目录备份")
    scan = _choose_scan_file()
    payload = _load_scan(scan)
    metrics = _print_capacity(payload)
    destination = _backup_root()
    free = _destination_free_bytes(destination)
    print(f"  统一备份根目录: {destination}")
    if free is not None:
        print(f"  当前剩余空间: {_format_bytes(free)}")
        if free < metrics["directory_required"]:
            raise RuntimeError("备份目标空间不足")
    if not _ask_yes_no("确认把该扫描结果中的全部候选复制到上述目录", default=True):
        return 0
    return cli.main(["backup", "--from-scan", str(scan), "--dest", str(destination)])


def _verify_flow() -> int:
    print("\n步骤 5/7 · 人工检查后再次验证备份")
    backup = _choose_backup()
    print(f"  请先确认目录结构可人工读取: {backup / 'files'}")
    return cli.main(["verify", str(backup)])


def _delete_sources_flow() -> int:
    print("\n步骤 6/7 · 删除源文件 / 继续未完成删除")
    backup = _choose_backup()
    state_file = migration_state_path(backup)
    if state_file.is_file():
        state = json.loads(state_file.read_text(encoding="utf-8"))
        print(f"  已存在删除状态: {state.get('status', '-')}")
        print(f"  deleted={state.get('deleted', 0)}  failed={state.get('failed', 0)}  total={state.get('total', 0)}")
        if state.get("status") == "completed":
            print(cli._success("该备份对应的源文件删除任务已经完成。"))
            return 0
        if not _ask_yes_no("继续处理上次未删除的文件", default=True):
            return 0
        return cli.main(["remove-resume", str(backup)])

    manifest = read_backup_manifest(backup)
    print(f"  manifest 文件数: {len(manifest['items'])}")
    print(cli._warning("程序会重新验证整个备份和全部源文件；删除失败的文件会跳过并记录，其他文件继续处理。"))
    return cli.main(["remove-sources", str(backup)])


def _restore_flow() -> int:
    print("\n步骤 7/7 · 恢复备份文件")
    backup = _choose_backup()
    print("恢复冲突策略: 1=skip(推荐)  2=rename  3=overwrite")
    choice = _ask_choice("请选择", {"1", "2", "3"}, default="1")
    conflict = {"1": "skip", "2": "rename", "3": "overwrite"}[choice]
    return cli.main(["restore", str(backup), "--conflict", conflict])


def _print_main_menu() -> None:
    print("\n" + "=" * 72)
    print(cli._info("FileCheck v0.1.1 · 便携索引 → 扫描 → 目录备份 → 验证 → 删除 → 恢复"))
    print("=" * 72)
    print("  1. 环境与索引（选择磁盘、设置备份目录、建立索引）")
    print("  2. 扫描文件（结果保存到程序目录 scan-results）")
    print("  3. 核对扫描结果（JSON / CSV）")
    print("  4. 创建目录备份（全部候选，保持原目录结构）")
    print("  5. 检查并再次验证备份")
    print("  6. 删除源文件 / 继续未完成删除")
    print("  7. 恢复备份文件到各自原路径")
    print("  8. 继续未完成的备份复制任务")
    print("  9. 运行本机自检")
    print(" 10. 显示高级命令帮助")
    print("  0. 退出")


def _resume_flow() -> int:
    print(cli._warning("当前运行入口未加载可续传扩展。"))
    return 0


def run_menu() -> int:
    while True:
        _print_main_menu()
        try:
            choice = _ask_choice("请选择功能", {str(i) for i in range(11)}, default="1")
            if choice == "0":
                print("已退出 FileCheck。")
                return 0
            if choice == "1":
                _environment_and_index_flow()
            elif choice == "2":
                _run_scan_flow()
            elif choice == "3":
                _review_scan_flow()
            elif choice == "4":
                _backup_flow()
            elif choice == "5":
                _verify_flow()
            elif choice == "6":
                _delete_sources_flow()
            elif choice == "7":
                _restore_flow()
            elif choice == "8":
                _resume_flow()
            elif choice == "9":
                cli.main(["selftest"])
            elif choice == "10":
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

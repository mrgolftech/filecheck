from __future__ import annotations

import sys

from . import menu


def _print_main_menu() -> None:
    print("\n" + "=" * 72)
    print(menu.cli._info("FileCheck v0.1.1 · 便携索引 → 扫描 → 备份 → 删除 → 恢复"))
    print("=" * 72)
    print("  1. 环境检查与索引创建")
    print("  2. 扫描文件列表")
    print("  3. 核对扫描结果")
    print("  4. 创建备份 / 继续未完成的备份任务")
    print("  5. 检查备份")
    print("  6. 删除源文件 / 继续未完成的删除任务")
    print("  7. 恢复备份文件到源路径")
    print("  0. 退出")


def _backup_task_flow() -> int:
    print("\n备份任务：")
    print("  1. 创建新备份")
    print("  2. 继续未完成的备份任务")
    print("  0. 返回主菜单")
    choice = menu._ask_choice("请选择", {"0", "1", "2"}, default="1")
    if choice == "0":
        return 0
    if choice == "1":
        return int(menu._backup_flow() or 0)
    return int(menu._resume_flow() or 0)


def run_menu() -> int:
    allowed = {str(i) for i in range(8)}
    while True:
        _print_main_menu()
        try:
            choice = menu._ask_choice("请选择功能", allowed, default=None)
            if choice == "0":
                print("已退出 FileCheck。")
                return 0
            if choice == "1":
                menu._environment_and_index_flow()
            elif choice == "2":
                menu._run_scan_flow()
            elif choice == "3":
                menu._review_scan_flow()
            elif choice == "4":
                _backup_task_flow()
            elif choice == "5":
                menu._verify_flow()
            elif choice == "6":
                menu._delete_sources_flow()
            elif choice == "7":
                menu._restore_flow()
        except menu.MenuExit:
            print("\n返回主菜单。")
        except (RuntimeError, OSError, ValueError) as exc:
            print(menu.cli._paint(f"错误: {exc}", menu.cli.Fore.RED, bright=True), file=sys.stderr)


def install() -> None:
    menu._print_main_menu = _print_main_menu
    menu.run_menu = run_menu

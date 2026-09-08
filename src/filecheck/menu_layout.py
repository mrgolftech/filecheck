from __future__ import annotations

import sys

from . import menu


def _print_main_menu() -> None:
    print("\n" + "=" * 72)
    print(menu.cli._info("FileCheck v0.1.1 · 便携索引 → 扫描 → 目录备份 → 验证 → 删除 → 恢复"))
    print("=" * 72)
    print("  1. 环境与索引（选择磁盘、设置备份目录、建立索引）")
    print("  2. 扫描文件（结果保存到程序目录 scan-results）")
    print("  3. 核对扫描结果（JSON / CSV）")
    print("  4. 创建目录备份（全部候选，保持原目录结构）")
    print("  5. 继续未完成的备份复制任务")
    print("  6. 检查并再次验证备份")
    print("  7. 删除源文件 / 继续未完成删除")
    print("  8. 恢复备份文件到各自原路径")
    print("  0. 退出")


def run_menu() -> int:
    allowed = {str(i) for i in range(9)}
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
                menu._backup_flow()
            elif choice == "5":
                menu._resume_flow()
            elif choice == "6":
                menu._verify_flow()
            elif choice == "7":
                menu._delete_sources_flow()
            elif choice == "8":
                menu._restore_flow()
        except menu.MenuExit:
            print("\n返回主菜单。")
        except (RuntimeError, OSError, ValueError) as exc:
            print(menu.cli._paint(f"错误: {exc}", menu.cli.Fore.RED, bright=True), file=sys.stderr)


def install() -> None:
    menu._print_main_menu = _print_main_menu
    menu.run_menu = run_menu

from __future__ import annotations

import os
import sys
from pathlib import Path

from . import cli
from .portable_everything import configure_and_reindex, list_windows_drives, load_index_state


def _normalize_drive_token(token: str) -> str:
    value = token.strip().upper().rstrip(":\\/")
    if len(value) != 1 or not ("A" <= value <= "Z"):
        raise RuntimeError(f"无效盘符: {token}")
    return value


def _select_drives(raw: str, drives) -> list[str]:
    by_letter = {drive.root[0].upper(): drive for drive in drives}
    fixed = [drive.root for drive in drives if drive.kind == "fixed"]
    text = raw.strip().upper()
    if not text or text in {"A", "ALL", "*"}:
        if not fixed:
            raise RuntimeError("未检测到本地固定磁盘")
        return fixed

    normalized = text.replace(";", ",").replace(" ", ",")
    selected: list[str] = []
    seen: set[str] = set()
    for token in normalized.split(","):
        if not token.strip():
            continue
        letter = _normalize_drive_token(token)
        drive = by_letter.get(letter)
        if drive is None:
            raise RuntimeError(f"未检测到磁盘 {letter}:")
        key = os.path.normcase(drive.root)
        if key not in seen:
            seen.add(key)
            selected.append(drive.root)
    if not selected:
        raise RuntimeError("至少选择一个磁盘")
    return selected


def _index_progress_printer(selected_roots: list[str]):
    tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
    last_bucket = {"value": -1}
    spinner = "|/-\\"
    label = ", ".join(root.rstrip("\\") for root in selected_roots)

    def report(elapsed: float) -> None:
        second = max(0, int(elapsed))
        if tty:
            mark = spinner[second % len(spinner)]
            print(
                f"\r  {mark} Everything 正在建立索引: {label}  已用时 {elapsed:5.1f} 秒",
                end="",
                flush=True,
            )
            return
        bucket = second // 5
        if bucket != last_bucket["value"]:
            last_bucket["value"] = bucket
            print(f"  Everything 正在建立索引: {label}  已用时 {elapsed:.1f} 秒")

    return report, tty


def cmd_index(args) -> int:
    selected = list(args.drive or [])
    report, tty = _index_progress_printer(selected)
    print("索引策略：NTFS 本地卷使用 Everything MFT/USN 快速索引；其他文件系统回退目录索引。")
    print("说明：Everything 1.4/ES 不提供可靠的逐文件百分比，下面显示真实忙碌状态和已用时间。")
    try:
        result = configure_and_reindex(
            selected,
            args.backup_root,
            everything=args.everything,
            es=args.es,
            progress=report,
        )
    finally:
        if tty:
            print()

    print(cli._success("FileCheck 专用索引建立完成"))
    print(f"  Everything: {result.status.everything_version}")
    print(f"  实例: {result.status.instance or 'FileCheck'}")
    print(f"  索引范围: {', '.join(result.selected_roots)}")
    if result.ntfs_roots:
        print(f"  NTFS 快速索引: {', '.join(result.ntfs_roots)}")
    if result.folder_roots:
        print(f"  目录兼容索引: {', '.join(result.folder_roots)}")
    print(f"  配置文件: {result.config_path}")
    print(f"  数据库: {result.database_path}")
    print(f"  自动排除: {', '.join(result.excluded_roots)}")
    return 0


def environment_and_index_flow() -> int:
    print("\n步骤 1/7 · 环境与索引")
    cli.main(["doctor"])
    existing = load_index_state(required=False)
    drives = list_windows_drives()
    if not drives:
        raise RuntimeError("未检测到可索引的 Windows 本地磁盘")

    print("\n检测到磁盘：")
    for drive in drives:
        kind = "本地固定盘" if drive.kind == "fixed" else "可移动盘"
        mode = "NTFS 快速索引" if drive.filesystem.upper() == "NTFS" else "目录兼容索引"
        print(f"  {drive.root[:2]:<3} {drive.filesystem:<8} {kind:<10} {mode}")

    print("\n选择索引磁盘：")
    print("  直接回车 = 所有本地固定磁盘（默认）")
    print("  A          = 所有本地固定磁盘")
    print("  C,D        = 只索引 C: 和 D:")
    print("  C D        = 也可以用空格分隔")
    raw = _ask("请输入盘符或 A=全部", default="A")
    selected = _select_drives(raw, drives)

    print(f"  已选择: {', '.join(selected)}")
    ntfs_selected = [
        d.root for d in drives if d.root in selected and d.filesystem.upper() == "NTFS"
    ]
    if ntfs_selected:
        print(cli._info("  NTFS 卷将使用 Everything 原生 MFT/USN 快速索引。"))
        print(cli._warning("  NTFS 快速索引需要管理员权限；若当前不是管理员，程序会明确提示后退出本步骤。"))

    backup_default = str(existing.get("backup_root")) if existing else ""
    backup = _ask("请输入统一备份根目录（会自动排除在索引之外）", default=backup_default or None)
    if not backup:
        raise RuntimeError("必须指定备份根目录")
    Path(backup).expanduser().mkdir(parents=True, exist_ok=True)

    args = ["index"]
    for root in selected:
        args.extend(["--drive", root])
    args.extend(["--backup-root", backup])
    print("\n正在建立/重建 FileCheck 专用索引……")
    return cli.main(args)


def _ask(prompt: str, *, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    try:
        value = input(f"{prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt) as exc:
        raise RuntimeError("已取消索引设置") from exc
    if not value and default is not None:
        return default
    return value

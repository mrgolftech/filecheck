from __future__ import annotations

import os
from pathlib import Path

from . import cli as legacy
from .backup import read_backup_manifest, restore_backup
from .util import sha256_file, write_text


_REPORT_NAME = "restore-skipped.txt"


def _manifest_map(backup: Path) -> dict[str, dict]:
    manifest = read_backup_manifest(backup)
    return {
        os.path.normcase(os.path.abspath(str(item["source_path"]))): item
        for item in manifest["items"]
    }


def _skip_reason(target: Path, item: dict | None) -> str:
    if not target.exists():
        return "目标路径在恢复时被跳过，但当前已不存在"
    if item is None:
        return "目标路径已存在；默认 skip 策略未覆盖"
    try:
        if target.is_file() and target.stat().st_size == int(item["size"]):
            if sha256_file(target).lower() == str(item["sha256"]).lower():
                return "目标文件已存在，且内容与备份一致；默认 skip 策略保留现有文件"
    except OSError:
        pass
    return "目标文件已存在，内容与备份不一致或无法确认；默认 skip 策略未覆盖"


def _write_skipped_report(backup: Path, results: list[dict]) -> Path | None:
    report = backup / _REPORT_NAME
    skipped = [row for row in results if row.get("state") == "skipped"]
    if not skipped:
        try:
            report.unlink(missing_ok=True)
        except OSError:
            pass
        return None

    manifest_map = _manifest_map(backup)
    lines = [
        "FileCheck 恢复跳过文件清单",
        "说明：默认恢复策略为 skip。目标路径已存在时，不覆盖现有文件。",
        f"跳过数量: {len(skipped)}",
        "",
    ]
    for index, row in enumerate(skipped, start=1):
        target = Path(str(row["target"]))
        key = os.path.normcase(os.path.abspath(str(target)))
        reason = _skip_reason(target, manifest_map.get(key))
        lines.append(f"{index}. {target}")
        lines.append(f"   原因: {reason}")
        lines.append("")
    write_text(report, "\n".join(lines))
    return report


def cmd_restore(args) -> int:
    backup = Path(args.backup).expanduser().resolve()
    results = restore_backup(backup, conflict=args.conflict, progress=legacy._progress)
    restored = sum(1 for row in results if row["state"] == "restored")
    skipped = sum(1 for row in results if row["state"] == "skipped")
    report = _write_skipped_report(backup, results)

    print(legacy._success("恢复完成"))
    print(f"  restored={legacy._paint(str(restored), legacy.Fore.GREEN, bright=True)}")
    print(f"  skipped={legacy._paint(str(skipped), legacy.Fore.YELLOW)}")
    if report is not None:
        print(legacy._warning(f"  跳过清单: {report}"))
    return 0

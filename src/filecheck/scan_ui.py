from __future__ import annotations

from pathlib import Path

from . import cli as legacy_cli
from . import menu


def _print_scan_rules() -> None:
    """Show the effective filename keywords/extensions before a menu scan."""
    rules_path = Path(legacy_cli._default_rules_path()).expanduser().resolve()
    rules = legacy_cli._load_rules(rules_path)

    print("\n当前扫描规则：")
    print("  关键词：")
    keywords = rules.get("keywords", {})
    if isinstance(keywords, dict):
        for group, values in keywords.items():
            rendered = ", ".join(str(value) for value in values)
            print(f"    {group}: {rendered}")

    extensions = []
    for value in rules.get("extensions", []):
        text = str(value).strip()
        if text:
            extensions.append(text if text.startswith(".") else f".{text}")
    print(f"  文件扩展名: {', '.join(extensions)}")
    print(f"  配置文件: {rules_path}")
    print(legacy_cli._warning("  如需修改扫描关键词或文件扩展名，请编辑上述 config\\rules.json，保存后重新执行扫描。"))


def run_scan_flow() -> tuple[Path, dict] | None:
    print("\n步骤 2/7 · 扫描文件列表")
    menu._index_state()
    _print_scan_rules()
    match_path = menu._ask_yes_no("关键词是否同时匹配目录路径（推荐 N）", default=False)
    output = menu._default_scan_output()
    args = ["scan", "--output", str(output), "--list-limit", "50"]
    if match_path:
        args.append("--match-path")
    rc = menu.cli.main(args)
    if rc != 0:
        return None
    payload = menu._load_scan(output)
    print(menu.cli._warning("下一步请人工核对 JSON/CSV，确认候选范围后再创建备份。"))
    return output, payload


def install() -> None:
    menu._run_scan_flow = run_scan_flow

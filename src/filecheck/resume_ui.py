from __future__ import annotations

from . import cli
from . import resilient_cli
from .resumable import discover_operation_states


def menu_resume_flow() -> int:
    states = discover_operation_states(include_completed=False)
    if not states:
        print(cli._success("当前没有检测到未完成的备份复制任务。"))
        print(cli._info("如需高级手工恢复某个 operation.json，可使用命令行 migrate-resume <路径>。"))
        return 0
    return resilient_cli.menu_resume_flow()

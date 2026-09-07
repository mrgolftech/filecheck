from __future__ import annotations

from . import cli as legacy_cli
from . import fast_index
from . import menu
from . import resilient_cli
from . import restore_reporting
from . import resume_ui


# Route command execution and resume handling through the hardened v0.1.1
# implementations while keeping menu.py as the coherent user-facing workflow.
legacy_cli.cmd_index = fast_index.cmd_index
legacy_cli.cmd_restore = restore_reporting.cmd_restore
menu.cli = resilient_cli
menu._environment_and_index_flow = fast_index.environment_and_index_flow
menu._resume_flow = resume_ui.menu_resume_flow


def main(argv: list[str] | None = None) -> int:
    return menu.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())

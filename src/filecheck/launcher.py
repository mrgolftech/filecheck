from __future__ import annotations

from . import cli as legacy_cli
from . import fast_index
from . import menu
from . import resilient_cli


# Route command execution and resume handling through the resumable implementation.
# The menu layout itself stays owned by menu.py so backup/verify/delete/restore
# remain one coherent user-facing workflow.
legacy_cli.cmd_index = fast_index.cmd_index
menu.cli = resilient_cli
menu._environment_and_index_flow = fast_index.environment_and_index_flow
menu._resume_flow = resilient_cli.menu_resume_flow


def main(argv: list[str] | None = None) -> int:
    return menu.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())

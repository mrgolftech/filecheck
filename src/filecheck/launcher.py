from __future__ import annotations

from . import menu
from . import resilient_cli


# Route command execution and resume handling through the resumable implementation.
# The menu layout itself stays owned by menu.py so backup/verify/delete/restore
# remain one coherent user-facing workflow.
menu.cli = resilient_cli
menu._resume_flow = resilient_cli.menu_resume_flow


def main(argv: list[str] | None = None) -> int:
    return menu.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())

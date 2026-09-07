from __future__ import annotations

from . import menu
from . import resilient_cli


# Reuse the established menu layout while routing its command execution through
# the resumable backup/migration implementation.  This keeps all existing scan,
# doctor, verify, restore and selftest behavior intact.
menu.cli = resilient_cli
menu._resume_flow = resilient_cli.menu_resume_flow
menu._print_main_menu = resilient_cli.menu_print_main_menu


def main(argv: list[str] | None = None) -> int:
    return menu.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations


class Palette:
    # CustomTkinter accepts (light, dark) tuples. Keep the FileCheck blue brand
    # in both modes while adapting surfaces/text for a true dark appearance.
    PRIMARY = ("#2563EB", "#3B82F6")
    PRIMARY_HOVER = ("#1D4ED8", "#60A5FA")
    PRIMARY_SOFT = ("#EFF6FF", "#172554")
    ON_PRIMARY = ("#FFFFFF", "#FFFFFF")

    BG = ("#F4F7FB", "#0F172A")
    SURFACE = ("#FFFFFF", "#182235")
    SURFACE_SUBTLE = ("#F8FAFC", "#111827")
    BORDER = ("#E2E8F0", "#334155")

    TEXT = ("#0F172A", "#F8FAFC")
    TEXT_SECONDARY = ("#475569", "#CBD5E1")
    TEXT_MUTED = ("#94A3B8", "#94A3B8")

    SUCCESS = ("#15803D", "#4ADE80")
    SUCCESS_SOFT = ("#F0FDF4", "#14291D")
    WARNING = ("#B45309", "#FBBF24")
    WARNING_SOFT = ("#FFFBEB", "#332611")
    DANGER = ("#B91C1C", "#F87171")
    DANGER_HOVER = ("#991B1B", "#EF4444")
    DANGER_SOFT = ("#FEF2F2", "#38191D")

    DISABLED = ("#CBD5E1", "#475569")
    DISABLED_TEXT = ("#64748B", "#94A3B8")


class Spacing:
    XXS = 4
    XS = 8
    SM = 12
    MD = 16
    LG = 24
    XL = 32
    XXL = 40


class Radius:
    SMALL = 6
    CONTROL = 8
    CARD = 14


class Layout:
    SIDEBAR_WIDTH = 224
    PAGE_PADDING = 28
    CARD_PADDING = 22
    CONTROL_HEIGHT = 38
    BUTTON_HEIGHT = 40
    WINDOW_WIDTH = 1180
    WINDOW_HEIGHT = 760
    MIN_WIDTH = 1024
    MIN_HEIGHT = 640


class Typography:
    FAMILY = "Microsoft YaHei UI"
    PAGE_TITLE = (FAMILY, 28, "bold")
    SECTION_TITLE = (FAMILY, 18, "bold")
    CARD_TITLE = (FAMILY, 16, "bold")
    BODY = (FAMILY, 14)
    BODY_MEDIUM = (FAMILY, 14, "bold")
    CAPTION = (FAMILY, 13)
    SMALL = (FAMILY, 12)

from __future__ import annotations

from .theme import AppTheme


def build_theme_css(theme: AppTheme) -> str:
    surface_alt = theme.blend("surface", "background", 0.65)
    surface_hover = theme.blend("accent", "surface", 0.18)
    surface_focus = theme.blend("surface", "accent", 0.85)
    accent_soft = theme.blend("accent", "surface", 0.32)
    footer_description = theme.blend("surface", "background", 0.75)
    row_alt = theme.blend("surface", "background", 0.82)

    return f"""
        Screen {{
            background: {theme.background};
            color: {theme.foreground};
        }}

        Header {{
            background: {theme.surface};
            color: {theme.foreground};
        }}

        HeaderTitle {{
            color: {theme.accent};
        }}

        HeaderIcon {{
            color: {theme.accent};
        }}

        HeaderIcon:hover {{
            background: {accent_soft};
            color: {theme.background};
        }}

        Footer {{
            background: {theme.surface};
            color: {theme.foreground};
        }}

        FooterLabel {{
            background: {footer_description};
            color: {theme.foreground};
        }}

        FooterKey {{
            background: {theme.surface};
            color: {theme.foreground};
        }}

        FooterKey > .footer-key--key {{
            background: {theme.accent};
            color: {theme.background};
            text-style: bold;
        }}

        FooterKey > .footer-key--description {{
            background: {footer_description};
            color: {theme.foreground};
        }}

        FooterKey:hover {{
            background: {accent_soft};
            color: {theme.foreground};
        }}

        Tabs {{
            background: {theme.background};
        }}

        Tab {{
            background: {theme.background};
            color: {theme.muted};
        }}

        Tab:hover {{
            background: {surface_alt};
            color: {theme.foreground};
        }}

        Tab.-active {{
            background: {theme.surface};
            color: {theme.foreground};
            text-style: bold;
        }}

        Tabs:focus .-active {{
            background: {theme.accent};
            color: {theme.background};
            text-style: bold;
        }}

        Underline > .underline--bar {{
            color: {theme.accent};
            background: {surface_alt};
        }}

        Input {{
            background: {theme.surface};
            color: {theme.foreground};
            border: tall {theme.muted};
        }}

        Input:focus {{
            background: {surface_focus};
            border: tall {theme.accent};
        }}

        Input.-invalid {{
            border: tall {theme.error};
        }}

        Input.-invalid:focus {{
            border: tall {theme.error};
        }}

        Input > .input--cursor {{
            background: {theme.accent};
            color: {theme.background};
            text-style: bold;
        }}

        Input > .input--selection {{
            background: {accent_soft};
            color: {theme.foreground};
        }}

        Input > .input--placeholder,
        Input > .input--suggestion {{
            color: {theme.muted};
        }}

        DataTable {{
            background: {theme.surface};
            color: {theme.foreground};
        }}

        DataTable > .datatable--header {{
            background: {surface_alt};
            color: {theme.foreground};
        }}

        DataTable > .datatable--fixed {{
            background: {surface_alt};
            color: {theme.foreground};
        }}

        DataTable > .datatable--even-row {{
            background: {row_alt};
        }}

        DataTable > .datatable--cursor {{
            background: {accent_soft};
            color: {theme.foreground};
            text-style: bold;
        }}

        DataTable:focus > .datatable--cursor {{
            background: {theme.accent};
            color: {theme.background};
            text-style: bold;
        }}

        DataTable > .datatable--fixed-cursor {{
            background: {accent_soft};
            color: {theme.foreground};
        }}

        DataTable:focus > .datatable--fixed-cursor {{
            background: {theme.accent};
            color: {theme.background};
        }}

        DataTable > .datatable--header-cursor {{
            background: {theme.accent};
            color: {theme.background};
        }}

        DataTable > .datatable--header-hover {{
            background: {accent_soft};
            color: {theme.foreground};
        }}

        DataTable > .datatable--hover {{
            background: {surface_hover};
        }}

        Markdown {{
            background: {theme.background};
            color: {theme.foreground};
        }}
        """

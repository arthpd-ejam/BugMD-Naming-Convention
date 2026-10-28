"""Flat light/dark theme built on Tk's 'clam' engine.

An image-based theme (sv-ttk) looked similar but took ~0.4-0.7 s to switch on
Windows because every widget is redrawn from images; flat colors switch in
~60 ms. Both themes are created once, so switching is a single theme_use().
"""

import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

PALETTES = {
    "light": {
        "bg": "#f7f7f8", "fg": "#1b1b1f", "muted": "#5f6368", "border": "#dadce0",
        "input_bg": "#ffffff", "button": "#ffffff", "button_hover": "#f1f3f4",
        "button_pressed": "#e8eaed", "heading": "#f1f3f4", "select_bg": "#d3e3fd",
        "accent": "#0b57d0", "accent_hover": "#1a66e0", "accent_pressed": "#0842a0",
        "accent_fg": "#ffffff", "thumb": "#c4c7c5", "thumb_hover": "#9aa0a6",
        "error": "#c5221f", "warn": "#9a5b00", "ok": "#137333", "disabled": "#9aa0a6",
    },
    "dark": {
        "bg": "#1e1f22", "fg": "#e8eaed", "muted": "#9aa0a6", "border": "#3c4043",
        "input_bg": "#2a2b2e", "button": "#2f3033", "button_hover": "#3a3b3e",
        "button_pressed": "#45464a", "heading": "#2a2b2e", "select_bg": "#264a7a",
        "accent": "#8ab4f8", "accent_hover": "#a3c4fa", "accent_pressed": "#6f9ef0",
        "accent_fg": "#0b1a33", "thumb": "#55585c", "thumb_hover": "#70747a",
        "error": "#f28b82", "warn": "#fdd663", "ok": "#81c995", "disabled": "#5f6368",
    },
}

FONTS = {  # name: (family candidates, size, weight)
    "AppBody": (("Segoe UI", "Helvetica"), 10, "normal"),
    "AppStrong": (("Segoe UI Semibold", "Segoe UI", "Helvetica"), 10, "bold"),
    "AppCaption": (("Segoe UI", "Helvetica"), 9, "normal"),
    "AppTitle": (("Segoe UI Semibold", "Segoe UI", "Helvetica"), 15, "bold"),
}


def system_mode() -> str:
    """'dark' when Windows apps are set to dark mode, else 'light'."""
    if sys.platform.startswith("win"):
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            light, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if light else "dark"
        except OSError:
            pass
    return "light"


def palette(widget: tk.Misc) -> dict:
    return PALETTES[getattr(widget._root(), "theme_mode", "light")]


def _create_fonts(root: tk.Tk) -> None:
    families = set(tkfont.families(root))
    for name, (candidates, size, weight) in FONTS.items():
        family = next((f for f in candidates if f in families), "TkDefaultFont")
        # "Semibold" families are already heavy; don't double the weight.
        w = "normal" if "Semibold" in family else weight
        try:
            tkfont.nametofont(name, root).configure(family=family, size=size, weight=w)
        except tk.TclError:
            tkfont.Font(root, name=name, family=family, size=size, weight=w)


def _settings(p: dict) -> dict:
    flat = {"lightcolor": p["bg"], "darkcolor": p["bg"], "bordercolor": p["border"]}
    button = {
        "configure": {"background": p["button"], "foreground": p["fg"], "padding": (12, 5),
                      "relief": "flat", "borderwidth": 1, "anchor": "center",
                      "bordercolor": p["border"], "lightcolor": p["button"],
                      "darkcolor": p["button"], "focuscolor": p["button"]},
        "map": {"background": [("pressed", p["button_pressed"]), ("active", p["button_hover"])],
                "lightcolor": [("pressed", p["button_pressed"]), ("active", p["button_hover"])],
                "darkcolor": [("pressed", p["button_pressed"]), ("active", p["button_hover"])],
                "foreground": [("disabled", p["disabled"])]},
        "layout": [("Button.border", {"sticky": "nswe", "border": "1", "children": [
            ("Button.padding", {"sticky": "nswe", "children": [
                ("Button.label", {"sticky": "nswe"})]})]})],
    }

    def label(**kw):
        return {"configure": {"background": p["bg"], **kw}}

    field = {"fieldbackground": p["input_bg"], "foreground": p["fg"], "bordercolor": p["border"],
             "lightcolor": p["input_bg"], "darkcolor": p["input_bg"], "insertcolor": p["fg"],
             "selectbackground": p["select_bg"], "selectforeground": p["fg"], "padding": (8, 5)}
    field_map = {"bordercolor": [("focus", p["accent"])],
                 "lightcolor": [("focus", p["accent"])], "darkcolor": [("focus", p["accent"])]}
    accent_states = [("pressed", p["accent_pressed"]), ("active", p["accent_hover"])]
    hover_states = [("pressed", p["button_pressed"]), ("active", p["button_hover"])]
    return {
        ".": {"configure": {"background": p["bg"], "foreground": p["fg"], "font": "AppBody",
                            "troughcolor": p["bg"], "selectbackground": p["select_bg"],
                            "selectforeground": p["fg"], "insertcolor": p["fg"],
                            "fieldbackground": p["input_bg"], "focuscolor": p["accent"],
                            **flat},
              "map": {"foreground": [("disabled", p["disabled"])]}},
        "TFrame": {"configure": {"background": p["bg"]}},
        "Card.TFrame": {"configure": {"background": p["bg"], "relief": "solid", "borderwidth": 1,
                                      **flat}},
        "TLabel": label(foreground=p["fg"]),
        "Title.TLabel": label(font="AppTitle", foreground=p["fg"]),
        "Subtitle.TLabel": label(font="AppBody", foreground=p["muted"]),
        "Section.TLabel": label(font="AppStrong", foreground=p["fg"]),
        "Muted.TLabel": label(font="AppCaption", foreground=p["muted"]),
        "Field.TLabel": label(font="AppCaption", foreground=p["muted"]),
        "Missing.TLabel": label(font="AppCaption", foreground=p["error"]),
        "Ok.TLabel": label(font="AppStrong", foreground=p["ok"]),
        "Error.TLabel": label(font="AppStrong", foreground=p["error"]),
        "Empty.TLabel": {"configure": {"background": p["input_bg"], "foreground": p["muted"],
                                       "font": "AppBody"}},
        "TButton": button,
        "Accent.TButton": {
            "configure": {"background": p["accent"], "foreground": p["accent_fg"],
                          "bordercolor": p["accent"], "lightcolor": p["accent"],
                          "darkcolor": p["accent"], "focuscolor": p["accent"],
                          "padding": (18, 6), "font": "AppStrong"},
            "map": {"background": accent_states, "bordercolor": accent_states,
                    "lightcolor": accent_states, "darkcolor": accent_states,
                    "foreground": [("disabled", p["disabled"])]}},
        "Toolbutton": {
            "configure": {"background": p["bg"], "foreground": p["fg"], "padding": (6, 4),
                          "relief": "flat", "borderwidth": 1, "anchor": "center",
                          "lightcolor": p["bg"], "darkcolor": p["bg"], "bordercolor": p["bg"],
                          "focuscolor": p["bg"]},
            "map": {"background": hover_states, "lightcolor": hover_states,
                    "darkcolor": hover_states, "bordercolor": hover_states},
            "layout": button["layout"]},
        "Today.Toolbutton": {"configure": {"foreground": p["accent"], "font": "AppStrong"}},
        "TEntry": {"configure": field,
                   "map": {**field_map, "fieldbackground": [("readonly", p["input_bg"])]}},
        "TCombobox": {
            "configure": {**field, "background": p["input_bg"], "arrowcolor": p["muted"],
                          "arrowsize": 13},
            "map": {**field_map,
                    "fieldbackground": [("readonly", p["input_bg"])],
                    "background": [("active", p["button_hover"]), ("readonly", p["input_bg"])],
                    "selectbackground": [("readonly", p["input_bg"])],
                    "selectforeground": [("readonly", p["fg"])],
                    "foreground": [("disabled", p["disabled"])]}},
        "Treeview": {
            "configure": {"background": p["input_bg"], "fieldbackground": p["input_bg"],
                          "foreground": p["fg"], "rowheight": 30, "borderwidth": 0,
                          "bordercolor": p["border"], "lightcolor": p["input_bg"],
                          "darkcolor": p["input_bg"]},
            "map": {"background": [("selected", p["select_bg"])],
                    "foreground": [("selected", p["fg"])]}},
        "Treeview.Heading": {
            "configure": {"background": p["heading"], "foreground": p["fg"], "font": "AppStrong",
                          "relief": "flat", "padding": (6, 6), "bordercolor": p["border"],
                          "lightcolor": p["heading"], "darkcolor": p["heading"]},
            "map": {"background": [("active", p["button_hover"])]}},
        "TScrollbar": {
            "configure": {"background": p["thumb"], "troughcolor": p["input_bg"],
                          "bordercolor": p["input_bg"], "lightcolor": p["thumb"],
                          "darkcolor": p["thumb"], "arrowcolor": p["muted"], "gripcount": 0,
                          "arrowsize": 12, "relief": "flat"},
            "map": {"background": [("active", p["thumb_hover"])],
                    "lightcolor": [("active", p["thumb_hover"])],
                    "darkcolor": [("active", p["thumb_hover"])]}},
    }


def setup(root: tk.Tk) -> None:
    """Create fonts and both themes once; call before building widgets."""
    _create_fonts(root)
    # Entry text uses a widget option, not the style, so set it for all inputs.
    for pattern in ("*TEntry.font", "*TCombobox.font", "*TCombobox*Listbox.font"):
        root.option_add(pattern, "AppBody", "interactive")
    style = ttk.Style(root)
    for mode, p in PALETTES.items():
        name = f"bugmd-{mode}"
        if name not in style.theme_names():
            style.theme_create(name, parent="clam", settings=_settings(p))


def apply(root: tk.Tk, mode: str) -> dict:
    """Switch the whole app to 'light' or 'dark'. Returns the palette."""
    if "bugmd-light" not in ttk.Style(root).theme_names():
        setup(root)
    root.theme_mode = mode
    p = PALETTES[mode]
    ttk.Style(root).theme_use(f"bugmd-{mode}")
    # Combobox dropdown lists are plain tk Listboxes: new ones read these options,
    # existing ones are recolored below.
    for opt, key in (("background", "input_bg"), ("foreground", "fg"),
                     ("selectBackground", "select_bg"), ("selectForeground", "fg")):
        root.option_add(f"*TCombobox*Listbox.{opt}", p[key], "interactive")
    _recolor_tk_widgets(root, p)
    style_window(root)
    for child in root.winfo_children():
        if isinstance(child, tk.Toplevel):
            style_window(child)
    return p


def _recolor_tk_widgets(widget: tk.Misc, p: dict) -> None:
    for child in widget.winfo_children():
        if isinstance(child, ttk.Combobox):
            try:
                popdown = child.tk.call("ttk::combobox::PopdownWindow", child)
                child.tk.call(f"{popdown}.f.l", "configure", "-background", p["input_bg"],
                              "-foreground", p["fg"], "-selectbackground", p["select_bg"],
                              "-selectforeground", p["fg"], "-borderwidth", 0)
            except tk.TclError:
                pass
        elif hasattr(child, "recolor"):
            child.recolor()
        _recolor_tk_widgets(child, p)


def style_window(win: tk.Misc) -> None:
    """Background for a plain tk window, and a dark title bar on Windows."""
    p = palette(win)
    try:
        win.configure(background=p["bg"])
    except tk.TclError:
        pass
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        value = ctypes.c_int(1 if p is PALETTES["dark"] else 0)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (newer, older builds)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
    except Exception:
        pass


def style_text(text: tk.Text) -> None:
    """Colors for a plain tk.Text so it matches the ttk inputs."""
    p = palette(text)
    text.configure(background=p["input_bg"], foreground=p["fg"], insertbackground=p["fg"],
                   selectbackground=p["select_bg"], selectforeground=p["fg"],
                   relief="flat", borderwidth=0, highlightthickness=1,
                   highlightbackground=p["border"], highlightcolor=p["accent"],
                   padx=8, pady=6)

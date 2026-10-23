"""Light/dark theme: Sun Valley (Windows 11 style) ttk theme plus the app's own
colors for text, statuses and plain tk widgets."""

import sys
import tkinter as tk
from tkinter import ttk

import sv_ttk

PALETTES = {
    "light": {
        "bg": "#fafafa", "fg": "#1c1c1c", "muted": "#616161", "border": "#e5e5e5",
        "error": "#c42b1c", "warn": "#9d5d00", "ok": "#0f7b0f", "accent": "#005fb8",
        "input_bg": "#ffffff", "select_bg": "#cce4f7",
    },
    "dark": {
        "bg": "#1c1c1c", "fg": "#fafafa", "muted": "#a6a6a6", "border": "#3a3a3a",
        "error": "#ff99a4", "warn": "#fce100", "ok": "#6ccb5f", "accent": "#57c8ff",
        "input_bg": "#2b2b2b", "select_bg": "#264f78",
    },
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


def apply(root: tk.Tk, mode: str) -> dict:
    """Switch the whole app to 'light' or 'dark'. Returns the palette."""
    root.theme_mode = mode
    sv_ttk.set_theme(mode, root)
    if not getattr(root, "_label_fix_bound", False):
        # sv_ttk runs tk_setPalette on every <<ThemeChanged>> (also fired by any
        # style change), which writes fixed colors onto every widget. For ttk labels
        # that overrides their style colors, so clear them right after it runs.
        # Bound after set_theme so it comes after sv_ttk's own handler.
        root.bind_class("Tk", "<<ThemeChanged>>", lambda e: reset_labels(root), add="+")
        root._label_fix_bound = True
    p = PALETTES[mode]
    s = ttk.Style(root)
    # Custom styles must be re-created after every theme switch.
    s.configure("Title.TLabel", font="SunValleySubtitleFont")
    s.configure("Subtitle.TLabel", font="SunValleyBodyFont", foreground=p["muted"])
    s.configure("Section.TLabel", font="SunValleyBodyStrongFont")
    s.configure("Muted.TLabel", font="SunValleyCaptionFont", foreground=p["muted"])
    s.configure("Field.TLabel", font="SunValleyCaptionFont", foreground=p["muted"])
    s.configure("Missing.TLabel", font="SunValleyCaptionFont", foreground=p["error"])
    s.configure("Ok.TLabel", font="SunValleyBodyStrongFont", foreground=p["ok"])
    s.configure("Error.TLabel", font="SunValleyBodyStrongFont", foreground=p["error"])
    s.configure("Today.Toolbutton", foreground=p["accent"])
    s.configure("Accent.TButton", padding=(18, 6, 18, 7))
    s.configure("Treeview", rowheight=32)
    s.configure("Treeview.Heading", font="SunValleyBodyStrongFont")
    style_window(root)
    for child in root.winfo_children():
        if isinstance(child, tk.Toplevel):
            style_window(child)
    return p


def reset_labels(widget: tk.Misc) -> None:
    """Clear the palette's fixed colors from every ttk label under widget.
    Call after building a window, since new labels pick the palette up too."""
    for child in widget.winfo_children():
        if isinstance(child, ttk.Label):
            child.configure(foreground="", background="")
        reset_labels(child)


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

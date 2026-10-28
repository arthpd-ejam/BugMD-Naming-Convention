"""Reusable dialogs: a pop-up calendar and the dropdown-lists setup screen."""

import calendar
import copy
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk

from . import theme
from .settings import (APP_NAME, list_to_text, mapping_to_text, text_to_list,
                       text_to_mapping)


class DatePicker(tk.Toplevel):
    """Small month calendar shown under a widget; calls on_pick(date) when a day is clicked."""

    def __init__(self, anchor: tk.Widget, current: date | None, on_pick):
        super().__init__(anchor)
        self.on_pick = on_pick
        self.selected = current or date.today()
        self.month = self.selected.replace(day=1)
        self.title("Pick a date")
        self.resizable(False, False)
        self.transient(anchor.winfo_toplevel())
        theme.style_window(self)

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        head = ttk.Frame(frame)
        head.pack(fill="x")
        ttk.Button(head, text="\u2039", width=3, style="Toolbutton",
                   command=lambda: self._shift(-1)).pack(side="left")
        self.title_label = ttk.Label(head, anchor="center", style="Section.TLabel")
        self.title_label.pack(side="left", fill="x", expand=True)
        ttk.Button(head, text="\u203a", width=3, style="Toolbutton",
                   command=lambda: self._shift(1)).pack(side="right")
        self.grid_frame = ttk.Frame(frame)
        self.grid_frame.pack(pady=(8, 0))
        ttk.Button(frame, text="Today", command=lambda: self._pick(date.today())).pack(fill="x", pady=(8, 0))

        self.bind("<Escape>", lambda e: self.destroy())
        self._draw()
        # Open under the date box, but keep the whole calendar on screen.
        self.update_idletasks()
        x = min(anchor.winfo_rootx(), self.winfo_screenwidth() - self.winfo_reqwidth() - 8)
        y = anchor.winfo_rooty() + anchor.winfo_height() + 4
        if y + self.winfo_reqheight() > self.winfo_screenheight() - 40:
            y = anchor.winfo_rooty() - self.winfo_reqheight() - 36
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.grab_set()
        self.focus_set()

    def _shift(self, months: int):
        y, m = divmod(self.month.month - 1 + months, 12)
        self.month = date(self.month.year + y, m + 1, 1)
        self._draw()

    def _draw(self):
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self.title_label.config(text=self.month.strftime("%B %Y"))
        for i, name in enumerate(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]):
            ttk.Label(self.grid_frame, text=name, style="Muted.TLabel", anchor="center",
                      width=4).grid(row=0, column=i, pady=(0, 4))
        today = date.today()
        for r, week in enumerate(calendar.Calendar().monthdayscalendar(self.month.year, self.month.month), 1):
            for c, day in enumerate(week):
                if not day:
                    continue
                d = self.month.replace(day=day)
                style = ("Accent.TButton" if d == self.selected
                         else "Today.Toolbutton" if d == today else "Toolbutton")
                b = ttk.Button(self.grid_frame, text=str(day), width=3, style=style,
                               command=lambda d=d: self._pick(d))
                if style == "Accent.TButton":
                    b.configure(padding=(0, 2))
                b.grid(row=r, column=c, padx=1, pady=1)

    def _pick(self, d: date):
        self.on_pick(d)
        self.destroy()


class ToggleSwitch(tk.Canvas):
    """Small on/off switch drawn on a canvas (the flat theme has no switch graphic).
    Calls command() after the value changes; recolor() is called on theme changes."""

    W, H = 40, 22

    def __init__(self, parent, variable: tk.BooleanVar, command=None):
        super().__init__(parent, width=self.W, height=self.H, highlightthickness=0,
                         borderwidth=0, cursor="hand2", takefocus=1)
        self.var, self.command = variable, command
        self.bind("<Button-1>", self.toggle)
        self.bind("<space>", self.toggle)
        self.var.trace_add("write", lambda *_: self.recolor())
        self.recolor()

    def toggle(self, _=None):
        self.var.set(not self.var.get())
        if self.command:
            self.command()

    def recolor(self):
        p = theme.palette(self)
        on = bool(self.var.get())
        self.delete("all")
        self.configure(background=p["bg"])
        w, h, r = self.W - 2, self.H - 2, (self.H - 2) // 2
        fill, outline = (p["accent"], p["accent"]) if on else (p["input_bg"], p["muted"])
        # Rounded track: two end circles joined by a rectangle.
        self.create_oval(1, 1, 1 + h, 1 + h, fill=fill, outline=outline)
        self.create_oval(w - h + 1, 1, w + 1, 1 + h, fill=fill, outline=outline)
        self.create_rectangle(1 + r, 1, w + 1 - r, 1 + h, fill=fill, outline="")
        self.create_line(1 + r, 1, w + 1 - r, 1, fill=outline)
        self.create_line(1 + r, 1 + h, w + 1 - r, 1 + h, fill=outline)
        knob = p["accent_fg"] if on else p["muted"]
        cx = w + 1 - r if on else 1 + r
        k = r - 5
        self.create_oval(cx - k, 1 + r - k, cx + k, 1 + r + k, fill=knob, outline="")


class DateField(ttk.Frame):
    """Read-only date box that opens a DatePicker when clicked."""

    def __init__(self, parent, variable: tk.StringVar, date_format: str):
        super().__init__(parent)
        self.var, self.fmt = variable, date_format
        self.entry = ttk.Entry(self, textvariable=variable, width=12, state="readonly", cursor="hand2")
        self.entry.pack(side="left", fill="x", expand=True)
        ttk.Button(self, text="\u25be", width=2, command=self.open).pack(side="left", padx=(4, 0))
        ttk.Button(self, text="Today", command=self.set_today).pack(side="left", padx=(4, 0))
        self.entry.bind("<Button-1>", lambda e: self.open())

    def current(self) -> date | None:
        try:
            return datetime.strptime(self.var.get(), self.fmt).date()
        except ValueError:
            return None

    def open(self):
        DatePicker(self.entry, self.current(), lambda d: self.var.set(d.strftime(self.fmt)))

    def set_today(self):
        self.var.set(date.today().strftime(self.fmt))


# Flat lists: (settings key, title, hint)
LIST_FIELDS = [
    ("channels", "Channels", "One per line"),
    ("formats", "Format-Dimensions", "One per line, e.g. VID-1080x1920"),
    ("intro_styles", "Intro Styles", "One per line"),
    ("strategists", "Creative Strategists", "One per line"),
    ("editors", "Editors", "One per line"),
]
# Lists that depend on another choice: (settings key, title, hint)
MAP_FIELDS = [
    ("brands", "Brands → Products", "One brand per line:  BRAND: PRODUCT, PRODUCT"),
    ("project_types", "Project Types → Test Types",
     "One project type per line:  TYPE: TEST, TEST"),
]


class SetupDialog(tk.Toplevel):
    """Edit every dropdown list. on_save(new_settings) is called when saved."""

    def __init__(self, parent, settings: dict, on_save, first_run=False):
        super().__init__(parent)
        self.title(f"{APP_NAME} — Setup")
        self.settings, self.on_save = settings, on_save
        self.transient(parent)
        self.geometry("1100x700")
        self.minsize(900, 560)
        theme.style_window(self)

        outer = ttk.Frame(self, padding=(20, 16))
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Welcome! Set up your dropdowns" if first_run else "Dropdown lists",
                  style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Fill in the options for each dropdown. Change them any time with "
                  "the Setup button. Lists are saved for your Windows user.",
                  style="Subtitle.TLabel", wraplength=1000).pack(anchor="w", pady=(0, 10))

        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True)
        self.texts: dict[str, tk.Text] = {}
        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        for key, title, hint in MAP_FIELDS:
            self._text_box(left, key, title, hint, mapping_to_text(settings[key]), height=8)
        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)
        cols = [ttk.Frame(right) for _ in range(2)]
        for c in cols:
            c.pack(side="left", fill="both", expand=True, padx=4)
        for i, (key, title, hint) in enumerate(LIST_FIELDS):
            self._text_box(cols[i % 2], key, title, hint, list_to_text(settings[key]), height=6)

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Save", style="Accent.TButton", command=self.save).pack(side="right")
        ttk.Button(buttons, text="Skip for now" if first_run else "Cancel",
                   command=self.destroy).pack(side="right", padx=6)
        self.grab_set()
        self.focus_set()

    def _text_box(self, parent, key, title, hint, value, height):
        box = ttk.Frame(parent, style="Card.TFrame", padding=(12, 10))
        box.pack(fill="both", expand=True, pady=5)
        ttk.Label(box, text=title, style="Section.TLabel").pack(anchor="w")
        ttk.Label(box, text=hint, style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        frame = ttk.Frame(box)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, height=height, width=30, wrap="word", undo=True,
                       font=("Consolas", 10))
        theme.style_text(text)
        sb = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=sb.set)
        text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        text.insert("1.0", value)
        self.texts[key] = text

    def collect(self) -> tuple[dict, list[str]]:
        new = copy.deepcopy(self.settings)
        problems = []
        for key, title, _ in LIST_FIELDS:
            new[key] = text_to_list(self.texts[key].get("1.0", "end"))
            if not new[key]:
                problems.append(f"{title}: add at least one option")
        for key, title, _ in MAP_FIELDS:
            new[key] = text_to_mapping(self.texts[key].get("1.0", "end"))
            if not new[key]:
                problems.append(f"{title}: add at least one line")
        empty = [b for b, products in new["brands"].items() if not products]
        if empty:
            problems.append("Brands with no products: " + ", ".join(empty))
        return new, problems

    def save(self):
        new, problems = self.collect()
        if problems:
            messagebox.showerror(APP_NAME, "Please fix:\n\n• " + "\n• ".join(problems), parent=self)
            return
        try:
            self.on_save(new)
        except OSError as e:
            messagebox.showerror(APP_NAME, f"Could not save settings:\n{e}", parent=self)
            return
        self.destroy()

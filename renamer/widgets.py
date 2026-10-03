"""Reusable dialogs: a pop-up calendar and the dropdown-lists setup screen."""

import calendar
import copy
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk

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
        self.geometry(f"+{anchor.winfo_rootx()}+{anchor.winfo_rooty() + anchor.winfo_height() + 2}")

        frame = ttk.Frame(self, padding=6)
        frame.pack(padx=1, pady=1)
        head = ttk.Frame(frame)
        head.pack(fill="x")
        ttk.Button(head, text="◀", width=3, command=lambda: self._shift(-1)).pack(side="left")
        self.title_label = ttk.Label(head, anchor="center", font=("Segoe UI", 10, "bold"))
        self.title_label.pack(side="left", fill="x", expand=True)
        ttk.Button(head, text="▶", width=3, command=lambda: self._shift(1)).pack(side="right")
        self.grid_frame = ttk.Frame(frame)
        self.grid_frame.pack(pady=(6, 0))
        ttk.Button(frame, text="Today", command=lambda: self._pick(date.today())).pack(fill="x", pady=(6, 0))

        self.bind("<Escape>", lambda e: self.destroy())
        self._draw()
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
            ttk.Label(self.grid_frame, text=name, foreground="#666", anchor="center", width=4).grid(row=0, column=i)
        today = date.today()
        for r, week in enumerate(calendar.Calendar().monthdayscalendar(self.month.year, self.month.month), 1):
            for c, day in enumerate(week):
                if not day:
                    continue
                d = self.month.replace(day=day)
                b = tk.Button(self.grid_frame, text=str(day), width=3, relief="flat",
                              command=lambda d=d: self._pick(d))
                if d == self.selected:
                    b.config(background="#0063b1", foreground="white", activebackground="#0063b1")
                elif d == today:
                    b.config(background="#dbeafe")
                b.grid(row=r, column=c, padx=1, pady=1)

    def _pick(self, d: date):
        self.on_pick(d)
        self.destroy()


class DateField(ttk.Frame):
    """Read-only date box that opens a DatePicker when clicked."""

    def __init__(self, parent, variable: tk.StringVar, date_format: str):
        super().__init__(parent)
        self.var, self.fmt = variable, date_format
        self.entry = ttk.Entry(self, textvariable=variable, width=14, state="readonly", cursor="hand2")
        self.entry.pack(side="left")
        ttk.Button(self, text="\U0001F4C5", width=3, command=self.open).pack(side="left", padx=(4, 0))
        ttk.Button(self, text="Today", width=7, command=self.set_today).pack(side="left", padx=(4, 0))
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

        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        intro = ("Welcome! Fill in the options for each dropdown. " if first_run else "") + \
            "Change these any time with the Setup button. Lists are saved for your Windows user."
        ttk.Label(outer, text=intro, wraplength=1000).pack(anchor="w", pady=(0, 8))

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
        ttk.Button(buttons, text="Save", command=self.save).pack(side="right")
        ttk.Button(buttons, text="Skip for now" if first_run else "Cancel",
                   command=self.destroy).pack(side="right", padx=6)
        self.grab_set()
        self.focus_set()

    def _text_box(self, parent, key, title, hint, value, height):
        box = ttk.LabelFrame(parent, text=title, padding=6)
        box.pack(fill="both", expand=True, pady=4)
        ttk.Label(box, text=hint, foreground="#666").pack(anchor="w")
        frame = ttk.Frame(box)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, height=height, width=30, wrap="word", undo=True,
                       font=("Consolas", 10))
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

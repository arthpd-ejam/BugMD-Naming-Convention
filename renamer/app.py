"""Tkinter window: pick a folder, fill the shared ClickUp fields, check the
preview, rename."""

import re
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import core, ops, theme
from .media import read_resolution
from .settings import APP_NAME, load_settings, load_state, save_settings, save_state
from .widgets import DateField, SetupDialog

SHARED_FIELDS = ["task", "script", "pest_angle", "brand", "product", "channel",
                 "project_type", "test_type", "date", "strategist", "editor", "intro"]
COLUMNS = [("file", "Original file", 300), ("res", "Resolution", 100),
           ("variation", "Var", 55), ("intro", "Intro", 75), ("format", "Format", 135),
           ("status", "Status", 240), ("new", "New name", 760)]
EDITABLE = {"variation", "intro", "format"}


def natural_key(path: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1400x900")
        self.minsize(1000, 600)
        if self.tk.call("tk", "windowingsystem") == "win32":
            self.state("zoomed")
        self.settings, settings_warning = load_settings()
        self.state_data = load_state()
        self.theme_mode = self.state_data.get("theme") or theme.system_mode()
        self.palette = theme.apply(self, self.theme_mode)
        self.rows: list[core.FileRow] = []
        self.vars = {k: tk.StringVar() for k in SHARED_FIELDS}
        self.folder = tk.StringVar(value=self.state_data.get("folder", ""))
        self.editor_widget = None
        self.problems: list[str] = []

        self._build()
        theme.reset_labels(self)
        self._restore_state()
        for k, var in self.vars.items():
            var.trace_add("write", lambda *_, key=k: self._on_field_change(key))
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        if settings_warning:
            messagebox.showwarning(APP_NAME, settings_warning)
        if self.folder.get():
            self.load_folder(quiet=True)
        self.refresh()
        if not self.state_data.get("setup_complete"):
            self.after(300, lambda: self.open_setup(first_run=True))

    # --- layout ------------------------------------------------------------

    def _build(self):
        s = self.settings

        # Header: title on the left, dark mode + setup on the right.
        header = ttk.Frame(self, padding=(20, 16, 20, 8))
        header.pack(fill="x")
        titles = ttk.Frame(header)
        titles.pack(side="left")
        ttk.Label(titles, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(titles, text="Batch-rename videos to the BugMD naming convention",
                  style="Subtitle.TLabel").pack(anchor="w")
        ttk.Button(header, text="\u2699  Setup", command=self.open_setup).pack(side="right")
        self.dark_var = tk.BooleanVar(value=self.theme_mode == "dark")
        ttk.Checkbutton(header, text="Dark mode", style="Switch.TCheckbutton",
                        variable=self.dark_var, command=self.toggle_theme).pack(side="right", padx=16)

        body = ttk.Frame(self, padding=(20, 0, 20, 0))
        body.pack(fill="both", expand=True)

        # 1. Folder
        folder_card = ttk.Frame(body, style="Card.TFrame", padding=(16, 12))
        folder_card.pack(fill="x", pady=(8, 0))
        ttk.Label(folder_card, text="1   Video folder", style="Section.TLabel").pack(anchor="w")
        row = ttk.Frame(folder_card)
        row.pack(fill="x", pady=(8, 0))
        entry = ttk.Entry(row, textvariable=self.folder)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda e: self.load_folder())
        ttk.Button(row, text="Browse\u2026", command=self.browse).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="\u21bb  Refresh", command=self.load_folder).pack(side="left", padx=(8, 0))

        # 2. ClickUp fields: label above each input, four per row.
        fields_card = ttk.Frame(body, style="Card.TFrame", padding=(16, 12))
        fields_card.pack(fill="x", pady=(12, 0))
        head = ttk.Frame(fields_card)
        head.pack(fill="x")
        ttk.Label(head, text="2   ClickUp task", style="Section.TLabel").pack(side="left")
        ttk.Label(head, text="applies to every file \u2022 required fields turn red when empty",
                  style="Muted.TLabel").pack(side="left", padx=10)
        ttk.Button(head, text="Clear all fields", command=self.clear_fields).pack(side="right")
        grid = ttk.Frame(fields_card)
        grid.pack(fill="x", pady=(6, 0))
        for c in range(4):
            grid.columnconfigure(c, weight=1, uniform="field")
        self.widgets = {}
        self.labels = {}

        def cell(r, c, key):
            frame = ttk.Frame(grid)
            frame.grid(row=r, column=c, sticky="ew", padx=(0 if c == 0 else 12, 0), pady=4)
            text = core.FIELD_LABELS[key]
            if key not in s["required_fields"]:
                text += "  (optional)"
            lbl = ttk.Label(frame, text=text, style="Field.TLabel")
            lbl.pack(anchor="w", pady=(0, 2))
            self.labels[key] = lbl
            return frame

        def add(r, c, key, kind, values=None):
            frame = cell(r, c, key)
            values = self._choices(key, values or [])
            if kind == "entry":
                w = ttk.Entry(frame, textvariable=self.vars[key])
            else:
                w = ttk.Combobox(frame, textvariable=self.vars[key], values=values,
                                 state="readonly" if kind == "pick" else "normal")
            w.pack(fill="x")
            self.widgets[key] = w
            return w

        add(0, 0, "task", "entry")
        add(0, 1, "script", "entry")
        add(0, 2, "pest_angle", "entry")
        self.date_field = DateField(cell(0, 3, "date"), self.vars["date"], s["date_format"])
        self.date_field.pack(fill="x")
        add(1, 0, "brand", "pick", list(s["brands"]))
        add(1, 1, "product", "pick")
        add(1, 2, "channel", "pick", s["channels"])
        add(1, 3, "editor", "pick", s["editors"])
        add(2, 0, "project_type", "pick", list(s["project_types"]))
        add(2, 1, "test_type", "combo")
        add(2, 2, "strategist", "pick", s["strategists"])
        add(2, 3, "intro", "pick", s["intro_styles"])

        # 3. Preview table
        files_card = ttk.Frame(body, style="Card.TFrame", padding=(16, 12))
        files_card.pack(fill="both", expand=True, pady=(12, 0))
        head = ttk.Frame(files_card)
        head.pack(fill="x")
        ttk.Label(head, text="3   Preview", style="Section.TLabel").pack(side="left")
        self.summary = ttk.Label(head, text="", style="Muted.TLabel")
        self.summary.pack(side="left", padx=10)
        ttk.Button(head, text="Remove selected", command=self.remove_selected).pack(side="right")
        ttk.Button(head, text="Fix duplicates", command=self.fix_duplicates).pack(side="right", padx=8)
        ttk.Label(files_card, text="Intro Style above sets every file. Double-click Var, Intro or "
                  "Format to change one file \u2022 select rows and press Delete to leave files out.",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 8))
        table = ttk.Frame(files_card)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table, columns=[c[0] for c in COLUMNS], show="headings",
                                 selectmode="extended")
        for key, title, width in COLUMNS:
            self.tree.heading(key, text=title + (" \u270e" if key in EDITABLE else ""), anchor="w")
            self.tree.column(key, width=width, minwidth=40, stretch=key == "new", anchor="w")
        ys = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", self._edit_cell)
        self.tree.bind("<Delete>", lambda e: self.remove_selected())
        self.empty_label = ttk.Label(self.tree, text="Choose a folder with videos to get started",
                                     style="Subtitle.TLabel", background=self.palette["bg"])
        self._color_tags()

        # Footer: status message and the main actions.
        footer = ttk.Frame(self, padding=(20, 12, 20, 16))
        footer.pack(fill="x", side="bottom", before=body)  # always visible, even in a short window
        self.message = ttk.Label(footer, text="", style="Error.TLabel")
        self.message.pack(side="left", fill="x", expand=True)
        self.rename_btn = ttk.Button(footer, text="Rename", style="Accent.TButton", command=self.rename)
        self.rename_btn.pack(side="right")
        ttk.Button(footer, text="\u21b6  Undo last rename", command=self.undo).pack(side="right", padx=8)

    def _color_tags(self):
        p = self.palette
        self.tree.tag_configure("bad", foreground=p["error"])
        self.tree.tag_configure("warn", foreground=p["warn"])
        self.tree.tag_configure("good", foreground=p["ok"])
        self.tree.tag_configure("same", foreground=p["muted"])
        self.empty_label.configure(background=self.palette["bg"])

    def toggle_theme(self):
        self.theme_mode = "dark" if self.dark_var.get() else "light"
        self.palette = theme.apply(self, self.theme_mode)
        self._color_tags()  # after apply(): the empty-table label keeps an explicit background
        self.state_data["theme"] = self.theme_mode
        save_state(self.state_data)
        self.refresh()

    # --- state -------------------------------------------------------------

    def _restore_state(self):
        saved = self.state_data.get("fields", {})
        for k, var in self.vars.items():
            var.set(saved.get(k, ""))
        self._update_dependent_lists()
        if not self.vars["date"].get():
            self._set_today()

    def _save(self):
        self.state_data["folder"] = self.folder.get()
        # Date is always today on next launch; everything else is remembered.
        self.state_data["fields"] = {k: v.get() for k, v in self.vars.items() if k != "date"}
        save_state(self.state_data)

    def _on_close(self):
        self._save()
        self.destroy()

    def _set_today(self):
        self.date_field.set_today()

    def clear_fields(self):
        """Empty every ClickUp field; the date goes back to today."""
        for key, var in self.vars.items():
            if key != "date":
                var.set("")
        self._set_today()

    # --- events ------------------------------------------------------------

    def _update_dependent_lists(self):
        products = self.settings["brands"].get(self.vars["brand"].get(), [])
        self.widgets["product"]["values"] = products
        if self.vars["product"].get() not in products:
            self.vars["product"].set("")
        tests = self.settings["project_types"].get(self.vars["project_type"].get(), [])
        self.widgets["test_type"]["values"] = [""] + tests

    def _on_field_change(self, key):
        if key in ("brand", "project_type"):
            self._update_dependent_lists()
        if key == "intro":
            for row in self.rows:
                row.intro = self.vars["intro"].get()
        if key == "task":
            self._reassign_variations()
        self.refresh()

    def _reassign_variations(self):
        auto = [r for r in self.rows if not r.variation_edited]
        numbers = core.assign_variations([r.path.stem for r in auto], self.vars["task"].get(),
                                         core.dropdown_values(self.settings))
        for row, n in zip(auto, numbers):
            row.variation = str(n)

    def browse(self):
        folder = filedialog.askdirectory(initialdir=self.folder.get() or None)
        if folder:
            self.folder.set(folder)
            self.load_folder()

    def load_folder(self, quiet=False):
        folder = Path(self.folder.get().strip().strip('"'))
        if not folder.is_dir():
            if not quiet:
                messagebox.showerror(APP_NAME, f"Folder not found:\n{folder}")
            self.rows = []
            self.refresh()
            return
        exts = {e.lower() for e in self.settings["video_extensions"]}
        files = sorted((p for p in folder.iterdir()
                        if p.is_file() and p.suffix.lower() in exts and not p.name.startswith(".")),
                       key=natural_key)
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            self.rows = []
            for p in files:
                res = read_resolution(p)
                row = core.FileRow(path=p, intro=self.vars["intro"].get())
                row.resolution = f"{res[0]}x{res[1]}" if res else "unknown"
                row.format = core.format_for_resolution(*(res or (None, None)),
                                                        prefix=self.settings["format_prefix"])
                existing = core.parse_existing(p.stem, self.settings["intro_styles"],
                                               self.settings["format_prefix"])
                row.intro = existing.get("intro", row.intro)
                row.format = existing.get("format", row.format)
                self.rows.append(row)
            self._reassign_variations()
        finally:
            self.config(cursor="")
        if not files and not quiet:
            messagebox.showinfo(APP_NAME, "No video files found in this folder.")
        self.refresh()

    def fix_duplicates(self):
        dupes = [r for r in self.rows if r.status == "Duplicate name"]
        if not dupes:
            messagebox.showinfo(APP_NAME, "There are no duplicate names.")
            return
        changed = core.fix_duplicates(self.rows, self.shared_values(), self.settings)
        self.refresh()
        messagebox.showinfo(APP_NAME, f"Gave {changed} file(s) new variation numbers. "
                            "Check the Var column, and double-click a number to change it.")

    def remove_selected(self):
        drop = {int(i) for i in self.tree.selection()}
        self.rows = [r for i, r in enumerate(self.rows) if i not in drop]
        self.refresh()

    def open_setup(self, first_run=False):
        SetupDialog(self, self.settings, self.apply_settings, first_run=first_run)

    def apply_settings(self, new: dict):
        save_settings(new)
        self.settings = new
        self.state_data["setup_complete"] = True
        self._save()
        s = self.settings
        for key, values in (("brand", list(s["brands"])), ("channel", s["channels"]),
                            ("project_type", list(s["project_types"])),
                            ("strategist", s["strategists"]), ("editor", s["editors"]),
                            ("intro", s["intro_styles"])):
            values = self._choices(key, values)
            self.widgets[key]["values"] = values
            if self.vars[key].get() not in values:
                self.vars[key].set("")
        self._update_dependent_lists()
        self.refresh()

    def _choices(self, key: str, values: list[str]) -> list[str]:
        """Dropdown options; optional fields get a blank first entry so they can be emptied."""
        values = list(values)
        if key not in self.settings["required_fields"] and "" not in values:
            values.insert(0, "")
        return values

    # --- preview -----------------------------------------------------------

    def shared_values(self) -> dict:
        return {k: v.get() for k, v in self.vars.items() if k != "intro"}

    def refresh(self):
        shared = self.shared_values()
        problems = []
        missing = core.evaluate_batch(self.rows, shared, self.settings)
        if missing:
            problems.append("Fill in: " + ", ".join(missing))
        date = shared.get("date", "").strip()
        if date:
            try:
                datetime.strptime(date, self.settings["date_format"])
            except ValueError:
                problems.append("Date must look like " + datetime.now().strftime(self.settings["date_format"]))
        bad = [r for r in self.rows if not r.ok]
        if bad:
            problems.append(f"{len(bad)} file(s) need attention (see Status)")
        missing_keys = set(core.missing_fields(shared, self.settings["required_fields"]))
        # Intro lives on each file, so it is only missing when a file has none.
        missing_keys.discard("intro")
        if ("intro" in self.settings["required_fields"] and not self.vars["intro"].get()
                and (not self.rows or any(not r.intro for r in self.rows))):
            missing_keys.add("intro")
        for key, lbl in self.labels.items():
            lbl.config(style="Missing.TLabel" if key in missing_keys else "Field.TLabel")
        to_rename = [r for r in self.rows if r.ok and r.status != "Unchanged"]

        icons = {"good": "\u2713", "warn": "\u26a0", "bad": "\u2715", "same": "\u2013"}
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self.rows):
            tag = "bad" if not r.ok else ("warn" if r.warnings else "good")
            if r.ok and r.status == "Unchanged":
                tag = "same"
            status, new = r.status, r.new_name
            if missing:
                new = "(fill in the red fields above)"
                if r.ok:
                    tag, status = "warn", "Waiting for fields above"
            self.tree.insert("", "end", iid=str(i), tags=(tag,), values=(
                r.path.name, r.resolution, r.variation, r.intro, r.format,
                f"{icons[tag]}  {status}", new))

        if self.rows:
            self.empty_label.place_forget()
            ready = sum(r.ok for r in self.rows)
            issues = len(self.rows) - ready
            self.summary.config(text=f"{len(self.rows)} file(s) \u2022 {ready} ready"
                                + (f" \u2022 {issues} need attention" if issues else ""))
        else:
            self.empty_label.place(relx=0.5, rely=0.5, anchor="center")
            self.summary.config(text="")
            problems.insert(0, "Choose a folder with videos.")
        if problems:
            self.message.config(text="\u26a0  " + "   \u2022   ".join(problems), style="Error.TLabel")
        else:
            self.message.config(text=f"\u2713  Ready to rename {len(to_rename)} file(s)." if to_rename
                                else "\u2713  All files already have these names.", style="Ok.TLabel")
        self.problems = problems
        self.rename_btn.config(text=f"Rename {len(to_rename)} file(s)" if to_rename and not problems
                               else "Rename")

    # --- cell editing ------------------------------------------------------

    def _edit_cell(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        iid = self.tree.identify_row(event.y)
        col = COLUMNS[int(self.tree.identify_column(event.x)[1:]) - 1][0]
        if not iid or col not in EDITABLE:
            return
        row = self.rows[int(iid)]
        x, y, w, h = self.tree.bbox(iid, col)
        var = tk.StringVar(value=getattr(row, col))
        if col == "intro":
            widget = ttk.Combobox(self.tree, textvariable=var, state="readonly",
                                  values=self._choices("intro", self.settings["intro_styles"]))
        elif col == "format":
            values = list(self.settings["formats"])
            if row.format and row.format not in values:
                values.insert(0, row.format)
            widget = ttk.Combobox(self.tree, textvariable=var, values=values)
        else:
            widget = ttk.Entry(self.tree, textvariable=var)
        widget.place(x=x, y=y, width=max(w, 130 if col != "variation" else 60), height=h)
        widget.focus_set()
        self.editor_widget = widget

        def commit(_=None):
            if self.editor_widget is not widget:
                return
            self.editor_widget = None
            value = var.get().strip()
            if col == "variation":
                row.variation_edited = True
            setattr(row, col, value)
            widget.destroy()
            self.refresh()

        def cancel(_=None):
            self.editor_widget = None
            widget.destroy()

        widget.bind("<Return>", commit)
        widget.bind("<Escape>", cancel)
        widget.bind("<FocusOut>", lambda e: self.after(50, lambda: (
            commit() if self.focus_get() is None or
            not str(self.focus_get()).startswith(str(widget)) else None)))
        if isinstance(widget, ttk.Combobox):
            widget.bind("<<ComboboxSelected>>", commit)

    # --- actions -----------------------------------------------------------

    def rename(self):
        self.refresh()
        todo = [r for r in self.rows if r.ok and r.status != "Unchanged"]
        if self.problems:
            messagebox.showwarning(APP_NAME, "Can't rename yet:\n\n\u2022 " + "\n\u2022 ".join(self.problems))
            return
        if not todo:
            messagebox.showinfo(APP_NAME, "All files already have these names.")
            return
        folder = todo[0].path.parent
        sample = "\n".join(f"  {r.path.name}  →  {r.new_name}" for r in todo[:5])
        more = f"\n  ...and {len(todo) - 5} more" if len(todo) > 5 else ""
        if not messagebox.askyesno(APP_NAME, f"Rename {len(todo)} file(s) in\n{folder}?\n\n{sample}{more}"):
            return
        try:
            done = ops.rename_files([(r.path, r.path.with_name(r.new_name)) for r in todo])
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Nothing was renamed:\n{e}")
            self.load_folder(quiet=True)
            return
        ops.save_undo(folder, done)
        self._save()
        for row in todo:  # keep per-file choices instead of re-reading the folder
            row.path = row.path.with_name(row.new_name)
        self.refresh()
        messagebox.showinfo(APP_NAME, f"Renamed {len(done)} file(s).")

    def undo(self):
        last = ops.latest_undo()
        if not last:
            messagebox.showinfo(APP_NAME, "Nothing to undo.")
            return
        path, entry = last
        n = len(entry["renames"])
        sample = "\n".join(f"  {r['to']}  →  {r['from']}" for r in entry["renames"][:5])
        if not messagebox.askyesno(APP_NAME, f"Undo the rename from {entry['time']}?\n"
                                   f"{n} file(s) in {entry['folder']}\n\n{sample}"):
            return
        try:
            ops.undo(path, entry)
        except Exception as e:
            messagebox.showerror(APP_NAME, str(e))
            return
        messagebox.showinfo(APP_NAME, f"Restored {n} original name(s).")
        self.load_folder(quiet=True)


def main():
    App().mainloop()


if __name__ == "__main__":
    main()

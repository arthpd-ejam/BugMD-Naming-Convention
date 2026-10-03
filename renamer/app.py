"""Tkinter window: pick a folder, fill the shared ClickUp fields, check the
preview, rename."""

import re
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import core, ops
from .media import read_resolution
from .settings import APP_NAME, load_settings, load_state, save_state

SHARED_FIELDS = ["task", "script", "pest_angle", "brand", "product", "channel",
                 "project_type", "test_type", "date", "strategist", "editor", "intro"]
COLUMNS = [("file", "Original file", 230), ("res", "Resolution", 95),
           ("variation", "Var", 50), ("intro", "Intro", 70), ("format", "Format", 130),
           ("status", "Status", 190), ("new", "New name", 760)]
EDITABLE = {"variation", "intro", "format"}


def natural_key(path: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1350x760")
        self.minsize(1000, 600)
        if self.tk.call("tk", "windowingsystem") == "win32":
            self.state("zoomed")
        self.settings, self.settings_path, settings_warning = load_settings()
        self.state_data = load_state()
        self.rows: list[core.FileRow] = []
        self.vars = {k: tk.StringVar() for k in SHARED_FIELDS}
        self.folder = tk.StringVar(value=self.state_data.get("folder", ""))
        self.editor_widget = None

        self._build()
        self._restore_state()
        for k, var in self.vars.items():
            var.trace_add("write", lambda *_, key=k: self._on_field_change(key))
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        if settings_warning:
            messagebox.showwarning(APP_NAME, settings_warning)
        if self.folder.get():
            self.load_folder(quiet=True)
        self.refresh()

    # --- layout ------------------------------------------------------------

    def _build(self):
        s = self.settings
        pad = {"padx": 6, "pady": 4}

        top = ttk.Frame(self, padding=(10, 10, 10, 0))
        top.pack(fill="x")
        ttk.Label(top, text="Video folder:").pack(side="left")
        entry = ttk.Entry(top, textvariable=self.folder)
        entry.pack(side="left", fill="x", expand=True, padx=6)
        entry.bind("<Return>", lambda e: self.load_folder())
        ttk.Button(top, text="Browse...", command=self.browse).pack(side="left")
        ttk.Button(top, text="Load / Refresh", command=self.load_folder).pack(side="left", padx=(6, 0))

        box = ttk.LabelFrame(self, text="ClickUp task (applies to every file)", padding=8)
        box.pack(fill="x", padx=10, pady=8)
        self.widgets = {}

        def add(row, col, key, kind, values=None, width=22):
            ttk.Label(box, text=core.FIELD_LABELS[key] + ":").grid(row=row, column=col * 2, sticky="e", **pad)
            if kind == "entry":
                w = ttk.Entry(box, textvariable=self.vars[key], width=width + 3)
            else:
                w = ttk.Combobox(box, textvariable=self.vars[key], values=values or [],
                                 width=width, state="readonly" if kind == "pick" else "normal")
            w.grid(row=row, column=col * 2 + 1, sticky="w", **pad)
            self.widgets[key] = w
            return w

        add(0, 0, "task", "entry")
        add(0, 1, "script", "entry")
        add(0, 2, "pest_angle", "entry")
        add(1, 0, "brand", "pick", list(s["brands"]))
        add(1, 1, "product", "pick")
        add(1, 2, "channel", "pick", s["channels"])
        add(2, 0, "project_type", "pick", list(s["project_types"]))
        add(2, 1, "test_type", "combo")
        ttk.Label(box, text="Date:").grid(row=2, column=4, sticky="e", **pad)
        date_box = ttk.Frame(box)
        date_box.grid(row=2, column=5, sticky="w", **pad)
        ttk.Entry(date_box, textvariable=self.vars["date"], width=14).pack(side="left")
        ttk.Button(date_box, text="Today", width=7, command=self._set_today).pack(side="left", padx=(6, 0))
        add(3, 0, "strategist", "pick", [""] + s["strategists"])
        add(3, 1, "editor", "pick", s["editors"])
        add(3, 2, "intro", "pick", s["intro_styles"])
        ttk.Label(box, text="(Intro sets all files; change single files in the table)",
                  foreground="#666").grid(row=4, column=4, columnspan=2, sticky="w", padx=6)
        ttk.Label(box, text="Optional: Pest_Angle, Test Type, Strategist",
                  foreground="#666").grid(row=4, column=0, columnspan=3, sticky="w", padx=6)

        mid = ttk.Frame(self, padding=(10, 0))
        mid.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(mid, columns=[c[0] for c in COLUMNS], show="headings",
                                 selectmode="extended")
        for key, title, width in COLUMNS:
            self.tree.heading(key, text=title + (" ✎" if key in EDITABLE else ""))
            self.tree.column(key, width=width, minwidth=40, stretch=key == "new", anchor="w")
        self.tree.tag_configure("bad", foreground="#b00020")
        self.tree.tag_configure("warn", foreground="#a15c00")
        self.tree.tag_configure("good", foreground="#1b6e20")
        ys = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(mid, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        mid.rowconfigure(0, weight=1)
        mid.columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", self._edit_cell)
        self.tree.bind("<Delete>", lambda e: self.remove_selected())

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill="x")
        ttk.Label(bottom, text="Double-click Var, Intro or Format to change one file. "
                  "Select rows + Delete to leave files out.", foreground="#666").pack(anchor="w")
        self.message = ttk.Label(bottom, text="", foreground="#b00020")
        self.message.pack(anchor="w", pady=(4, 6))
        buttons = ttk.Frame(bottom)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Remove selected", command=self.remove_selected).pack(side="left")
        ttk.Button(buttons, text="Open settings.json", command=self.open_settings).pack(side="left", padx=6)
        self.rename_btn = ttk.Button(buttons, text="Rename", command=self.rename)
        self.rename_btn.pack(side="right")
        ttk.Button(buttons, text="Undo last rename", command=self.undo).pack(side="right", padx=6)

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
        self.vars["date"].set(datetime.now().strftime(self.settings["date_format"]))

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
        numbers = core.assign_variations([r.path.stem for r in auto], self.vars["task"].get())
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

    def remove_selected(self):
        drop = {int(i) for i in self.tree.selection()}
        self.rows = [r for i, r in enumerate(self.rows) if i not in drop]
        self.refresh()

    def open_settings(self):
        import os
        import subprocess
        import sys
        path = str(self.settings_path)
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # noqa: S606
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError as e:
            messagebox.showerror(APP_NAME, str(e))
            return
        messagebox.showinfo(APP_NAME, "After saving settings.json, close and reopen the app "
                            "to load the new lists.")

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
        to_rename = [r for r in self.rows if r.ok and r.status != "Unchanged"]

        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self.rows):
            tag = "bad" if not r.ok else ("warn" if r.warnings else "good")
            new = r.new_name if not missing else "(fill in the fields above)"
            self.tree.insert("", "end", iid=str(i), tags=(tag,), values=(
                r.path.name, r.resolution, r.variation, r.intro, r.format, r.status, new))

        if not self.rows:
            problems.insert(0, "Choose a folder with videos.")
        self.message.config(text="   •   ".join(problems),
                            foreground="#b00020" if problems else "#1b6e20")
        if not problems:
            self.message.config(text=f"Ready to rename {len(to_rename)} file(s)." if to_rename
                                else "All files already have these names.")
        ok = not problems and bool(to_rename)
        self.rename_btn.config(text=f"Rename {len(to_rename)} file(s)",
                               state="normal" if ok else "disabled")

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
                                  values=self.settings["intro_styles"])
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
        if str(self.rename_btn["state"]) == "disabled":
            return
        todo = [r for r in self.rows if r.ok and r.status != "Unchanged"]
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

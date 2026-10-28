"""Times dark-mode switching on a real Windows desktop (run by perf.yml)."""

import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["APPDATA"] = tempfile.mkdtemp()

from renamer import theme  # noqa: E402
from renamer.app import App  # noqa: E402

folder = Path(tempfile.mkdtemp())
for i in range(6):
    (folder / f"BM-75969-{i // 2 + 1}_BMD_VMS-Pro_META_VID-1080x{1350 if i % 2 else 1920}.mp4").write_bytes(b"")

app = App()
app.geometry("1920x1040+0+0")
app.folder.set(str(folder))
app.load_folder(quiet=True)
for _ in range(10):
    app.update()
    time.sleep(0.05)


def count(w):
    return 1 + sum(count(c) for c in w.winfo_children())


def timed(fn, runs=4):
    out = []
    for _ in range(runs):
        t = time.perf_counter()
        fn()
        app.update()
        out.append((time.perf_counter() - t) * 1000)
    return f"median {statistics.median(out):6.0f} ms   (runs: {', '.join(f'{x:.0f}' for x in out)})"


def flip():
    app.dark_var.set(not app.dark_var.get())


def current():
    flip()
    app.toggle_theme()


def plain():
    flip()
    app.theme_mode = "dark" if app.dark_var.get() else "light"
    app.palette = theme.apply(app, app.theme_mode)
    app._color_tags()
    app.refresh()


def withdrawn():
    app.withdraw()
    plain()
    app.update()
    app.deiconify()


def repaint_only():
    # Cost of Windows repainting the whole window once, without any theme change.
    w = app.winfo_width()
    app.geometry(f"{w - 1}x1040")
    app.update()
    app.geometry(f"{w}x1040")


import sv_ttk  # noqa: E402
from tkinter import ttk  # noqa: E402

results = [f"widgets: {count(app)}", f"tk scaling: {app.tk.call('tk', 'scaling')}"]
results.append(f"toggle (current build)   : {timed(current)}")
results.append(f"toggle without freeze    : {timed(plain)}")


def other():
    return "light" if app.theme_mode == "dark" else "dark"


def step_theme_use():
    app.theme_mode = other()
    sv_ttk.set_theme(app.theme_mode, app)


def step_styles():
    p = theme.PALETTES[app.theme_mode]
    st = ttk.Style(app)
    for name in ("Subtitle.TLabel", "Muted.TLabel", "Field.TLabel"):
        st.configure(name, foreground=p["muted"])
    st.configure("Missing.TLabel", foreground=p["error"])
    st.configure("Treeview", rowheight=32)


results.append(f"step: sv_ttk.set_theme   : {timed(step_theme_use)}")
results.append(f"step: style configures   : {timed(step_styles)}")
results.append(f"step: refresh()          : {timed(app.refresh)}")
results.append(f"step: reset_labels       : {timed(lambda: theme.reset_labels(app))}")
results.append(f"step: style_window       : {timed(lambda: theme.style_window(app))}")

# Prepared styles: configure custom styles once per theme, then a switch is theme_use only.
for mode in ("dark", "light"):
    theme.apply(app, mode)
app.update()


def prepared():
    app.theme_mode = other()
    sv_ttk.set_theme(app.theme_mode, app)
    app.palette = theme.PALETTES[app.theme_mode]
    app._color_tags()
    app.configure(background=app.palette["bg"])


results.append(f"toggle prepared styles   : {timed(prepared)}")
app.tk.eval("proc tk_setPalette args {}")
results.append(f"prepared w/o setPalette  : {timed(prepared)}")

report = "\n".join(results)
print(report)
summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    with open(summary, "a", encoding="utf-8") as f:
        f.write("```\n" + report + "\n```\n")
app.destroy()

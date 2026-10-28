"""Times dark-mode switching on a real Windows desktop (run by perf.yml)."""

import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["APPDATA"] = tempfile.mkdtemp()

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


def timed(fn, runs=6):
    out = []
    for _ in range(runs):
        t = time.perf_counter()
        fn()
        app.update()
        out.append((time.perf_counter() - t) * 1000)
    return f"median {statistics.median(out):6.0f} ms   (runs: {', '.join(f'{x:.0f}' for x in out)})"


def click_switch():
    app.dark_switch.toggle()


def type_letter():
    app.vars["script"].set(app.vars["script"].get() + "a")


results = [f"widgets: {count(app)}", f"tk scaling: {app.tk.call('tk', 'scaling')}",
           f"dark mode switch : {timed(click_switch)}",
           f"typing a letter  : {timed(type_letter)}",
           f"preview refresh  : {timed(app.refresh)}"]
report = "\n".join(results)
print(report)
summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    with open(summary, "a", encoding="utf-8") as f:
        f.write("```\n" + report + "\n```\n")
app.destroy()

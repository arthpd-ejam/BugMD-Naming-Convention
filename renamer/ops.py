"""Performs renames safely (two-phase, so A->B and B->A swaps work) and keeps an
undo log per batch in the user's AppData folder."""

import json
import time
import uuid
from pathlib import Path

from .settings import user_data_dir


def log_dir() -> Path:
    path = user_data_dir() / "undo"
    path.mkdir(parents=True, exist_ok=True)
    return path


def rename_files(pairs: list[tuple[Path, Path]]) -> list[tuple[Path, Path]]:
    """Rename each (src, dst). On failure, completed renames are rolled back and
    the error is re-raised. Returns the pairs that were renamed."""
    # Compare as text: Windows paths compare case-insensitively, which would skip a.mp4 -> A.mp4.
    pairs = [(Path(s), Path(d)) for s, d in pairs if str(s) != str(d)]
    # Each entry is [original, current location] so a failure can be undone.
    moved = []
    try:
        for src, _ in pairs:
            tmp = src.with_name(f".renaming-{uuid.uuid4().hex}{src.suffix}")
            src.rename(tmp)
            moved.append([src, tmp])
        for entry, (_, dst) in zip(moved, pairs):
            if dst.exists():
                raise FileExistsError(f"{dst.name} already exists")
            entry[1].rename(dst)
            entry[1] = dst
    except Exception:
        for src, current in reversed(moved):
            try:
                current.rename(src)
            except OSError:
                pass
        raise
    return pairs


def save_undo(folder: Path, renamed: list[tuple[Path, Path]]) -> Path:
    entry = {
        "folder": str(folder),
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "renames": [{"from": s.name, "to": d.name} for s, d in renamed],
    }
    path = log_dir() / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}.json"
    path.write_text(json.dumps(entry, indent=2), encoding="utf-8")
    return path


def latest_undo() -> tuple[Path, dict] | None:
    logs = sorted(log_dir().glob("*.json"))
    for path in reversed(logs):
        try:
            return path, json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            path.unlink(missing_ok=True)
    return None


def undo(path: Path, entry: dict) -> int:
    folder = Path(entry["folder"])
    pairs = [(folder / r["to"], folder / r["from"]) for r in entry["renames"]]
    missing = [s.name for s, _ in pairs if not s.exists()]
    if missing:
        raise FileNotFoundError("Can't undo, these files were moved or renamed since: "
                                + ", ".join(missing[:5]))
    rename_files(pairs)
    path.unlink(missing_ok=True)
    return len(pairs)
